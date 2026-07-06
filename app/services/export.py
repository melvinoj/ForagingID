"""
Confirmed plants export service.

After identification, copies high-confidence plant photos into a clean,
organised folder. Originals are NEVER moved or modified.

Target layout:
  photos/confirmed_plants/
    sambucus-nigra/
      IMG_1234.jpg
      IMG_5678.jpg
    urtica-dioica/
      DSC_0045.jpg
    unknown-species/       ← no species_primary set
      photo.jpg

Rules:
  - Copy only if identification_status = 'identified' AND top score ≥ CONFIRMED_THRESHOLD
  - Idempotent: skip if confirmed_copy_path already set
  - Use shutil.copy2 — preserves file timestamps and metadata
  - Slugify species name: lowercase, spaces/special chars → hyphens
  - If species_primary is None: subfolder is 'unknown-species'
  - Filename collision: append _2, _3, ... rather than overwriting
  - Always log to processing_logs
"""

import json
import re
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation
from app.models.processing import ProcessingLog

# Must match identification.LOW_CONFIDENCE_THRESHOLD
CONFIRMED_THRESHOLD = 0.65


def _slugify(text: str) -> str:
    """Convert species name to a safe directory name. 'Sambucus nigra' → 'sambucus-nigra'."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unknown-species"


def _unique_dest(dest_dir: Path, filename: str) -> Path:
    """Return a destination path that doesn't collide with existing files."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = dest_dir / filename
    counter = 2
    while candidate.exists():
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def _top_score(obs: Observation) -> float:
    """Extract the top candidate score from the denormalised JSON field."""
    if not obs.species_candidates_json:
        return 0.0
    try:
        candidates = json.loads(obs.species_candidates_json)
        return float(candidates[0]["score"]) if candidates else 0.0
    except Exception:
        return 0.0


def copy_single(obs: Observation, confirmed_dir: Path) -> Optional[Path]:
    """
    Copy one observation's image to confirmed_dir.

    Returns the destination path, or None if the file couldn't be copied.
    Does NOT modify the observation object — caller does that.
    """
    src = Path(obs.file_path)
    if not src.exists():
        return None

    species_folder = _slugify(obs.species_primary or "unknown-species")
    dest_dir = confirmed_dir / species_folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = _unique_dest(dest_dir, src.name)
    shutil.copy2(src, dest)
    return dest


async def run_export_batch(
    session: AsyncSession,
    confirmed_dir: Path,
    threshold: float = CONFIRMED_THRESHOLD,
    rerun: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """
    Copy all confirmed plant photos to confirmed_dir.

    Args:
        rerun:     Re-copy observations that already have confirmed_copy_path set.
        threshold: Minimum top-candidate score to qualify as confirmed.

    Returns summary dict.
    """
    confirmed_dir.mkdir(parents=True, exist_ok=True)

    stmt = select(Observation).where(
        Observation.identification_status == "identified",
        Observation.is_duplicate.is_(False),
    )
    if not rerun:
        stmt = stmt.where(Observation.confirmed_copy_path.is_(None))

    rows = (await session.execute(stmt)).scalars().all()

    # Filter in Python — SQLite can't easily query inside a JSON field
    eligible = [obs for obs in rows if _top_score(obs) >= threshold]
    total = len(eligible)

    copied = skipped_low = skipped_no_file = failed = 0

    for i, obs in enumerate(eligible):
        start = time.monotonic()
        try:
            dest = copy_single(obs, confirmed_dir)
            if dest is None:
                skipped_no_file += 1
                session.add(ProcessingLog(
                    observation_id=obs.id,
                    stage="export",
                    status="failed",
                    message=f"Source file not found: {obs.file_path}",
                ))
            else:
                obs.confirmed_copy_path = str(dest)
                session.add(obs)
                copied += 1
                session.add(ProcessingLog(
                    observation_id=obs.id,
                    stage="export",
                    status="success",
                    message=str(dest),
                    duration_ms=int((time.monotonic() - start) * 1000),
                ))

        except Exception as exc:
            failed += 1
            session.add(ProcessingLog(
                observation_id=obs.id,
                stage="export",
                status="failed",
                message=str(exc),
            ))

        if (i + 1) % 50 == 0:
            await session.commit()

        if progress_callback:
            progress_callback(i + 1, total)

    await session.commit()

    return {
        "total_eligible": total,
        "copied": copied,
        "skipped_low_confidence": skipped_low,
        "skipped_no_file": skipped_no_file,
        "failed": failed,
        "threshold_used": threshold,
        "destination": str(confirmed_dir),
    }
