"""
Syncthing import pipeline — monitors ~/Local (unsynced)/PhoneForaging/ for new photos
and processes them automatically.

Processing rules:
  1. Scan PhoneForaging dir for image files not yet in the database.
  2. For each new file: ingest (EXIF + thumbnail + hash), prefilter, identify.
  3. Both PlantNet and iNaturalist run in parallel.
  4. Both APIs agree on same species at or above upload_auto_approve_threshold → auto-approve (pin on map).
  5. Disagree, low confidence, or one API unavailable → review queue,
     badged "Syncthing — needs review".
  6. New species → species card created + added to enrichment queue.
  7. Known species → observation linked to existing card automatically.

upload_source = "syncthing" for all files processed by this pipeline.
Source files are READ-ONLY — originals are never modified or deleted.
Each new file is COPIED into photos/pipeline2/ so observation records are
project-local and survive external HD removal (Option B, migration 0021).
"""

import asyncio
import json as _json
import logging
import shutil
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

log = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select, or_, and_

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.observation import Observation, PHONE_ORIGIN_SOURCE
from app.models.processing import ProcessingLog
from app.services.ingest_guard import blacklisted_skip
from app.services.settings_service import get_setting


def _get_phone_dir() -> Path:
    """Return the Syncthing watch directory.

    Reads photo_library_path from the settings service first (editable from
    the scan page); falls back to the hardcoded phone_foraging_dir from config
    so existing installations continue working without any DB override.
    """
    override = get_setting("photo_library_path")
    if override:
        return Path(override).expanduser()
    return settings.phone_foraging_dir

router = APIRouter(prefix="/api/syncthing", tags=["syncthing"])

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# ---------------------------------------------------------------------------
# In-memory session state — cleared on server restart, not persisted
# ---------------------------------------------------------------------------
_state = {
    "processing":              False,
    "in_flight":               0,        # files currently being processed
    "session_total":           0,        # files processed this session
    "session_approved":        0,
    "session_review":          0,
    "session_failed":          0,
    "session_files_received":  0,        # total files submitted in current/last batch
    "last_checked":            None,     # ISO datetime string
    "last_auto_scan":          None,     # ISO datetime of last server-side auto-scan tick
    "new_count":               0,        # cached from last scan
    "errors":                  [],       # last N error messages
}

# Species confirmed during the current batch — used for auto-enrichment
_batch_new_species: set = set()
_MAX_ERRORS = 20
_CONCURRENT_LIMIT = 3               # max parallel identifications

# ── Persisted session tracking (Pipeline 1) ──────────────────────────────────
# ID of the scan_sessions row for the currently running batch; None when idle.
# Set at the start of _process_all, cleared in the finally block.
_current_p1_session_id: Optional[int] = None

_semaphore: Optional[asyncio.Semaphore] = None

# Hashes already logged as blacklist-filtered this process. Bounded by the size
# of deleted_hashes (12 rows today), cleared on restart — see
# _log_blacklist_filter_skip for why this is deduped rather than logged per tick.
_blacklist_logged: set = set()

# Path last logged as missing, or None when the watch dir is present. Latch, not
# a counter — see _record_watch_dir_missing for why this is not per-tick.
_watch_dir_missing_logged: Optional[str] = None

# Lenient prefilter for Pipeline 1 — only the clearest non-biological subjects.
# Anything plausibly biological (indoor, low-signal, sky, food) passes through.
# Rejects are saved with identification_status="not_plant" and are recoverable
# via POST /{obs_id}/override-prefilter, same as Pipeline 2.
_P1_REJECT_CATEGORIES = {"screenshot", "ui_blank", "person_animal"}


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_CONCURRENT_LIMIT)
    return _semaphore


# ---------------------------------------------------------------------------
# Utility: find image files in PhoneForaging not yet in the database
# ---------------------------------------------------------------------------

def _watch_dir_ok(path: Path) -> None:
    """Clear the missing-dir latch so a later disappearance logs again."""
    global _watch_dir_missing_logged
    if _watch_dir_missing_logged is not None:
        log.info("watch directory is available again: %s", path)
        _watch_dir_missing_logged = None


