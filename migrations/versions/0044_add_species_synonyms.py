"""Add species_synonyms table (taxonomic-synonym resolution layer)

Maps an older/alternate accepted scientific name to the species row that now
carries the currently-accepted name, so a name_key lookup miss on a known
synonym resolves to the existing card instead of creating a duplicate.

Idempotent: guarded CREATE so it no-ops on a DB where init_db()'s create_all
already bootstrapped the table (SpeciesSynonym model, app/main.py noqa
import), then stamps head — same pattern as 0015_add_notification_dismissals.

Revision ID: 0044_add_species_synonyms
Revises:     0043_species_photo_taken_idx
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_add_species_synonyms"
down_revision = "0043_species_photo_taken_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {t[0] for t in op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "species_synonyms" not in existing:
        op.create_table(
            "species_synonyms",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("synonym_name_key", sa.String(200), nullable=False, unique=True),
            sa.Column("synonym_scientific_name", sa.String(200), nullable=False),
            sa.Column("canonical_species_id", sa.Integer, sa.ForeignKey("species.id"), nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_species_synonyms_canonical_species_id", "species_synonyms", ["canonical_species_id"])


def downgrade() -> None:
    op.drop_index("ix_species_synonyms_canonical_species_id", "species_synonyms")
    op.drop_table("species_synonyms")
