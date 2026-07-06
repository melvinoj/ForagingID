"""add scan_sessions table

Revision ID: 0008_add_scan_sessions
Revises: 0007_add_phenological_fields
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_add_scan_sessions"
down_revision = "0007_add_phenological_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {t[0] for t in op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "scan_sessions" not in existing:
        op.create_table(
            "scan_sessions",
            sa.Column("id",              sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("pipeline",        sa.Integer, nullable=False),
            sa.Column("label",           sa.Text,    nullable=False),
            sa.Column("started_at",      sa.DateTime, nullable=False),
            sa.Column("ended_at",        sa.DateTime, nullable=True),
            sa.Column("files_received",  sa.Integer, nullable=False, server_default="0"),
            sa.Column("files_processed", sa.Integer, nullable=False, server_default="0"),
            sa.Column("files_approved",  sa.Integer, nullable=False, server_default="0"),
            sa.Column("files_review",    sa.Integer, nullable=False, server_default="0"),
            sa.Column("files_rejected",  sa.Integer, nullable=False, server_default="0"),
            sa.Column("files_failed",    sa.Integer, nullable=False, server_default="0"),
            sa.Column("source_path",     sa.Text,    nullable=True),
        )
        op.create_index("ix_scan_sessions_pipeline", "scan_sessions", ["pipeline"])
        op.create_index("ix_scan_sessions_started_at", "scan_sessions", ["started_at"])


def downgrade() -> None:
    op.drop_table("scan_sessions")
