"""Alembic environment for ForagingID.

Runs migrations synchronously against the SQLite file. The async
`sqlite+aiosqlite://` URL from app config is converted to a plain
`sqlite://` URL since Alembic operates with a synchronous engine.

`render_as_batch=True` is required for SQLite: it rewrites ALTER TABLE
operations as copy-and-recreate "batch" blocks, since SQLite cannot
ALTER most column attributes in place.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import the app's metadata and EVERY model module so autogenerate/check sees all
# tables and can resolve cross-model foreign keys (e.g. guest_tokens.workshop_session_id
# → foraging_sessions). This list must stay in sync with main.py's model registration;
# a missing module previously broke `alembic check` with NoReferencedTableError.
from app.database import Base
from app import models  # noqa: F401 — registers the subset declared in models/__init__
from app.models import (  # noqa: F401 — register every remaining model on Base.metadata
    observation, species, culinary, location, notes, processing, settings,
    sources, tags, walk, workshop, foray_session, encounter, data_source,
    scan_session, personal_list, notification, recorded_walk, process, about,
)
from app.config import settings as app_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """Convert the app's async SQLite URL to a sync URL for Alembic."""
    return app_settings.database_url.replace("+aiosqlite", "")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
