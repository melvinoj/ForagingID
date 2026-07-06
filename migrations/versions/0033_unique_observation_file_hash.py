"""UNIQUE index on observations.file_hash — close the P1/P2 dedup race

Revision ID: 0033_unique_observation_file_hash
Revises:     0032_add_encounter_client_uuid
Create Date: 2026-06-14

Tier-2 resilience. The file_hash dedup was a check-then-insert SELECT with no DB-level
guard, so concurrent P1 (Syncthing) / P2 (browser upload) ingest of the same image
could insert duplicate observations. Replace the non-unique ix_observations_file_hash
with a UNIQUE index so the database enforces one row per content hash; the insert paths
catch IntegrityError and return the existing row (same pattern as encounters.client_uuid).

SQLite treats NULLs as distinct in a UNIQUE index, so any hash-less rows (none today)
remain valid.

Pre-requisite (done 2026-06-14 before this migration): existing duplicates resolved —
removed 2 byte-identical rejected dups of hash 742d4bc… (kept observation 16005). The
unique index would otherwise fail to build on live data.
"""
from alembic import op

revision      = "0033_unique_observation_file_hash"
down_revision = "0032_add_encounter_client_uuid"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.drop_index("ix_observations_file_hash", table_name="observations")
    op.create_index("ix_observations_file_hash", "observations", ["file_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_observations_file_hash", table_name="observations")
    op.create_index("ix_observations_file_hash", "observations", ["file_hash"], unique=False)
