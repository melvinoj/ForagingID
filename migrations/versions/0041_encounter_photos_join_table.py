"""Add encounter_photos many-to-many join table

Revision ID: 0041_encounter_photos
Revises:     0040_add_gbif_usage_key
Create Date: 2026-06-23

Adds an explicit many-to-many link between encounters and observations so
one encounter can carry several photos.  Each link row records how the
binding was made (proximity / filename / manual) for auditing.

The existing encounters.observation_id single-FK is kept (additive only)
but new code should use encounter_photos instead.

Structured habitat columns (aspect, soil, altitude) and chemotype-tag
columns are deliberately deferred — they stay freeform inside text_note
for v1.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0041_encounter_photos"
down_revision = "0040_add_gbif_usage_key"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "encounter_photos",
        sa.Column("id",            sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("encounter_id",  sa.Integer(), sa.ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("observation_id",sa.Integer(), sa.ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("binding_method",sa.Text(),    nullable=False),  # "proximity" | "filename" | "manual"
        sa.Column("binding_detail",sa.Text(),    nullable=True),   # optional: distance_m, matched filename, etc.
        sa.Column("created_at",    sa.DateTime(),nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("encounter_id", "observation_id", name="uq_encounter_observation"),
    )


def downgrade() -> None:
    op.drop_table("encounter_photos")
