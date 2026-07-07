"""
File upload pipeline — handles browser/phone uploads.

Upload flow (browser → POST /api/scan):
  1. Validate file type
  2. Read bytes; compute SHA-256 hash (duplicate check happens before any disk write)
  3. Write to a TEMPORARY file
  4. Extract EXIF, resolve GPS (EXIF → Takeout sidecar only; no device fallback)
  5. Run pre-filter on the temp file:
     - REJECTED → delete temp file immediately (never touches permanent disk),
                  return {passed:false, prefilter:category, ...} — no DB record created
     - PASSED   → move temp → permanent uploads dir, generate thumbnail, create
                  Observation record, trigger identification as background task
  6. Return {observation_id, passed:true, prefilter, ...}; client polls for ID result
  7. After identification:
     - File upload: ALWAYS needs_review unless dual-agree ≥ upload_auto_approve_threshold setting
     - If species found and not in DB → create species card + flag for enrichment

Path integrity:
  ~/ForagingID/uploads/ — permanent, written only after prefilter pass
  ~/ForagingID/photos/  — permanent, never abandon
  ~/Documents/Pictures            — expendable for unconfirmed observations

upload_source values:
  "file_upload" — browser drag-drop or phone upload (always needs_review)
  "phone"       — legacy alias for file_upload (treated identically)
  "syncthing"   — Syncthing pipeline (auto-approves on dual-API agreement only)

POST /api/scan/{obs_id}/override-prefilter  — override a pre-filter rejection
GET  /api/scan/{obs_id}/status              — poll identification progress
"""

import asyncio
import hashlib
import httpx
import json as _json
import logging
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text as _sqla_text
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.observation import Observation, is_terminal_review_status
from app.models.processing import ProcessingLog
from app.services.background_processes import bp_start, bp_progress, bp_finish
from app.services.file_cleanup import delete_observation_file
from app.services.prefilter import classify_plant_likelihood
from app.services.species_link import set_observation_species
from app.services.taxonomy import collapse_autonym, normalize_taxon_key
from app.utils.exif import extract_exif
from app.utils.thumbnail import generate_thumbnail

router = APIRouter(prefix="/api/scan", tags=["scan"])

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
_VALID_SOURCES = {"plantnet", "inaturalist", "both"}
_VALID_UPLOAD_SOURCES = {"file_upload", "phone"}   # "syncthing" handled by syncthing.py

# In-memory status map: {obs_id: "processing" | "done" | "failed"}
_scan_status: dict = {}

# ── Pipeline 2 session tracking ───────────────────────────────────────────────
# Maps obs_id → (session_id, filename) so the identification callback can
# update the row and push SSE narration. Removed after identification completes.
_p2_obs_session: dict = {}   # {obs_id: (session_id, filename)}

# ── Pipeline 2 live-progress SSE ─────────────────────────────────────────────
# Keyed by session_id. Created when process-delta arms a session; consumed by
# the SSE endpoint. Best-effort in-memory only — not persisted to DB.
_p2_progress: dict = {}          # {session_id: asyncio.Queue}
_p2_session_counter: dict = {}   # {session_id: int}  — in-memory processed count

# ── Pipeline 2 pause flag ─────────────────────────────────────────────────────
# Session IDs that have been paused. _identify_scanned checks this before
# processing each file and exits cleanly if the session is flagged.
_p2_paused_sessions: set = set()

# ── Archive scan (server-side DIGIERA batch) ──────────────────────────────────
# Keyed by job_id (int timestamp). Each job spans multiple year-folder sessions
# processed sequentially. SSE queue carries folder-level events; per-file detail
# flows through the per-session _p2_progress queue as normal.
_archive_queues: dict = {}
_ARCHIVE_ROOT_DEFAULT = "/Volumes/DIGIERA/Pictures"

# ---------------------------------------------------------------------------
# Caffeinate — prevent Mac sleep during long scans
# ---------------------------------------------------------------------------

_caffeinate_proc: Optional[asyncio.subprocess.Process] = None


