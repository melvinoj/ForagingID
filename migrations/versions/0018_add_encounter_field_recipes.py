"""add field_recipes to encounters

Phase 12 — Field Recipes. Stores a JSON field recipe artefact on the encounter
record. One recipe per encounter. Linked to species via ingredients[].species_id.

Revision ID: 0018_add_encounter_field_recipes
Revises: 0017_add_species_foraging_notes
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_add_encounter_field_recipes"
down_revision = "0017_add_species_foraging_notes"
branch_labels = None
depends_on = None


def _enc_columns() -> set:
    return {
        r[1] for r in op.get_bind().execute(
            sa.text("PRAGMA table_info(encounters)")
        ).fetchall()
    }


def upgrade() -> None:
    cols = _enc_columns()
    if "field_recipes" not in cols:
        op.add_column(
            "encounters",
            sa.Column("field_recipes", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("encounters", "field_recipes")
