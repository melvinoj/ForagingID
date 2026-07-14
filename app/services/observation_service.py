from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.observation import Observation, ObservationEdit
from app.services.species_link import set_observation_species
from app.config import settings

def _log_edit(
    session: AsyncSession,
    obs: Observation,
    field_name: str,
    old_value: Optional[str],
    new_value: Optional[str],
    edited_by: str,
) -> None:
    session.add(ObservationEdit(
        observation_id=obs.id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        edited_by=edited_by,
    ))


def _copy_to_confirmed(obs: Observation) -> None:
    """
    Copy the observation's original photo to photos/confirmed_plants/{species-slug}/.
    Destination is always inside the ForagingID project root so files are git-tracked.
    Originals are never moved or modified.
    Best-effort — failure is silent so it never blocks the review action.
    """
    try:
        from app.services.export import copy_single
        dest = copy_single(obs, settings.confirmed_plants_dir)
        if dest:
            obs.confirmed_copy_path = str(dest)
    except Exception:
        pass  # non-critical: export_confirmed.py can be re-run to catch any misses


async def update_observation_status(
    session: AsyncSession,
    obs: Observation,
    review_status: str,
    species_name: Optional[str] = None,
    human_corrected: Optional[bool] = None,
    edited_by: str = "human",
    update_species: bool = False,
) -> None:
    """
    Canonical helper to update an observation's status, species, and metadata consistently.
    Applies constraints, logs changes to observation_edits, clears review labels, and copies files.
    """
    prev_status = obs.review_status
    prev_species = obs.species_primary
    prev_id_status = obs.identification_status

    # 1. Update species if requested
    if update_species:
        if prev_species != species_name:
            _log_edit(session, obs, "species_primary", prev_species, species_name, edited_by)
            await set_observation_species(session, obs, species_name)
            # Drop the moved-off name from the candidate cache so it reflects
            # current reality (no-op when prev_species is empty, i.e. a
            # promotion rather than a move-off). Audit trail is preserved in the
            # SpeciesCandidate table.
            from app.services.species_link import strip_candidate_from_obs
            strip_candidate_from_obs(obs, prev_species)

    # 2. Update review status
    if prev_status != review_status:
        _log_edit(session, obs, "review_status", prev_status, review_status, edited_by)
        obs.review_status = review_status
        obs.reviewed_at = datetime.utcnow()

    # 3. Handle human correction flag
    if human_corrected is not None:
        obs.human_corrected = human_corrected
    elif review_status == "manually_verified":
        obs.human_corrected = True

    # 4. Handle confirmed state promotions (approved or manually_verified)
    confirmed_statuses = ("approved", "manually_verified")
    is_confirmed = review_status in confirmed_statuses

    if is_confirmed:
        # Promote identification status if species_primary is set
        if obs.species_primary and obs.identification_status != "identified":
            _log_edit(session, obs, "identification_status", prev_id_status, "identified", edited_by)
            obs.identification_status = "identified"

        # Clear stale review labels (essential fix for stuck cohorts)
        if obs.review_label is not None:
            _log_edit(session, obs, "review_label", obs.review_label, None, edited_by)
            obs.review_label = None

        # Auto-copy photo to confirmed folder on first entry
        if prev_status not in confirmed_statuses and not obs.confirmed_copy_path:
            _copy_to_confirmed(obs)