@router.post("/caffeinate/start")
async def caffeinate_start():
    """Start caffeinate -dimsu to keep the Mac awake during a scan session."""
    global _caffeinate_proc
    if _caffeinate_proc is not None and _caffeinate_proc.returncode is None:
        return {"active": True, "pid": _caffeinate_proc.pid, "started": False}
    try:
        _caffeinate_proc = await asyncio.create_subprocess_exec(
            "caffeinate", "-dimsu",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return {"active": True, "pid": _caffeinate_proc.pid, "started": True}
    except FileNotFoundError:
        # caffeinate only exists on macOS
        return {"active": False, "error": "caffeinate not available on this system"}


@router.post("/caffeinate/stop")
async def caffeinate_stop():
    """Kill the caffeinate process — allow Mac to sleep normally again."""
    global _caffeinate_proc
    if _caffeinate_proc is None or _caffeinate_proc.returncode is not None:
        _caffeinate_proc = None
        return {"active": False, "stopped": False}
    try:
        _caffeinate_proc.terminate()
        await asyncio.wait_for(_caffeinate_proc.wait(), timeout=2.0)
    except Exception:
        try:
            _caffeinate_proc.kill()
        except Exception:
            pass
    _caffeinate_proc = None
    return {"active": False, "stopped": True}


@router.get("/caffeinate/status")
async def caffeinate_status():
    """Return whether caffeinate is currently active."""
    global _caffeinate_proc
    active = _caffeinate_proc is not None and _caffeinate_proc.returncode is None
    if not active:
        _caffeinate_proc = None
    return {"active": active, "pid": _caffeinate_proc.pid if active else None}


# ---------------------------------------------------------------------------
# GET /api/scan/inat-token-status
# ---------------------------------------------------------------------------

@router.get("/inat-token-status")
async def inat_token_status():
    """Check whether the iNaturalist API token is configured and valid."""
    token = settings.inaturalist_api_token
    if not token:
        return {"state": "missing", "message": "No token configured in .env"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://api.inaturalist.org/v1/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            login = (resp.json().get("results") or [{}])[0].get("login", "")
            return {"state": "valid", "login": login}
        elif resp.status_code == 401:
            return {"state": "invalid", "message": "Token rejected (401 Unauthorized)"}
        else:
            return {"state": "error", "message": f"Unexpected HTTP {resp.status_code}"}
    except Exception as exc:
        return {"state": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# POST /api/scan
# ---------------------------------------------------------------------------

@router.post("")
async def scan_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str = Form("both"),
    upload_source: str = Form("file_upload"),
    scan_session_id: Optional[int] = Form(None),   # Pipeline 2 session tracking
):
    """
    Accept a photo from the browser. Pre-filter runs FIRST on a temp file.
    Rejected files are deleted immediately — never written to permanent storage.
    Passed files are moved to the uploads dir, then identification is queued.

    Returns:
      - {passed:false, prefilter, prefilter_confidence, filename} if rejected
      - {passed:true, observation_id, prefilter, ...} if accepted; poll /status

    Optional form fields:
        upload_source    — "file_upload" (default) or "phone" (legacy alias)
        scan_session_id  — pipeline 2 session id (from POST /api/scan/sessions)
    """
    # Normalise upload_source — reject syncthing (wrong endpoint)
    if upload_source not in _VALID_UPLOAD_SOURCES:
        upload_source = "file_upload"
    settings.ensure_dirs()

    # ── Validate extension / MIME ─────────────────────────────────────────
    # Non-image files (JSON sidecars, .mp clips, etc.) are SKIPPED — returned
    # as {skipped: true} rather than a 4xx error so they don't inflate the
    # "failed" counter in batch session summaries.
    ext = Path(file.filename or "").suffix.lower()
    is_heic = ext in {".heic", ".heif"} or (file.content_type or "").lower() in {"image/heic", "image/heif"}

    if is_heic or ext not in _ALLOWED_EXTENSIONS:
        # Increment session's skipped counter (fire-and-forget)
        if scan_session_id:
            from app.services.scan_sessions import session_inc as _sinc
            await _sinc(scan_session_id, files_skipped=1)
            await _p2_auto_close(scan_session_id)
        msg = (
            "HEIC photos are not yet supported. "
            "On iPhone: Settings → Camera → Formats → Most Compatible to shoot in JPEG."
            if is_heic else
            f"Non-image file skipped (ext='{ext}'). Accepted: jpg, jpeg, png, webp."
        )
        log.debug("Skipping non-image file: %s (ext=%s)", file.filename, ext)
        return JSONResponse(status_code=200, content={
            "skipped":  True,
            "reason":   "non_image",
            "is_heic":  is_heic,
            "ext":      ext,
            "filename": file.filename or "",
            "message":  msg,
        })

    if file.content_type and file.content_type not in _ALLOWED_MIME:
        if not file.content_type.startswith("image/"):
            if scan_session_id:
                from app.services.scan_sessions import session_inc as _sinc
                await _sinc(scan_session_id, files_skipped=1)
                await _p2_auto_close(scan_session_id)
            log.debug("Skipping bad MIME: %s (type=%s)", file.filename, file.content_type)
            return JSONResponse(status_code=200, content={
                "skipped":  True,
                "reason":   "non_image",
                "is_heic":  False,
                "ext":      ext,
                "filename": file.filename or "",
                "message":  f"Non-image MIME type skipped ('{file.content_type}').",
            })

    # ── Read bytes + hash (before any disk write) ─────────────────────────
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (max 50 MB).")
    except HTTPException:
        raise

    sha = hashlib.sha256(content).hexdigest()

    # ── Duplicate check (before writing anything) ─────────────────────────
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(Observation).where(Observation.file_hash == sha)
        )
        if existing:
            # P2 session tracking: count as processed + duplicate so the
            # lifetime breakdown reconciles against files received.
            if scan_session_id:
                from app.services.scan_sessions import session_inc as _sinc
                await _sinc(scan_session_id, files_processed=1, files_duplicate=1)
                await _p2_auto_close(scan_session_id)
            return {
                "passed": True,            # already accepted previously
                "observation_id": existing.id,
                "duplicate": True,
                "prefilter": existing.prefilter_category or "unknown",
                "status": existing.identification_status or "pending_identification",
                "review_url": f"/review?id={existing.id}",
            }

    # ── Write to TEMP file (cheap; deleted on prefilter rejection) ─────────
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=ext)
    tmp_path = Path(tmp_name)
    try:
        with open(tmp_fd, "wb") as f:
            f.write(content)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to write temp file: {exc}")

    # ── EXIF extraction ────────────────────────────────────────────────────
    try:
        exif = extract_exif(tmp_path)
    except Exception:
        exif = type("E", (), {
            "taken_at": None, "latitude": None, "longitude": None,
            "altitude_m": None, "camera_make": None, "camera_model": None,
        })()

    # GPS source resolution — EXIF → Takeout sidecar ONLY:
    #   1. EXIF embedded in the image
    #   2. Google Takeout JSON sidecar
    # Browser geolocation removed (2026-06-13): a single device-location reading
    # is not a valid per-photo location for archive batch uploads of photos taken
    # elsewhere/earlier. If both sources are absent the observation gets NULL
    # coordinates (truthful — location unknown), never a device fallback.
    _gps_source = "exif" if exif.latitude is not None else None
    if exif.latitude is None:
        try:
            from app.utils.sidecar import read_takeout_gps as _read_sidecar
            _sidecar_gps = _read_sidecar(tmp_path)
            if _sidecar_gps:
                exif = type("E", (), {
                    "taken_at":    exif.taken_at,
                    "latitude":    _sidecar_gps[0],
                    "longitude":   _sidecar_gps[1],
                    "altitude_m":  exif.altitude_m,
                    "camera_make": exif.camera_make,
                    "camera_model": exif.camera_model,
                })()
                _gps_source = "sidecar_json"
        except Exception:
            pass

    # ── Pre-filter — runs on temp file BEFORE permanent save ──────────────
    # Rejected files are deleted here; nothing written to uploads/ or DB.
    try:
        # Pipeline 2 (file upload) uses a tighter green threshold to reduce
        # non-plant pass-throughs from close-up or indoor photos.
        from app.services.settings_service import get_setting as _gs
        _p2_threshold = _gs("prefilter_pipeline2_green_threshold")
        is_plant, pf_conf, pf_category = classify_plant_likelihood(
            tmp_path,
            has_gps=(exif.latitude is not None),
            green_threshold_override=_p2_threshold,
        )
    except Exception:
        is_plant, pf_conf, pf_category = True, 1.0, "plant"

    if not is_plant:
        # Rejected — save the file so the user can recover false positives via
        # /override-prefilter.  An observation record is created with
        # identification_status="not_plant" so the endpoint can pick it up.
        reject_stem = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').stem}"
        reject_path = settings.phone_uploads_dir / f"{reject_stem}{ext}"
        try:
            shutil.move(str(tmp_path), str(reject_path))
        except Exception:
            tmp_path.unlink(missing_ok=True)
            reject_path = None

        try:
            thumb = generate_thumbnail(
                reject_path,
                thumbnails_dir=Path(settings.thumbnails_dir),
                size=_gs("thumbnail_size"),
            ) if reject_path else None
        except Exception:
            thumb = None

        async with AsyncSessionLocal() as session:
            rej_obs = Observation(
                file_path=str(reject_path) if reject_path else "",
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
                review_status="pending",
                processing_stage="prefilter_rejected",
                identification_status="not_plant",
                upload_source=upload_source,
                is_plant_likely=False,
                plant_detect_confidence=pf_conf,
                prefilter_category=pf_category,
            )
            session.add(rej_obs)
            try:
                await session.flush()
                session.add(ProcessingLog(
                    observation_id=rej_obs.id,
                    stage="scan_prefilter",
                    status="rejected",
                    message=(
                        f"Prefilter rejected: category={pf_category} "
                        f"conf={pf_conf:.3f} — saved for possible override"
                    ),
                ))
                await session.commit()
                rej_obs_id = rej_obs.id
            except IntegrityError:
                # Concurrent race on file_hash — the UNIQUE index blocked the dup.
                await session.rollback()
                existing = await session.scalar(select(Observation).where(Observation.file_hash == sha))
                if existing is None:
                    raise
                log.info("scan_image(reject): file_hash race on %s — returning existing obs %d", sha[:12], existing.id)
                if scan_session_id:
                    from app.services.scan_sessions import session_inc as _sinc
                    await _sinc(scan_session_id, files_processed=1, files_duplicate=1)
                    await _p2_auto_close(scan_session_id)
                return {
                    "passed": True, "observation_id": existing.id, "duplicate": True,
                    "prefilter": existing.prefilter_category or "unknown",
                    "status": existing.identification_status or "pending_identification",
                    "review_url": f"/review?id={existing.id}",
                }

        # ── P2 session tracking: prefilter rejected ───────────────────────
        if scan_session_id:
            from app.services.scan_sessions import session_inc as _sinc
            await _sinc(scan_session_id, files_processed=1, files_rejected=1)
            await _p2_auto_close(scan_session_id)

        return {
            "passed": False,
            "duplicate": False,
            "observation_id": rej_obs_id,
            "prefilter": pf_category,
            "prefilter_confidence": round(pf_conf, 3),
            "filename": file.filename or "upload",
            "thumbnail": f"/thumbnails/{thumb.name}" if thumb else None,
            "message": (
                f"Pre-filter rejected: {pf_category} "
                f"({pf_conf:.0%} confidence) — saved, can be overridden"
            ),
        }

    # ── Passed pre-filter — move temp → permanent uploads dir ────────────
    unique_stem = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').stem}"
    save_path = settings.phone_uploads_dir / f"{unique_stem}{ext}"
    try:
        shutil.move(str(tmp_path), str(save_path))
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")

    # ── Thumbnail ─────────────────────────────────────────────────────────
    try:
        thumb = generate_thumbnail(
            save_path,
            thumbnails_dir=Path(settings.thumbnails_dir),
            size=_gs("thumbnail_size"),
        )
    except Exception:
        thumb = None

    # ── Create Observation record ─────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        obs = Observation(
            file_path=str(save_path),
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
            review_status="pending",
            processing_stage="ingested",
            identification_status="pending_identification",
            upload_source=upload_source,
            is_plant_likely=True,
            plant_detect_confidence=pf_conf,
            prefilter_category=pf_category,
        )
        session.add(obs)
        try:
            await session.flush()
            session.add(ProcessingLog(
                observation_id=obs.id,
                stage="scan_prefilter",
                status="success",
                message=(
                    f"Prefilter passed: category={pf_category} "
                    f"conf={pf_conf:.3f} gps={'yes' if exif.latitude is not None else 'no'}"
                ),
            ))
            await session.commit()
            obs_id = obs.id
        except IntegrityError:
            # True concurrent race: another pipeline committed this file_hash between
            # the dedup pre-check and our commit. The UNIQUE index rejected the second
            # write (no duplicate created) — return the row that landed.
            await session.rollback()
            existing = await session.scalar(select(Observation).where(Observation.file_hash == sha))
            if existing is None:
                raise
            log.info("scan_image: file_hash race on %s — returning existing obs %d", sha[:12], existing.id)
            return {
                "passed": True, "observation_id": existing.id, "duplicate": True,
                "prefilter": existing.prefilter_category or "unknown",
                "status": existing.identification_status or "pending_identification",
                "review_url": f"/review?id={existing.id}",
            }

    # Normalise source
    if source not in _VALID_SOURCES:
        source = "both"

    # ── Trigger identification as background task ─────────────────────────
    _scan_status[obs_id] = "processing"
    background_tasks.add_task(_identify_scanned, obs_id, source)

    # ── Photo→encounter binding (fire-and-forget, non-fatal) ─────────────
    async def _run_photo_binding(oid: int):
        try:
            from app.services.photo_binding import run_resolvers
            await run_resolvers(oid)
        except Exception as e:
            log.debug("[P2] photo_binding non-fatal: %s", e)
    background_tasks.add_task(_run_photo_binding, obs_id)

    # ── P2 session tracking: register obs for identification callback ─────
    if scan_session_id:
        _p2_obs_session[obs_id] = (scan_session_id, file.filename or "")

    return {
        "passed": True,
        "observation_id": obs_id,
        "duplicate": False,
        "prefilter": pf_category,
        "prefilter_passed": True,
        "prefilter_confidence": round(pf_conf, 3),
        "has_gps": exif.latitude is not None,
        "gps_source": _gps_source,
        "source": source,
        "status": "processing",
        "message": "Pre-filter passed — identification running",
        "review_url": f"/review?id={obs_id}",
    }


# ---------------------------------------------------------------------------
# GET /api/scan/{obs_id}/status
# ---------------------------------------------------------------------------

@router.get("/{obs_id}/status")
async def scan_status(obs_id: int):
    """Poll identification status for a scanned observation."""
    async with AsyncSessionLocal() as session:
        obs = await session.get(Observation, obs_id)
        if not obs:
            raise HTTPException(status_code=404, detail="Observation not found")

        candidates = []
        if obs.species_candidates_json:
            try:
                raw = _json.loads(obs.species_candidates_json)
                candidates = raw[:5]
            except Exception:
                pass

        return {
            "observation_id": obs_id,
            "identification_status": obs.identification_status,
            "review_status": obs.review_status,
            "species_primary": obs.species_primary,
            "species_suggested": obs.species_suggested,  # best guess when below min threshold
            "confidence": candidates[0]["score"] if candidates else None,
            "candidates": candidates,
            "is_plant_likely": obs.is_plant_likely,
            "prefilter_category": obs.prefilter_category,
            "upload_source": obs.upload_source,
            "processing": _scan_status.get(obs_id) == "processing",
            "review_url": f"/review?id={obs_id}",
            "species_url": (
                f"/species?s={obs.species_primary}"
                if obs.species_primary
                else None
            ),
        }


# ---------------------------------------------------------------------------
# POST /api/scan/{obs_id}/override-prefilter
# ---------------------------------------------------------------------------

@router.post("/{obs_id}/override-prefilter")
async def override_prefilter(obs_id: int, background_tasks: BackgroundTasks):
    """
    Override a pre-filter rejection — user asserts the image may be a plant.
    Only applicable to folder-scan observations (phone uploads always proceed).
    """
    async with AsyncSessionLocal() as session:
        obs = await session.get(Observation, obs_id)
        if not obs:
            raise HTTPException(status_code=404, detail="Observation not found")
        if obs.identification_status != "not_plant":
            raise HTTPException(
                status_code=400,
                detail="Observation is not in pre-filter rejected state",
            )
        obs.identification_status = "pending_identification"
        obs.review_status = "pending"
        obs.is_plant_likely = True
        session.add(ProcessingLog(
            observation_id=obs_id,
            stage="prefilter_override",
            status="success",
            message="Pre-filter rejection overridden by user — queued for identification",
        ))
        await session.commit()

    _scan_status[obs_id] = "processing"
    background_tasks.add_task(_identify_scanned, obs_id, force_review=True)

    return {
        "observation_id": obs_id,
        "status": "processing",
        "message": "Override accepted — queued for identification",
    }


# ---------------------------------------------------------------------------
# POST /api/scan/recheck-threshold
# ---------------------------------------------------------------------------

