"""Add compound index (species_id, photo_taken_at) on observations

Revision ID: 0043_species_photo_taken_idx
Revises:     0042_expected_filename
Create Date: 2026-06-24

Supports nearest-date-per-species queries for the timeline UI.
Without this, the query does a full 13K-row scan + temp sort.

NOTE: the model declares species_primary with index=True but the DB
has no such index (model/DB drift). Not fixed here — noted only.
"""
from alembic import op

revision      = "0043_species_photo_taken_idx"
down_revision = "0042_expected_filename"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_index(
        "ix_observations_species_photo_taken",
        "observations",
        ["species_id", "photo_taken_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_observations_species_photo_taken", table_name="observations")
