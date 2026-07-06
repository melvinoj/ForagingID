"""Add background_processes table

Revision ID: 0026_add_background_processes
Revises:     0025_add_review_label_to_observations
Create Date: 2026-06-05

Additive only — new table for durable long-running process state.
Covers enrichment_run, scan_session, itis_backfill and any future process.
Rows are never deleted — kept as an audit trail.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0026_add_background_processes"
down_revision = "0025_add_review_label_to_observations"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    )}

    if "background_processes" not in existing:
        op.create_table(
            "background_processes",
            sa.Column("process_id",       sa.Integer,      primary_key=True, autoincrement=True),
            sa.Column("process_type",     sa.String(32),   nullable=False),
            sa.Column("status",           sa.String(16),   nullable=False, server_default="running"),
            sa.Column("started_at",       sa.DateTime,     nullable=False,  server_default=sa.func.now()),
            sa.Column("updated_at",       sa.DateTime,     nullable=False,  server_default=sa.func.now()),
            sa.Column("last_heartbeat",   sa.DateTime,     nullable=True),
            sa.Column("progress_current", sa.Integer,      nullable=True,   server_default="0"),
            sa.Column("progress_total",   sa.Integer,      nullable=True,   server_default="0"),
            sa.Column("detail",           sa.String(255),  nullable=True),
            sa.Column("error",            sa.String(512),  nullable=True),
        )


def downgrade() -> None:
    op.drop_table("background_processes")
