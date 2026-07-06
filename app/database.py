import time as _time
import sqlalchemy
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={
        "check_same_thread": False,
        # 10-second busy timeout so concurrent requests wait rather than crash.
        "timeout": 10,
    },
)


# Enable FK enforcement on every connection.
# FK violations were confirmed absent before enabling (migration 0005 check).
@event.listens_for(engine.sync_engine, "connect")
def _set_fk_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    _t0 = _time.perf_counter()
    print(f"[TIMING] init_db: start", flush=True)

    async with engine.begin() as conn:
        _t_conn = _time.perf_counter()
        print(f"[TIMING] init_db: engine.begin() (connection): {_t_conn - _t0:.1f}s", flush=True)

        # WAL mode: idempotent, but acquiring the exclusive lock needed to switch
        # modes can block if another connection is still open (e.g. during a
        # uvicorn --reload cycle).  Only set these pragmas when the DB is not
        # already in WAL mode, and wrap in a try/except so a transient lock
        # contention never prevents the server from starting.
        try:
            result = await conn.execute(sqlalchemy.text("PRAGMA journal_mode"))
            row = result.fetchone()
            if row and row[0] != "wal":
                await conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))
                await conn.execute(sqlalchemy.text("PRAGMA synchronous=NORMAL"))
        except Exception:
            pass  # WAL switch is best-effort; don't block startup if it fails
        _t_wal = _time.perf_counter()
        print(f"[TIMING] init_db: WAL pragma check/set: {_t_wal - _t_conn:.1f}s", flush=True)

        # create_all bootstraps a fresh DB from the current models (it never
        # alters existing tables). Incremental schema changes to an existing
        # DB are handled by Alembic migrations (see migrations/), run with
        # `alembic upgrade head` — not by ad-hoc ALTER statements here.
        await conn.run_sync(Base.metadata.create_all)
        _t_create_all = _time.perf_counter()
        print(f"[TIMING] init_db: Base.metadata.create_all: {_t_create_all - _t_wal:.1f}s", flush=True)

        # Fix 6 rescue: P1 (syncthing) observations that were auto-rejected on
        # confidence (below_threshold / failed_identification) must surface in the
        # review queue.  Only not_plant pre-filter rejects and manually-rejected
        # rows (review_status='rejected' AND identification_status='not_plant', or
        # reviewed_at IS NOT NULL as the manual-rejection marker) are left alone.
        # Gate: probe first so the full-table UPDATE scan is skipped once applied.
        _t_probe0 = _time.perf_counter()
        _probe = await conn.execute(sqlalchemy.text("""
            SELECT 1 FROM observations
            WHERE upload_source = 'syncthing'
              AND review_status = 'rejected'
              AND identification_status IN ('below_threshold', 'failed_identification')
              AND reviewed_at IS NULL
            LIMIT 1
        """))
        if _probe.fetchone():
            await conn.execute(sqlalchemy.text("""
                UPDATE observations
                SET review_status = 'needs_review'
                WHERE upload_source = 'syncthing'
                  AND review_status = 'rejected'
                  AND identification_status IN ('below_threshold', 'failed_identification')
                  AND reviewed_at IS NULL
            """))
        _t_probe1 = _time.perf_counter()
        print(f"[TIMING] init_db: probe gate + syncthing fix: {_t_probe1 - _t_probe0:.1f}s", flush=True)

        # Idempotent FK backfill: set observations.species_id for any rows that
        # have species_primary populated but species_id not yet set (e.g. records
        # created before Phase 9 added the column, or via legacy code paths).
        _t_fk0 = _time.perf_counter()
        await conn.execute(sqlalchemy.text("""
            UPDATE observations
            SET species_id = (
                SELECT id FROM species
                WHERE scientific_name = observations.species_primary
                LIMIT 1
            )
            WHERE species_id IS NULL
            AND species_primary IS NOT NULL
            AND species_primary != ''
            AND EXISTS (
                SELECT 1 FROM species
                WHERE scientific_name = observations.species_primary
            )
        """))
        _t_fk1 = _time.perf_counter()
        print(f"[TIMING] init_db: FK backfill (species_id): {_t_fk1 - _t_fk0:.1f}s", flush=True)

        _t_ev0 = _time.perf_counter()
        # Phase 12 Prompt 3 — edibility_verified_by provenance backfill.
        # Runs idempotently on every server start (guard: edibility_verified_by IS NULL).
        # Classifies the 212 legacy edibility_verified=True species into four buckets:
        #   safety_constant  — Pteridium aquilinum (bracken hardcode)
        #   human            — Group B: no enrichment fingerprint → human provenance
        #   auto             — fingerprinted + PFAF rating >=4 (conf>=0.8)
        #   unlocked_for_review — all remaining fingerprinted species
        #
        # SAFETY: unlocking here is only correct because Prompt 1 made
        # PFAF/Wikidata verdict-writes structural no-ops — edibility_status
        # cannot be auto-overwritten regardless of this flag. If that no-op
        # is ever reverted, this backfill's unlocks need re-auditing.

        # A: bracken — safety hardcode regardless of edibility_verified value
        await conn.execute(sqlalchemy.text("""
            UPDATE species
               SET edibility_verified_by = 'safety_constant'
             WHERE scientific_name = 'Pteridium aquilinum'
               AND edibility_verified_by IS NULL
        """))

        # B: Group B — no enrichment fingerprint → human provenance
        await conn.execute(sqlalchemy.text("""
            UPDATE species
               SET edibility_verified_by = 'human'
             WHERE edibility_verified = 1
               AND scientific_name != 'Pteridium aquilinum'
               AND edibility_verified_by IS NULL
               AND id NOT IN (
                   SELECT species_id FROM culinary_info
                    WHERE ai_approved_fields_json IS NOT NULL
               )
        """))

        # C: auto — fingerprinted + PFAF rating >=4 (extraction_confidence >=0.8)
        await conn.execute(sqlalchemy.text("""
            UPDATE species
               SET edibility_verified_by = 'auto'
             WHERE edibility_verified = 1
               AND edibility_verified_by IS NULL
               AND id IN (
                   SELECT species_id FROM enrichment_sources
                    WHERE source_name = 'pfaf'
                    GROUP BY species_id
                   HAVING MAX(extraction_confidence) >= 0.8
               )
        """))

        # D: unlock remaining fingerprinted (all edibility_verified=1 still NULL after A–C)
        await conn.execute(sqlalchemy.text("""
            UPDATE species
               SET edibility_verified    = 0,
                   edibility_verified_by = 'unlocked_for_review'
             WHERE edibility_verified = 1
               AND edibility_verified_by IS NULL
        """))

        # E: flag unlocked species into the enrichment review queue
        await conn.execute(sqlalchemy.text("""
            UPDATE culinary_info
               SET review_requested      = 1,
                   review_requested_at   = datetime('now'),
                   review_request_note   = 'edibility_verified unlocked — PFAF/source agreement insufficient; needs manual review'
             WHERE species_id IN (
                       SELECT id FROM species
                        WHERE edibility_verified_by = 'unlocked_for_review'
                   )
               AND review_requested = 0
        """))

        _t_ev1 = _time.perf_counter()
        print(f"[TIMING] init_db: edibility_verified_by backfill (A–E): {_t_ev1 - _t_ev0:.1f}s", flush=True)

        # Phase 12 Prompt 1 — Mushroom Observer data source registry entry.
        # Idempotent: INSERT OR IGNORE — safe to run on every server start.
        # Mushroom Observer was absent from data_sources at time of implementation
        # (FAO Wild Edible Fungi is ID 36; this adds MO as a fungi-scope source).
        _t_mo0 = _time.perf_counter()
        await conn.execute(sqlalchemy.text("""
            INSERT OR IGNORE INTO data_sources
                (label, url, data_types, species_scope, region, status, last_test_status)
            VALUES
                (
                    'Mushroom Observer',
                    'https://mushroomobserver.org',
                    '["id_notes","culinary"]',
                    'fungi',
                    'Global',
                    'active',
                    'untested'
                )
        """))
        _t_mo1 = _time.perf_counter()
        print(f"[TIMING] init_db: INSERT OR IGNORE data_sources (MO): {_t_mo1 - _t_mo0:.1f}s", flush=True)
        print(f"[TIMING] init_db: TOTAL: {_t_mo1 - _t0:.1f}s", flush=True)