def _record_watch_dir_missing(path: Path) -> None:
    """
    Record that the configured watch directory does not exist.

    Deliberately NOT routed through _record_auto_scan_failure: that function
    takes an exception and calls log.exception, which without live exception
    context would attach a meaningless "NoneType: None" traceback, and it writes
    stage='auto_scan' status='failed'. A missing directory is a configuration
    state, not a tick failure. Same three channels, same visibility bar, honest
    labelling.

    Latched on the path value, not deduped per process: _find_new_files runs on
    a 60-second loop, so logging every tick would write ~1,440 identical rows a
    day. One row per distinct bad path, re-armed by _watch_dir_ok when the
    directory reappears, so a genuine break/fix/break cycle is still recorded.

    MUST NOT raise — it sits on the ingest path and a failed audit write must
    never stop directory scanning.
    """
    global _watch_dir_missing_logged
    if _watch_dir_missing_logged == str(path):
        return
    _watch_dir_missing_logged = str(path)

    override = get_setting("photo_library_path")
    source = "photo_library_path setting" if override else "config.py fallback"
    detail = f"watch directory does not exist: {path} (from {source})"

    try:
        log.error("P1 auto-scan disabled — %s", detail)
    except Exception:
        pass

    try:
        _state["errors"].append(f"auto-scan: {detail}")
        if len(_state["errors"]) > _MAX_ERRORS:
            _state["errors"] = _state["errors"][-_MAX_ERRORS:]
    except Exception:
        pass

    try:
        asyncio.create_task(_write_watch_dir_missing_log(detail))
    except Exception:
        pass


async def _write_watch_dir_missing_log(detail: str) -> None:
    """Durable half of _record_watch_dir_missing. Swallows its own errors."""
    try:
        async with AsyncSessionLocal() as log_session:
            log_session.add(ProcessingLog(
                observation_id=None,   # configuration state, no row involved
                stage="auto_scan",
                status="skipped",
                message=(
                    f"action=watch_dir_missing {detail} "
                    "— no files can be ingested until this path is corrected"
                ),
            ))
            await log_session.commit()
    except Exception:
        log.warning("could not persist watch-dir-missing log for: %s", detail)


async def _log_blacklist_filter_skip(sha: str, path: Path) -> None:
    """
    Emit one blacklisted_hash_skip log for a file filtered out by the deleted-hash
    tier of _find_new_files.

    Deduped per process, not per call. _find_new_files runs on a 60-second loop
    against a directory whose contents persist, so an unconditional log here
    would rewrite the same rows every minute (~17k/day for the current 12
    blacklisted files) and bury the signal it exists to provide. One line per
    hash per server lifetime keeps the fact visible and also gives a useful
    per-boot snapshot of the blacklist-versus-directory intersection.

    Logging is delegated to services.ingest_guard.blacklisted_skip so the format
    stays identical to the five ingest call sites; that function re-checks the
    hash against deleted_hashes itself, which is the authoritative read. The
    prefetched set is only a cheap filter to decide whether to ask, so this
    costs one indexed query per genuinely blacklisted file, not per candidate.
    """
    if sha in _blacklist_logged:
        return
    _blacklist_logged.add(sha)
    try:
        async with AsyncSessionLocal() as session:
            await blacklisted_skip(session, sha, "p1_autoscan_filter", str(path))
    except Exception:
        # Never let an audit-log failure break directory scanning.
        log.warning("could not log blacklist skip for %s", path, exc_info=True)


