"""
Ingestion trigger endpoint — kick off a scan from the API.
For large libraries use the CLI script instead.

Photo storage policy:
  Photos are read in place from their source folder (default ~/Documents/Pictures).
  No photos are copied into the app directory during ingestion.
  Only confirmed/approved photos are exported to photos/confirmed_plants/.
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.ingestion import scan_folder
from app.utils.caffeinate import keep_awake

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

_scan_status: dict = {"running": False, "last_result": None}


class ScanRequest(BaseModel):
    # If omitted or empty, falls back to settings.photo_library_path
    folder: Optional[str] = None
    skip_existing: bool = True


async def _run_scan(folder: Path):
    _scan_status["running"] = True

    # ── Durable process row (Pass C — additive, display-only) ─────────────
    # POST /api/ingest/scan validates the folder and rejects a concurrent run
    # (409) before scheduling this task, so reaching here means real work.
    # scan_folder already takes a sync progress_callback — that existing hook
    # is reused; no new loop, no change to the scan itself.
    import asyncio as _asyncio
    from app.services.background_processes import bp_start, bp_progress, bp_finish
    _fs_pid = await bp_start("folder_scan", progress_total=0,
                             detail=f"Folder scan: {folder}")
    _fs_seen = {"current": 0, "total": 0}
    _fs_ok = False

    def _fs_cb(current: int, total: int) -> None:
        _fs_seen["current"] = current
        _fs_seen["total"]   = total
        # One durable write per 10 files; libraries here run to 5-6 figures.
        if current % 10 == 0 or current == total:
            _asyncio.create_task(bp_progress(
                _fs_pid, current, total,
                detail=f"Folder scan: {current} of {total}",
            ))

    try:
        from app.services.settings_service import get_setting
        with keep_awake("ForagingID folder scan in progress"):
            async with AsyncSessionLocal() as session:
                result = await scan_folder(
                    session,
                    folder,
                    thumbnails_dir=settings.thumbnails_dir,
                    # Read from settings service so UI changes take effect without restart
                    thumbnail_size=get_setting("thumbnail_size"),
                    batch_size=get_setting("batch_size"),
                    progress_callback=_fs_cb,
                )
        _scan_status["last_result"] = result
        _fs_ok = True
    except Exception as exc:
        _scan_status["last_result"] = {"error": str(exc)}
    finally:
        _scan_status["running"] = False
        await bp_finish(
            _fs_pid,
            "complete" if _fs_ok else "failed",
            error="" if _fs_ok else str(_scan_status.get("last_result") or "Folder scan failed"),
            current=_fs_seen["current"],
            total=_fs_seen["total"],
        )


@router.get("/default-folder")
async def get_default_folder():
    """Return the configured default photo source path."""
    return {"folder": str(settings.photo_library_path)}


@router.get("/recent-folders")
async def get_recent_folders():
    """
    Return paths that have been scanned before, derived from checkpoint files.
    Checkpoint filenames encode the original folder path as a safe slug.
    """
    data_dir = Path(settings.data_dir)
    folders = []
    if data_dir.exists():
        for cp in sorted(data_dir.glob("checkpoint_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            # Decode slug back to a path: strip prefix, replace _ with /
            raw = cp.stem[len("checkpoint_"):]
            path_str = "/" + raw.replace("_", "/")
            folders.append({"path": path_str, "checkpoint": cp.name})
    return {"folders": folders[:10]}


@router.post("/scan")
async def trigger_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    # Use provided folder, or fall back to the configured default
    raw = req.folder.strip() if req.folder and req.folder.strip() else None
    folder = Path(raw).expanduser() if raw else Path(settings.photo_library_path)

    if not folder.exists() or not folder.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Folder not found: {folder}. Set PHOTO_LIBRARY_PATH in .env to override the default."
        )
    if _scan_status["running"]:
        raise HTTPException(status_code=409, detail="Scan already running")
    background_tasks.add_task(_run_scan, folder)
    return {"status": "started", "folder": str(folder)}


@router.get("/status")
async def scan_status():
    return _scan_status


@router.get("/pipeline-stats")
async def pipeline_stats():
    """
    Single-call stats for both pipeline status bars on the scan page.
    Combines observation counts, prefilter results, phone upload counts,
    and last scan info without requiring multiple round-trips.
    """
    from sqlalchemy import func, text
    from sqlalchemy.sql import case
    from datetime import date

    async with AsyncSessionLocal() as db:
        from app.models.observation import Observation, PHONE_ORIGIN_SOURCE
        from sqlalchemy import select

        stmt = select(
            func.count(Observation.id).label("total"),
            # Prefilter state
            func.sum(case((Observation.is_plant_likely == True, 1), else_=0)).label("prefilter_passed"),
            func.sum(case((Observation.is_plant_likely == False, 1), else_=0)).label("prefilter_rejected"),
            func.sum(case((Observation.is_plant_likely == None, 1), else_=0)).label("not_filtered"),
            # Identification state
            func.sum(case((Observation.identification_status == "pending_identification", 1), else_=0)).label("pending_id"),
            func.sum(case((Observation.identification_status == "failed_identification", 1), else_=0)).label("failed_id"),
            func.sum(case((Observation.identification_status == "identified", 1), else_=0)).label("identified"),
            # Review state
            func.sum(case((Observation.review_status.in_(["approved", "manually_verified"]), 1), else_=0)).label("confirmed"),
            func.sum(case((Observation.review_status == "needs_review", 1), else_=0)).label("needs_review"),
            func.sum(case((Observation.review_status == "rejected", 1), else_=0)).label("rejected"),
            # Syncthing pipeline
            func.sum(case((Observation.upload_source == PHONE_ORIGIN_SOURCE, 1), else_=0)).label("syncthing_total"),
            func.sum(case(((Observation.upload_source == PHONE_ORIGIN_SOURCE) & (Observation.identification_status == "pending_identification"), 1), else_=0)).label("syncthing_pending_id"),
            func.sum(case(((Observation.upload_source == PHONE_ORIGIN_SOURCE) & (Observation.identification_status == "identified"), 1), else_=0)).label("syncthing_identified"),
            func.sum(case(((Observation.upload_source == PHONE_ORIGIN_SOURCE) & (Observation.review_status.in_(["approved", "manually_verified"])), 1), else_=0)).label("syncthing_approved"),
            func.sum(case(((Observation.upload_source == PHONE_ORIGIN_SOURCE) & (Observation.review_status == "needs_review"), 1), else_=0)).label("syncthing_needs_review"),
            # File upload pipeline (file_upload + legacy phone)
            func.sum(case((Observation.upload_source.in_(["file_upload", "phone"]), 1), else_=0)).label("upload_total"),
            func.sum(case(((Observation.upload_source.in_(["file_upload", "phone"])) & (Observation.identification_status == "pending_identification"), 1), else_=0)).label("upload_pending_id"),
            func.sum(case(((Observation.upload_source.in_(["file_upload", "phone"])) & (Observation.identification_status == "identified"), 1), else_=0)).label("upload_identified"),
            func.sum(case(((Observation.upload_source.in_(["file_upload", "phone"])) & (Observation.review_status == "needs_review"), 1), else_=0)).label("upload_needs_review"),
        )
        row = (await db.execute(stmt)).one()

        # Uploads today (created_at date = today)
        today_str = date.today().isoformat()
        upload_today_row = await db.execute(
            text("SELECT COUNT(*) FROM observations WHERE upload_source IN ('file_upload','phone') AND DATE(created_at) = :today"),
            {"today": today_str},
        )
        upload_today = upload_today_row.scalar() or 0

        syncthing_today_row = await db.execute(
            text("SELECT COUNT(*) FROM observations WHERE upload_source='syncthing' AND DATE(created_at) = :today"),
            {"today": today_str},
        )
        syncthing_today = syncthing_today_row.scalar() or 0

    return {
        # Overall counts (all pipelines)
        "total": row.total or 0,
        "prefilter_passed": row.prefilter_passed or 0,
        "prefilter_rejected": row.prefilter_rejected or 0,
        "not_filtered": row.not_filtered or 0,
        "pending_id": row.pending_id or 0,
        "failed_id": row.failed_id or 0,
        "identified": row.identified or 0,
        "confirmed": row.confirmed or 0,
        "needs_review": row.needs_review or 0,
        "rejected": row.rejected or 0,
        # Pipeline 1 — Syncthing auto-import
        "syncthing_total": row.syncthing_total or 0,
        "syncthing_today": syncthing_today,
        "syncthing_pending_id": row.syncthing_pending_id or 0,
        "syncthing_identified": row.syncthing_identified or 0,
        "syncthing_approved": row.syncthing_approved or 0,
        "syncthing_needs_review": row.syncthing_needs_review or 0,
        # Pipeline 2 — File upload (file_upload + legacy phone)
        "upload_total": row.upload_total or 0,
        "upload_today": upload_today,
        "upload_pending_id": row.upload_pending_id or 0,
        "upload_identified": row.upload_identified or 0,
        "upload_needs_review": row.upload_needs_review or 0,
        # Legacy aliases (phone_*) for any old clients
        "phone_total": row.upload_total or 0,
        "phone_today": upload_today,
        "phone_pending_id": row.upload_pending_id or 0,
        "phone_identified": row.upload_identified or 0,
        "phone_needs_review": row.upload_needs_review or 0,
        # Scan state (bulk folder scan — legacy)
        "scan_running": _scan_status["running"],
        "last_scan_result": _scan_status["last_result"],
        "folder": str(settings.photo_library_path),
    }


@router.get("/db-summary")
async def db_summary():
    """
    Full database summary grouped by category (Plant / Fungi / Unknown / All).
    Columns: total, with_gps, without_gps, confirmed, needs_review, no_match,
             enriched, partial, not_enriched, edibility_categorised, unknown_edibility,
             pipeline_1, pipeline_2.
    Used by the Scan page database overview table.
    """
    from sqlalchemy import select, func, case, or_
    from app.models.observation import Observation
    from app.models.species import Species
    from app.models.culinary import CulinaryInfo

    async with AsyncSessionLocal() as db:
        # Fetch observations joined with species + culinary_info.
        # IMPORTANT: rejected records are excluded from the overview entirely so
        # they never appear in any column or in the Total. Two rejection paths:
        #   1. Manual rejection      -> review_status == 'rejected'
        #   2. Prefilter rejection   -> prefilter_category in (no_plant_signal,
        #                               person_animal)  [non-plant images]
        # NULL prefilter_category is kept (legitimate, un-prefiltered records).
        rows = (await db.execute(
            select(
                Observation.id,
                Observation.latitude,
                Observation.review_status,
                Observation.identification_status,
                Observation.prefilter_category,
                Observation.upload_source,
                Observation.species_primary,
                Species.kingdom,
                CulinaryInfo.data_confidence,
                Species.edibility_status,
            )
            .outerjoin(Species, Species.id == Observation.species_id)
            .outerjoin(CulinaryInfo, CulinaryInfo.species_id == Species.id)
            .where(Observation.review_status != "rejected")
            .where(or_(
                Observation.prefilter_category.is_(None),
                Observation.prefilter_category.not_in(["no_plant_signal", "person_animal"]),
            ))
        )).all()

        # Count of records excluded from the overview (rejected manually or by
        # the prefilter) — surfaced as a transparency note, never as table data.
        total_all = (await db.execute(
            select(func.count()).select_from(Observation)
        )).scalar() or 0
        excluded = total_all - len(rows)

    def _cat(row) -> str:
        """Classify a row into plant / fungi / unknown."""
        if row.kingdom == "Fungi":
            return "fungi"
        if row.prefilter_category == "plant" or row.kingdom == "Plantae":
            return "plant"
        return "unknown"

    def _agg(subset) -> dict:
        total = len(subset)
        with_gps = sum(1 for r in subset if r.latitude is not None)
        confirmed_statuses = {"approved", "manually_verified"}
        confirmed = sum(1 for r in subset if r.review_status in confirmed_statuses)
        needs_rev = sum(1 for r in subset if r.review_status == "needs_review")
        pending = sum(1 for r in subset if r.review_status == "pending")
        no_match = sum(1 for r in subset if r.identification_status == "failed_identification")
        # Enrichment status is only meaningful for observations whose species is
        # actually in enrichment scope — i.e. confirmed (approved / manually_verified)
        # observations. Rejected and still-pending observations are never enriched,
        # so counting them as "not enriched" inflated the backlog into the thousands
        # and made it look like enrichment had stopped early. We restrict all three
        # enrichment tallies to confirmed observations.
        enr_subset = [r for r in subset if r.review_status in confirmed_statuses]
        enriched = sum(1 for r in enr_subset if r.data_confidence is not None and r.data_confidence >= 1.0)
        partial = sum(1 for r in enr_subset if r.data_confidence is not None and 0.0 < r.data_confidence < 1.0)
        not_enr = sum(1 for r in enr_subset if r.data_confidence is None or r.data_confidence == 0.0)
        edib_ok = sum(1 for r in subset if r.edibility_status and r.edibility_status not in ("unknown", "unclear"))
        edib_unk = sum(1 for r in subset if not r.edibility_status or r.edibility_status in ("unknown", "unclear"))
        p1 = sum(1 for r in subset if r.upload_source == PHONE_ORIGIN_SOURCE)
        p2 = sum(1 for r in subset if r.upload_source in ("file_upload", "phone"))
        return {
            "total": total,
            "with_gps": with_gps,
            "without_gps": total - with_gps,
            "confirmed": confirmed,
            "needs_review": needs_rev,
            "pending": pending,
            "no_match": no_match,
            "enriched": enriched,
            "partial": partial,
            "not_enriched": not_enr,
            "edibility_categorised": edib_ok,
            "unknown_edibility": edib_unk,
            "pipeline_1": p1,
            "pipeline_2": p2,
        }

    plants  = [r for r in rows if _cat(r) == "plant"]
    fungi   = [r for r in rows if _cat(r) == "fungi"]
    unknown = [r for r in rows if _cat(r) == "unknown"]

    return {
        "categories": [
            {"category": "All",     **_agg(rows)},
            {"category": "Plant",   **_agg(plants)},
            {"category": "Fungi",   **_agg(fungi)},
            {"category": "Unknown", **_agg(unknown)},
        ],
        "excluded": excluded,
    }


class SendToReviewRequest(BaseModel):
    category: str  # "all" | "plant" | "fungi" | "unknown"


@router.post("/send-to-review")
async def send_to_review(req: SendToReviewRequest):
    """
    Bulk-move observations in a category from 'identified'/'pending' state into
    'needs_review' so they appear in the review queue.

    Only changes observations that are NOT already in a terminal state
    (approved, manually_verified, rejected, needs_review).
    Returns: {"queued": N, "category": category}
    """
    from sqlalchemy import select, update as sqla_update
    from app.models.observation import Observation
    from app.models.species import Species

    async with AsyncSessionLocal() as db:
        # Load obs that are reviewable (identified but not yet in a terminal state)
        eligible = (await db.execute(
            select(
                Observation.id,
                Observation.prefilter_category,
                Observation.species_primary,
                Observation.review_status,
                Species.kingdom,
            )
            .outerjoin(Species, Species.id == Observation.species_id)
            .where(Observation.review_status.not_in(
                ["approved", "manually_verified", "rejected", "needs_review"]
            ))
        )).all()

        def _cat(row) -> str:
            if row.kingdom == "Fungi":
                return "fungi"
            if row.prefilter_category == "plant" or row.kingdom == "Plantae":
                return "plant"
            return "unknown"

        cat = req.category.lower()
        if cat == "all":
            to_update = [r.id for r in eligible]
        else:
            to_update = [r.id for r in eligible if _cat(r) == cat]

        if to_update:
            await db.execute(
                sqla_update(Observation)
                .where(Observation.id.in_(to_update))
                .values(review_status="needs_review")
            )
            await db.commit()

    return {"queued": len(to_update), "category": req.category}


@router.get("/open-folder-picker")
async def open_folder_picker():
    """
    Open a native macOS Finder folder-chooser dialog.
    Returns {"folder": "/path/to/chosen"} or {"folder": ""} if cancelled.
    Requires the server to be running in a GUI session (not over SSH).
    Falls back gracefully with a 503 if tkinter/display is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        folder = filedialog.askdirectory(title="Choose a photo folder to scan")
        root.destroy()
        return {"folder": folder or ""}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Folder picker unavailable ({exc}). "
                "Enter the path manually instead."
            ),
        )
