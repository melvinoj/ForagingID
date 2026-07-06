"""
ITIS name-validation API.

  POST /api/itis/backfill          — run ITIS lookup for all un-checked species
  GET  /api/itis/backfill/status   — progress of a running backfill
  POST /api/itis/lookup/{name}     — single on-demand lookup
  POST /api/itis/accept-rename/{name} — apply ITIS accepted name as a rename suggestion
                                        (human-confirmed, queues for review only)

Integration rules (NEVER auto-rename):
  - ITIS result is stored as a suggestion only.
  - itis_name_match = 'synonym' surfaces in the enrichment review queue.
  - Human must confirm any rename via the existing rename flow.
  - No change to identification_status, review_status, or species_primary.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.integrations.itis import ITISResult, lookup_itis
from app.models.species import Species

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/itis", tags=["itis"])

ITIS_RATE_LIMIT_S = 1.0    # ITIS fair-use: 1 request/second
ITIS_DATA_SOURCE_ID = 37   # Registered in data_sources table (migration 0019)

# ---------------------------------------------------------------------------
# Module-level backfill state (in-memory — resets on restart, intentionally)
# ---------------------------------------------------------------------------

_backfill_state: dict = {
    "running":   False,
    "total":     0,
    "done":      0,
    "errors":    0,
    "started_at": None,
    "finished_at": None,
    "last_name": None,
}


# ---------------------------------------------------------------------------
# POST /api/itis/backfill
# ---------------------------------------------------------------------------

@router.post("/backfill")
async def start_backfill(background_tasks: BackgroundTasks):
    """
    Trigger async ITIS lookup for all species where:
      - itis_name_match IS NULL (never checked), OR
      - itis_name_match = 'pending' (marked for retry)

    Rate-limited to 1 request/second (ITIS fair-use policy).
    Returns immediately; progress available via GET /api/itis/backfill/status.
    """
    if _backfill_state["running"]:
        return {
            "ok": False,
            "message": "Backfill already running",
            "status": _backfill_state,
        }

    # Count pending species before launching
    async with AsyncSessionLocal() as session:
        count = await session.scalar(
            select(Species)
            .where(
                or_(
                    Species.itis_name_match.is_(None),
                    Species.itis_name_match == "pending",
                )
            )
            .with_only_columns(Species.id)
        )
        # count is a scalar int, but select().with_only_columns returns rows
        # Use a count query instead
        from sqlalchemy import func
        total = await session.scalar(
            select(func.count(Species.id)).where(
                or_(
                    Species.itis_name_match.is_(None),
                    Species.itis_name_match == "pending",
                )
            )
        )

    if not total:
        return {"ok": True, "message": "No species need ITIS checking", "total": 0}

    from app.services.background_processes import bp_start
    process_id = await bp_start("itis_backfill", progress_total=total, detail=f"Starting ITIS backfill for {total} species")

    _backfill_state.update({
        "running": True,
        "total": total,
        "done": 0,
        "errors": 0,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "finished_at": None,
        "last_name": None,
        "process_id": process_id,
    })

    background_tasks.add_task(_run_backfill)
    return {
        "ok": True,
        "message": f"ITIS backfill started for {total} species",
        "total": total,
        "process_id": process_id,
    }


@router.get("/backfill/status")
async def backfill_status():
    """Current state of a running (or last completed) ITIS backfill."""
    return _backfill_state


# ---------------------------------------------------------------------------
# POST /api/itis/lookup/{name}
# ---------------------------------------------------------------------------

@router.post("/lookup/{name:path}")
async def lookup_one(name: str, db: AsyncSession = Depends(get_db)):
    """
    Run an on-demand ITIS lookup for a single species.
    Stores result in the species row and returns it.
    """
    sp = await db.scalar(select(Species).where(Species.scientific_name == name))
    if not sp:
        raise HTTPException(404, detail=f"Species '{name}' not found")

    result = await _do_itis_lookup(sp.scientific_name)
    await _apply_result(db, sp, result)
    await db.commit()

    # Activate ITIS data source on first successful real lookup
    if result.match_status != "no_match":
        await _activate_data_source(db)
        await db.commit()

    return {
        "scientific_name":  sp.scientific_name,
        "itis_tsn":         sp.itis_tsn,
        "itis_accepted_name": sp.itis_accepted_name,
        "itis_name_match":  sp.itis_name_match,
        "itis_checked_at":  sp.itis_checked_at.isoformat() if sp.itis_checked_at else None,
    }


# ---------------------------------------------------------------------------
# POST /api/itis/accept-rename/{name}
# ---------------------------------------------------------------------------

@router.post("/accept-rename/{name:path}")
async def accept_rename(name: str, db: AsyncSession = Depends(get_db)):
    """
    Queue the ITIS accepted name as a rename suggestion in the enrichment
    review queue.  Does NOT apply the rename — human confirms via species page.

    Only valid when itis_name_match = 'synonym'.
    """
    from app.api.culinary import _get_species_or_404
    from app.models.culinary import CulinaryInfo

    sp = await _get_species_or_404(db, name)

    if sp.itis_name_match != "synonym":
        raise HTTPException(400, detail="Species is not an ITIS synonym — no rename to queue")
    if not sp.itis_accepted_name:
        raise HTTPException(400, detail="No ITIS accepted name stored for this species")

    # Flag in the enrichment review queue with context note
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if not ci:
        ci = CulinaryInfo(species_id=sp.id)
        db.add(ci)
        await db.flush()

    ci.review_requested     = True
    ci.review_requested_at  = datetime.utcnow()
    ci.review_request_note  = (
        f"ITIS suggests rename → '{sp.itis_accepted_name}' "
        f"(TSN {sp.itis_tsn}). Please verify and rename if correct."
    )
    await db.commit()

    return {
        "ok": True,
        "queued_for_review": True,
        "current_name":  sp.scientific_name,
        "suggested_name": sp.itis_accepted_name,
        "itis_tsn": sp.itis_tsn,
    }


# ---------------------------------------------------------------------------
# Background backfill task
# ---------------------------------------------------------------------------

async def _run_backfill() -> None:
    """
    Iterate all un-checked species, call ITIS for each, store results.
    Rate-limited to ITIS_RATE_LIMIT_S between calls.
    Runs until all pending species are processed or an unrecoverable error occurs.
    """
    log.info("[ITIS backfill] starting")
    first_success = True

    from app.services.background_processes import bp_progress, bp_finish
    process_id = _backfill_state.get("process_id")
    _hb_counter = 0

    try:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(Species.id, Species.scientific_name)
                    .where(
                        or_(
                            Species.itis_name_match.is_(None),
                            Species.itis_name_match == "pending",
                        )
                    )
                    .order_by(Species.scientific_name)
                )
            ).all()

        for sp_id, sp_name in rows:
            # Honour pause/cancel signals
            if _backfill_state.get("_cancelled"):
                break

            _backfill_state["last_name"] = sp_name
            try:
                result = await _do_itis_lookup(sp_name)
                async with AsyncSessionLocal() as session:
                    sp = await session.get(Species, sp_id)
                    if sp:
                        await _apply_result(session, sp, result)
                        await session.commit()
                if first_success and result.match_status != "no_match":
                    async with AsyncSessionLocal() as session:
                        await _activate_data_source(session)
                        await session.commit()
                    first_success = False
                _backfill_state["done"] += 1
            except Exception as exc:
                log.warning("[ITIS backfill] error for %r: %s", sp_name, exc)
                _backfill_state["errors"] += 1
                try:
                    async with AsyncSessionLocal() as session:
                        sp = await session.get(Species, sp_id)
                        if sp:
                            sp.itis_name_match = "pending"
                            await session.commit()
                except Exception:
                    pass

            _hb_counter += 1
            if _hb_counter % 5 == 0 and process_id:
                done = _backfill_state["done"]
                total = _backfill_state["total"]
                await bp_progress(process_id, done, total,
                                  detail=f"ITIS: {sp_name} ({done} of {total})")

            await asyncio.sleep(ITIS_RATE_LIMIT_S)

    except Exception as exc:
        log.error("[ITIS backfill] fatal: %s", exc)
        await bp_finish(process_id, status="failed", error=str(exc))
    else:
        done = _backfill_state["done"]
        total = _backfill_state["total"]
        await bp_finish(process_id, status="complete", current=done, total=total)
    finally:
        _backfill_state["running"]     = False
        _backfill_state["finished_at"] = datetime.utcnow().isoformat() + "Z"
        _backfill_state.pop("_cancelled", None)
        log.info(
            "[ITIS backfill] done — %d/%d checked, %d errors",
            _backfill_state["done"],
            _backfill_state["total"],
            _backfill_state["errors"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _do_itis_lookup(scientific_name: str) -> ITISResult:
    """Call the ITIS integration; return ITISResult or raise on error."""
    return await lookup_itis(scientific_name)


async def _apply_result(session: AsyncSession, sp: Species, result: ITISResult) -> None:
    """Write ITIS result fields onto the Species row (no commit)."""
    sp.itis_tsn           = result.tsn
    sp.itis_accepted_name = result.accepted_name
    sp.itis_name_match    = result.match_status
    sp.itis_checked_at    = datetime.utcnow()

    # If ITIS returned a kingdom and the species row doesn't have one, apply it
    if result.kingdom and not sp.kingdom:
        sp.kingdom = result.kingdom

    if result.match_status == "synonym":
        log.info(
            "[ITIS] synonym: '%s' → '%s' (TSN %s → %s)",
            sp.scientific_name, result.accepted_name,
            result.tsn, result.accepted_tsn,
        )
    elif result.match_status == "no_match":
        log.info("[ITIS] no match for '%s'", sp.scientific_name)


async def _activate_data_source(session: AsyncSession) -> None:
    """Flip ITIS data source status from 'pending' → 'active' on first real result."""
    from app.models.data_source import DataSource
    ds = await session.get(DataSource, ITIS_DATA_SOURCE_ID)
    if ds and ds.status == "pending":
        ds.status = "active"
        log.info("[ITIS] data source %d activated", ITIS_DATA_SOURCE_ID)


# ---------------------------------------------------------------------------
# Called from scan.py after new species creation
# ---------------------------------------------------------------------------

async def trigger_itis_for_new_species(scientific_name: str) -> None:
    """
    Async task: run ITIS lookup for a newly created species card.
    Called via asyncio.create_task() — no return value, failures are logged.
    """
    await asyncio.sleep(5)  # slight delay — let the species commit settle
    try:
        result = await _do_itis_lookup(scientific_name)
        async with AsyncSessionLocal() as session:
            sp = await session.scalar(
                select(Species).where(Species.scientific_name == scientific_name)
            )
            if sp:
                await _apply_result(session, sp, result)
                await session.commit()
                # Activate data source on first hit
                if result.match_status != "no_match":
                    await _activate_data_source(session)
                    await session.commit()
        log.info("[ITIS] new species '%s' → %s", scientific_name, result.match_status)
    except Exception as exc:
        log.warning("[ITIS] lookup failed for new species '%s': %s", scientific_name, exc)