async def _find_new_files() -> List[Path]:
    """
    Return image paths in PhoneForaging that have no matching observation.

    Matching is two-tier:
      1. Exact file_path string match (fast path — the common case).
      2. Content hash (sha256) match for files not matched by path.

    The hash tier prevents a hang: Syncthing sometimes re-imports a photo under
    a different filename (e.g. "PXL_….jpg" → "PXL_… (1).jpg"). Those files have
    a NEW path but the SAME content as an existing observation. Without the hash
    check they'd be reported as "new" on every scan, _ingest_file would silently
    skip them as hash-duplicates (incrementing nothing), and the frontend would
    auto-retrigger /process forever — appearing stuck on "Starting…".
    """
    phone_dir = _get_phone_dir()
    if not phone_dir.exists():
        # Fail-quiet class: an empty list here is indistinguishable from
        # "nothing new to ingest", so a mistyped photo_library_path — or the
        # stale config.py fallback, which points at a path that does not exist —
        # silently disables P1 ingest for the life of the process. Behaviour is
        # deliberately unchanged; only its visibility.
        _record_watch_dir_missing(phone_dir)
        return []
    _watch_dir_ok(phone_dir)

    # All image files in the directory (recursive)
    all_images = [
        p for p in phone_dir.rglob("*")
        if p.suffix.lower() in _IMAGE_EXTENSIONS and p.is_file()
    ]
    if not all_images:
        return []

    # Query DB for file_paths already ingested from this directory
    dir_prefix = str(phone_dir)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Observation.file_path).where(
                Observation.file_path.like(f"{dir_prefix}%")
            )
        )
        known_paths = {row[0] for row in result.fetchall()}

    path_new = [p for p in all_images if str(p) not in known_paths]
    if not path_new:
        return []

    # Second tier: exclude content-duplicates (same sha256 already in DB under a
    # different filename). Only the path-unmatched candidates are hashed, so the
    # common case (everything matched by path) costs nothing.
    from app.utils.hashing import file_sha256

    from app.models.observation import DeletedHash

    # These two sets were previously merged into one. They are kept separate so
    # the skip loop below can tell WHY a file was excluded: an ordinary content
    # duplicate (silent, uninteresting) or a blacklisted deleted hash (worth a
    # log line — this tier was the one silent skip the ingest guard never saw).
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Observation.file_hash))
        known_hashes = {row[0] for row in result.fetchall() if row[0]}
        del_result = await session.execute(select(DeletedHash.file_hash))
        blacklisted_hashes = {row[0] for row in del_result.fetchall() if row[0]}

    truly_new = []
    for p in path_new:
        try:
            sha = file_sha256(p)
        except Exception:
            sha = None
        if sha and sha in known_hashes:
            continue  # content already ingested under a different filename
        if sha and sha in blacklisted_hashes:
            # Permanently deleted by the user — must not be re-ingested. The
            # skip itself is correct and unchanged; only its invisibility was
            # the bug. Logging is delegated to the shared ingest guard so this
            # tier emits the same blacklisted_hash_skip shape as the five
            # ingest call sites, rather than a second bespoke log format.
            await _log_blacklist_filter_skip(sha, p)
            continue
        truly_new.append(p)

    return sorted(truly_new)


# ---------------------------------------------------------------------------
# GET /api/syncthing/status
# ---------------------------------------------------------------------------

@router.get("/status")
async def syncthing_status():
    """
    Check how many new photos are waiting in PhoneForaging.
    Also returns processing state and session stats.
    """
    phone_dir = _get_phone_dir()
    new_files = await _find_new_files()
    _state["new_count"] = len(new_files)
    _state["last_checked"] = datetime.utcnow().isoformat()

    # Overall DB counts for this pipeline
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                Observation.review_status,
                Observation.identification_status,
                Observation.species_primary,
            ).where(Observation.upload_source == PHONE_ORIGIN_SOURCE)
        )
        rows = result.fetchall()

    total = len(rows)
    approved = sum(1 for r in rows if r[0] in ("approved", "manually_verified"))
    needs_review = sum(1 for r in rows if r[0] == "needs_review")
    rejected = sum(1 for r in rows if r[0] == "rejected")
    pending_review = sum(1 for r in rows if r[0] == "pending")
    pending_id = sum(1 for r in rows if r[1] == "pending_identification")
    failed_id  = sum(1 for r in rows if r[1] == "failed_identification")
    # Distinct confirmed species from this pipeline
    confirmed_species = len({
        r[2] for r in rows
        if r[0] in ("approved", "manually_verified") and r[2]
    })

    return {
        "watch_dir":         str(phone_dir),
        "dir_exists":        phone_dir.exists(),
        "new_count":         _state["new_count"],
        "new_files":         [str(p) for p in new_files[:50]],  # first 50 names
        "processing":        _state["processing"],
        "in_flight":         _state["in_flight"],
        "session_total":            _state["session_total"],
        "session_approved":         _state["session_approved"],
        "session_review":           _state["session_review"],
        "session_failed":           _state["session_failed"],
        "session_files_received":   _state["session_files_received"],
        "last_checked":      _state["last_checked"],
        "last_auto_scan":    _state["last_auto_scan"],
        # Lifetime DB totals for this pipeline
        "db_total":          total,
        "db_approved":       approved,
        "db_needs_review":   needs_review,
        "db_rejected":       rejected,
        "db_pending_review": pending_review,
        "db_confirmed_species": confirmed_species,
        "db_pending_id":     pending_id,
        "db_failed_id":      failed_id,
        "errors":            _state["errors"][-5:],  # last 5 errors
    }


# ---------------------------------------------------------------------------
# GET /api/syncthing/rejected — rejection log for the Pipeline 1 panel
# ---------------------------------------------------------------------------

