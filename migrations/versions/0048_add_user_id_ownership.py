"""Add nullable user_id ownership column to observations, map_notes,
recorded_walks, saved_walks (multi-tenancy groundwork)

Additive ONLY. Each column is INTEGER, NULLABLE, and carries NO foreign key
and NO NOT NULL constraint — the FK/NOT-NULL tightening is a later supervised
migration. Existing rows are backfilled to the curator (user_id=1) in the same
supervised session (data step, not schema), single-tenant assumption.

Unlike a new table, init_db()'s create_all cannot add columns to an existing
table, so there is no create_all race here — this migration is the only path
that adds the columns. Guarded per-column against sqlite_master/PRAGMA so a
re-run is a no-op.

SQLite ADD COLUMN is emulated via batch_alter_table (render_as_batch is also
global in env.py). Both are SQLite/Postgres-portable.

Revision ID: 0048_add_user_id_ownership
Revises:     0047_add_users
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0048_add_user_id_ownership"
down_revision = "0047_add_users"
branch_labels = None
depends_on = None

_TABLES = ("observations", "map_notes", "recorded_walks", "saved_walks")


def _has_column(bind, table: str, column: str) -> bool:
    rows = bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        if not _has_column(bind, table, "user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("user_id")