@router.post("/recheck-threshold")
async def recheck_threshold():
    """
    Flag existing review-queue observations whose top candidate score is below
    the current min_identification_confidence threshold.

    For each affected row:
      - Moves species_primary → species_suggested (nothing discarded)
      - Sets species_primary = NULL
      - Adds a ProcessingLog entry marking it "flagged by threshold recheck"
      - Does NOT change review_status (stays needs_review) — human reviews it

    Returns:
      {flagged: N, threshold: float, message: str}
    """
    from app.services.settings_service import get_setting as _gs

    threshold = _gs("min_identification_confidence")

    async with AsyncSessionLocal() as session:
        # Find needs_review observations that still have a species assigned
        result = await session.execute(
            select(Observation).where(
                Observation.review_status == "needs_review",
                Observation.species_primary.is_not(None),
                Observation.human_corrected.is_(False),
            )
        )
        rows = result.scalars().all()

        flagged = 0
        for obs in rows:
            # Parse top candidate score from candidates JSON
            top_score = 0.0
            if obs.species_candidates_json:
                try:
                    cands = _json.loads(obs.species_candidates_json)
                    if cands:
                        top_score = cands[0].get("score", 0.0)
                except Exception:
                    pass

            if top_score < threshold:
                old_name = obs.species_primary
                obs.species_suggested = old_name
                await set_observation_species(session, obs, None)
                session.add(ProcessingLog(
                    observation_id=obs.id,
                    stage="threshold_recheck",
                    status="success",
                    message=(
                        f"Threshold recheck: {old_name!r} ({top_score:.2%}) is below "
                        f"min threshold ({threshold:.0%}) — species_primary cleared, "
                        f"stored in species_suggested for reviewer."
                    ),
                ))
                flagged += 1

        await session.commit()

    return {
        "flagged": flagged,
        "threshold": round(threshold * 100),
        "message": (
            f"Flagged {flagged} observation{'s' if flagged != 1 else ''} below "
            f"{threshold:.0%} confidence for human review."
        ),
    }


# ---------------------------------------------------------------------------
# POST /api/scan/reprocess-pending
# ---------------------------------------------------------------------------

@router.post("/reprocess-pending")
async def reprocess_pending(body: dict):
    """
    Re-run the identification pipeline on observations that match a
    review_status + file_path filter.

    Body:
        filter  — substring matched against file_path (LIKE '%filter%')
        status  — review_status to match (default: "pending")

    Returns {"queued": N} immediately; processing runs in background.

    Rules:
    - Skips observations with identification_status = 'not_plant'
      (use override-prefilter for those).
    - Resets identification_status → pending_identification on each
      matched observation before queueing so status polls show "processing".
    - Results route through normal review-queue logic — no auto-approve bypass.
    - Processed in batches of 20; existing _INAT_SEMAPHORE controls iNat rate.
    """
    filter_str       = str(body.get("filter") or "")
    status_str       = str(body.get("status") or "pending")
    include_not_plant = bool(body.get("include_not_plant", False))

    async with AsyncSessionLocal() as session:
        _where = [
            Observation.review_status == status_str,
            Observation.file_path.like(f"%{filter_str}%"),
        ]
        if not include_not_plant:
            _where.append(Observation.identification_status != "not_plant")

        result = await session.execute(
            select(Observation).where(*_where).order_by(Observation.id)
        )
        rows = result.scalars().all()

        obs_ids = []
        for obs in rows:
            obs.identification_status = "pending_identification"
            obs_ids.append(obs.id)

        await session.commit()

    log.info(
        "[reprocess-pending] queued %d observations "
        "(status=%r filter=%r)",
        len(obs_ids), status_str, filter_str,
    )

    pid = None
    if obs_ids:
        pid = await bp_start(
            "reprocess_pending",
            progress_total=len(obs_ids),
            detail=f"Re-processing {len(obs_ids)} observations",
        )
        asyncio.create_task(_reprocess_pending_batch(obs_ids, pid))

    return {"queued": len(obs_ids), "process_id": pid}


async def _reprocess_pending_batch(obs_ids: list, pid: Optional[int] = None) -> None:
    """
    Run _identify_scanned on obs_ids in batches of 20.

    Each batch is awaited before the next starts so console logs are
    readable and the iNat semaphore never faces more than 20 concurrent
    callers at once. Within a batch, asyncio.gather runs them concurrently;
    _INAT_SEMAPHORE inside _identify_scanned caps live iNat calls further.
    """
    batch_size  = 20
    total       = len(obs_ids)
    num_batches = (total + batch_size - 1) // batch_size
    processed   = 0

    for batch_idx in range(num_batches):
        start  = batch_idx * batch_size
        batch  = obs_ids[start:start + batch_size]
        log.info(
            "[reprocess-pending] batch %d/%d — obs ids %s",
            batch_idx + 1, num_batches, batch,
        )
        try:
            await asyncio.gather(*[_identify_scanned(obs_id) for obs_id in batch])
        except Exception:
            log.exception(
                "[reprocess-pending] unhandled error in batch %d", batch_idx + 1
            )
        processed += len(batch)
        await bp_progress(
            pid, processed, total,
            f"Batch {batch_idx + 1}/{num_batches} done",
        )

    await bp_finish(pid, "complete", current=total, total=total)
    log.info("[reprocess-pending] all %d observations processed", total)


# ---------------------------------------------------------------------------
# P2 session tracking helpers — additive observer, never in pipeline logic
# ---------------------------------------------------------------------------

async def _p2_auto_close(session_id: int) -> None:
    """
    Close a P2 session when all received files have been accounted for
    (processed OR skipped). On close, pushes a 'done' event to the SSE queue
    so connected clients can terminate their stream.
    Fire-and-forget: catches and logs any exception.
    """
    from app.services.scan_sessions import session_close
    try:
        async with AsyncSessionLocal() as _db:
            row = (await _db.execute(
                _sqla_text(
                    "SELECT files_processed, files_received, ended_at, "
                    "COALESCE(files_skipped, 0), "
                    "COALESCE(files_new, 0), COALESCE(files_retryable, 0) "
                    "FROM scan_sessions WHERE id = :id"
                ),
                {"id": session_id},
            )).fetchone()
        # Close when processed >= target. Target is files_new + files_retryable when
        # set (pre-filtered batch), falling back to files_received for legacy sessions.
        files_new_ret = (row[4] or 0) + (row[5] or 0) if len(row) > 5 else 0
        target = files_new_ret if files_new_ret > 0 else row[1]
        if row and row[2] is None and target > 0 and row[0] >= target:
            await session_close(session_id)
            # Signal SSE consumers that the session is finished
            q = _p2_progress.pop(session_id, None)
            _p2_session_counter.pop(session_id, None)
            if q is not None:
                await q.put({"done": True, "status": "complete"})
    except Exception:
        log.exception("_p2_auto_close failed (session_id=%s)", session_id)


async def _p2_tick(obs_id: int, **fields: int) -> None:
    """
    Increment P2 session counters for a single completed observation,
    push a live-progress SSE event, then auto-close if all files done.
    Cleans up _p2_obs_session. Fire-and-forget: never propagates exceptions.
    """
    entry = _p2_obs_session.pop(obs_id, None)
    if entry is None:
        return
    # Support both old-style int and new-style (session_id, filename) tuples
    if isinstance(entry, tuple):
        session_id, filename = entry
    else:
        session_id, filename = entry, ""
    try:
        from app.services.scan_sessions import session_inc, session_heartbeat
        await session_inc(session_id, **fields)
        # Heartbeat every 10 completions so stall detection stays current
        count_so_far = _p2_session_counter.get(session_id, 0) + 1
        if count_so_far % 10 == 0:
            await session_heartbeat(session_id)
        # ── SSE narration push (best-effort, in-memory only) ──────────────
        q = _p2_progress.get(session_id)
        if q is not None:
            _p2_session_counter[session_id] = _p2_session_counter.get(session_id, 0) + 1
            # Derive outcome label from fields
            if fields.get("files_approved"):
                status_label = "approved"
            elif fields.get("files_review"):
                status_label = "review"
            elif fields.get("files_rejected"):
                status_label = "rejected"
            elif fields.get("files_failed"):
                status_label = "failed"
            elif fields.get("files_duplicate"):
                status_label = "duplicate"
            else:
                status_label = "done"
            try:
                async with AsyncSessionLocal() as _db:
                    _row = (await _db.execute(
                        _sqla_text(
                            "SELECT files_received, "
                            "COALESCE(files_new,0)+COALESCE(files_retryable,0) "
                            "FROM scan_sessions WHERE id = :id"
                        ),
                        {"id": session_id},
                    )).fetchone()
                # Use files_new+retryable as total when set (pre-filtered batch)
                # so SSE shows "Identifying X of 1,053" not "X of 18,456"
                if _row:
                    total = _row[1] if _row[1] > 0 else (_row[0] or 0)
                else:
                    total = 0
            except Exception:
                total = 0
            await q.put({
                "current":  _p2_session_counter[session_id],
                "total":    total,
                "filename": filename,
                "status":   status_label,
            })
        await _p2_auto_close(session_id)
    except Exception:
        log.exception(
            "_p2_tick failed (obs_id=%s session_id=%s)", obs_id, session_id
        )


# ---------------------------------------------------------------------------
# Background identification
# ---------------------------------------------------------------------------