@router.get("/rejected")
async def list_rejected():
    """
    List Pipeline 1 (Syncthing) observations with review_status='rejected'.

    Powers the expandable rejection log in the Syncthing Import panel. Each row
    carries enough to display (filename, date, reason) and to send back to the
    review queue. The reason is derived from identification_status, since these
    rejections (manual or audit) do not store a free-text reason on the record:
      - identified            -> "Manually rejected" (had a species ID)
      - failed_identification -> "No species match"
      - anything else         -> the raw status

    All rows are sendable to review (there are no duplicate-hash records here —
    duplicates are skipped at ingest and never create an observation).
    """
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(
                Observation.id,
                Observation.file_path,
                Observation.photo_taken_at,
                Observation.reviewed_at,
                Observation.identification_status,
                Observation.species_primary,
                Observation.thumbnail_path,
            )
            .where(
                Observation.upload_source == PHONE_ORIGIN_SOURCE,
                Observation.review_status == "rejected",
            )
            .order_by(Observation.reviewed_at.desc().nullslast(),
                      Observation.photo_taken_at.desc().nullslast())
        )).all()

    def _reason(ident_status: Optional[str]) -> str:
        if ident_status == "identified":
            return "Manually rejected"
        if ident_status == "failed_identification":
            return "No species match"
        return ident_status or "Rejected"

    items = []
    for r in rows:
        filename = Path(r.file_path).name if r.file_path else f"#{r.id}"
        # Prefer the rejection date; fall back to the photo's capture date.
        date = r.reviewed_at or r.photo_taken_at
        items.append({
            "observation_id": r.id,
            "filename": filename,
            "date": date.isoformat() if date else None,
            "reason": _reason(r.identification_status),
            "species_primary": r.species_primary,
            "thumbnail": r.thumbnail_path,
            "sendable": True,   # Option 1: every rejected Pipeline 1 obs is recoverable
        })

    return {"count": len(items), "rejects": items}


# ---------------------------------------------------------------------------
# Server-side auto-scan loop (60-second tick, independent of browser)
# ---------------------------------------------------------------------------

def _record_auto_scan_failure(exc: BaseException) -> None:
    """
    Record a failed auto-scan tick. MUST NOT raise — it is called from inside
    an `except` block, so any exception escaping here would propagate out of
    the handler and kill the loop, which is the exact failure this replaced.

    Channels are ordered by how likely they are to survive the failure being
    reported. The stderr logger goes first and is the only guaranteed one: the
    most likely causes of a tick failure (DB lock, disk full) are precisely the
    conditions under which the processing_logs write below will also fail.
    """
    detail = f"{type(exc).__name__}: {exc}"

    # 1. stderr logger — always available, carries the full traceback.
    try:
        log.exception("auto-scan tick failed: %s", detail)
    except Exception:
        pass

    # 2. In-memory state — surfaced by GET /api/syncthing/status (errors[-5:]).
    try:
        _state["errors"].append(f"auto-scan: {detail}")
        if len(_state["errors"]) > _MAX_ERRORS:
            _state["errors"] = _state["errors"][-_MAX_ERRORS:]
    except Exception:
        pass

    # 3. processing_logs — durable, survives restart. Fire-and-forget so a slow
    #    or blocked DB cannot stall the 60s cadence.
    try:
        tb = traceback.format_exc()
        asyncio.create_task(_write_auto_scan_failure_log(detail, tb))
    except Exception:
        pass


async def _write_auto_scan_failure_log(detail: str, tb: str) -> None:
    """Durable half of _record_auto_scan_failure. Swallows its own errors."""
    try:
        async with AsyncSessionLocal() as log_session:
            log_session.add(ProcessingLog(
                observation_id=None,   # loop-level failure, no row involved
                stage="auto_scan",
                status="failed",
                message=(
                    f"action=auto_scan_tick_failed error={detail}\n"
                    f"traceback:\n{tb}"
                ),
            ))
            await log_session.commit()
    except Exception:
        # Already reported via logger + _state; nothing further to do.
        log.warning("auto-scan: could not persist failure log for: %s", detail)


async def _auto_scan_loop() -> None:
    """
    Runs as a background asyncio task for the life of the server process.
    Every 60 seconds: check for new files in PhoneForaging and start
    processing if any are found and no batch is already running.
    """
    await asyncio.sleep(15)          # brief startup delay
    while True:
        try:
            _state["last_auto_scan"] = datetime.utcnow().isoformat()
            if not _state["processing"]:
                new_files = await _find_new_files()
                if new_files:
                    settings.ensure_dirs()
                    asyncio.create_task(_process_all(new_files))
        except Exception as exc:
            # This tick failed. Never re-raise: the loop must survive every
            # error or auto-scan dies silently for the life of the process.
            # Previously `except Exception: pass` — which hid DB locks, hash
            # IO errors and permission failures with zero trace.
            _record_auto_scan_failure(exc)
        await asyncio.sleep(60)


