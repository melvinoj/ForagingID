"""add encounter transcript + extracted suggestions

Phase 11a.4 — transcription + extraction layer. Two additive nullable columns on
the encounters table:
  - transcript            : Whisper transcript text (deliberate laptop step)
  - encounter_suggestions : JSON string of Claude-extracted suggestions (user confirms)

Idempotent: each column is added only if absent, so it no-ops on a DB where
init_db()'s create_all already bootstrapped the column, then stamps head.

Revision ID: 0014_add_encounter_transcript
Revises: 0013_add_personal_lists
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_add_encounter_transcript"
down_revision = "0013_add_personal_lists"
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
    if "transcript" not in cols:
        op.add_column("encounters", sa.Column("transcript", sa.Text(), nullable=True))
    if "encounter_suggestions" not in cols:
        op.add_column("encounters", sa.Column("encounter_suggestions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("encounters", "encounter_suggestions")
    op.drop_column("encounters", "transcript")
