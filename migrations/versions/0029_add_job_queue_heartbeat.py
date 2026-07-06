"""Add last_heartbeat column to job_queue

Revision ID: 0029_add_job_queue_heartbeat
Revises:     0028_add_job_queue
Create Date: 2026-06-07

Additive only — adds last_heartbeat to job_queue so server-driven jobs can
signal liveness, enabling stale / interrupted detection on startup and list load.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0029_add_job_queue_heartbeat"
down_revision = "0028_add_job_queue"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {row[1] for row in bind.execute(sa.text("PRAGMA table_info(job_queue)"))}
    if "last_heartbeat" not in cols:
        op.add_column("job_queue", sa.Column("last_heartbeat", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # SQLite does not support DROP COLUMN in older versions; leave as-is.
    pass