# ---------------------------------------------------------------------------
# POST /api/syncthing/process
# ---------------------------------------------------------------------------

@router.post("/process")
async def syncthing_process(background_tasks: BackgroundTasks):
    """
    Trigger processing of all new files in PhoneForaging.
    Returns immediately; processing runs in background.
    """
    if _state["processing"]:
        new_files = await _find_new_files()
        return {
            "status": "already_processing",
            "message": f"Already processing — {_state['in_flight']} in flight, {len(new_files)} still waiting",
            "in_flight": _state["in_flight"],
        }

    new_files = await _find_new_files()
    if not new_files:
        return {
            "status": "nothing_to_do",
            "message": "No new files found in PhoneForaging",
            "new_count": 0,
        }

    settings.ensure_dirs()
    background_tasks.add_task(_process_all, new_files)

    return {
        "status": "started",
        "message": f"Processing {len(new_files)} new file{'s' if len(new_files) != 1 else ''}",
        "started": len(new_files),
    }


# ---------------------------------------------------------------------------
# POST /api/syncthing/reprocess
# ---------------------------------------------------------------------------

def _no_id_result_filter():
    """Rows in needs_review with no usable identification result: either the ID
    step failed, or it produced no candidates / suggested / primary name. These
    are the rows a re-run should retry (e.g. after the threshold or API routing
    changed, or after an ID bug was fixed)."""
    return and_(
        Observation.upload_source == PHONE_ORIGIN_SOURCE,
        Observation.review_status == "needs_review",
        or_(
            Observation.identification_status == "failed_identification",
            and_(
                or_(
                    Observation.species_candidates_json.is_(None),
                    Observation.species_candidates_json.in_(("", "[]")),
                ),
                Observation.species_primary.is_(None),
                Observation.species_suggested.is_(None),
            ),
        ),
    )


@router.post("/reprocess")
async def syncthing_reprocess(background_tasks: BackgroundTasks, limit: int = 0):
    """
    Re-run the identification pipeline on Syncthing observations that are stuck
    in needs_review with no usable ID result. Handles the case where settings
    (confidence threshold, API routing) changed since original ingestion, or
    where identification previously failed.

    Source files are read from the watch directory; nothing is re-ingested.
    Pass ?limit=N to cap the run (useful for a test pass).
    """
    if _state["processing"]:
        return {
            "status": "already_processing",
            "message": f"Already processing — {_state['in_flight']} in flight",
            "in_flight": _state["in_flight"],
        }

    async with AsyncSessionLocal() as session:
        ids = [r[0] for r in (await session.execute(
            select(Observation.id).where(_no_id_result_filter()).order_by(Observation.id)
        )).all()]

    if limit and limit > 0:
        ids = ids[:limit]

    if not ids:
        return {"status": "nothing_to_do", "message": "No observations need re-identification", "count": 0}

    background_tasks.add_task(_reprocess_ids, ids)
    return {
        "status": "started",
        "message": f"Re-identifying {len(ids)} observation{'s' if len(ids) != 1 else ''}",
        "count": len(ids),
    }


async def _reprocess_ids(ids: List[int]) -> None:
    """Re-run identification on an explicit list of existing observation ids."""
    global _batch_new_species
    _state["processing"] = True
    _batch_new_species = set()
    _state["session_total"] = len(ids)
    _state["session_approved"] = 0
    _state["session_review"] = 0
    _state["session_failed"] = 0

    async def _one(oid: int) -> None:
        _state["in_flight"] += 1
        try:
            async with _get_semaphore():
                await _run_identification(oid)
        except Exception as exc:
            _state["session_failed"] += 1
            _state["errors"].append(f"reprocess obs#{oid}: {exc}")
            if len(_state["errors"]) > _MAX_ERRORS:
                _state["errors"] = _state["errors"][-_MAX_ERRORS:]
        finally:
            _state["in_flight"] -= 1

    try:
        await asyncio.gather(*[_one(i) for i in ids], return_exceptions=True)
    finally:
        _state["processing"] = False

    if _batch_new_species:
        from app.api.enrich import _run_enrichment_task
        asyncio.create_task(
            _run_enrichment_task(list(_batch_new_species), trigger="auto")
        )


