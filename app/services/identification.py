"""
Species identification pipeline — Phase 5.

Design rules (per spec):
  - Completely separate from ingestion. Never called during scan.
  - Operates only on observations that already exist in the DB.
  - Failures stored as 'failed_identification' — data is NEVER discarded.
  - Low confidence (< LOW_CONFIDENCE_THRESHOLD) → review_status = 'needs_review'
  - Stores: species_primary, species_candidates_json, plantnet_raw_json
  - Also writes to the species_candidates table for full relational access.
  - Retryable: re-run on 'failed_identification' rows at any time.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import select
from app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.plantnet import PlantNetError, PlantNetResult, identify_image
from app.services.species_link import set_observation_species
from app.services.taxonomy import normalize_taxon_key
from app.models.observation import Observation, ObservationEdit
from app.models.processing import ProcessingLog
from app.models.species import SpeciesCandidate
from app.services.file_cleanup import delete_observation_file as _delete_file

_id_log = logging.getLogger("foragingid.identification")

# iNaturalist kingdom gate. iNat scores are normalised to 0.0–1.0 in the
# integration (combined_score / 100), so this threshold is on the 0–1 scale.
# Any iNat top result outside Plantae/Fungi at/above this score is auto-rejected.
_INAT_KINGDOM_THRESHOLD = 0.05   # 5% on the normalised 0–1 scale
_INAT_ALLOWED_KINGDOMS  = {"plantae", "fungi"}

# Results at or above this score are auto-approved onto the map immediately.
# Below this score (but PlantNet returned candidates): sent to review queue.
# Images where PlantNet returned NO candidates at all: auto-rejected.
LOW_CONFIDENCE_THRESHOLD = 0.70

# Fix 5 — single-source fallback: a PlantNet-only result at/above this score
# auto-approves even without iNaturalist corroboration. Flagged in reviewer_notes
# as 'single-source auto-approve' for auditing. Fungi are never auto-approved.
SINGLE_SOURCE_AUTO_APPROVE = 0.92

# AUTO_REJECT_THRESHOLD removed: any PlantNet result, even low confidence,
# now goes to the review queue rather than being silently discarded.
# Only no-candidate results are auto-rejected.
AUTO_REJECT_THRESHOLD = 0.0   # effectively disabled — kept for import compatibility

# Max concurrent PlantNet requests — sequential (1) avoids burst-rate 429s.
# The original batch failures were all HTTP 429; sequential + 1.5s gap keeps
# us well within typical burst limits regardless of tier.
_API_SEMAPHORE = asyncio.Semaphore(1)

# Pause between requests — 1.5 s gives ~40 req/min, safe for all API tiers.
# Note: daily quota is separate; use the stop button to pause across days.
API_DELAY_S = 1.5

# iNaturalist vision rate-limit control (Fix 4). Previously the iNat call had
# no concurrency limit or delay, so batch bursts hit HTTP 429 and were silently
# dropped. Mirror the PlantNet approach: sequential, with a short gap.
_INAT_SEMAPHORE = asyncio.Semaphore(1)
INAT_DELAY_S = 1.0


# ---------------------------------------------------------------------------
# Core single-observation identifier
# ---------------------------------------------------------------------------

async def identify_observation(
    session: AsyncSession,
    obs: Observation,
    api_key: str,
    dry_run: bool = False,
    source: str = "plantnet",
) -> str:
    """
    Run identification for a single observation.
    source: "plantnet" | "inaturalist" | "both"
    Returns the new identification_status string.
    """
    from app.config import settings as _settings

    # Respect pre-filter
    if obs.is_plant_likely is False:
        _log(session, obs.id, "not_plant", "Skipped — pre-filter marked as not_plant")
        return "not_plant"

    # Landscape: no identification pipeline
    if (obs.obs_category or "plant") == "landscape":
        return "identified"   # no-op: treated as manually placed

    path = Path(obs.file_path)
    if not path.exists():
        status = "failed_identification"
        _log(session, obs.id, status, f"Image file not found: {path}")
        obs.identification_status = status
        return status

    start = time.monotonic()
    if dry_run:
        return "pending_identification"

    use_pn   = source in ("plantnet", "both") and bool(api_key)
    use_inat = source in ("inaturalist", "both") and bool(_settings.inaturalist_api_token)

    # ── Fungi routing ─────────────────────────────────────────────────────
    # If the observation category is 'fungi', skip PlantNet entirely.
    # This overrides the api_source_* pipeline setting unconditionally —
    # PlantNet has no fungi coverage, so fungi must never go to PlantNet.
    if (obs.obs_category or "plant") == "fungi":
        use_pn = False
        if not use_inat and bool(_settings.inaturalist_api_token):
            use_inat = True

    # Legacy: if the observation has a confirmed fungi species, skip PlantNet.
    if use_pn and obs.species_primary:
        from app.models.species import Species as _Species
        from sqlalchemy import select as _select
        _sp_row = await session.scalar(
            _select(_Species).where(_Species.name_key == normalize_taxon_key(obs.species_primary))
        )
        if _sp_row and (_sp_row.kingdom or "").lower() == "fungi":
            use_pn = False
            if not use_inat and bool(_settings.inaturalist_api_token):
                use_inat = True
            log.info(
                "[ID] Routing %r to iNaturalist only — known fungi species",
                obs.species_primary,
            )

    pn_result  = None
    pn_error   = None
    inat_hits  = []
    # True if any source we tried failed because the device is offline
    # (timeout / connection error). Used to route to 'pending_connection'.
    connection_failed = False

    # ── Fetch from applicable sources ────────────────────────────────────
    if use_pn:
        try:
            async with _API_SEMAPHORE:
                pn_result = await identify_image(
                    path, api_key=api_key,
                    lat=obs.latitude, lng=obs.longitude,
                )
                await asyncio.sleep(API_DELAY_S)
            # Log a retried success so the ~1-in-8 transient-stall rate stays
            # measurable in processing_logs rather than being masked by the
            # retry. Silent on a clean first attempt — no log noise.
            _pn_attempts = getattr(pn_result, "attempts", 1)
            if _pn_attempts > 1:
                _log(session, obs.id, "identify",
                     f"PlantNet: transport retry — succeeded on attempt {_pn_attempts}")
        except PlantNetError as exc:
            pn_error = str(exc)
            if getattr(exc, "is_connection_error", False):
                connection_failed = True
            _log(session, obs.id, "failed_identification", f"PlantNet: {exc}")

    if use_inat:
        from app.integrations.inaturalist import (
            score_image as _inat_score,
            INatConnectionError as _INatConnectionError,
        )
        try:
            async with _INAT_SEMAPHORE:
                inat_hits = await _inat_score(
                    path, api_token=_settings.inaturalist_api_token,
                    raise_on_connection_error=True,
                    lat=obs.latitude, lng=obs.longitude,
                    observed_on=(obs.photo_taken_at.date().isoformat()
                                 if obs.photo_taken_at else None),
                )
                await asyncio.sleep(INAT_DELAY_S)
        except _INatConnectionError as exc:
            connection_failed = True
            _log(session, obs.id, "failed_identification", f"iNaturalist: {exc}")

    duration_ms = int((time.monotonic() - start) * 1000)

    # ── iNaturalist kingdom signal ────────────────────────────────────────────
    # Twin of the gate in scan.py:1250 — see the full reasoning there. Both
    # pipelines call one or the other, so fixing one and not the other would
    # leave the destructive path live on half the traffic.
    #
    # Was: reject + unlink the files when iNat's top candidate fell outside
    # Plantae/Fungi at ≥5%. It fired on four real plant photos (dog 6.8%, cat
    # 12.1%, cow 9.4%, lime gall mite 48.4%) and was wrong every time. A
    # low-confidence non-plant guess frequently names something *in* the frame
    # rather than the subject.
    #
    # Now: routes to needs_review, never deletes, records the candidate and its
    # score honestly so the reviewer can judge the signal for themselves.
    # force_review is honoured trivially — the only outcome left is needs_review.
    if inat_hits:
        _ik = inat_hits[0]
        _kingdom = (_ik.iconic_taxon_name or "").lower()
        if _kingdom and _kingdom not in _INAT_ALLOWED_KINGDOMS and _ik.score >= _INAT_KINGDOM_THRESHOLD:
            _old_status = obs.review_status
            obs.identification_status = "identified"
            await set_observation_species(session, obs, None)
            obs.species_candidates_json = json.dumps([])
            obs.processing_stage = "identified"
            obs.review_status = "needs_review"
            obs.review_label = "non_plant"
            # prefilter_category deliberately left alone — the prefilter passed
            # these as plant; calling them a prefilter rejection was untrue.
            _note = (
                f"Possible non-plant subject — iNaturalist's top candidate was "
                f"{_ik.scientific_name} ({_ik.iconic_taxon_name}) at {_ik.score:.1%}. "
                f"Sent to review, not rejected: a low-confidence non-plant guess is a "
                f"signal, not a verdict, and may name something in the frame rather "
                f"than the subject."
            )
            existing = obs.reviewer_notes or ""
            obs.reviewer_notes = existing + ("\n" if existing else "") + _note
            session.add(ObservationEdit(
                observation_id=obs.id,
                field_name="review_status",
                old_value=_old_status,
                new_value="needs_review",
                edited_by="identify:kingdom_signal",
            ))
            _log(session, obs.id, "identified", _note, duration_ms)
            await session.flush()
            # No _delete_file() — this path must never destroy the only copy on a
            # probabilistic guess.
            return "identified"

    # ── Build per-source candidate lists ──────────────────────────────────
    # Keep PlantNet and iNaturalist results separate so the two-source
    # agreement check can compare them independently.  We no longer
    # deduplicate across sources: both sources' results are stored as-is
    # so the reviewer and the audit trail can see each source's opinion.
    pn_candidates: list = []
    inat_candidates: list = []

    if pn_result and pn_result.candidates:
        for c in pn_result.candidates:
            pn_candidates.append({
                "rank": c.rank,
                "scientific_name": c.scientific_name,
                "common_names": c.common_names,
                "score": round(c.score, 4),
                "family": c.family,
                "genus": c.genus,
                "gbif_id": c.gbif_id,
                "source": "plantnet",
            })

    if inat_hits:
        for idx, ic in enumerate(inat_hits, start=1):
            inat_candidates.append({
                "rank": idx,
                "scientific_name": ic.scientific_name,
                "common_names": ic.common_names,
                "score": round(ic.score, 4),
                "family": None,
                "genus": None,
                "gbif_id": None,
                "source": "inaturalist",
                "kingdom": ic.iconic_taxon_name,  # stored for future kingdom audits
            })

    # Merged list for storage and display — sorted by score, re-ranked.
    # Both sources appear independently; no deduplication.
    candidates = sorted(
        pn_candidates + inat_candidates,
        key=lambda c: c["score"],
        reverse=True,
    )
    for i, c in enumerate(candidates, start=1):
        c["rank"] = i

    # ── Regional frequency reweighting ────────────────────────────────────
    # Fetch local observation counts from iNat in parallel (best-effort, 0 on error).
    if obs.latitude is not None and obs.longitude is not None:
        from app.integrations.inaturalist import get_regional_obs_count
        counts = await asyncio.gather(*[
            get_regional_obs_count(c["scientific_name"], obs.latitude, obs.longitude)
            for c in candidates
        ])
        for c, count in zip(candidates, counts):
            c["regional_obs_count"] = count
            if count == 0:
                multiplier = 0.7
            elif count < 10:
                multiplier = 0.9
            elif count < 50:
                multiplier = 1.0
            else:
                multiplier = 1.1
            c["score"] = round(c["score"] * multiplier, 4)
        candidates.sort(key=lambda c: c["score"], reverse=True)
        for i, c in enumerate(candidates, start=1):
            c["rank"] = i

    obs.plantnet_raw_json = json.dumps(pn_result.raw_response if pn_result else {})

    # ── Connection failure → awaiting connection ──────────────────────────
    # If the API call(s) failed because the device is offline (timeout /
    # connection error) AND we have no candidates to work with, do NOT
    # auto-reject or mark failed. Park the observation in a clear pending
    # state so the reconnect hook can re-run identification later. Data is
    # never discarded and never left in an ambiguous state.
    if connection_failed and not candidates:
        obs.identification_status = "pending_connection"
        obs.processing_stage = "ingested"
        obs.review_status = "needs_review"
        note = "Awaiting connection — identification not run"
        obs.routing_reason = note
        _log(session, obs.id, "pending_connection", note, duration_ms)
        return "pending_connection"

    # ── No candidates → auto-reject ───────────────────────────────────────
    if not candidates:
        obs.identification_status = "identified"
        await set_observation_species(session, obs, None)
        obs.species_candidates_json = json.dumps([])
        obs.processing_stage = "identified"
        obs.review_status = "rejected"
        note = "No species candidates — auto-rejected"
        if pn_error:
            note += f" (PlantNet error: {pn_error})"
        _log(session, obs.id, "identified", note, duration_ms)
        await session.flush()
        try:
            _delete_file(obs)
        except Exception as _exc:
            _id_log.warning("identify obs %d: file cleanup failed: %s", obs.id, _exc)
        return "identified"

    top_d = candidates[0]
    top_score = top_d["score"]
    top_name  = top_d["scientific_name"]

    obs.species_candidates_json = json.dumps(candidates)
    obs.identification_status   = "identified"
    obs.processing_stage        = "identified"

    # Populate cached trust columns (Phase 10.5)
    # Normalisation guard: all candidate scores are 0.0–1.0, but defend against a
    # stray 0–100 value ever reaching the column again (legacy rows had this).
    obs.top_score = (top_score / 100.0) if top_score > 1.0 else top_score
    # dual_source_agreement is set below, only when the two sources actually
    # agree on the same species at/above threshold (see Fix 3).

    # ── Minimum confidence threshold ─────────────────────────────────────
    # If the top result is below the configured minimum, do NOT assign a
    # species name. Store it in species_suggested for reviewer reference
    # and route to the review queue as unidentified.
    from app.services.settings_service import get_setting as _gs
    _min_conf = _gs("min_identification_confidence")
    if top_score < _min_conf:
        await set_observation_species(session, obs, None)
        obs.species_suggested = top_name
        obs.review_status     = "needs_review"
        _log(session, obs.id, "identified",
             f"[no-match] {top_name} ({top_score:.2%}) < min threshold "
             f"({_min_conf:.0%}) — sent to review as unidentified",
             duration_ms)
        return "identified"

    await set_observation_species(session, obs, top_name)

    # Guard: never auto-approve an observation that was never pre-filtered.
    prefilter_ran = obs.is_plant_likely is not None

    from app.services.settings_service import get_setting as _gs
    # Single-source auto-approve removed — see 9.6 fix. Dual-API agreement
    # required or observation goes to review queue.
    _threshold = _gs("upload_auto_approve_threshold")

    # ── Two-source agreement check ────────────────────────────────────────
    # Auto-approval requires BOTH independent sources to name the same species
    # at or above the confidence threshold.
    #
    # Plants:  PlantNet + iNaturalist must agree.
    # Fungi:   Mushroom Observer has no image-scoring API — iNaturalist is the
    #          only available image classifier.  A single source cannot satisfy
    #          the two-source requirement, so fungi are always queued for review.
    # Fallback (only one source configured): always review queue.
    is_fungi = (obs.obs_category or "plant") == "fungi"

    auto_approve = False
    dual_agree = False           # Fix 3 — only true on genuine cross-source agreement
    single_source_approve = False  # Fix 5 — PlantNet-only high-confidence approval
    agreement_note = ""
    route_reason = ""

    # Best PlantNet candidate at/above the single-source fallback threshold.
    pn_strong = next((c for c in pn_candidates if c["score"] >= SINGLE_SOURCE_AUTO_APPROVE), None)

    if is_fungi:
        # Single image-scoring source available for fungi → never auto-approve
        route_reason = "fungi — iNaturalist-only (Mushroom Observer has no vision API)"
    elif use_pn and use_inat:
        # Both sources available — require above-threshold agreement on same species
        pn_at  = next((c for c in pn_candidates   if c["score"] >= _threshold), None)
        inat_at = next((c for c in inat_candidates if c["score"] >= _threshold), None)
        if (
            pn_at is not None
            and inat_at is not None
            and pn_at["scientific_name"] == inat_at["scientific_name"]
        ):
            auto_approve = True
            dual_agree = True
            agreement_note = (
                f"plantnet+inaturalist agree: {pn_at['scientific_name']} "
                f"(pn={pn_at['score']:.2%} / inat={inat_at['score']:.2%})"
            )
        elif pn_strong is not None:
            # Fix 5 — iNaturalist did not corroborate, but PlantNet is highly confident.
            auto_approve = True
            single_source_approve = True
            agreement_note = (
                f"single-source auto-approve: plantnet {pn_strong['scientific_name']} "
                f"({pn_strong['score']:.2%}) ≥ {SINGLE_SOURCE_AUTO_APPROVE:.0%}"
            )
        elif pn_at is None:
            route_reason = (
                f"PlantNet below threshold "
                f"({pn_candidates[0]['score']:.2%})" if pn_candidates
                else "PlantNet returned no candidates"
            )
        elif inat_at is None:
            route_reason = (
                f"iNaturalist below threshold "
                f"({inat_candidates[0]['score']:.2%})" if inat_candidates
                else "iNaturalist returned no candidates"
            )
        else:
            route_reason = (
                f"sources disagree — "
                f"pn={pn_at['scientific_name']!r} vs "
                f"inat={inat_at['scientific_name']!r}"
            )
    elif use_pn and not use_inat:
        # Single source only — Fix 5 fallback for high-confidence PlantNet results.
        if pn_strong is not None:
            auto_approve = True
            single_source_approve = True
            agreement_note = (
                f"single-source auto-approve: plantnet {pn_strong['scientific_name']} "
                f"({pn_strong['score']:.2%}) ≥ {SINGLE_SOURCE_AUTO_APPROVE:.0%}"
            )
        else:
            route_reason = (
                f"iNaturalist not configured — PlantNet below single-source threshold "
                f"({pn_candidates[0]['score']:.2%} < {SINGLE_SOURCE_AUTO_APPROVE:.0%})"
                if pn_candidates else "iNaturalist not configured — no PlantNet candidates"
            )
    else:
        route_reason = "PlantNet not used — single source"

    # Fix 3 — the column reflects genuine agreement only.
    obs.dual_source_agreement = 1 if dual_agree else 0

    if auto_approve and prefilter_ran:
        obs.review_status = "approved"
        flag_note = f"Auto-approved — {agreement_note}"
        if single_source_approve:
            # Audit marker so single-source approvals can be found and reviewed.
            existing = obs.reviewer_notes or ""
            obs.reviewer_notes = existing + ("\n" if existing else "") + "single-source auto-approve"
    elif auto_approve and not prefilter_ran:
        obs.review_status = "needs_review"
        flag_note = f"Review queue (pre-filter never ran) — {agreement_note}"
    else:
        obs.review_status = "needs_review"
        flag_note = f"Review queue — {route_reason}"

    # Write to species_candidates table
    for c in candidates:
        session.add(SpeciesCandidate(
            observation_id=obs.id,
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

    full_log_msg = f"{top_name} ({top_score:.2%}) [{top_d['source']}] — {flag_note}"
    obs.routing_reason = full_log_msg
    _log(session, obs.id, "identified", full_log_msg, duration_ms)
    return "identified"


def _log(
    session: AsyncSession,
    obs_id: Optional[int],
    status: str,
    message: str,
    duration_ms: Optional[int] = None,
) -> None:
    session.add(ProcessingLog(
        observation_id=obs_id,
        stage="identify",
        status="success" if status == "identified" else "failed",
        message=message,
        duration_ms=duration_ms,
    ))


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

async def run_identification_batch(
    session: AsyncSession,
    api_key: str,
    batch_size: int = 20,
    retry_failed: bool = False,
    dry_run: bool = False,
    source: str = "plantnet",
    progress_callback: Optional[Callable[[int, int], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """
    Process all pending observations through PlantNet.

    Args:
        retry_failed:  Also retry rows with 'failed_identification' status.
        dry_run:       Discover eligible rows and report counts — no API calls.

    Returns summary dict.
    """
    # pending_connection rows are offline-deferred IDs — always eligible so the
    # reconnect hook simply re-runs the batch once a connection is restored.
    statuses = ["pending_identification", "pending_connection"]
    if retry_failed:
        statuses.append("failed_identification")

    stmt = (
        select(Observation)
        .where(Observation.identification_status.in_(statuses))
        .where(Observation.is_duplicate.is_(False))
        # Exclude images the pre-filter marked as not_plant — no API call needed
        .where(Observation.is_plant_likely.is_not(False))
        .order_by(Observation.id)
    )
    rows = (await session.execute(stmt)).scalars().all()
    total = len(rows)

    if dry_run:
        return {
            "total_eligible": total,
            "identified": 0,
            "failed": 0,
            "low_confidence_flagged": 0,
            "dry_run": True,
        }

    identified = failed = low_confidence = pending_connection = 0
    stopped = False

    for i, obs in enumerate(rows):
        # Check for graceful stop request (stops after current photo completes)
        if stop_check and stop_check():
            stopped = True
            break

        status = await identify_observation(session, obs, api_key=api_key, source=source)

        if status == "identified":
            identified += 1
            candidates = json.loads(obs.species_candidates_json or "[]")
            top_score = candidates[0]["score"] if candidates else 0.0
            if top_score < LOW_CONFIDENCE_THRESHOLD:
                low_confidence += 1  # queued for review or auto-rejected
        elif status == "pending_connection":
            pending_connection += 1  # offline — will be retried by reconnect hook
        else:
            failed += 1

        # Commit every batch_size rows
        if (i + 1) % batch_size == 0:
            await session.commit()

        if progress_callback:
            progress_callback(i + 1, total)

    # Final commit
    await session.commit()

    # --- Post-identification: copy confirmed plants ---
    # Runs automatically after identification. Copies only high-confidence
    # results (≥ CONFIRMED_THRESHOLD). Originals are never touched.
    export_result: dict = {}
    try:
        from app.services.export import run_export_batch, CONFIRMED_THRESHOLD
        confirmed_dir = settings.confirmed_plants_dir
        export_result = await run_export_batch(session, confirmed_dir=confirmed_dir)
    except Exception as exc:
        export_result = {"error": str(exc)}

    return {
        "total_eligible": total,
        "identified": identified,
        "failed": failed,
        "pending_connection": pending_connection,
        "low_confidence_flagged": low_confidence,
        "confirmed_export": export_result,
        "stopped": stopped,
        "processed": identified + failed + pending_connection,
    }
