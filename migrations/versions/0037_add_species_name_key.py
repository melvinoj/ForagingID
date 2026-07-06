"""Add species.name_key — normalized taxon lookup key

Revision ID: 0037_add_species_name_key
Revises:     0036_add_edibility_verified_by
Create Date: 2026-06-15

Adds a nullable VARCHAR(200) column name_key to species, with a non-unique
index. No unique constraint in this revision — collision report runs first
before any uniqueness is enforced.

Backfill of name_key values is handled by the one-off script
scripts/backfill_name_key.py, not by this migration.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0037_add_species_name_key"
down_revision = "0036_add_edibility_verified_by"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.add_column(
            sa.Column("name_key", sa.String(200), nullable=True)
        )
        batch_op.create_index("ix_species_name_key", ["name_key"])


def downgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.drop_index("ix_species_name_key")
        batch_op.drop_column("name_key")
