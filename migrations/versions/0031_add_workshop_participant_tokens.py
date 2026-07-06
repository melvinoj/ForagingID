"""Add workshop_participants and guest_tokens tables

Revision ID: 0031_add_workshop_participant_tokens
Revises:     0030_add_medicinal_clinical_to_culinary_info
Create Date: 2026-06-12

Phase 13.1 — durable-identity foundation.
- workshop_participants: names + notes; curator reserves id/user_id=1 (never in this table).
- guest_tokens: UUID token → participant_id + workshop_session_id scoping.
- Sequence seeded so first participant insert yields id=2.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0031_add_workshop_participant_tokens"
down_revision = "0030_add_medicinal_clinical_to_culinary_info"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "workshop_participants",
        sa.Column("id",         sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("name",       sa.Text(),     nullable=False),
        sa.Column("notes",      sa.Text(),     nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_table(
        "guest_tokens",
        sa.Column("id",                  sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("token",               sa.Text(),     nullable=False, unique=True),
        sa.Column("participant_id",      sa.Integer(),  sa.ForeignKey("workshop_participants.id"), nullable=True),
        sa.Column("workshop_session_id", sa.Integer(),  sa.ForeignKey("foraging_sessions.id"),     nullable=True),
        sa.Column("expires_at",          sa.DateTime(), nullable=False),
        sa.Column("is_active",           sa.Boolean(),  nullable=False, server_default=sa.text("1")),
        sa.Column("created_at",          sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_guest_tokens_token", "guest_tokens", ["token"], unique=True)
    # Reserve id=1 permanently so the first real participant insert yields id=2.
    # Curator uses user_id=1 and is never in this table; this tombstone makes
    # that invariant durable without requiring the SQLite AUTOINCREMENT keyword.
    # SQLite gives the next insert max(id)+1 = 2 as long as this row stays.
    op.execute("INSERT INTO workshop_participants(id, name) VALUES (1, '__reserved__')")


def downgrade() -> None:
    op.drop_table("guest_tokens")
    op.drop_table("workshop_participants")
