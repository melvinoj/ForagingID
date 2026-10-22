from datetime import datetime
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.observation import Observation, ObservationEdit, qualifies_as_identified
from app.services.species_link import set_observation_species
from app.config import settings

_log = logging.getLogger(__name__)

async def apply_species_category(session: AsyncSession, obs: Observation, edited_by: str = "human") -> bool:
    """A CONFIRMED observation of a fungal species is filed as fungi (Melvin,
    20 Oct 2026). The ONLY place this rule lives — called by every approve /
    correct path: update_observation_status (single approve, correct-species,
    reidentify confirm, trust accept), the bulk approve worker and the
    restore-from-rejected path. Only plant → fungi: scene rows and rows already
    fungi are untouched, and nothing is ever moved back to plant. Audit row
    written; returns True when it changed the category."""
    from sqlalchemy import select
    from app.models.species import Species, is_fungal_kingdom
    if obs.obs_category != "plant" or not obs.species_id:
        return False
    kingdom = await session.scalar(select(Species.kingdom).where(Species.id == obs.species_id))
    if not is_fungal_kingdom(kingdom):
        return False
    _log_edit(session, obs, "obs_category", obs.obs_category, "fungi", edited_by)
    obs.obs_category = "fungi"
    return True


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
    Copy the observation's original photo to photos/confirmed_plants/{species-slug}/
    — the ONE copy of this helper (E-05c: bulk_actions imports it). The folder is
    inside the project but NOT git-tracked (.gitignore ignores
    photos/confirmed_plants/*). Originals are never moved or modified.
    Best-effort — it never blocks the review action, but a failure or a missing
    original is logged (obs id, path, reason) so a skipped copy leaves a trace.
    """
    try:
        from app.services.export import copy_single
        dest = copy_single(obs, settings.confirmed_plants_dir)
        if dest:
            obs.confirmed_copy_path = str(dest)
        else:
            _log.warning("confirmed copy skipped for obs %s: original not found at %s", obs.id, obs.file_path)
    except Exception as exc:
        _log.warning("confirmed copy FAILED for obs %s (%s): %s", obs.id, obs.file_path, exc)


async def update_observation_status(
    session: AsyncSession,
    obs: Observation,
    review_status: str,
    species_name: Optional[str] = None,
    human_corrected: Optional[bool] = None,
    edited_by: str = "human",
    update_species: bool = False,
    common_name: Optional[str] = None,
    hazard_ack: Optional[str] = None,
) -> None:
    """
    Canonical helper to update an observation's status, species, and metadata consistently.
    Applies constraints, logs changes to observation_edits, clears review labels, and copies files.
    common_name: only used to label a confirmed species no API listed (B1-08).
    hazard_ack: the second tap — comma-separated scientific names of the hazard
    candidates the curator was shown. Approving as any species other than a
    hazard candidate raises 409 hazard_ack_required without it (Melvin, 22 Oct
    2026; app/services/hazard_candidates.py). Checked before any write.
    """
    if review_status in ("approved", "manually_verified"):
        from app.services.hazard_candidates import check_hazard_ack
        if update_species:
            await check_hazard_ack(session, obs, species_name, None, hazard_ack)
        else:
            await check_hazard_ack(session, obs, obs.species_primary or obs.species_suggested,
                                   obs.species_id if obs.species_primary else None, hazard_ack)

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
            from app.services.species_link import confirmed_candidate_first, strip_candidate_from_obs
            strip_candidate_from_obs(obs, prev_species)
            # The chosen species goes to the front with its own score, so the
            # card %, "Also:", map-pin confidence and top_score describe it (B1-08).
            if species_name:
                confirmed_candidate_first(obs, [common_name] if common_name else None)
        # A species set by hand resolves any pending suggestion. Left in place it
        # could be promoted over this choice by a later approve that read the row
        # before this commit (audit C-04: obs 21585 'norway spruce').
        if species_name and obs.species_suggested is not None:
            _log_edit(session, obs, "species_suggested", obs.species_suggested, None, edited_by)
            obs.species_suggested = None

    # 2. Update review status
    if prev_status != review_status:
        _log_edit(session, obs, "review_status", prev_status, review_status, edited_by)
        obs.review_status = review_status
        # reviewed_at is what makes a confirmed row human-confirmed
        # (is_human_confirmed), so its old value is logged too: reject-undo
        # restores it (B1-05) instead of turning an AI-agreed row into a human one.
        new_reviewed_at = datetime.utcnow()
        _log_edit(session, obs, "reviewed_at",
                  obs.reviewed_at.isoformat() if obs.reviewed_at else None, new_reviewed_at.isoformat(), edited_by)
        obs.reviewed_at = new_reviewed_at
        # Reject → orphan-GC the cards it pointed at; un-reject → clear markers.
        from app.services.species_link import refresh_orphan_markers
        await refresh_orphan_markers(session, obs)

    # 3. Handle human correction flag
    if human_corrected is not None:
        obs.human_corrected = human_corrected
    elif review_status == "manually_verified":
        obs.human_corrected = True

    # 4. Handle confirmed state promotions (approved or manually_verified)
    confirmed_statuses = ("approved", "manually_verified")
    is_confirmed = review_status in confirmed_statuses

    if is_confirmed:
        # Promote identification status when identification is complete —
        # a species was assigned, OR this is a scene row that has none by
        # nature. Shared with bulk_actions.py via qualifies_as_identified so
        # single-approve and bulk-approve cannot diverge again.
        if qualifies_as_identified(obs) and obs.identification_status != "identified":
            _log_edit(session, obs, "identification_status", prev_id_status, "identified", edited_by)
            obs.identification_status = "identified"

        # Clear stale review labels (essential fix for stuck cohorts)
        if obs.review_label is not None:
            _log_edit(session, obs, "review_label", obs.review_label, None, edited_by)
            obs.review_label = None

        # A confirmed species name always has a species row, linked (C-03) —
        # before the fungi rule, which reads the row's kingdom.
        from app.services.species_link import ensure_species_row
        await ensure_species_row(session, obs)

        # A confirmed fungus is filed as fungi (species' kingdom, not the AI guess).
        await apply_species_category(session, obs, edited_by)

        # Auto-copy photo to confirmed folder on first entry
        if prev_status not in confirmed_statuses and not obs.confirmed_copy_path:
            _copy_to_confirmed(obs)
