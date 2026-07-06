"""Add client_uuid to encounters for offline write-queue idempotency

Revision ID: 0032_add_encounter_client_uuid
Revises:     0031_add_workshop_participant_tokens
Create Date: 2026-06-13

Phase 13.10b — offline encounter write queue.
- client_uuid: client-generated UUID per encounter (the idempotency key). Generated
  at capture time, before any network attempt, and sent with the POST so a replayed
  request whose first response was lost to flaky cellular returns the existing row
  instead of creating a duplicate.
- Nullable + unique. Nullable keeps old clients (which send no client_uuid) working.
  In SQLite a UNIQUE index treats NULLs as distinct, so any number of legacy
  client_uuid-less rows coexist; only non-NULL values must be unique.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0032_add_encounter_client_uuid"
down_revision = "0031_add_workshop_participant_tokens"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column("encounters", sa.Column("client_uuid", sa.Text(), nullable=True))
    op.create_index("ix_encounters_client_uuid", "encounters", ["client_uuid"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_encounters_client_uuid", table_name="encounters")
    op.drop_column("encounters", "client_uuid")
