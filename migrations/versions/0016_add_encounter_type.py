"""add encounter_type to encounters

Phase 11a Prompt 2 — additive capture-context column on the encounters table:
  - encounter_type : "field" (New Encounter tab, default) or "season" (recorded
                     from the My Season tab record button). Display/grouping only.

Idempotent: the column is added only if absent, so it no-ops on a DB where
init_db()'s create_all already bootstrapped the column, then stamps head.

Revision ID: 0016_add_encounter_type
Revises: 0015_add_notification_dismissals
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_add_encounter_type"
down_revision = "0015_add_notification_dismissals"
branch_labels = None
depends_on = None


def _encounter_columns() -> set:
    return {
        r[1] for r in op.get_bind().execute(
            sa.text("PRAGMA table_info(encounters)")
        ).fetchall()
    }


def upgrade() -> None:
    cols = _encounter_columns()
    if "encounter_type" not in cols:
        op.add_column(
            "encounters",
            sa.Column("encounter_type", sa.Text(), nullable=False, server_default="field"),
        )


def downgrade() -> None:
    op.drop_column("encounters", "encounter_type")
