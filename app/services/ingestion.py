"""
Photo ingestion pipeline — Phase 4 hardened version.

Key design decisions:
- Batch commits (every N rows) instead of per-image, critical for 50k–200k libraries
- Checkpoint file tracks scan progress so interrupted jobs resume cleanly
- Dry-run mode: discover and report without writing anything
- HEIC memory guard: semaphore limits concurrent thumbnail conversions
- Ingestion is a pure data layer — zero API calls, zero inference
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.observation import Observation
from app.models.processing import ProcessingLog
from app.utils.exif import extract_exif
from app.utils.hashing import file_sha256
from app.utils.sidecar import read_takeout_gps
from app.utils.thumbnail import generate_thumbnail, is_supported_image

# Limit concurrent HEIC conversions — each one can use 200–400 MB peak RAM
_HEIC_SEMAPHORE = asyncio.Semaphore(3)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _checkpoint_path(folder: Path) -> Path:
    safe = str(folder.resolve()).replace("/", "_").replace(" ", "_").lstrip("_")
    return Path(settings.data_dir) / f"checkpoint_{safe[:80]}.json"


def _load_checkpoint(folder: Path) -> set[str]:
    cp = _checkpoint_path(folder)
    if cp.exists():
        try:
            data = json.loads(cp.read_text())
            return set(data.get("done", []))
        except Exception:
            return set()
    return set()


def _save_checkpoint(folder: Path, done: set[str]) -> None:
    cp = _checkpoint_path(folder)
    cp.write_text(json.dumps({"done": list(done)}, indent=2))


def clear_checkpoint(folder: Path) -> None:
    cp = _checkpoint_path(folder)
    if cp.exists():
        cp.unlink()


# ---------------------------------------------------------------------------
# Core DB helpers
# ---------------------------------------------------------------------------

async def _path_already_ingested(session: AsyncSession, file_path: str) -> bool:
    result = await session.execute(
        select(Observation.id).where(Observation.file_path == file_path).limit(1)
    )
    return result.scalar() is not None


async def _find_duplicate_by_hash(
    session: AsyncSession, file_hash: str, exclude_path: str
) -> Optional[int]:
    result = await session.execute(
        select(Observation.id)
        .where(Observation.file_hash == file_hash)
        .where(Observation.file_path != exclude_path)
        .limit(1)
    )
    return result.scalar()


# ---------------------------------------------------------------------------
# Single-file ingest (no commit — caller batches commits)
# ---------------------------------------------------------------------------

async def _ingest_one_no_commit(
    session: AsyncSession,
    file_path: Path,
    thumbnails_dir: Path,
    thumbnail_size: int,
) -> tuple[Optional[Observation], str]:
    """
    Prepare one Observation and add it to the session (unflushed).
    Returns (obs, status) where status is 'ingested' | 'duplicate' | 'failed'.
    """
    path_str = str(file_path.resolve())
    start = time.monotonic()

    try:
        file_hash = file_sha256(file_path)
        file_size = file_path.stat().st_size
        file_format = file_path.suffix.lower().lstrip(".")

        exif = extract_exif(file_path)

        # Google Takeout sidecar: fill GPS when EXIF has none.
        # Sidecars sit alongside the photo as <filename>.json.
        # This is a permanent part of the ingestion pipeline — not a one-off.
        if exif.latitude is None:
            sidecar_gps = read_takeout_gps(file_path)
            if sidecar_gps:
                exif.latitude, exif.longitude = sidecar_gps

        # Throttle HEIC thumbnail generation
        if file_format in ("heic", "heif"):
            async with _HEIC_SEMAPHORE:
                thumb_path = await asyncio.get_event_loop().run_in_executor(
                    None, generate_thumbnail, file_path, thumbnails_dir, thumbnail_size
                )
        else:
            thumb_path = await asyncio.get_event_loop().run_in_executor(
                None, generate_thumbnail, file_path, thumbnails_dir, thumbnail_size
            )

        thumb_str = str(thumb_path) if thumb_path else None

        existing_id = await _find_duplicate_by_hash(session, file_hash, path_str)
        if existing_id is not None:
            # Exact duplicate (same SHA-256) already in DB — skip entirely.
            # No new Observation row is created; this path is just counted and logged.
            duration_ms = int((time.monotonic() - start) * 1000)
            session.add(ProcessingLog(
                stage="ingest",
                status="skipped",
                duration_ms=duration_ms,
                message=f"Hash duplicate of obs #{existing_id}: {path_str}",
            ))
            return None, "duplicate"

        obs = Observation(
            file_path=path_str,
            file_hash=file_hash,
            file_size_bytes=file_size,
            file_format=file_format,
            thumbnail_path=thumb_str,
            photo_taken_at=exif.taken_at,
            latitude=exif.latitude,
            longitude=exif.longitude,
            altitude_m=exif.altitude_m,
            camera_make=exif.camera_make,
            camera_model=exif.camera_model,
            is_duplicate=False,
            processing_stage="ingested",
            review_status="pending",
            identification_status="pending_identification",
        )
        session.add(obs)

        duration_ms = int((time.monotonic() - start) * 1000)
        session.add(ProcessingLog(
            stage="ingest",
            status="success",
            duration_ms=duration_ms,
            message=path_str,
        ))

        return obs, "ingested"

    except Exception as exc:
        session.add(ProcessingLog(
            stage="ingest",
            status="failed",
            message=f"{path_str}: {exc}",
        ))
        return None, "failed"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scan_folder(
    session: AsyncSession,
    folder: Path,
    thumbnails_dir: Path,
    thumbnail_size: int = 300,
    batch_size: int = 50,
    dry_run: bool = False,
    resume: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """
    Recursively scan *folder* and ingest all supported images.

    Args:
        dry_run:  Discover files and report counts without writing to DB.
        resume:   Skip files recorded in the checkpoint file (default True).

    Returns a summary dict: {total, ingested, skipped, failed, geotagged, duplicates}.
    """
    files = sorted(p for p in folder.rglob("*") if is_supported_image(p))
    total = len(files)

    if dry_run:
        geotagged_estimate = 0
        for p in files[:min(200, total)]:  # sample first 200
            exif = extract_exif(p)
            if exif.latitude is not None:
                geotagged_estimate += 1
        sample_rate = geotagged_estimate / min(200, total) if total else 0
        return {
            "total": total,
            "ingested": 0,
            "skipped": 0,
            "failed": 0,
            "geotagged": int(total * sample_rate),
            "duplicates": 0,
            "dry_run": True,
            "note": "No data written (dry run)",
        }

    # Load checkpoint (set of already-processed absolute path strings)
    done_set: set[str] = _load_checkpoint(folder) if resume else set()

    ingested = skipped = failed = geotagged = duplicates = 0
    batch_pending: list[tuple[Observation, str]] = []

    async def _flush_batch():
        nonlocal ingested, geotagged, duplicates, failed
        try:
            await session.commit()
            for obs, status in batch_pending:
                if status == "ingested":
                    ingested += 1
                    if obs is not None and obs.latitude is not None:
                        geotagged += 1
                elif status == "duplicate":
                    # Same-content file already in DB — counted but no Observation created
                    duplicates += 1
                else:
                    failed += 1
        except Exception as exc:
            await session.rollback()
            failed += len(batch_pending)
        batch_pending.clear()

    for i, file_path in enumerate(files):
        path_str = str(file_path.resolve())

        # Already in DB or in checkpoint
        if path_str in done_set or await _path_already_ingested(session, path_str):
            skipped += 1
            done_set.add(path_str)
        else:
            obs, status = await _ingest_one_no_commit(
                session, file_path, thumbnails_dir, thumbnail_size
            )
            batch_pending.append((obs, status) if obs else (None, status))  # type: ignore
            done_set.add(path_str)

            # Flush batch
            if len(batch_pending) >= batch_size:
                await _flush_batch()
                _save_checkpoint(folder, done_set)

        if progress_callback:
            progress_callback(i + 1, total)

    # Flush remaining
    if batch_pending:
        await _flush_batch()

    _save_checkpoint(folder, done_set)

    return {
        "total": total,
        "ingested": ingested,
        "skipped": skipped,
        "failed": failed,
        "geotagged": geotagged,
        "duplicates": duplicates,
    }
