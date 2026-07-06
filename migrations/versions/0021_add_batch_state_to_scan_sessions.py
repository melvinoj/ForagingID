"""Add durable batch state columns to scan_sessions + delete stale P2 sessions

Adds five columns to scan_sessions (all nullable / defaulted so existing rows
are untouched):

  status                TEXT     DEFAULT 'complete'
  last_heartbeat        DATETIME NULL
  files_new             INTEGER  DEFAULT 0
  files_retryable       INTEGER  DEFAULT 0
  files_already_processed INTEGER DEFAULT 0

After the ALTER TABLE statements, deletes all pipeline = 2 rows.  This is safe:
the observations table has no scan_session_id column — there is no FK link —
so no observation record is affected.  The 63 identified P2 observations remain
untouched.  New batches will get proper durable state from the start.

Revision ID: 0021_add_batch_state_to_scan_sessions
Revises:     0020_add_files_skipped_to_scan_sessions
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision      = "0021_add_batch_state_to_scan_sessions"
down_revision = "0020_add_files_skipped_to_scan_sessions"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {row[1] for row in bind.execute(
        sa.text("PRAGMA table_info(scan_sessions)")
    ).fetchall()}

    if "status" not in cols:
        op.add_column(
            "scan_sessions",
            sa.Column("status", sa.Text, nullable=True, server_default="complete"),
        )

    if "last_heartbeat" not in cols:
        op.add_column(
            "scan_sessions",
            sa.Column("last_heartbeat", sa.DateTime, nullable=True),
        )

    if "files_new" not in cols:
        op.add_column(
            "scan_sessions",
            sa.Column("files_new", sa.Integer, nullable=False, server_default="0"),
        )

    if "files_retryable" not in cols:
        op.add_column(
            "scan_sessions",
            sa.Column("files_retryable", sa.Integer, nullable=False, server_default="0"),
        )

    if "files_already_processed" not in cols:
        op.add_column(
            "scan_sessions",
            sa.Column("files_already_processed", sa.Integer, nullable=False, server_default="0"),
        )

    # Backfill status on all existing rows that have ended_at set — they are
    # complete by definition.  Rows with ended_at NULL are implicitly stalled
    # (server was killed mid-run); mark them accordingly so the UI can surface
    # them without special-casing NULL.
    bind.execute(sa.text(
        "UPDATE scan_sessions SET status = 'complete' WHERE ended_at IS NOT NULL AND status IS NULL"
    ))
    bind.execute(sa.text(
        "UPDATE scan_sessions SET status = 'stalled' WHERE ended_at IS NULL AND status IS NULL"
    ))

    # Delete all stale Pipeline 2 sessions.  Confirmed safe: observations has
    # no scan_session_id FK; the 63 P2 observation records are unaffected.
    bind.execute(sa.text("DELETE FROM scan_sessions WHERE pipeline = 2"))


def downgrade() -> None:
    # SQLite does not support DROP COLUMN before 3.35; leave columns in place.
    # Deleted rows cannot be restored here — downgrade is a no-op for the DELETE.
    pass