async def _identify_scanned(
    obs_id: int,
    source: str = "both",
    force_review: bool = False,
) -> None:
    """
    Identify a single scanned/uploaded observation.

    force_review=True: result goes to needs_review regardless of confidence.
    This is always True for phone uploads and override-prefilter actions.
    """
    from app.integrations.plantnet import identify_image as pn_identify, PlantNetError
    from app.integrations.inaturalist import score_image as inat_score
    from app.services.identification import (
        LOW_CONFIDENCE_THRESHOLD,
        _INAT_SEMAPHORE,   # shared singleton — same object as the identification service
        INAT_DELAY_S,      # 1 s gap; keeps scan + re-id calls in the same queue
    )
    from app.models.species import SpeciesCandidate
    # Imported once at the top of the function so the name is bound before its
    # first use. (Regression fix: a later in-body `import ... as _gs` made `_gs`
    # a function-local, so the earlier use at the min-confidence check raised
    # UnboundLocalError and failed identification for every photo.)
    from app.services.settings_service import get_setting as _gs

    api_key    = settings.plantnet_api_key
    inat_token = settings.inaturalist_api_token

    use_pn   = source in ("plantnet", "both") and bool(api_key)
    use_inat = source in ("inaturalist", "both") and bool(inat_token)

    # ── Pause check — exit cleanly without processing ────────────────────
    _entry = _p2_obs_session.get(obs_id)
    if _entry is not None:
        _sess_id = _entry[0] if isinstance(_entry, tuple) else _entry
        if _sess_id in _p2_paused_sessions:
            # Mark obs as failed_identification so the next rescan classifies
            # it as retryable rather than already-done.
            try:
                async with AsyncSessionLocal() as _pdb:
                    _pobs = await _pdb.get(Observation, obs_id)
                    if _pobs and _pobs.identification_status == "pending_identification":
                        _pobs.identification_status = "failed_identification"
                        await _pdb.commit()
            except Exception:
                log.exception("pause: failed to mark obs %s as failed", obs_id)
            _p2_obs_session.pop(obs_id, None)
            return

    # ── Category-aware routing ───────────────────────────────────────────
    async with AsyncSessionLocal() as _kchk:
        _obs_kchk = await _kchk.get(Observation, obs_id)
        if _obs_kchk:
            _cat = (_obs_kchk.obs_category or "plant").lower()

            # Landscape: no identification pipeline at all
            if _cat == "landscape":
                _scan_status[obs_id] = "done"
                await _p2_tick(obs_id, files_processed=1, files_review=1)
                return

            # Fungi category: skip PlantNet, use iNaturalist only.
            # This overrides the api_source_* pipeline setting unconditionally —
            # PlantNet has no fungi coverage, so fungi must never go to PlantNet.
            if _cat == "fungi":
                use_pn = False
                if bool(inat_token):
                    use_inat = True

            # Legacy kingdom-based fungi routing (obs_category still 'plant'
            # but species was previously identified as fungi)
            elif _obs_kchk.species_primary:
                from app.models.species import Species as _Sp
                from sqlalchemy import select as _sel
                _sp_kchk = await _kchk.scalar(
                    _sel(_Sp).where(_Sp.name_key == normalize_taxon_key(_obs_kchk.species_primary))
                )
                if _sp_kchk and (_sp_kchk.kingdom or "").lower() == "fungi":
                    use_pn = False
                    if bool(inat_token):
                        use_inat = True

    cred_warnings = []
    if source in ("plantnet", "both") and not api_key and use_pn:
        cred_warnings.append("PLANTNET_API_KEY not set")
    if source in ("inaturalist", "both") and not inat_token:
        cred_warnings.append("INATURALIST_API_TOKEN not set")

    if not use_pn and not use_inat:
        _scan_status[obs_id] = "failed"
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if obs:
                obs.identification_status = "failed_identification"
                obs.review_status = "needs_review"
                obs.review_label  = "failed_id"
                session.add(ProcessingLog(
                    observation_id=obs_id, stage="identify", status="failed",
                    message="; ".join(cred_warnings) or "No identification source available",
                ))
                await session.commit()
        await _p2_tick(obs_id, files_processed=1, files_failed=1)
        return

    try:
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if not obs:
                return

            # Reload upload_source to know if we must force_review.
            # "file_upload" and legacy "phone" are both treated as manual uploads
            # that require human review regardless of confidence.
            # "syncthing" CAN auto-approve on dual-agree ≥ auto_approve_threshold (force_review=False).
            is_phone = obs.upload_source in ("phone", "file_upload")
            # Fungi observations always need human review (safety-critical)
            is_fungi = (obs.obs_category or "plant") == "fungi"
            force_review = force_review or is_phone or is_fungi

            path = Path(obs.file_path)
            if not path.exists():
                obs.identification_status = "failed_identification"
                # Every rejected observation has its file deleted by the reject
                # flow, so this branch fires on any re-identify attempt against
                # one — never clobber a status a human has already finalized.
                if not is_terminal_review_status(obs.review_status):
                    obs.review_status = "needs_review"
                    obs.review_label  = "failed_id"
                session.add(ProcessingLog(
                    observation_id=obs_id, stage="identify", status="failed",
                    message=f"Image file not found: {path}",
                ))
                await session.commit()
                _scan_status[obs_id] = "failed"
                await _p2_tick(obs_id, files_processed=1, files_failed=1)
                return

            pn_result  = None
            pn_error   = None
            inat_hits  = []

            async def _get_pn() -> None:
                nonlocal pn_result, pn_error
                try:
                    pn_result = await pn_identify(
                        path, api_key=api_key,
                        lat=obs.latitude, lng=obs.longitude,
                    )
                except PlantNetError as exc:
                    pn_error = str(exc)

            async def _get_inat() -> None:
                nonlocal inat_hits
                async with _INAT_SEMAPHORE:
                    inat_hits = await inat_score(
                        path, api_token=inat_token,
                        lat=obs.latitude, lng=obs.longitude,
                        observed_on=(obs.photo_taken_at.date().isoformat()
                                     if obs.photo_taken_at else None),
                    )
                    await asyncio.sleep(INAT_DELAY_S)

            tasks = []
            if use_pn:   tasks.append(_get_pn())
            if use_inat: tasks.append(_get_inat())
            await asyncio.gather(*tasks)

            if pn_error:
                session.add(ProcessingLog(
                    observation_id=obs_id, stage="identify", status="failed",
                    message=f"PlantNet error: {pn_error}",
                ))

            # ── Merge candidates ──────────────────────────────────────────
            candidates = []

            if pn_result and pn_result.candidates:
                for c in pn_result.candidates:
                    candidates.append({
                        "rank": c.rank,
                        "scientific_name": c.scientific_name,
                        "common_names": c.common_names,
                        "score": round(c.score, 4),
                        "family": c.family,
                        "genus": c.genus,
                        "gbif_id": c.gbif_id,
                        "source": "plantnet",
                    })

            # ── iNat kingdom gate ─────────────────────────────────────────
            # If iNaturalist's top result is outside Plantae/Fungi at ≥5%
            # confidence, the subject is definitively non-target. Auto-reject
            # before any candidate merge — mirrors the gate in identification.py.
            _INAT_ALLOWED = {"plantae", "fungi"}
            if inat_hits:
                _top_kingdom = (inat_hits[0].iconic_taxon_name or "").lower()
                if _top_kingdom and _top_kingdom not in _INAT_ALLOWED \
                        and inat_hits[0].score >= 0.05 \
                        and obs.review_status != "manually_verified" \
                        and not obs.human_corrected:
                    obs.identification_status = "identified"
                    obs.review_status         = "rejected"
                    obs.prefilter_category    = "person_animal"
                    obs.processing_stage      = "identified"
                    _note = (
                        f"Auto-rejected: iNat kingdom={inat_hits[0].iconic_taxon_name}"
                        f" ({inat_hits[0].scientific_name} {inat_hits[0].score:.1%})"
                    )
                    obs.reviewer_notes = (
                        (obs.reviewer_notes + "\n" if obs.reviewer_notes else "") + _note
                    )
                    session.add(ProcessingLog(
                        observation_id=obs_id, stage="identify", status="success",
                        message=_note,
                    ))
                    await session.commit()
                    try:
                        delete_observation_file(obs)
                    except Exception as _del_exc:
                        log.warning("scan identify obs %d: file cleanup failed: %s", obs_id, _del_exc)
                    _scan_status[obs_id] = "done"
                    await _p2_tick(obs_id, files_processed=1, files_rejected=1)
                    return

            if inat_hits:
                pn_names = {c["scientific_name"] for c in candidates}
                for ic in inat_hits:
                    if ic.scientific_name not in pn_names:
                        candidates.append({
                            "rank": len(candidates) + 1,
                            "scientific_name": ic.scientific_name,
                            "common_names": ic.common_names,
                            "score": round(ic.score, 4),
                            "family": None,
                            "genus": None,
                            "gbif_id": None,
                            "source": "inaturalist",
                        })

            # ── Fungi auto-detection ──────────────────────────────────────
            # If the top iNaturalist result has iconic_taxon_name == 'Fungi',
            # store a category suggestion so the reviewer sees it on the card.
            if inat_hits and inat_hits[0].iconic_taxon_name == "Fungi":
                if obs.obs_category == "plant":   # only suggest, never overwrite
                    obs.category_suggested = "fungi"
                # Fungi observations always need human review regardless of confidence
                force_review = True

            obs.plantnet_raw_json = _json.dumps(
                pn_result.raw_response if pn_result else {}
            )

            # ── No candidates ─────────────────────────────────────────────
            if not candidates:
                obs.identification_status = "below_threshold"
                await set_observation_species(session, obs, None)
                obs.species_candidates_json = _json.dumps([])
                obs.processing_stage = "identified"
                # No candidates → always review queue. P1 (syncthing) must never
                # be auto-rejected on confidence; only not_plant pre-filter rejects.
                # Never clobber a status a human has already finalized — a retry-
                # identify re-run was silently un-rejecting observations otherwise.
                if not is_terminal_review_status(obs.review_status):
                    obs.review_status = "needs_review"
                    obs.review_label  = "failed_id"
                note = "No candidates from any source"
                if pn_error:
                    note += f" (PlantNet: {pn_error})"
                note += " — sent to review queue"
                log.warning(
                    "[ID no-candidates] obs#%s: no candidates returned "
                    "(PlantNet error: %s) — file seen, no species assigned",
                    obs_id, pn_error or "none",
                )
                session.add(ProcessingLog(
                    observation_id=obs_id, stage="identify", status="success",
                    message=note,
                ))
                await session.commit()
                _scan_status[obs_id] = "done"
                await _p2_tick(obs_id, files_processed=1, files_review=1)
                return

            # ── Store top result ──────────────────────────────────────────
            top = candidates[0]
            obs.species_candidates_json = _json.dumps(candidates)
            obs.identification_status   = "identified"
            obs.processing_stage        = "identified"
            # Cache top candidate confidence so the review-queue confidence sort
            # (server-side) works for syncthing-pipeline imports too. Same
            # normalisation guard as the upload path (identification.py).
            _ts = top.get("score")
            if _ts is not None:
                obs.top_score = (_ts / 100.0) if _ts > 1.0 else _ts

            # ── Minimum confidence threshold ──────────────────────────────
            # If the best result is below the minimum threshold, do NOT assign
            # a species name — store it in species_suggested for reviewer
            # reference and route straight to the review queue as unidentified.
            MIN_ID_CONF = _gs("min_identification_confidence")
            if top["score"] < MIN_ID_CONF:
                await set_observation_species(session, obs, None)
                obs.species_suggested        = top["scientific_name"]
                obs.review_status            = "needs_review"
                obs.review_label             = "low_confidence"
                obs.identification_status    = "below_threshold"  # distinct from 'identified'
                msg = (
                    f"[no-match] Best candidate {top['scientific_name']!r} "
                    f"({top['score']:.2%}) is below min threshold "
                    f"({MIN_ID_CONF:.0%}) — sent to review as unidentified"
                )
                log.warning(
                    "[ID no-match] obs#%s: %s @ %.1f%%, threshold %.0f%% "
                    "— file seen but no species assigned (review queue)",
                    obs_id, top["scientific_name"], top["score"] * 100, MIN_ID_CONF * 100,
                )
                session.add(ProcessingLog(
                    observation_id=obs_id, stage="identify", status="success",
                    message=msg,
                ))
                await session.commit()
                _scan_status[obs_id] = "done"
                await _p2_tick(obs_id, files_processed=1, files_review=1)
                return

            await set_observation_species(session, obs, top["scientific_name"])

            # ── Auto-approve logic ────────────────────────────────────────
            # Single-source auto-approve removed — see 9.6 fix.
            # Dual-API agreement required or observation goes to review queue.
            #
            # Both pipelines use the same rule:
            #   BOTH PlantNet AND iNaturalist must name the same species as
            #   their top result, EACH at or above upload_auto_approve_threshold.
            #   APIs disagree, single source, or below threshold → review queue.
            #   Fungi are never auto-approved (iNaturalist only, no second source).
            UPLOAD_AUTO_APPROVE_THRESHOLD = _gs("upload_auto_approve_threshold")

            # Extract raw top results (before merge) for agreement check
            _pn_top_name  = (pn_result.candidates[0].scientific_name
                             if pn_result and pn_result.candidates else None)
            _pn_top_score = (pn_result.candidates[0].score
                             if pn_result and pn_result.candidates else 0.0)
            _inat_top_name  = inat_hits[0].scientific_name if inat_hits else None
            _inat_top_score = inat_hits[0].score if inat_hits else 0.0

            _dual_agree = (
                use_pn
                and use_inat
                and _pn_top_name is not None
                and _inat_top_name is not None
                and _pn_top_name == _inat_top_name
                and _pn_top_score >= UPLOAD_AUTO_APPROVE_THRESHOLD
                and _inat_top_score >= UPLOAD_AUTO_APPROVE_THRESHOLD
            )

            if _dual_agree:
                # Both APIs agree at or above threshold → auto-approve, plot on map immediately
                # (unless this observation already has a finalized human decision).
                if not is_terminal_review_status(obs.review_status):
                    obs.review_status  = "approved"
                    obs.reviewer_notes = None
                flag = (
                    f"Auto-approved — both APIs agree: {top['scientific_name']} "
                    f"PN={_pn_top_score:.0%} iNat={_inat_top_score:.0%}"
                )

            else:
                # No dual-agree (includes single-source, API disagreement, below threshold,
                # force_review override, phone uploads) → always review queue.
                # Single-source auto-approve removed — see 9.6 fix.
                # Never clobber a status a human has already finalized.
                if not is_terminal_review_status(obs.review_status):
                    obs.review_status = "needs_review"

                if is_phone or force_review:
                    if is_phone:
                        # Build a concise reason for the reviewer badge
                        if _pn_top_name and _inat_top_name and _pn_top_name != _inat_top_name:
                            _reason = (f"APIs disagree: "
                                       f"PN={_pn_top_name!r} ({_pn_top_score:.0%}) vs "
                                       f"iNat={_inat_top_name!r} ({_inat_top_score:.0%})")
                            obs.review_label = "low_confidence"
                        elif top["score"] < UPLOAD_AUTO_APPROVE_THRESHOLD:
                            _reason = f"confidence below threshold ({top['score']:.0%} < {UPLOAD_AUTO_APPROVE_THRESHOLD:.0%})"
                            obs.review_label = "low_confidence"
                        elif not use_pn or not use_inat:
                            _reason = "dual API confirmation not available (check API tokens)"
                            obs.review_label = "failed_id"
                        else:
                            _reason = "one or both APIs returned no candidates"
                            obs.review_label = "failed_id"
                        flag = f"File upload — needs review ({_reason})"
                        obs.reviewer_notes = "File upload — needs review"
                    else:
                        # Pre-filter override — review but no upload badge (fungi or force)
                        flag = f"Review queue (pre-filter override) — {top['source']} {top['score']:.2%}"
                        obs.review_label = "non_plant" if is_fungi else "low_confidence"
                else:
                    # Syncthing: dual-agree check failed → review queue
                    if _pn_top_name and _inat_top_name and _pn_top_name != _inat_top_name:
                        _reason = (f"APIs disagree: PN={_pn_top_name!r} ({_pn_top_score:.0%}) "
                                   f"vs iNat={_inat_top_name!r} ({_inat_top_score:.0%})")
                        obs.review_label = "low_confidence"
                    elif not use_pn or not use_inat:
                        _reason = "dual API confirmation not available (check API tokens)"
                        obs.review_label = "failed_id"
                    else:
                        _reason = f"below threshold ({top['score']:.0%} < {UPLOAD_AUTO_APPROVE_THRESHOLD:.0%})"
                        obs.review_label = "low_confidence"
                    flag = f"Review queue — {_reason}"

            session.add(ProcessingLog(
                observation_id=obs_id, stage="identify", status="success",
                message=f"{top['scientific_name']} ({top['score']:.2%}) [{top['source']}] — {flag}",
            ))

            for c in candidates:
                session.add(SpeciesCandidate(
                    observation_id=obs_id,
                    scientific_name_raw=c["scientific_name"],
                    common_name_raw=(c["common_names"] or [None])[0],
                    confidence_score=c["score"],
                    rank=c["rank"],
                    api_source=c["source"],
                    api_response_raw=None,
                    source_url=(
                        "https://my-api.plantnet.org/v2/identify/all"
                        if c["source"] == "plantnet"
                        else "https://api.inaturalist.org/v1/computervision/score_image"
                    ),
                ))

            await session.commit()

            # ── Species card upsert ───────────────────────────────────────
            # Create/link species record so the observation is immediately
            # visible in the species list and enrichment queue.
            if top["scientific_name"]:
                await _upsert_species_card(obs_id, top, candidates)

        _scan_status[obs_id] = "done"
        # ── P2 session tracking: main path ───────────────────────────────
        if obs.review_status == "approved":
            await _p2_tick(obs_id, files_processed=1, files_approved=1)
        else:
            await _p2_tick(obs_id, files_processed=1, files_review=1)

    except Exception as exc:
        _scan_status[obs_id] = "failed"
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if obs:
                obs.identification_status = "failed_identification"
                obs.review_status = "needs_review"
                session.add(ProcessingLog(
                    observation_id=obs_id, stage="identify", status="failed",
                    message=str(exc),
                ))
                await session.commit()
        await _p2_tick(obs_id, files_processed=1, files_failed=1)


