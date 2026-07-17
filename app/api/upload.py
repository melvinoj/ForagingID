"""
Browser upload endpoint — accepts a single image, creates an observation,
runs the pre-filter and PlantNet identification pipeline.

Upload flow:
  1. Validate file type (jpg/jpeg/png/webp only)
  2. Save to uploads/{uuid}_{original_name}  (unique name, no overwrite)
  3. Extract EXIF, generate thumbnail
  4. Create Observation record — review_status='pending'
  5. Run pre-filter synchronously (~1ms)
  6. Trigger PlantNet identification in background
  7. Return {observation_id, prefilter, status}  immediately

Identification result:
  - Returns to review_status='needs_review' or 'rejected' — never 'approved'.
  - The observation enters the Review Queue; a human must approve before it
    can become a confirmed sighting on the map or species page.
  - Uploads NEVER directly modify canonical species data.
"""

import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.observation import Observation
from app.models.processing import ProcessingLog
from app.services.file_cleanup import delete_observation_file
from app.services.ingest_guard import blacklisted_skip
from app.services.prefilter import classify_plant_likelihood
from app.services.identification import identify_observation
from app.utils.exif import extract_exif, ExifData
from app.utils.hashing import file_sha256
from app.utils.thumbnail import generate_thumbnail

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Allowed MIME types and extensions for browser uploads
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}

# Background identification task status (in-memory; lost on restart but DB is source of truth)
_upload_status: dict = {}   # {obs_id: "processing" | "done" | "failed"}


# ---------------------------------------------------------------------------
# POST /api/upload
# ---------------------------------------------------------------------------

