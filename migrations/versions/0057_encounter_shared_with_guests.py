"""encounters.shared_with_guests — per-encounter "Share with guests" (batch 8)

Curator encounters are invisible to workshop participants unless the curator
marks one shareable (Melvin, 22 Oct 2026). Additive, default off: every
existing encounter stays private. Participants' own notes never need it —
they always see their own (app.services.guest_access.encounter_visible_to).

Revision ID: 0057_encounter_shared_with_guests
Revises: 0056_device_tokens
"""
from alembic import op
import sqlalchemy as sa

revision = "0057_encounter_shared_with_guests"
down_revision = "0056_device_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("encounters") as batch_op:
        batch_op.add_column(sa.Column("shared_with_guests", sa.Boolean(), nullable=False,
                                      server_default=sa.text("0")))


def downgrade() -> None:
    with op.batch_alter_table("encounters") as batch_op:
        batch_op.drop_column("shared_with_guests")