# ---------------------------------------------------------------------------
# Species card upsert — called after identification
# ---------------------------------------------------------------------------

async def _upsert_species_card(
    obs_id: int,
    top_candidate: dict,
    all_candidates: list,
) -> None:
    """
    Ensure a Species row exists for the identified species.

    - If new: create stub Species record + ProcessingLog flagging it for enrichment.
    - If existing: link silently (observation already has species_primary set).
    - Never overwrites enriched data.
    - Taxonomy (family/genus/common_names) is back-filled from PlantNet candidates.
    """
    from app.models.species import Species
    import json as _j

    scientific_name = top_candidate["scientific_name"]

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(Species).where(Species.name_key == normalize_taxon_key(scientific_name))
        )

        if existing is None:
            # Known-synonym resolution (read-only) — before creating a new
            # card, check whether this name is a registered synonym of an
            # existing species. Never writes; just changes which row "exists".
            from app.services.synonyms import resolve_synonym_species_id
            canonical_id = await resolve_synonym_species_id(session, scientific_name)
            if canonical_id is not None:
                existing = await session.get(Species, canonical_id)

        if existing:
            # Already in DB (directly or via a registered synonym) — nothing
            # to do, observation is linked via species_primary
            return

        # New species — create a stub record
        family = top_candidate.get("family")
        genus  = top_candidate.get("genus")

        # Collect common names from all candidates for this species
        common_names = []
        for c in all_candidates:
            if c["scientific_name"] == scientific_name and c.get("common_names"):
                common_names = c["common_names"]
                break

        _sci = collapse_autonym(scientific_name)
        new_species = Species(
            scientific_name=_sci,
            name_key=normalize_taxon_key(_sci),
            family=family,
            genus=genus,
            common_names=_j.dumps(common_names) if common_names else None,
            edibility_status="unknown",
        )
        session.add(new_species)
        await session.flush()

        # Log it for the enrichment queue
        session.add(ProcessingLog(
            observation_id=obs_id,
            stage="species_card_created",
            status="success",
            message=(
                f"New species card created: {scientific_name} "
                f"(family={family}, genus={genus}) — "
                "auto-enrichment queued."
            ),
        ))

        await session.commit()

    # Fire-and-forget enrichment — runs outside the session above so the
    # commit has landed before we start fetching PFAF/Wikidata.
    asyncio.create_task(_enrich_new_species_card(scientific_name))
    # Fire-and-forget ITIS name validation — separate task, no blocking.
    from app.api.itis import trigger_itis_for_new_species as _itis_trigger
    asyncio.create_task(_itis_trigger(scientific_name))


# ---------------------------------------------------------------------------
# Background enrichment for newly-created species cards
# ---------------------------------------------------------------------------

async def _enrich_new_species_card(scientific_name: str) -> None:
    """
    Auto-enrich a brand-new species card created by _upsert_species_card.

    Rules:
      - Runs as asyncio.create_task() so it doesn't block identification.
      - Short delay to avoid hammering external APIs during rapid scan batches.
      - No-ops silently if the species already has a culinary_info row.
    """
    from app.models.species import Species
    from app.models.culinary import CulinaryInfo
    from app.services.enrichment import enrich_species

    await asyncio.sleep(3)   # brief pause — let the commit settle and avoid API bursts

    # --- Taxonomy enrichment (GBIF full lineage) --------------------------
    # Pure descriptive metadata. Runs in its OWN session with its own error
    # isolation so a GBIF hiccup can never touch the culinary enrichment below.
    # Sits entirely outside identification, confidence scoring, dual-API
    # agreement, auto-approve routing, and edibility — it only fills the
    # taxonomic rank columns. Same EXACT-only write-gate + non-clobber-of-
    # human-values rule as the Step 3 backfill (app/integrations/gbif.py).
    # Guarded on gbif_match_type IS NULL so it resolves each card once.
    try:
        async with AsyncSessionLocal() as tax_session:
            sp_tax = await tax_session.scalar(
                select(Species).where(Species.name_key == normalize_taxon_key(scientific_name))
            )
            if sp_tax is not None and sp_tax.gbif_match_type is None:
                from app.integrations.gbif import enrich_species_taxonomy
                res = await enrich_species_taxonomy(sp_tax)
                await tax_session.commit()
                _flags = ("; ".join(res["flags"])) if res["flags"] else ""
                log.info(
                    "[auto-taxonomy] %r → %s%s",
                    scientific_name, res["status"],
                    (" | conflicts: " + _flags) if _flags else "",
                )
    except Exception as exc:
        log.warning("[auto-taxonomy] Failed for %r: %s", scientific_name, exc)

    async with AsyncSessionLocal() as session:
        try:
            sp = await session.scalar(
                select(Species).where(Species.name_key == normalize_taxon_key(scientific_name))
            )
            if not sp:
                return

            # Skip if already enriched by a concurrent path
            ci_exists = await session.scalar(
                select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
            )
            if ci_exists:
                return

            status = await enrich_species(session, sp, dry_run=False, re_enrich=False)
            await session.commit()
            log.info("[auto-enrich] %r → %s", scientific_name, status)
        except Exception as exc:
            log.warning("[auto-enrich] Failed for %r: %s", scientific_name, exc)


# ---------------------------------------------------------------------------
# GET /api/scan/prefilter-rejects
# ---------------------------------------------------------------------------

