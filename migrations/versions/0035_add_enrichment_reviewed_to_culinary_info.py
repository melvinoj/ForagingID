"""Add enrichment_reviewed to culinary_info — decouple enrichment-text review from edibility verdict

Revision ID: 0035_add_enrichment_reviewed_to_culinary_info
Revises:     0034_add_recorded_walk_to_foraging_sessions
Create Date: 2026-06-15

enrichment_reviewed tracks whether a curator has signed off on the AI-generated enrichment
text (edible_parts, preparation_warnings, look_alike_warnings, AI drafts) for a species.
It replaces the previous misuse of edibility_verified as a proxy for "enrichment text reviewed."

edibility_verified remains the sole write-path for "a human has confirmed the species
edibility verdict" and is only written via the Edibility tab (PATCH /api/edibility/status).
"""
from alembic import op
import sqlalchemy as sa

revision      = "0035_add_enrichment_reviewed_to_culinary_info"
down_revision = "0034_add_recorded_walk_to_foraging_sessions"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("culinary_info") as batch_op:
        batch_op.add_column(
            sa.Column(
                "enrichment_reviewed",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("culinary_info") as batch_op:
        batch_op.drop_column("enrichment_reviewed")
