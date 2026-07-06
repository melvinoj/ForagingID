"""add foraging_notes to species

Phase 11a — Foraging Notes section redesign. Additive per-species running-notes
column on the species table:
  - foraging_notes : free-text editable notes shown on the species card. Whisper
                     transcripts from foraging_note encounters are appended here
                     with a datestamp separator. Separate from per-recording
                     encounter transcripts (encounters.transcript).

Idempotent: the column is added only if absent, so it no-ops on a DB where
init_db()'s create_all already bootstrapped the column, then stamps head.

Revision ID: 0017_add_species_foraging_notes
Revises: 0016_add_encounter_type
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_add_species_foraging_notes"
down_revision = "0016_add_encounter_type"
branch_labels = None
depends_on = None


def _species_columns() -> set:
    return {
        r[1] for r in op.get_bind().execute(
            sa.text("PRAGMA table_info(species)")
        ).fetchall()
    }


def upgrade() -> None:
    cols = _species_columns()
    if "foraging_notes" not in cols:
        op.add_column(
            "species",
            sa.Column("foraging_notes", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("species", "foraging_notes")
