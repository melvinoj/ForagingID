import time as _time
import sqlalchemy
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


# connect_args below are pysqlite/aiosqlite-specific (check_same_thread is a
# sqlite3.connect kwarg; timeout is SQLite's busy-timeout) and are invalid for
# other dialects — e.g. asyncpg raises on an unexpected check_same_thread kwarg.
# Scope them to the sqlite backend so a future Postgres URL (Phase 14) skips
# them. SQLite path is unchanged: same args, same values.
_is_sqlite = sqlalchemy.make_url(settings.database_url).get_backend_name() == "sqlite"

# Lock wait, in seconds. Raised 10 → 30 on 15 Oct 2026 as a stopgap margin:
# the real fix is that no code path holds the write lock across a network call
# (enrichment.py transaction A/B split, enrich_gate scheduling). Applied twice,
# deliberately: as sqlite3's connect timeout AND as PRAGMA busy_timeout in the
# connect hook below, so every pooled connection carries the same value.
_SQLITE_BUSY_TIMEOUT_S = 30

_connect_args = (
    {
        "check_same_thread": False,
        # Busy timeout so concurrent requests wait rather than crash.
        "timeout": _SQLITE_BUSY_TIMEOUT_S,
    }
    if _is_sqlite
    else {}
)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=_connect_args,
)


# Enable FK enforcement on every connection (SQLite only — Postgres always
# enforces FKs and has no such PRAGMA, so registering this on a Postgres engine
# would raise on every connect). FK violations were confirmed absent before
# enabling (migration 0005 check).
#
# busy_timeout and synchronous are per-connection settings (unlike
# journal_mode=WAL, which is stored in the DB file). synchronous=NORMAL was
# previously set only on the one connection that switched the file to WAL, so
# every other pooled connection ran at the default FULL. Both now apply to
# every connection. NORMAL is the documented-safe level under WAL.
def _set_fk_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute(f"PRAGMA busy_timeout = {_SQLITE_BUSY_TIMEOUT_S * 1000}")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.close()

if engine.dialect.name == "sqlite":
    event.listen(engine.sync_engine, "connect", _set_fk_pragma)

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

        # WAL mode (SQLite only): idempotent, but acquiring the exclusive lock
        # needed to switch modes can block if another connection is still open
        # (e.g. during a uvicorn --reload cycle).  Only set these pragmas when the
        # DB is not already in WAL mode.  WAL / synchronous are SQLite-only
        # concepts, so the whole block is skipped on any other dialect.
        if engine.dialect.name == "sqlite":
            try:
                result = await conn.execute(sqlalchemy.text("PRAGMA journal_mode"))
                row = result.fetchone()
                if row and row[0] != "wal":
                    await conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))
                    await conn.execute(sqlalchemy.text("PRAGMA synchronous=NORMAL"))
            except OperationalError as _e:
                # Narrowed from a bare `except Exception: pass`.  The only
                # tolerated failure is transient "database is locked" contention
                # during a --reload cycle (WAL switch is best-effort and must not
                # block startup).  It is now logged rather than silently swallowed,
                # and any non-OperationalError propagates instead of being hidden.
                print(f"[init_db] WARNING: WAL pragma switch skipped (transient lock?): {_e}", flush=True)
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
        # Classifies the 212 legacy edibility_verified=True species into buckets:
        #   safety_constant  — Pteridium aquilinum (bracken hardcode)
        #   unlocked_for_review — every other locked row with no provenance
        # The old 'auto' bucket (fingerprinted + PFAF conf >=0.8) and 'human'
        # Group B (no enrichment fingerprint) are gone (audit B2-07, batch 11 +
        # leftover, Melvin 25 Oct 2026): a machine never writes a lock flag that
        # reads as confirmed — only Melvin's own actions write 'human'. Such rows
        # now fall to D and are unlocked for review (0 rows matched either on 25 Oct).
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

        # D: unlock remaining fingerprinted (all edibility_verified=1 still NULL after A–C)
        await conn.execute(sqlalchemy.text("""
            UPDATE species
               SET edibility_verified    = 0,
                   edibility_verified_by = 'unlocked_for_review'
             WHERE edibility_verified = 1
               AND edibility_verified_by IS NULL
        """))

        # E: flag unlocked species into the enrichment review queue.
        # `datetime('now')` is SQLite-only; Postgres uses NOW(). Both return a
        # UTC timestamp — branch on dialect so the SQLite path is byte-identical.
        _now_sql = "datetime('now')" if engine.dialect.name == "sqlite" else "NOW()"
        await conn.execute(sqlalchemy.text(f"""
            UPDATE culinary_info
               SET review_requested      = 1,
                   review_requested_at   = {_now_sql},
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
        # `INSERT OR IGNORE` is SQLite-only and relies on the UNIQUE(url)
        # constraint to no-op on repeat boots. Postgres uses the equivalent
        # `ON CONFLICT (url) DO NOTHING`, targeting that same unique column.
        if engine.dialect.name == "sqlite":
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
        else:
            await conn.execute(sqlalchemy.text("""
                INSERT INTO data_sources
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
                ON CONFLICT (url) DO NOTHING
            """))
        _t_mo1 = _time.perf_counter()
        print(f"[TIMING] init_db: INSERT OR IGNORE data_sources (MO): {_t_mo1 - _t_mo0:.1f}s", flush=True)
        print(f"[TIMING] init_db: TOTAL: {_t_mo1 - _t0:.1f}s", flush=True)