@router.get("/prefilter-rejects")
async def list_prefilter_rejects(limit: int = 30, source: str = ""):
    """
    Return recent prefilter-rejected observations.

    source="" (default) — all pipelines
    source="syncthing"  — Pipeline 1 only
    source="file_upload"— Pipeline 2 only
    """
    _SOURCE_MAP = {
        "syncthing":   ["syncthing"],
        "file_upload": ["file_upload", "phone"],
    }
    sources = _SOURCE_MAP.get(source, ["file_upload", "phone", "syncthing"])

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Observation)
            .where(
                Observation.identification_status == "not_plant",
                Observation.upload_source.in_(sources),
                Observation.review_status == "pending",
            )
            .order_by(Observation.id.desc())
            .limit(limit)
        )).scalars().all()

    results = []
    for obs in rows:
        thumb_url = None
        if obs.thumbnail_path:
            thumb_url = "/thumbnails/" + Path(obs.thumbnail_path).name
        results.append({
            "observation_id": obs.id,
            "prefilter_category": obs.prefilter_category,
            "prefilter_confidence": obs.plant_detect_confidence,
            "filename": Path(obs.file_path).name if obs.file_path else None,
            "thumbnail": thumb_url,
            "created_at": obs.created_at.isoformat() if obs.created_at else None,
        })
    return {"rejects": results}


# ---------------------------------------------------------------------------
# POST /api/scan/sessions  — create a new P2 scan session
# GET  /api/scan/sessions?pipeline=2&limit=10  — recent sessions
# GET  /api/scan/sessions/all?pipeline=2        — full session history
# ---------------------------------------------------------------------------

@router.post("/sessions")
async def create_scan_session(body: dict):
    """
    Create a new Pipeline 2 (file-upload) scan session before a batch upload.

    Body: {"files_received": N, "source_path": "..." | null}
    Returns: {"session_id": int | null}

    Call this once per upload batch; pass the returned session_id as
    scan_session_id in each subsequent POST /api/scan form field.
    """
    from app.services.scan_sessions import session_create
    files_received = int(body.get("files_received") or 0)
    source_path    = body.get("source_path") or None
    session_id = await session_create(
        pipeline=2,
        files_received=files_received,
        source_path=source_path,
    )
    return {"session_id": session_id}


@router.get("/sessions/all")
async def list_all_sessions(pipeline: int = 2):
    """Return every session for a pipeline, newest first."""
    from app.services.scan_sessions import sessions_list
    return {"sessions": await sessions_list(pipeline=pipeline)}


@router.get("/available-folders")
async def available_folders():
    """Year folders from DIGIERA HD (if mounted) + unique source paths from P2 sessions."""
    import os
    from app.services.scan_sessions import sessions_list

    seen: set[str] = set()

    for s in await sessions_list(pipeline=2):
        sp = (s.get("source_path") or "").strip()
        if sp:
            name = os.path.basename(sp.rstrip("/\\")) or sp
            if name:
                seen.add(name)

    digiera = "/Volumes/DIGIERA/Pictures"
    if os.path.isdir(digiera):
        try:
            for entry in os.scandir(digiera):
                if entry.is_dir() and entry.name.isdigit() and len(entry.name) == 4:
                    seen.add(entry.name)
        except OSError:
            pass

    return {"folders": sorted(seen, reverse=True)}


@router.get("/sessions")
async def list_recent_sessions(pipeline: int = 2, limit: int = 10):
    """Return the most recent sessions for a pipeline (default 10), newest first."""
    from app.services.scan_sessions import sessions_list
    return {"sessions": await sessions_list(pipeline=pipeline, limit=limit)}


@router.get("/lifetime-breakdown")
async def lifetime_breakdown(pipeline: int = 1):
    """
    Lifetime file-count breakdown for a pipeline, so the scan page can explain
    why the completed-observation tally is lower than the raw file count:
    files received split into pre-filter rejects, duplicates, failures, and
    completed-pipeline observations. Summed across recorded sessions only —
    activity before session tracking can't be broken down.
    """
    from app.services.scan_sessions import sessions_breakdown
    return await sessions_breakdown(pipeline)


