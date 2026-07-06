"""Add ITIS name-validation fields to species table

Revision ID: 0023_add_itis_fields_to_species
Revises:     0022_add_recorded_walks
Create Date: 2026-06-04

Adds four columns (additive only):
  itis_tsn           — ITIS Taxonomic Serial Number for the searched name
  itis_accepted_name — currently accepted scientific name per ITIS
  itis_name_match    — "accepted" | "synonym" | "no_match" | "pending" (NULL = not yet checked)
  itis_checked_at    — timestamp of the most recent ITIS lookup
"""
from alembic import op
import sqlalchemy as sa

revision      = "0023_add_itis_fields_to_species"
down_revision = "0022_add_recorded_walks"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_cols = {
        row[1]
        for row in bind.execute(sa.text("PRAGMA table_info(species)"))
    }

    with op.batch_alter_table("species") as batch_op:
        if "itis_tsn" not in existing_cols:
            batch_op.add_column(sa.Column("itis_tsn",           sa.Integer(),    nullable=True))
        if "itis_accepted_name" not in existing_cols:
            batch_op.add_column(sa.Column("itis_accepted_name", sa.String(200),  nullable=True))
        if "itis_name_match" not in existing_cols:
            batch_op.add_column(sa.Column("itis_name_match",    sa.String(20),   nullable=True))
        if "itis_checked_at" not in existing_cols:
            batch_op.add_column(sa.Column("itis_checked_at",    sa.DateTime(),   nullable=True))

    # Indexes for backfill queries and review-queue filtering
    existing_indexes = {
        row[1]
        for row in bind.execute(sa.text("SELECT * FROM sqlite_master WHERE type='index'"))
    }
    if "ix_species_itis_name_match" not in existing_indexes:
        op.create_index("ix_species_itis_name_match", "species", ["itis_name_match"])
    if "ix_species_itis_tsn" not in existing_indexes:
        op.create_index("ix_species_itis_tsn", "species", ["itis_tsn"])


def downgrade() -> None:
    bind = op.get_bind()
    existing_indexes = {
        row[1]
        for row in bind.execute(sa.text("SELECT * FROM sqlite_master WHERE type='index'"))
    }
    if "ix_species_itis_tsn" in existing_indexes:
        op.drop_index("ix_species_itis_tsn", "species")
    if "ix_species_itis_name_match" in existing_indexes:
        op.drop_index("ix_species_itis_name_match", "species")

    with op.batch_alter_table("species") as batch_op:
        for col in ("itis_checked_at", "itis_name_match", "itis_accepted_name", "itis_tsn"):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass
