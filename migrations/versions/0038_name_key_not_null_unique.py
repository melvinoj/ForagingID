"""Make species.name_key NOT NULL and add plain UNIQUE index

Revision ID: 0038_name_key_not_null_unique
Revises:     0037_add_species_name_key
Create Date: 2026-06-16

Backfills the one NULL name_key row (id=606 Dianthus carthusianorum —
a 2-token binomial, so lower(trim(scientific_name)) is identical to
normalize_taxon_key output), then tightens the column to NOT NULL and
adds a plain UNIQUE index. NOT NULL + UNIQUE together close the hole
where a forgetful create path could insert a NULL key and bypass
uniqueness.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0038_name_key_not_null_unique"
down_revision = "0037_add_species_name_key"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Backfill any remaining NULL name_key rows (should be exactly 1).
    # All current NULLs are plain binomials, so lower(trim(scientific_name))
    # is equivalent to normalize_taxon_key().
    op.execute(
        "UPDATE species SET name_key = lower(trim(scientific_name)) "
        "WHERE name_key IS NULL"
    )

    with op.batch_alter_table("species") as batch_op:
        # Drop the nullable non-unique index added in 0037.
        batch_op.drop_index("ix_species_name_key")
        # Tighten the column to NOT NULL.
        batch_op.alter_column(
            "name_key",
            existing_type=sa.String(200),
            nullable=False,
        )
        # Add a plain UNIQUE index — this is the dedup fence.
        batch_op.create_index("uq_species_name_key", ["name_key"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.drop_index("uq_species_name_key")
        batch_op.alter_column(
            "name_key",
            existing_type=sa.String(200),
            nullable=True,
        )
        batch_op.create_index("ix_species_name_key", ["name_key"])
