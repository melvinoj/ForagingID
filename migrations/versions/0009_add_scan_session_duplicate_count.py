"""add files_duplicate counter to scan_sessions

Separates duplicate-hash skips from pre-filter rejects so the scan page can
show a full pipeline breakdown (received = prefilter + duplicate + failed +
completed). Existing rows default to 0 — historical batches predate this split,
so their duplicate count is unknown and reported as such in the UI.

Revision ID: 0009_add_scan_session_duplicate_count
Revises: 0008_add_scan_sessions
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_add_scan_session_duplicate_count"
down_revision = "0008_add_scan_sessions"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    rows = op.get_bind().execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def upgrade() -> None:
    if "files_duplicate" not in _columns("scan_sessions"):
        op.add_column(
            "scan_sessions",
            sa.Column("files_duplicate", sa.Integer, nullable=False, server_default="0"),
        )


def downgrade() -> None:
    # SQLite supports DROP COLUMN from 3.35+; guard for older builds.
    if "files_duplicate" in _columns("scan_sessions"):
        with op.batch_alter_table("scan_sessions") as batch:
            batch.drop_column("files_duplicate")
