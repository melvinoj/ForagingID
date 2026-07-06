"""Add edibility_verified_by to species — provenance tracking for edibility_verified flag

Revision ID: 0036_add_edibility_verified_by
Revises:     0035_add_enrichment_reviewed_to_culinary_info
Create Date: 2026-06-15

edibility_verified_by records the provenance of the edibility_verified flag:
  'human'            — set by a curator via the Edibility tab
  'auto'             — set by automated pipeline with high confidence (PFAF rating >=4)
  'safety_constant'  — hardcoded safety rule (Pteridium aquilinum / bracken)
  'unlocked_for_review' — was auto-verified but confidence insufficient; unlocked for manual review
  NULL               — not yet verified (new species or explicitly unverified by curator)

Backfill is handled by init_db() on first server start after this migration.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0036_add_edibility_verified_by"
down_revision = "0035_add_enrichment_reviewed_to_culinary_info"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.add_column(
            sa.Column(
                "edibility_verified_by",
                sa.String(30),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.drop_column("edibility_verified_by")
