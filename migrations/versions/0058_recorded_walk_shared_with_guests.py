"""recorded_walks.shared_with_guests — per-walk "Show to guests" (22 Oct 2026)

Recorded walks are curator recordings. Workshop participants see one (list,
detail, trace) only when the curator switches it on (Melvin, 22 Oct 2026).
Additive, default off: every existing recorded walk becomes hidden from
guests. The audio note stays curator-only either way (guest_access.py).

Revision ID: 0058_recorded_walk_shared_with_guests
Revises: 0057_encounter_shared_with_guests
"""
from alembic import op
import sqlalchemy as sa

revision = "0058_recorded_walk_shared_with_guests"
down_revision = "0057_encounter_shared_with_guests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recorded_walks") as batch_op:
        batch_op.add_column(sa.Column("shared_with_guests", sa.Boolean(), nullable=False,
                                      server_default=sa.text("0")))


def downgrade() -> None:
    with op.batch_alter_table("recorded_walks") as batch_op:
        batch_op.drop_column("shared_with_guests")