# ---------------------------------------------------------------------------
# Background: process all new files
# ---------------------------------------------------------------------------

async def _process_all(files: List[Path]) -> None:
    from app.services.pipeline_lock import pipeline_try_acquire, pipeline_release, pipeline_holder
    acquired = await pipeline_try_acquire("P1 (Syncthing)")
    if not acquired:
        log.warning(
            "[P1 pipeline] SKIPPED at %s — pipeline mutex is held by %s. "
            "Syncthing will re-fire on next sync.",
            datetime.utcnow().isoformat(), pipeline_holder(),
        )
        return

    global _batch_new_species, _current_p1_session_id
    _state["processing"] = True
    _batch_new_species = set()

    # ── Open a persisted session row (additive observer only) ──────────────
    # session_open_p1 coalesces into the previous session when a phone batch
    # arrives within 5 minutes of the last one closing, so a single Syncthing
    # transfer that trickles in over 1-3 minutes is recorded as one session.
    from app.services.scan_sessions import (
        session_open_p1, session_close, session_heartbeat,
    )
    _current_p1_session_id = await session_open_p1(files_received=len(files))
    _state["session_files_received"] = len(files)

    # ── Durable process row (additive, display-only) ───────────────────────
    # Purely so the global job widget can see a P1 ingest from any page. The
    # in-memory _state above and /api/syncthing/status are the scan page's live
    # P1 card and are deliberately left untouched. bp_* helpers swallow their
    # own exceptions, so this can never affect the batch.
    from app.services.background_processes import bp_start, bp_progress, bp_finish
    _p1_pid = await bp_start(
        "p1_syncthing",
        progress_total=len(files),
        detail=f"P1 ingest: {len(files)} new",
    )
    _p1_ok = False

    # Heartbeat counter — stamp last_heartbeat every 10 files so the UI can
    # distinguish a live batch from a stalled / crashed one.
    _p1_hb_counter = 0

    async def _heartbeat_tick() -> None:
        nonlocal _p1_hb_counter
        _p1_hb_counter += 1
        if _p1_hb_counter % 10 == 0:
            await session_heartbeat(_current_p1_session_id)
            # Mirror the same cadence onto the bp row (one write per 10 files).
            await bp_progress(
                _p1_pid, _p1_hb_counter, len(files),
                detail=f"P1 ingest: {_p1_hb_counter} of {len(files)}",
            )

    try:
        sem = _get_semaphore()
        tasks = [_process_one(p, sem, _heartbeat_tick) for p in files]
        await asyncio.gather(*tasks, return_exceptions=True)
        _p1_ok = True
    finally:
        _state["processing"] = False
        _state["session_files_received"] = 0
        await session_close(_current_p1_session_id)
        _current_p1_session_id = None
        # Terminal either way; 'failed' only if we never reached the line above.
        await bp_finish(
            _p1_pid,
            "complete" if _p1_ok else "failed",
            error="" if _p1_ok else "P1 batch aborted before completion",
            current=len(files) if _p1_ok else _p1_hb_counter,
            total=len(files),
        )
        pipeline_release()

    # Auto-enrich any species newly confirmed in this batch
    if _batch_new_species:
        from app.api.enrich import _run_enrichment_task
        asyncio.create_task(
            _run_enrichment_task(list(_batch_new_species), trigger="auto")
        )


async def _process_one(
    file_path: Path,
    sem: asyncio.Semaphore,
    heartbeat_cb=None,
) -> None:
    """Ingest one file from PhoneForaging and queue identification."""
    _state["in_flight"] += 1
    try:
        async with sem:
            result = await _ingest_file(file_path)
            if isinstance(result, int):
                await _run_identification(result)
                try:
                    from app.services.photo_binding import run_resolvers
                    await run_resolvers(result)
                except Exception as _pb_err:
                    log.debug("[P1] photo_binding non-fatal: %s", _pb_err)
            elif result == "duplicate":
                # Same content already in the archive — no record created.
                from app.services.scan_sessions import session_inc
                await session_inc(_current_p1_session_id,
                                  files_processed=1, files_duplicate=1)
            elif result == "prefilter":
                # Saved but pre-filter rejected (recoverable).
                from app.services.scan_sessions import session_inc
                await session_inc(_current_p1_session_id,
                                  files_processed=1, files_rejected=1)
            # result is None → file vanished before read; nothing to count.
            if heartbeat_cb:
                await heartbeat_cb()
    except Exception as exc:
        _state["session_failed"] += 1
        err_msg = f"{file_path.name}: {exc}"
        _state["errors"].append(err_msg)
        log.error("[P1 pipeline] File seen but not processed — %s", err_msg, exc_info=True)
        if len(_state["errors"]) > _MAX_ERRORS:
            _state["errors"] = _state["errors"][-_MAX_ERRORS:]
        from app.services.scan_sessions import session_inc
        await session_inc(_current_p1_session_id,
                          files_processed=1, files_failed=1)
        if heartbeat_cb:
            await heartbeat_cb()
    finally:
        _state["in_flight"] -= 1


