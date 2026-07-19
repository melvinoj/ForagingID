"""
Orphan sweep — recovers observations stranded before identification ever ran.

WHAT IT LOOKS FOR
    processing_stage='ingested' AND no processing_logs row with stage='identify'.
    That pair means the pipeline committed the row and then never reached the
    identify stage at all — distinct from a failure, which now always leaves a
    stage='identify' log (see scan._mark_identify_failed).

WHY IT EXISTS
    Nine rows sat in exactly that state from 2026-06-07 to 2026-07-17. Nothing
    retried them, nothing surfaced them, and they were found only because a queue
    count forced someone to look. The prologue bug that stranded them is fixed,
    but "the bug is fixed" is not a recovery mechanism: any future path that
    strands a row — a hard kill between commit and identify, an unhandled edge in
    a new caller — leaves it stranded forever. This is the backstop.

DESIGN

  Trigger    Periodic asyncio task started from lifespan, alongside
             syncthing._auto_scan_loop. First run 120 s after boot (well clear of
             startup), then every 10 minutes.

             Why not startup-only, like recover_stale_jobs: the failure happens
             *during* a live scan, and this server runs for days. Startup-only
             would leave an orphan stranded until the next restart — which is
             precisely how nine rows survived six weeks.

             Why not every 60 s like the scan loop: orphans are rare (9 in seven
             weeks). A 10-minute cadence recovers them promptly while adding
             almost no load, and each cycle on a healthy queue is one indexed
             SELECT returning nothing.

  Contention This sweep must never become the concurrent writer that caused the
             bug. It takes the same mutex P1 and the archive scan take, via
             pipeline_try_acquire — non-blocking. If a scan holds it, the sweep
             skips the cycle and tries again in 10 minutes. It can therefore
             never overlap a live pipeline, and never queues behind one.

  Grace      Only rows whose created_at is older than GRACE_MINUTES (15) are
             eligible. This is load-bearing, not caution: a row sits at
             stage='ingested' for the entire duration of its own identification.
             With no grace period the sweep would seize rows that are being
             identified right now and run them a second time — duplicate API
             calls and a write race on the same row. 15 minutes is orders of
             magnitude beyond any legitimate in-flight window (identification
             takes seconds).

  Action     Re-queues through the normal path: scan._identify_scanned, with the
             pipeline's own configured source for that row's upload_source, so
             routing is unchanged. force_review=True — a row that fell through a
             crack and sat for weeks must land in front of a human, never
             auto-approve. Touches nothing else: no obs_category, no edibility,
             no thresholds, no scores.

  Cap        MAX_PER_CYCLE (20). A large backlog drains over several cycles
             rather than hammering the providers in one burst.

  Logging    A processing_logs row per swept observation (stage='identify',
             status='info') recording that the sweep re-queued it and how long it
             had been stranded, plus a summary line to the app log. A silent
             recovery would be the same mistake as the silent failure.

  Terminates A swept row cannot loop: identification either succeeds (leaves
             'ingested') or fails, and a failure now always writes a
             stage='identify' log, which makes the row ineligible for this
             predicate forever after.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.models.observation import Observation, is_phone_origin
from app.models.processing import ProcessingLog

log = logging.getLogger(__name__)

GRACE_MINUTES = 15
MAX_PER_CYCLE = 20
SWEEP_INTERVAL_S = 600      # 10 minutes
STARTUP_DELAY_S = 120


async def find_identify_orphans(grace_minutes: int = GRACE_MINUTES,
                                limit: int = MAX_PER_CYCLE) -> list:
    """
    Rows committed at 'ingested' that never reached identify. Read-only.
    Returns [(id, created_at)] oldest first.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=grace_minutes)
    async with AsyncSessionLocal() as session:
        rows = await session.execute(text("""
            SELECT o.id, o.created_at
            FROM observations o
            WHERE o.processing_stage = 'ingested'
              AND o.created_at < :cutoff
              AND NOT EXISTS (
                    SELECT 1 FROM processing_logs p
                    WHERE p.observation_id = o.id AND p.stage = 'identify')
            ORDER BY o.created_at
            LIMIT :limit
        """), {"cutoff": cutoff.isoformat(sep=" "), "limit": limit})
        return [(r[0], r[1]) for r in rows.fetchall()]


async def sweep_identify_orphans(dry_run: bool = False) -> dict:
    """
    One sweep cycle. Returns a summary dict; never raises.

    Takes the shared pipeline mutex non-blockingly — returns {'skipped': True}
    when a scan holds it rather than competing for the single SQLite writer.
    """
    from app.services.pipeline_lock import (
        pipeline_try_acquire, pipeline_release, pipeline_holder,
    )

    acquired = await pipeline_try_acquire("orphan_sweep")
    if not acquired:
        log.debug("[orphan_sweep] skipped — mutex held by %s", pipeline_holder())
        return {"skipped": True, "reason": f"mutex held by {pipeline_holder()}",
                "found": 0, "requeued": 0}

    try:
        orphans = await find_identify_orphans()
        if not orphans:
            return {"skipped": False, "found": 0, "requeued": 0}

        log.warning("[orphan_sweep] found %d observation(s) stranded before identify: %s",
                    len(orphans), [o[0] for o in orphans])
        if dry_run:
            return {"skipped": False, "found": len(orphans), "requeued": 0,
                    "ids": [o[0] for o in orphans], "dry_run": True}

        from app.api.scan import _identify_scanned
        from app.services.settings_service import get_setting

        requeued = []
        for obs_id, created_at in orphans:
            try:
                async with AsyncSessionLocal() as session:
                    obs = await session.get(Observation, obs_id)
                    if obs is None:
                        continue
                    src_setting = ("api_source_syncthing"
                                   if is_phone_origin(obs)
                                   else "api_source_file_upload")
                    session.add(ProcessingLog(
                        observation_id=obs_id,
                        stage="identify",
                        status="info",
                        message=(
                            f"action=orphan_sweep_requeue "
                            f"stranded_since={created_at} "
                            f"upload_source={obs.upload_source} "
                            "— committed at stage='ingested' with no identify attempt; "
                            "re-queued with force_review=True"
                        ),
                    ))
                    await session.commit()

                # force_review=True: never auto-approve a row nobody has seen.
                await _identify_scanned(
                    obs_id, source=get_setting(src_setting), force_review=True,
                )
                requeued.append(obs_id)
            except Exception:
                log.exception("[orphan_sweep] obs %s: re-queue failed", obs_id)

        log.warning("[orphan_sweep] re-queued %d/%d: %s",
                    len(requeued), len(orphans), requeued)
        return {"skipped": False, "found": len(orphans),
                "requeued": len(requeued), "ids": requeued}
    except Exception:
        log.exception("[orphan_sweep] cycle failed")
        return {"skipped": False, "found": 0, "requeued": 0, "error": True}
    finally:
        pipeline_release()


async def orphan_sweep_loop() -> None:
    """Background task for the life of the process. Started from lifespan."""
    await asyncio.sleep(STARTUP_DELAY_S)
    while True:
        try:
            await sweep_identify_orphans()
        except Exception:
            log.exception("[orphan_sweep] loop iteration failed")
        await asyncio.sleep(SWEEP_INTERVAL_S)
