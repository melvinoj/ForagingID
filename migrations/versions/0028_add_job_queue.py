"""Add job_queue table

Revision ID: 0028_add_job_queue
Revises:     0027_add_notes_to_culinary_info_history
Create Date: 2026-06-07

Additive only — new table for the universal job queue panel.
Stores all pipeline operations (filter/identify/enrich/p1_scan/re_enrich)
with status, progress, and payload so the UI panel persists across server
restarts and browser navigation.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0028_add_job_queue"
down_revision = "0027_add_notes_to_culinary_info_history"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    )}

    if "job_queue" not in existing:
        op.create_table(
            "job_queue",
            sa.Column("id",               sa.Integer,  primary_key=True, autoincrement=True),
            sa.Column("job_type",         sa.String(32),  nullable=False),
            sa.Column("label",            sa.Text(),      nullable=False),
            sa.Column("status",           sa.String(16),  nullable=False, server_default="queued"),
            sa.Column("queue_position",   sa.Integer,     nullable=True),
            sa.Column("progress_current", sa.Integer,     nullable=False, server_default="0"),
            sa.Column("progress_total",   sa.Integer,     nullable=False, server_default="0"),
            sa.Column("payload",          sa.Text(),      nullable=True),
            sa.Column("created_at",       sa.DateTime(),  nullable=False),
            sa.Column("started_at",       sa.DateTime(),  nullable=True),
            sa.Column("ended_at",         sa.DateTime(),  nullable=True),
            sa.Column("error_message",    sa.Text(),      nullable=True),
        )


def downgrade() -> None:
    op.drop_table("job_queue")