@router.post("")
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Accept a browser image upload, ingest it, and queue it for identification.

    Returns immediately with {observation_id, prefilter_result} so the client
    can start polling /api/upload/{id}/status while identification runs.
    """
    settings.ensure_dirs()

    # ── Validate file type ────────────────────────────────────────────────
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: jpg, jpeg, png, webp."
        )
    if file.content_type and file.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported MIME type '{file.content_type}'."
        )

    # ── Save file ─────────────────────────────────────────────────────────
    unique_stem = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').stem}"
    save_path = Path(settings.uploads_dir) / f"{unique_stem}{ext}"

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
        if len(content) > 50 * 1024 * 1024:  # 50 MB cap
            raise HTTPException(status_code=413, detail="File too large (max 50 MB).")
        save_path.write_bytes(content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    # ── Extract EXIF ──────────────────────────────────────────────────────
    try:
        exif = extract_exif(save_path)
    except Exception:
        exif = ExifData()   # extract_exif never raises, but guard returns safe defaults

    # ── Generate thumbnail ────────────────────────────────────────────────
    try:
        thumb = generate_thumbnail(
            save_path,
            thumbnails_dir=Path(settings.thumbnails_dir),
            size=settings.thumbnail_size,
        )
    except Exception:
        thumb = None

    # ── Hash ──────────────────────────────────────────────────────────────
    try:
        sha = file_sha256(save_path)
    except Exception:
        sha = None

    # ── Create Observation record ─────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        # Deleted-hash gate — a permanently deleted photo must never re-enter by
        # any path. Must precede the duplicate check: DELETE removes the
        # observations row, so the duplicate check cannot catch it.
        if await blacklisted_skip(session, sha, "p2_upload", save_path.name):
            save_path.unlink(missing_ok=True)
            return {
                "observation_id": None,
                "blacklisted": True,
                "prefilter": "blacklisted",
                "status": "skipped",
                "reason": "previously deleted by user — not re-ingested",
            }

        # Check for duplicate (same hash already ingested)
        if sha:
            existing = await session.scalar(
                select(Observation).where(Observation.file_hash == sha)
            )
            if existing:
                save_path.unlink(missing_ok=True)
                return {
                    "observation_id": existing.id,
                    "duplicate": True,
                    "prefilter": existing.prefilter_category or "unknown",
                    "status": existing.identification_status or "pending_identification",
                    "review_url": f"/review?id={existing.id}",
                }

        obs = Observation(
            file_path=str(save_path),
            file_hash=sha,
            file_size_bytes=len(content),
            file_format=ext.lstrip("."),
            thumbnail_path=str(thumb) if thumb else None,
            # EXIF fields — ExifData dataclass attribute access (not dict)
            photo_taken_at=exif.taken_at,
            latitude=exif.latitude,
            longitude=exif.longitude,
            altitude_m=exif.altitude_m,
            camera_make=exif.camera_make,
            camera_model=exif.camera_model,
            # Status
            review_status="pending",
            processing_stage="ingested",
            identification_status="pending_identification",
        )
        session.add(obs)
        await session.flush()   # get obs.id before commit

        # ── Run pre-filter synchronously (fast) ───────────────────────────
        is_plant, conf, category = classify_plant_likelihood(
            save_path,
            has_gps=(obs.latitude is not None),
        )
        obs.is_plant_likely = is_plant
        obs.plant_detect_confidence = conf
        obs.prefilter_category = category

        if not is_plant:
            obs.identification_status = "not_plant"
            obs.review_status = "rejected"

        session.add(ProcessingLog(
            observation_id=obs.id,
            stage="upload_prefilter",
            status="success",
            message=f"plant_likely={is_plant} conf={conf:.3f} category={category}",
        ))

        await session.commit()
        obs_id = obs.id

        if not is_plant:
            delete_observation_file(obs)

    # ── Queue PlantNet identification in background ───────────────────────
    if is_plant:
        _upload_status[obs_id] = "processing"
        background_tasks.add_task(_identify_uploaded, obs_id)

    return {
        "observation_id": obs_id,
        "duplicate": False,
        "prefilter": category,
        "is_plant_likely": is_plant,
        "status": "processing" if is_plant else "rejected",
        "review_url": f"/review?id={obs_id}",
    }


# ---------------------------------------------------------------------------
# GET /api/upload/{obs_id}/status
# ---------------------------------------------------------------------------

@router.get("/{obs_id}/status")
async def upload_status(obs_id: int):
    """
    Poll the identification status of an uploaded observation.
    Returns current DB state — the frontend polls this until done.
    """
    async with AsyncSessionLocal() as session:
        obs = await session.get(Observation, obs_id)
        if not obs:
            raise HTTPException(status_code=404, detail="Observation not found")

        candidates = []
        if obs.species_candidates_json:
            import json as _json
            try:
                raw = _json.loads(obs.species_candidates_json)
                candidates = raw[:5]   # top 5 only for status response
            except Exception:
                pass

        return {
            "observation_id": obs_id,
            "identification_status": obs.identification_status,
            "review_status": obs.review_status,
            "species_primary": obs.species_primary,
            "confidence": candidates[0]["score"] if candidates else None,
            "candidates": candidates,
            "is_plant_likely": obs.is_plant_likely,
            "prefilter_category": obs.prefilter_category,
            "processing": _upload_status.get(obs_id) == "processing",
            "review_url": f"/review?id={obs_id}",
            "species_url": (
                f"/species?s={obs.species_primary}"
                if obs.species_primary and obs.review_status in ("approved", "manually_verified")
                else None
            ),
        }


# ---------------------------------------------------------------------------
# Background identification helper
# ---------------------------------------------------------------------------

async def _identify_uploaded(obs_id: int) -> None:
    """Run PlantNet identification for a single uploaded observation."""
    api_key = settings.plantnet_api_key
    if not api_key:
        _upload_status[obs_id] = "failed"
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if obs:
                obs.identification_status = "failed_identification"
                obs.review_status = "needs_review"
                session.add(ProcessingLog(
                    observation_id=obs_id,
                    stage="identify",
                    status="failed",
                    message="PLANTNET_API_KEY not configured",
                ))
                await session.commit()
        return

    try:
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if not obs:
                return
            from app.services.settings_service import get_setting
            # API source is user-configurable (Settings → Pipelines → api_source_file_upload).
            # Fungi always route to iNaturalist only — enforced inside identify_observation
            # regardless of this setting (PlantNet has no fungi coverage).
            await identify_observation(
                session, obs, api_key=api_key,
                source=get_setting("api_source_file_upload"),
            )
            # High-confidence uploads are auto-approved (same rule as batch pipeline).
            # rejected / needs_review / approved are all set by identify_observation.
            await session.commit()
        _upload_status[obs_id] = "done"
    except Exception as exc:
        _upload_status[obs_id] = "failed"
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if obs:
                obs.identification_status = "failed_identification"
                obs.review_status = "needs_review"
                session.add(ProcessingLog(
                    observation_id=obs_id,
                    stage="identify",
                    status="failed",
                    message=str(exc),
                ))
                await session.commit()