async def _ingest_file(file_path: Path) -> Union[int, str, None]:
    """
    Create an Observation record for a PhoneForaging image file.

    The source file is READ-ONLY — it is never modified or deleted.
    A project-local copy is made in photos/pipeline2/ so the observation record
    survives external HD removal (Option B, migration 0021).

    Returns:
      - int  — the new observation id (proceed to identification)
      - "duplicate"  — same content already ingested (no record created, no copy made)
      - "prefilter"  — saved but pre-filter rejected (skip identification)
      - None — file vanished before it could be read
    """
    from app.utils.exif import extract_exif, ExifData
    from app.utils.hashing import file_sha256
    from app.utils.thumbnail import generate_thumbnail
    from app.services.prefilter import classify_plant_likelihood

    # Safety check
    if not file_path.exists():
        return None

    # Read & hash (need content for file_size; sha for dup check)
    try:
        content = file_path.read_bytes()
        sha = file_sha256(file_path)
    except Exception as exc:
        raise RuntimeError(f"Could not read {file_path.name}: {exc}")

    # Early duplicate check before doing any file I/O — avoids wasting a copy.
    # The deleted_hashes half of this check now routes through the shared gate in
    # services/ingest_guard.py: it was previously implemented inline here and
    # nowhere else, which is how four other ingest paths ended up without it.
    # One implementation, five call sites. Behaviour here is unchanged ("duplicate"
    # is still returned so P1 counting is untouched) — the gate adds the skip log
    # this path never wrote.
    if sha:
        async with AsyncSessionLocal() as _dup_check:
            existing = await _dup_check.scalar(
                select(Observation).where(Observation.file_hash == sha)
            )
            if existing:
                return "duplicate"
            if await blacklisted_skip(_dup_check, sha, "p1_syncthing", file_path.name):
                return "duplicate"

    # Extract EXIF from the original source file
    try:
        exif = extract_exif(file_path)
    except Exception:
        exif = ExifData()

    # Try Google Takeout sidecar GPS if EXIF has no GPS
    if exif.latitude is None:
        try:
            from app.utils.sidecar import read_takeout_gps
            sidecar_gps = read_takeout_gps(file_path)
            if sidecar_gps:
                exif = ExifData(
                    latitude=sidecar_gps[0],
                    longitude=sidecar_gps[1],
                    altitude_m=exif.altitude_m,
                    taken_at=exif.taken_at,
                    camera_make=exif.camera_make,
                    camera_model=exif.camera_model,
                )
        except Exception:
            pass

    # ── Copy source file to project-local storage ─────────────────────────
    # photos/pipeline2/<uuid>_<original-stem><ext> — same naming convention
    # as phone uploads so path handling elsewhere is uniform.
    ext = file_path.suffix.lower()
    unique_stem = f"{uuid.uuid4().hex}_{file_path.stem}"
    dest_dir = settings.pipeline2_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_path = dest_dir / f"{unique_stem}{ext}"
    try:
        shutil.copy2(str(file_path), str(local_path))
    except Exception as exc:
        raise RuntimeError(f"Could not copy {file_path.name} to pipeline2 store: {exc}")

    # Generate thumbnail from the local copy (source may become unavailable)
    try:
        from app.services.settings_service import get_setting as _gs_st
        thumb = generate_thumbnail(
            local_path,
            thumbnails_dir=Path(settings.thumbnails_dir),
            size=_gs_st("thumbnail_size"),
        )
    except Exception:
        thumb = None

    async with AsyncSessionLocal() as session:
        # Secondary duplicate check by hash (race guard — another worker may
        # have ingested the same file while we were copying)
        if sha:
            existing = await session.scalar(
                select(Observation).where(Observation.file_hash == sha)
            )
            if existing:
                # Remove the just-made copy — it's redundant
                local_path.unlink(missing_ok=True)
                return "duplicate"

        obs = Observation(
            file_path=str(local_path),   # project-local copy, never HD-dependent
            file_hash=sha,
            file_size_bytes=len(content),
            file_format=ext.lstrip("."),
            thumbnail_path=str(thumb) if thumb else None,
            photo_taken_at=exif.taken_at,
            latitude=exif.latitude,
            longitude=exif.longitude,
            altitude_m=exif.altitude_m,
            camera_make=exif.camera_make,
            camera_model=exif.camera_model,
            upload_source=PHONE_ORIGIN_SOURCE,
            review_status="pending",
            processing_stage="ingested",
            identification_status="pending_identification",
        )
        session.add(obs)
        await session.flush()

        # Lenient pre-filter — rejects only clear non-biological subjects
        try:
            is_plant, conf, category = classify_plant_likelihood(
                file_path,
                has_gps=(exif.latitude is not None),
            )
        except Exception:
            is_plant, conf, category = True, 0.5, "plant"

        gps_note = "GPS present" if exif.latitude is not None else "GPS missing"

        if category in _P1_REJECT_CATEGORIES:
            # Clear non-biological subject — save record but skip identification.
            # Recoverable via POST /{obs_id}/override-prefilter.
            obs.identification_status = "not_plant"
            obs.review_status         = "pending"
            obs.processing_stage      = "prefilter_rejected"
            obs.is_plant_likely       = False
            obs.plant_detect_confidence = conf
            obs.prefilter_category    = category
            session.add(ProcessingLog(
                observation_id=obs.id,
                stage="syncthing_prefilter_reject",
                status="info",
                message=(
                    f"Syncthing prefilter rejected: {file_path.name} — "
                    f"category={category} conf={conf:.3f} {gps_note}"
                ),
            ))
            await session.commit()
            _state["session_total"] += 1
            return "prefilter"   # skip _run_identification; obs is saved and recoverable
        else:
            obs.is_plant_likely       = True
            obs.plant_detect_confidence = conf
            obs.prefilter_category    = category
            session.add(ProcessingLog(
                observation_id=obs.id,
                stage="syncthing_ingest",
                status="success",
                message=(
                    f"Syncthing import: {file_path.name} — "
                    f"prefilter={category} conf={conf:.3f} {gps_note}"
                ),
            ))
            await session.commit()
            _state["session_total"] += 1
            return obs.id


