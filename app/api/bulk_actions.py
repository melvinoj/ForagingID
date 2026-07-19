"""
Bulk action endpoints with background_processes tracking.

Each endpoint returns immediately with a process_id; the actual work runs
as a background task that updates progress via bp_start / bp_progress / bp_finish.
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.database import AsyncSessionLocal
from app.models.observation import Observation, ObservationEdit
from app.models.processing import ProcessingLog
from app.config import settings
from app.services.background_processes import bp_start, bp_progress, bp_finish

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bulk", tags=["bulk"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class BulkReviewBody(BaseModel):
    observation_ids: List[int]
    status: str  # "approved" or "rejected"


class BulkIdsBody(BaseModel):
    observation_ids: List[int]


# ---------------------------------------------------------------------------
# Helpers (shared with observations.py but kept local to avoid import tangles)
# ---------------------------------------------------------------------------

def _log_edit(session, obs, field_name, old_value, new_value):
    """Write an immutable audit row to observation_edits."""
    session.add(ObservationEdit(
        observation_id=obs.id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        edited_by="human",
    ))


def _copy_to_confirmed(obs):
    """Copy photo to confirmed_plants/. Best-effort, never blocks."""
    try:
        from app.services.export import copy_single
        dest = copy_single(obs, settings.confirmed_plants_dir)
        if dest:
            obs.confirmed_copy_path = str(dest)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# POST /api/bulk/review
# ---------------------------------------------------------------------------

@router.post("/review")
async def bulk_review(body: BulkReviewBody, background_tasks: BackgroundTasks):
    """
    Bulk approve or reject observations.  Returns immediately with a
    process_id; work runs in the background.
    """
    if body.status not in ("approved", "rejected"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")

    total = len(body.observation_ids)
    pid = await bp_start(
        "bulk_review",
        progress_total=total,
        detail=f"Bulk {body.status} for {total} observations",
    )
    background_tasks.add_task(_bulk_review_task, body.observation_ids, body.status, pid)
    return {"ok": True, "process_id": pid, "total": total}


async def _bulk_review_task(obs_ids: List[int], status: str, pid: Optional[int]):
    """Background worker: apply review status to each observation sequentially."""
    total = len(obs_ids)
    errors = 0
    confirmed_statuses = ("approved", "manually_verified")

    for i, obs_id in enumerate(obs_ids):
        try:
            async with AsyncSessionLocal() as session:
                obs = await session.get(Observation, obs_id)
                if not obs:
                    log.warning("[bulk_review] obs %d not found, skipping", obs_id)
                    errors += 1
                    await bp_progress(pid, i + 1, total, f"obs {obs_id} not found")
                    continue

                prev_status = obs.review_status

                if prev_status != status:
                    _log_edit(session, obs, "review_status", prev_status, status)
                    obs.review_status = status

                obs.reviewed_at = datetime.utcnow()

                # Auto-copy on first approval
                entering_confirmed = (
                    status in confirmed_statuses
                    and prev_status not in confirmed_statuses
                )
                if entering_confirmed and not obs.confirmed_copy_path:
                    _copy_to_confirmed(obs)

                # Promote species_suggested -> species_primary when approving
                if (
                    status in confirmed_statuses
                    and not obs.species_primary
                    and obs.species_suggested
                ):
                    from app.services.species_link import set_observation_species
                    _log_edit(session, obs, "species_primary", None, obs.species_suggested)
                    await set_observation_species(session, obs, obs.species_suggested)
                    obs.species_suggested = None
                    obs.human_corrected = True

                # Upgrade identification_status when approving.
                #
                # Two cases qualify as "identification is done":
                #   • a species was assigned, or
                #   • the row is a landscape/scene shot, which legitimately has
                #     NO species and never will. observations.py's category
                #     change already sets identified + species NULL for exactly
                #     this state; bulk approve did not, so approving a landscape
                #     row here left it approved + below_threshold + NULL —
                #     invariant-breaking (the map filters on identified, the
                #     card counts on review_status) and the sole cause of the
                #     six known drifted rows. This makes the two paths agree.
                #
                # No species is invented and species_primary is never written.
                # A NON-landscape row with no species still does NOT qualify:
                # for a plant/fungi row, "approved but unidentified" is a real
                # unresolved state, not a finished one.
                _scene_no_species = (
                    not obs.species_primary and obs.obs_category == "landscape"
                )
                if (
                    status in confirmed_statuses
                    and (obs.species_primary or _scene_no_species)
                    and obs.identification_status != "identified"
                ):
                    _log_edit(
                        session, obs,
                        "identification_status", obs.identification_status, "identified",
                    )
                    obs.identification_status = "identified"

                await session.commit()

            # Post-commit actions (outside the session)
            if status == "rejected" and prev_status != "rejected":
                from app.services.file_cleanup import delete_observation_file
                delete_observation_file(obs)

            if entering_confirmed and obs.species_primary:
                from app.services.enrichment import trigger_ai_drafts_for_species
                await trigger_ai_drafts_for_species(obs.species_primary)

        except Exception:
            log.exception("[bulk_review] error processing obs %d", obs_id)
            errors += 1

        await bp_progress(pid, i + 1, total, f"Processed obs {obs_id}")

    error_msg = f"{errors} failed" if errors else ""
    await bp_finish(pid, "complete", error=error_msg, current=total, total=total)
    log.info("[bulk_review] done — %d processed, %d errors", total, errors)


# ---------------------------------------------------------------------------
# POST /api/bulk/retry-identify
# ---------------------------------------------------------------------------

@router.post("/retry-identify")
async def bulk_retry_identify(body: BulkIdsBody, background_tasks: BackgroundTasks):
    """
    Bulk re-run identification on observations. Uses the same _identify_scanned
    pipeline as reprocess-pending (full identify + route, not interactive candidate
    selection).
    """
    total = len(body.observation_ids)
    pid = await bp_start(
        "bulk_retry_identify",
        progress_total=total,
        detail=f"Retry identification for {total} observations",
    )
    background_tasks.add_task(_bulk_retry_identify_task, body.observation_ids, pid)
    return {"ok": True, "process_id": pid, "total": total}


async def _bulk_retry_identify_task(obs_ids: List[int], pid: Optional[int]):
    """Background worker: re-identify each observation sequentially."""
    from app.api.scan import _identify_scanned

    total = len(obs_ids)
    errors = 0

    for i, obs_id in enumerate(obs_ids):
        try:
            await _identify_scanned(obs_id)
        except Exception:
            log.exception("[bulk_retry_identify] error on obs %d", obs_id)
            errors += 1

        await bp_progress(pid, i + 1, total, f"Identified obs {obs_id}")

    error_msg = f"{errors} failed" if errors else ""
    await bp_finish(pid, "complete", error=error_msg, current=total, total=total)
    log.info("[bulk_retry_identify] done — %d processed, %d errors", total, errors)


# ---------------------------------------------------------------------------
# POST /api/bulk/unlock-prefilter
# ---------------------------------------------------------------------------

@router.post("/unlock-prefilter")
async def bulk_unlock_prefilter(body: BulkIdsBody, background_tasks: BackgroundTasks):
    """
    Bulk override pre-filter rejections and re-run identification.
    Only processes observations currently in 'not_plant' status; others are skipped.
    """
    total = len(body.observation_ids)
    pid = await bp_start(
        "bulk_unlock_prefilter",
        progress_total=total,
        detail=f"Unlock prefilter for {total} observations",
    )
    background_tasks.add_task(_bulk_unlock_prefilter_task, body.observation_ids, pid)
    return {"ok": True, "process_id": pid, "total": total}


async def _bulk_unlock_prefilter_task(obs_ids: List[int], pid: Optional[int]):
    """Background worker: override prefilter + identify each observation."""
    from app.api.scan import _identify_scanned

    total = len(obs_ids)
    errors = 0

    for i, obs_id in enumerate(obs_ids):
        try:
            async with AsyncSessionLocal() as session:
                obs = await session.get(Observation, obs_id)
                if not obs:
                    log.warning("[bulk_unlock_prefilter] obs %d not found", obs_id)
                    errors += 1
                    await bp_progress(pid, i + 1, total, f"obs {obs_id} not found")
                    continue

                if obs.identification_status != "not_plant":
                    log.info(
                        "[bulk_unlock_prefilter] obs %d status=%s, skipping",
                        obs_id, obs.identification_status,
                    )
                    await bp_progress(pid, i + 1, total, f"obs {obs_id} skipped (not not_plant)")
                    continue

                obs.identification_status = "pending_identification"
                obs.review_status = "pending"
                obs.is_plant_likely = True
                session.add(ProcessingLog(
                    observation_id=obs_id,
                    stage="prefilter_override",
                    status="success",
                    message="Pre-filter rejection overridden (bulk) — queued for identification",
                ))
                await session.commit()

            # Run identification (force_review=True matches single-item behaviour)
            await _identify_scanned(obs_id, force_review=True)

        except Exception:
            log.exception("[bulk_unlock_prefilter] error on obs %d", obs_id)
            errors += 1

        await bp_progress(pid, i + 1, total, f"Processed obs {obs_id}")

    error_msg = f"{errors} failed" if errors else ""
    await bp_finish(pid, "complete", error=error_msg, current=total, total=total)
    log.info("[bulk_unlock_prefilter] done — %d processed, %d errors", total, errors)
