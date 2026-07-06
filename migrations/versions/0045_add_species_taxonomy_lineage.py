"""Add GBIF full-lineage metadata columns to species

Additive-only taxonomic data layer (Unit A). Adds the missing rank columns and
GBIF match-metadata columns to `species`. Descriptive metadata only — never read
by identification, confidence scoring, auto-approve routing, or edibility logic.

Reuses existing columns and does NOT duplicate them:
  - kingdom / family / genus already exist (migrations pre-0040 + 0040) — left as-is
  - the canonical GBIF key is the existing `gbif_usage_key` (INTEGER, migration
    0040) — no separate gbif_taxon_key column is added

New columns (all nullable):
  - phylum                 String(100)
  - class_                 String(100)   (DB name class_ — dodges reserved word CLASS)
  - order_                 String(100)   (DB name order_ — dodges reserved word ORDER)
  - gbif_match_type        String(20)    EXACT | FUZZY | HIGHERRANK | NONE
  - gbif_match_confidence  Integer

render_as_batch via batch_alter_table. Does NOT drop or alter existing columns.

Revision ID: 0045_add_species_taxonomy_lineage
Revises:     0044_add_species_synonyms
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0045_add_species_taxonomy_lineage"
down_revision = "0044_add_species_synonyms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.add_column(sa.Column("phylum", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("class_", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("order_", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("gbif_match_type", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("gbif_match_confidence", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.drop_column("gbif_match_confidence")
        batch_op.drop_column("gbif_match_type")
        batch_op.drop_column("order_")
        batch_op.drop_column("class_")
        batch_op.drop_column("phylum")