# ---------------------------------------------------------------------------
# Background identification (reuses scan.py logic)
# ---------------------------------------------------------------------------

async def _run_identification(obs_id: int) -> None:
    """
    Identify a Syncthing observation. Imports and calls scan.py's worker,
    which already handles upload_source=PHONE_ORIGIN_SOURCE correctly:
      - dual-agree ≥80% → auto-approved
      - otherwise → needs_review "Syncthing — needs review"
    """
    from app.api.scan import _identify_scanned
    from app.services.settings_service import get_setting
    try:
        # API source is user-configurable (Settings → Pipelines → api_source_syncthing).
        # Fungi always route to iNaturalist only — enforced inside _identify_scanned
        # regardless of this setting (PlantNet has no fungi coverage).
        await _identify_scanned(
            obs_id, source=get_setting("api_source_syncthing"), force_review=False
        )
        # Check result to update session counters and collect new species
        from app.services.scan_sessions import session_inc
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if obs:
                if obs.review_status in ("approved", "manually_verified"):
                    _state["session_approved"] += 1
                    await session_inc(_current_p1_session_id,
                                      files_processed=1, files_approved=1)
                    if obs.species_primary:
                        _batch_new_species.add(obs.species_primary)
                else:
                    _state["session_review"] += 1
                    await session_inc(_current_p1_session_id,
                                      files_processed=1, files_review=1)
    except Exception as exc:
        _state["session_failed"] += 1
        _state["errors"].append(f"ID obs#{obs_id}: {exc}")
        # Durable record — the in-memory _state above dies with the process, and
        # scan_sessions.files_failed is a bare integer with no diagnosis. That
        # combination is why the 15 July stalls left six weeks of silence: the
        # only trace of three failures was "files_failed=3" on session 40.
        # _mark_identify_failed writes a processing_logs row naming the real
        # exception and never raises.
        #
        # Backstop only: _identify_scanned now records its own failures, so an
        # exception reaching here means its recorder itself failed. Recording
        # twice is acceptable; recording nothing is what we are fixing.
        from app.api.scan import _mark_identify_failed
        await _mark_identify_failed(obs_id, exc)
        from app.services.scan_sessions import session_inc
        await session_inc(_current_p1_session_id,
                          files_processed=1, files_failed=1)