@router.get("/p2-stats")
async def p2_stats():
    """Observation-level counts for the File Upload (P2) pipeline top chips."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            _sqla_text(
                "SELECT "
                "COUNT(DISTINCT file_hash) AS total_seen, "
                "SUM(CASE WHEN review_status='approved' AND identification_status='identified' THEN 1 ELSE 0 END) AS auto_approved, "
                "SUM(CASE WHEN review_status='manually_verified' THEN 1 ELSE 0 END) AS manually_approved, "
                "SUM(CASE WHEN review_status='needs_review' THEN 1 ELSE 0 END) AS in_review, "
                "SUM(CASE WHEN review_status='pending' THEN 1 ELSE 0 END) AS pending, "
                "SUM(CASE WHEN review_status='rejected' THEN 1 ELSE 0 END) AS rejected "
                "FROM observations WHERE upload_source='file_upload'"
            )
        )).fetchone()
    return {
        "total_seen":        rows[0] or 0,
        "auto_approved":     rows[1] or 0,
        "manually_approved": rows[2] or 0,
        "in_review":         rows[3] or 0,
        "pending":           rows[4] or 0,
        "rejected":          rows[5] or 0,
    }


# ---------------------------------------------------------------------------
# Phase 10.9 — Rescan + Process Delta + SSE progress
# ---------------------------------------------------------------------------

_P2_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@router.post("/rescan")
async def rescan_folder(body: dict):
    """
    Folder reconciliation — read-only, no pipeline calls.

    Body: {
        "source_path": str,           # folder name for labelling (optional)
        "session_id":  int | null,    # update existing session if supplied
        "files": [
            {"name": "IMG_001.jpg",  "sha256": "abc..."},  # image files
            {"name": "IMG_001.json", "sha256": null},       # non-images: sha256 omitted
        ]
    }

    Classifies each file:
      already_processed — SHA256 matches an observation that is not failed
      retryable         — SHA256 matches an observation with failed_identification
      new               — SHA256 not in DB (or image file with no hash supplied)
      skipped           — non-image extension

    Returns: { session_id, already_processed, new, retryable, skipped, total,
               retryable_obs: [{obs_id, sha256}] }

    retryable_obs carries the obs_ids so the frontend can call /retry-id on each.
    """
    from app.services.scan_sessions import session_create, session_set_status

    source_path = body.get("source_path") or None
    session_id  = body.get("session_id")
    files       = body.get("files") or []

    already = new = retryable = skipped = 0
    retryable_obs: list = []
    new_sha256s:   list = []

    async with AsyncSessionLocal() as db:
        for f in files:
            name = (f.get("name") or "")
            ext  = Path(name).suffix.lower()
            if ext not in _P2_IMAGE_EXTS:
                skipped += 1
                continue
            sha = f.get("sha256")
            if not sha:
                # Image file but hash wasn't sent (shouldn't happen; treat as new)
                new += 1
                new_sha256s.append(None)
                continue
            obs = await db.scalar(
                select(Observation).where(Observation.file_hash == sha)
            )
            if obs is None:
                new += 1
                new_sha256s.append(sha)
            elif obs.identification_status in ("failed_identification", "pending_identification"):
                # pending_identification = paused mid-batch; failed = previous failure
                retryable += 1
                retryable_obs.append({"obs_id": obs.id, "sha256": sha})
            else:
                already += 1

    total = already + new + retryable + skipped

    if session_id:
        # Update existing session with reconciled bucket counts + status.
        # Regenerate the label from the (possibly new) source_path and total so
        # the dropdown doesn't show a stale folder name from a previous rescan.
        from app.services.scan_sessions import _label_p2
        from datetime import datetime as _dt
        try:
            async with AsyncSessionLocal() as db:
                row = (await db.execute(
                    _sqla_text("SELECT started_at, source_path FROM scan_sessions WHERE id = :id"),
                    {"id": session_id},
                )).fetchone()
                if row:
                    started = row[0] if isinstance(row[0], _dt) else _dt.fromisoformat(str(row[0]))
                    effective_sp = source_path or row[1]
                    new_label = _label_p2(started, total, effective_sp)
                else:
                    new_label = None
                # Reset outcome counters alongside reconciliation buckets so that
                # a re-run of the same session reflects only the current pass.
                # files_processed is reset later in process-delta; the others
                # (approved/review/rejected/failed) reset here at rescan time so
                # the batch table shows zeros between rescan and process-delta.
                await db.execute(
                    _sqla_text(
                        "UPDATE scan_sessions SET "
                        "  files_new = :new, files_retryable = :ret, "
                        "  files_already_processed = :already, "
                        "  files_skipped = :skipped, "
                        "  files_received = :total, "
                        "  files_approved = 0, files_review = 0, "
                        "  files_rejected = 0, files_failed = 0, files_duplicate = 0, "
                        "  status = 'rescanned', "
                        "  source_path = COALESCE(:sp, source_path)"
                        + (", label = :label" if new_label else "") +
                        " WHERE id = :id"
                    ),
                    {
                        "new": new, "ret": retryable, "already": already,
                        "skipped": skipped, "total": total,
                        "sp": source_path, "id": session_id,
                        **({"label": new_label} if new_label else {}),
                    },
                )
                await db.commit()
        except Exception:
            log.exception("rescan: failed to update session %s", session_id)
    else:
        # Fix 1: always create a new session row when no session_id is supplied.
        # Previous behaviour looked up by source_path and reused the most recent
        # row, which caused outcome counters (files_processed, files_approved,
        # files_review, files_rejected, files_failed) to accumulate across
        # multiple runs of the same folder. Each folder selection now gets a
        # fresh row so the dropdown shows one entry per upload pass — correct.
        session_id = await session_create(
            pipeline=2,
            files_received=total,
            source_path=source_path,
        )
        if session_id:
            try:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        _sqla_text(
                            "UPDATE scan_sessions SET "
                            "  files_new = :new, files_retryable = :ret, "
                            "  files_already_processed = :already, "
                            "  files_skipped = :skipped, "
                            "  status = 'rescanned' "
                            "WHERE id = :id"
                        ),
                        {
                            "new": new, "ret": retryable,
                            "already": already, "skipped": skipped,
                            "id": session_id,
                        },
                    )
                    await db.commit()
            except Exception:
                log.exception("rescan: failed to set bucket counts on new session %s", session_id)

    return {
        "session_id":       session_id,
        "already_processed": already,
        "new":              new,
        "retryable":        retryable,
        "skipped":          skipped,
        "total":            total,
        "retryable_obs":    retryable_obs,
        "new_sha256s":      new_sha256s,
    }


@router.post("/process-delta")
async def process_delta(body: dict):
    """
    Arm a rescanned session for delta processing.

    Body: { "session_id": int }

    Validates that the session has status = 'rescanned', sets it to 'running',
    creates an in-memory SSE queue so GET /progress/{session_id} can stream
    narration, and returns the bucket counts so the frontend knows how many
    files to upload.

    The frontend then uploads only the new files via the standard POST /api/scan
    flow (which will naturally detect already-processed files as duplicates),
    and calls POST /api/scan/{obs_id}/retry-id for each retryable obs.
    """
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            _sqla_text(
                "SELECT status, files_new, files_retryable, files_received "
                "FROM scan_sessions WHERE id = :id"
            ),
            {"id": session_id},
        )).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    current_status = row[0] or "complete"
    # Accept 'rescanned' (normal flow), 'paused' (explicit pause), or stalled 'running'.
    from app.services.scan_sessions import session_set_status, session_heartbeat, session_reopen
    if current_status == "rescanned":
        pass  # normal flow
    elif current_status == "paused":
        # Intentional pause — re-arm directly, remove from paused set
        _p2_paused_sessions.discard(session_id)
        await session_reopen(session_id)
    elif current_status == "running":
        # Allow re-arm only if heartbeat is absent or stale (stalled batch)
        heartbeat_val = None
        try:
            async with AsyncSessionLocal() as _hb_db:
                hb_row = (await _hb_db.execute(
                    _sqla_text("SELECT last_heartbeat FROM scan_sessions WHERE id = :id"),
                    {"id": session_id},
                )).fetchone()
            if hb_row and hb_row[0]:
                from datetime import datetime as _dt
                hb_ts = hb_row[0] if isinstance(hb_row[0], _dt) else _dt.fromisoformat(str(hb_row[0]))
                heartbeat_val = (_dt.utcnow() - hb_ts).total_seconds()
        except Exception:
            pass
        # NULL heartbeat or >5 min stale = stalled → allow resume
        if heartbeat_val is not None and heartbeat_val <= 300:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Session {session_id} is actively running "
                    f"(heartbeat {int(heartbeat_val)}s ago). "
                    "Wait for it to finish or stall before resuming."
                ),
            )
        await session_reopen(session_id)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Session {session_id} has status '{current_status}'; "
                "only 'rescanned', 'paused', or stalled sessions can be processed."
            ),
        )

    # Fix 2: reset outcome counters so each process pass reflects only that run.
    # Reconciliation buckets (files_new, files_retryable, files_already_processed,
    # files_skipped, files_received) are reset by /rescan before this endpoint is
    # called. Outcome counters (processed/approved/review/rejected/failed) must
    # also start from zero here so re-runs — whether on a new session created by
    # Fix 1 or on a resumed/stalled session re-armed via Branch 1 — never carry
    # over counts from a previous pass.
    try:
        async with AsyncSessionLocal() as _rc_db:
            await _rc_db.execute(
                _sqla_text(
                    "UPDATE scan_sessions SET "
                    "  files_processed = 0, files_approved = 0, "
                    "  files_review = 0, files_rejected = 0, files_failed = 0, "
                    "  files_duplicate = 0 "
                    "WHERE id = :id"
                ),
                {"id": session_id},
            )
            await _rc_db.commit()
    except Exception:
        log.exception("process-delta: failed to reset outcome counters for session %s", session_id)

    files_new       = row[1] or 0
    files_retryable = row[2] or 0
    files_received  = row[3] or 0

    await session_heartbeat(session_id)

    # Arm the SSE queue — the scan endpoint will push events as files complete
    _p2_progress[session_id]       = asyncio.Queue()
    _p2_session_counter[session_id] = 0

    return {
        "session_id":       session_id,
        "status":           "running",
        "files_new":        files_new,
        "files_retryable":  files_retryable,
        "files_to_process": files_new + files_retryable,
        "files_received":   files_received,
    }


# ---------------------------------------------------------------------------
# Archive scan — server-side batch from DIGIERA volume
# ---------------------------------------------------------------------------

@router.post("/scan-archive")
async def scan_archive(body: dict, background_tasks: BackgroundTasks):
    """
    Server-side batch scan of the DIGIERA photo archive.

    Discovers immediate year subfolders under root_path, creates one P2
    scan_session per year folder, and processes them sequentially (single
    writer rule). Returns {job_id} immediately; stream progress via
    GET /api/scan/archive-progress/{job_id}.

    Body: { "root_path": "/Volumes/DIGIERA/Downloads/Pictures" }   (optional override)
    """
    import os
    import time as _time

    root     = (body.get("root_path") or _ARCHIVE_ROOT_DEFAULT).rstrip("/")
    dry_run  = bool(body.get("dry_run"))

    if not os.path.isdir(root):
        raise HTTPException(
            status_code=503,
            detail=(
                f"Archive folder not accessible: {root!r}. "
                "Connect the DIGIERA drive and try again."
            ),
        )

    try:
        year_dirs = sorted(
            [e.path for e in os.scandir(root)
             if e.is_dir() and e.name.isdigit() and len(e.name) == 4],
            key=lambda p: os.path.basename(p),   # oldest → newest
        )
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Cannot list archive folders: {exc}")

    if not year_dirs:
        raise HTTPException(status_code=404, detail="No year folders found in archive root.")

    year_names = [os.path.basename(d) for d in year_dirs]

    # dry_run=True: probe only — return folder list without starting a job
    if dry_run:
        return {"year_dirs": year_names, "total_folders": len(year_dirs)}

    job_id = int(_time.time() * 1000)
    _archive_queues[job_id] = asyncio.Queue()

    background_tasks.add_task(_run_archive_scan, job_id, year_dirs)

    return {
        "job_id":         job_id,
        "year_dirs":      year_names,
        "total_folders":  len(year_dirs),
    }


@router.get("/archive-progress/{job_id}")
async def archive_progress(job_id: int):
    """
    SSE stream for an archive scan job.

    Events:
      {type:"folder_start", folder:"2023", session_id:N, total_files:N}
      {type:"file",         folder:"2023", done:N, total:N}
      {type:"folder_done",  folder:"2023", session_id:N, new:N, already:N,
                            rejected:N, failed:N}
      {type:"done",  total_new:N, total_already:N}
      {type:"error", message:"..."}
    """
    async def _generate():
        q = _archive_queues.get(job_id)
        if q is None:
            yield f"data: {_json.dumps({'type': 'error', 'message': f'Archive job {job_id} not found'})}\n\n"
            return
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {_json.dumps(event)}\n\n"
                    if event.get("type") in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            _archive_queues.pop(job_id, None)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_archive_scan(job_id: int, year_dirs: list) -> None:
    """
    Background task: walk year_dirs sequentially, create one P2 scan_session
    per folder, copy new images to pipeline2/, create observations, identify.

    Never runs folders in parallel — single writer rule.
    """
    import os
    from app.services.pipeline_lock import pipeline_try_acquire, pipeline_release, pipeline_holder
    from app.services.scan_sessions import session_create, session_set_status, session_inc as _sinc
    from app.services.settings_service import get_setting as _gs

    q = _archive_queues.get(job_id)

    async def _push(event: dict) -> None:
        if q is not None:
            try:
                await q.put(event)
            except Exception:
                pass

    acquired = await pipeline_try_acquire("P2 (archive scan)")
    if not acquired:
        _holder = pipeline_holder()
        log.warning(
            "[P2 archive scan] SKIPPED at %s — pipeline mutex is held by %s.",
            datetime.utcnow().isoformat(), _holder,
        )
        await _push({
            "type": "error",
            "message": f"Pipeline mutex held by {_holder} — archive scan skipped. Try again when that pipeline finishes.",
        })
        return

    total_new = total_already = 0

    try:
        for year_dir in year_dirs:
            year_name = os.path.basename(year_dir)

            # List image files — flat, immediate children only
            try:
                image_files = sorted([
                    e.path for e in os.scandir(year_dir)
                    if e.is_file()
                    and Path(e.path).suffix.lower() in _P2_IMAGE_EXTS
                ])
            except OSError as exc:
                await _push({"type": "error", "folder": year_name, "message": str(exc)})
                continue

            if not image_files:
                continue

            # One session per year folder
            session_id = await session_create(
                pipeline=2,
                files_received=len(image_files),
                source_path=year_dir,
            )
            if not session_id:
                await _push({
                    "type": "error", "folder": year_name,
                    "message": "Failed to create scan session",
                })
                continue

            # Prime the per-session SSE queue so /progress/{session_id} works
            _p2_progress[session_id] = asyncio.Queue()

            await _push({
                "type":        "folder_start",
                "folder":      year_name,
                "session_id":  session_id,
                "total_files": len(image_files),
            })

            _p2_threshold = _gs("prefilter_pipeline2_green_threshold")
            _thumb_size   = _gs("thumbnail_size")
            folder_new = folder_already = folder_rejected = folder_failed = 0

            for i, fpath in enumerate(image_files):
                fname = os.path.basename(fpath)
                tmp_path: Optional[Path] = None
                try:
                    # ── Read + hash ───────────────────────────────────────
                    try:
                        with open(fpath, "rb") as fh:
                            content = fh.read()
                    except OSError as exc:
                        log.warning("archive_scan: cannot read %s: %s", fpath, exc)
                        folder_failed += 1
                        await _sinc(session_id, files_failed=1)
                        continue

                    if len(content) == 0 or len(content) > 50 * 1024 * 1024:
                        folder_failed += 1
                        await _sinc(session_id, files_failed=1)
                        continue

                    sha = hashlib.sha256(content).hexdigest()

                    # ── Duplicate check ───────────────────────────────────
                    async with AsyncSessionLocal() as _db:
                        _existing = await _db.scalar(
                            select(Observation).where(Observation.file_hash == sha)
                        )
                    if _existing:
                        folder_already += 1
                        total_already  += 1
                        await _sinc(session_id, files_processed=1, files_duplicate=1)
                        continue

                    ext = Path(fname).suffix.lower()

                    # ── Temp file for EXIF + prefilter ────────────────────
                    tmp_fd, tmp_name = tempfile.mkstemp(suffix=ext)
                    tmp_path = Path(tmp_name)
                    try:
                        with open(tmp_fd, "wb") as tf:
                            tf.write(content)
                    except Exception as exc:
                        tmp_path.unlink(missing_ok=True)
                        tmp_path = None
                        log.warning("archive_scan: temp write failed for %s: %s", fname, exc)
                        folder_failed += 1
                        await _sinc(session_id, files_failed=1)
                        continue

                    # ── EXIF + Takeout sidecar GPS ────────────────────────
                    try:
                        exif = extract_exif(tmp_path)
                    except Exception:
                        exif = type("_E", (), {
                            "taken_at": None, "latitude": None, "longitude": None,
                            "altitude_m": None, "camera_make": None, "camera_model": None,
                        })()

                    if exif.latitude is None:
                        try:
                            from app.utils.sidecar import read_takeout_gps as _read_sidecar
                            _sgps = _read_sidecar(Path(fpath))
                            if _sgps:
                                exif = type("_E", (), {
                                    "taken_at":     exif.taken_at,
                                    "latitude":     _sgps[0],
                                    "longitude":    _sgps[1],
                                    "altitude_m":   exif.altitude_m,
                                    "camera_make":  exif.camera_make,
                                    "camera_model": exif.camera_model,
                                })()
                        except Exception:
                            pass

                    # ── Prefilter ─────────────────────────────────────────
                    try:
                        is_plant, pf_conf, pf_category = classify_plant_likelihood(
                            tmp_path,
                            has_gps=(exif.latitude is not None),
                            green_threshold_override=_p2_threshold,
                        )
                    except Exception:
                        is_plant, pf_conf, pf_category = True, 1.0, "plant"

                    unique_stem = f"{uuid.uuid4().hex}_{Path(fname).stem}"

                    if not is_plant:
                        # ── Prefilter rejected ────────────────────────────
                        dest_path = settings.pipeline2_dir / f"rejected_{unique_stem}{ext}"
                        try:
                            shutil.move(str(tmp_path), str(dest_path))
                            tmp_path = None
                        except Exception:
                            dest_path = None

                        try:
                            thumb = generate_thumbnail(
                                dest_path,
                                thumbnails_dir=Path(settings.thumbnails_dir),
                                size=_thumb_size,
                            ) if dest_path else None
                        except Exception:
                            thumb = None

                        async with AsyncSessionLocal() as _db:
                            _rej = Observation(
                                file_path=str(dest_path) if dest_path else "",
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
                                review_status="pending",
                                processing_stage="prefilter_rejected",
                                identification_status="not_plant",
                                upload_source="file_upload",
                                is_plant_likely=False,
                                plant_detect_confidence=pf_conf,
                                prefilter_category=pf_category,
                            )
                            _db.add(_rej)
                            await _db.commit()

                        folder_rejected += 1
                        await _sinc(session_id, files_processed=1, files_rejected=1)

                    else:
                        # ── Passed prefilter — copy to pipeline2/ ─────────
                        dest_path = settings.pipeline2_dir / f"{unique_stem}{ext}"
                        try:
                            shutil.move(str(tmp_path), str(dest_path))
                            tmp_path = None
                        except Exception as exc:
                            log.warning("archive_scan: move failed for %s: %s", fname, exc)
                            folder_failed += 1
                            await _sinc(session_id, files_failed=1)
                            continue

                        try:
                            thumb = generate_thumbnail(
                                dest_path,
                                thumbnails_dir=Path(settings.thumbnails_dir),
                                size=_thumb_size,
                            )
                        except Exception:
                            thumb = None

                        async with AsyncSessionLocal() as _db:
                            _obs = Observation(
                                file_path=str(dest_path),
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
                                review_status="pending",
                                processing_stage="ingested",
                                identification_status="pending_identification",
                                upload_source="file_upload",
                                is_plant_likely=True,
                                plant_detect_confidence=pf_conf,
                                prefilter_category=pf_category,
                            )
                            _db.add(_obs)
                            await _db.flush()
                            _db.add(ProcessingLog(
                                observation_id=_obs.id,
                                stage="scan_prefilter",
                                status="success",
                                message=(
                                    f"Archive ingest ({year_name}): prefilter passed "
                                    f"category={pf_category} conf={pf_conf:.3f}"
                                ),
                            ))
                            await _db.commit()
                            _obs_id = _obs.id

                        # Register for P2 session progress callbacks
                        _p2_obs_session[_obs_id] = (session_id, fname)

                        # Identify — awaited directly (sequential; no BackgroundTasks)
                        await _identify_scanned(_obs_id, "both")

                        folder_new += 1
                        total_new  += 1

                except Exception as exc:
                    log.exception(
                        "archive_scan: unexpected error on %s in %s: %s",
                        fname, year_name, exc,
                    )
                    folder_failed += 1
                    try:
                        await _sinc(session_id, files_failed=1)
                    except Exception:
                        pass
                finally:
                    if tmp_path is not None:
                        tmp_path.unlink(missing_ok=True)

                # Archive-level progress tick every 10 files + on last file
                if (i + 1) % 10 == 0 or (i + 1) == len(image_files):
                    await _push({
                        "type":   "file",
                        "folder": year_name,
                        "done":   i + 1,
                        "total":  len(image_files),
                    })

            # Close this year's session
            await session_set_status(session_id, "complete")

            await _push({
                "type":       "folder_done",
                "folder":     year_name,
                "session_id": session_id,
                "new":        folder_new,
                "already":    folder_already,
                "rejected":   folder_rejected,
                "failed":     folder_failed,
            })

        await _push({"type": "done", "total_new": total_new, "total_already": total_already})

    except Exception as exc:
        log.exception("archive_scan job %s failed: %s", job_id, exc)
        try:
            await _push({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        pipeline_release()


@router.get("/progress/{session_id}")
async def scan_progress(session_id: int):
    """
    SSE stream of live narration events for a running P2 session.

    Each event: data: {"current":N,"total":N,"filename":"...","status":"approved"}
    Terminal:   data: {"done":true,"status":"complete"|"failed"}

    If the session is already complete/failed when the client connects, a single
    terminal event is sent and the stream closes immediately (no stale stream).
    Reconnecting clients read durable DB state first, then subscribe here.
    """
    async def _generate():
        # Check current session state before opening a long-lived stream
        try:
            async with AsyncSessionLocal() as db:
                row = (await db.execute(
                    _sqla_text(
                        "SELECT status, files_processed, files_received "
                        "FROM scan_sessions WHERE id = :id"
                    ),
                    {"id": session_id},
                )).fetchone()
        except Exception:
            row = None

        if not row:
            yield f"data: {_json.dumps({'error': 'session not found'})}\n\n"
            return

        db_status = row[0] or "complete"
        if db_status in ("complete", "failed"):
            yield f"data: {_json.dumps({'done': True, 'status': db_status, 'current': row[1], 'total': row[2]})}\n\n"
            return

        # Get or lazily create the queue (handles reconnects after process-delta)
        if session_id not in _p2_progress:
            _p2_progress[session_id] = asyncio.Queue()

        q = _p2_progress[session_id]

        # Stream until done or 5-minute idle (stalled detection ceiling)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {_json.dumps(event)}\n\n"
                    if event.get("done"):
                        break
                except asyncio.TimeoutError:
                    # 30-second keep-alive ping so proxies don't close the connection
                    yield ": ping\n\n"
                    # Re-check DB — if session died without pushing 'done', close cleanly
                    try:
                        async with AsyncSessionLocal() as db:
                            chk = (await db.execute(
                                _sqla_text("SELECT status FROM scan_sessions WHERE id = :id"),
                                {"id": session_id},
                            )).fetchone()
                        if chk and chk[0] in ("complete", "failed", "stalled"):
                            yield f"data: {_json.dumps({'done': True, 'status': chk[0]})}\n\n"
                            break
                    except Exception:
                        pass
        finally:
            # Clean up queue reference on disconnect — don't block future reconnects
            pass

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/retryable-obs")
async def get_session_retryable_obs(session_id: int):
    """
    Return observations in this session that are retryable after a page reload or
    server restart.  Includes failed_identification (paused mid-run) and
    pending_identification (upload never started) so _jqResumeJob can pass them
    to _runProcessPass without needing the original File handles.
    """
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            _sqla_text(
                "SELECT id FROM observations "
                "WHERE scan_session_id = :sid "
                "  AND identification_status IN ('failed_identification','pending_identification')"
            ),
            {"sid": session_id},
        )).fetchall()
    return {"retryable_obs": [{"obs_id": r[0]} for r in rows]}


@router.post("/{obs_id}/retry-id")
async def retry_identification(obs_id: int, background_tasks: BackgroundTasks, body: dict = None):
    """
    Re-run identification on an observation whose identification_status is
    'failed_identification'. Used by the process-delta flow for retryable files.

    Accepts optional body: { "session_id": int, "source": "both"|"plantnet"|"inaturalist" }
    Does NOT change auto-approve or review gating — same rules as initial scan.
    """
    body = body or {}
    session_id = body.get("session_id")
    source     = body.get("source", "both")

    async with AsyncSessionLocal() as db:
        obs = await db.get(Observation, obs_id)
        if not obs:
            raise HTTPException(status_code=404, detail=f"Observation {obs_id} not found")
        if obs.identification_status not in ("failed_identification", "pending_identification"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Observation {obs_id} has status '{obs.identification_status}'; "
                    "only failed/pending observations can be retried here."
                ),
            )
        filename = Path(obs.file_path).name if obs.file_path else f"obs-{obs_id}"

    _scan_status[obs_id] = "processing"
    background_tasks.add_task(_identify_scanned, obs_id, source)

    if session_id:
        _p2_obs_session[obs_id] = (session_id, filename)

    return {"obs_id": obs_id, "queued": True, "source": source}


@router.post("/pause/{session_id}")
async def pause_session(session_id: int):
    """
    Pause a running P2 batch.

    Sets status='paused' on the session row and adds the session to the
    in-memory _p2_paused_sessions set. Each in-flight _identify_scanned
    background task checks this set before processing its file: if paused,
    it marks the observation as failed_identification (so the next rescan
    classifies it as retryable) and exits without calling _p2_tick.

    The SSE stream receives a 'paused' terminal event so the frontend can
    close the stream cleanly.
    """
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            _sqla_text("SELECT pipeline, status FROM scan_sessions WHERE id = :id"),
            {"id": session_id},
        )).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if row[0] != 2:
        raise HTTPException(status_code=400, detail="Only Pipeline 2 sessions can be paused.")

    if row[1] != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Session {session_id} has status '{row[1]}'; only running sessions can be paused.",
        )

    from app.services.scan_sessions import session_set_status
    await session_set_status(session_id, "paused")
    _p2_paused_sessions.add(session_id)

    # Signal any connected SSE stream that the session is paused
    q = _p2_progress.pop(session_id, None)
    _p2_session_counter.pop(session_id, None)
    if q is not None:
        await q.put({"done": True, "status": "paused"})

    return {"paused": True, "session_id": session_id}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int):
    """
    Delete an abandoned / unwanted scan session row.

    Safety: scan_sessions has no foreign key from observations — deleting a
    session row never touches any observation data. Only P2 sessions may be
    deleted; P1 sessions are read-only history. Running sessions are rejected
    (use Resume to finish them first).
    """
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            _sqla_text(
                "SELECT pipeline, status FROM scan_sessions WHERE id = :id"
            ),
            {"id": session_id},
        )).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    pipeline, status = row[0], row[1] or "complete"

    if pipeline == 1:
        raise HTTPException(
            status_code=400,
            detail="Pipeline 1 sessions cannot be deleted — they are read-only history.",
        )

    if status == "running":
        # Check if it's genuinely active (fresh heartbeat)
        try:
            async with AsyncSessionLocal() as _hb_db:
                hb_row = (await _hb_db.execute(
                    _sqla_text("SELECT last_heartbeat FROM scan_sessions WHERE id = :id"),
                    {"id": session_id},
                )).fetchone()
            if hb_row and hb_row[0]:
                from datetime import datetime as _dt
                hb_ts = hb_row[0] if isinstance(hb_row[0], _dt) else _dt.fromisoformat(str(hb_row[0]))
                age = (_dt.utcnow() - hb_ts).total_seconds()
                if age <= 300:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Session {session_id} is actively running "
                            f"(heartbeat {int(age)}s ago). "
                            "Wait for it to finish or stall before deleting."
                        ),
                    )
        except HTTPException:
            raise
        except Exception:
            pass

    async with AsyncSessionLocal() as db:
        await db.execute(
            _sqla_text("DELETE FROM scan_sessions WHERE id = :id"),
            {"id": session_id},
        )
        await db.commit()

    return {"deleted": session_id}
