"""add files_skipped column to scan_sessions

Tracks non-image files (JSON sidecars, .mp, etc.) that are rejected
at intake before entering the pipeline — distinct from 'failed' which
means a pipeline error on a real image file.

Revision ID: 0020_add_files_skipped_to_scan_sessions
Revises: 0019_add_data_source_seeds_v2
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_add_files_skipped_to_scan_sessions"
down_revision = "0019_add_data_source_seeds_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {row[1] for row in bind.execute(
        sa.text("PRAGMA table_info(scan_sessions)")
    ).fetchall()}
    if "files_skipped" not in cols:
        op.add_column(
            "scan_sessions",
            sa.Column("files_skipped", sa.Integer, nullable=False, server_default="0"),
        )


def downgrade() -> None:
    # SQLite does not support DROP COLUMN before 3.35; leave in place.
    pass
