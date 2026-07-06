"""Add species.gbif_usage_key for GBIF vernacular name lookups

Revision ID: 0040_add_gbif_usage_key
Revises:     0039_add_toxicity_severity
Create Date: 2026-06-22

Stores the GBIF backbone usageKey so vernacular name lookups don't
need to re-resolve the name on every call.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0040_add_gbif_usage_key"
down_revision = "0039_add_toxicity_severity"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.add_column(
            sa.Column("gbif_usage_key", sa.Integer(), nullable=True)
        )
        batch_op.create_index("ix_species_gbif_usage_key", ["gbif_usage_key"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.drop_index("ix_species_gbif_usage_key")
        batch_op.drop_column("gbif_usage_key")
