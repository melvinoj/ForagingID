"""Add nullable species.orphaned_at marker (orphan-GC groundwork)

Additive ONLY. `orphaned_at` is a nullable DATETIME set when an observation
moves off / is deleted and leaves a species card with NO backing observation
(true phantom — no obs references it by species_id OR species_primary). It is a
reversible marker, NOT a delete: re-identifying back onto the name clears it.
No trim/delete happens here — a later supervised step reads this column.

Guarded per-column against PRAGMA so a re-run is a no-op. SQLite ADD COLUMN is
emulated via batch_alter_table (render_as_batch is also global in env.py); both
are SQLite/Postgres-portable.

Revision ID: 0049_add_species_orphaned_at
Revises:     0048_add_user_id_ownership
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0049_add_species_orphaned_at"
down_revision = "0048_add_user_id_ownership"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    rows = bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "species", "orphaned_at"):
        with op.batch_alter_table("species") as batch_op:
            batch_op.add_column(sa.Column("orphaned_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.drop_column("orphaned_at")
