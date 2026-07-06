"""Add encounters.expected_filename for photo-binding

Revision ID: 0042_expected_filename
Revises:     0041_encounter_photos
Create Date: 2026-06-23

The encounter recorder can capture or name a photo at encounter time.
expected_filename stores the camera filename the encounter is waiting for
(set by online own-naming or offline tap-pick), so p1 can bind on arrival.

Structured habitat columns (aspect, soil, altitude) and chemotype-tag
columns are deliberately deferred — they stay freeform inside text_note
for v1.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0042_expected_filename"
down_revision = "0041_encounter_photos"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("encounters") as batch_op:
        batch_op.add_column(
            sa.Column("expected_filename", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("encounters") as batch_op:
        batch_op.drop_column("expected_filename")
