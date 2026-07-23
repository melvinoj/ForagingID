"""Pass B Phase 3b — source_job_queue_id join key on background_processes

Adds ONE nullable INTEGER column, source_job_queue_id, to background_processes.
It is the explicit join key from a bp row back to its job_queue twin: the widget
currently de-dups the two feeds by matching job_type == process_type (a fragile
type-string heuristic — see Pass B Phase 3a census). This column lets a later
phase de-dup by identity instead.

TRANSITIONAL COLUMN — NOT permanent. It exists only for as long as BOTH feeds
(job_queue and background_processes) are live in parallel. In Pass B Phase 4,
when job_queue is retired and background_processes becomes the single store, this
column is dropped together with the job_queue table (there is nothing left to
point at). Do not build anything on it that must outlive job_queue.

This phase writes the column from exactly one live path (culinary._create_backfill_job,
the AI-draft/id-notes twin). Every other bp_start caller leaves it NULL. No reader
consumes it yet — de-dup repointing is a later phase.

Schema-only migration: native ALTER TABLE ADD COLUMN, nullable, no server_default,
no index, no table rewrite. env.py configures render_as_batch=True globally, so
these op.add_column/op.drop_column calls render in batch mode; on SQLite 3.35+
(here 3.51) batch resolves to a native ALTER (recreate='auto' — no rewrite for a
plain add/drop), keeping the downgrade DROP COLUMN reversible too.

Revision ID: 0052_bp_source_job_queue_id
Revises: 0051_bp_dualwrite_columns
"""
from alembic import op
import sqlalchemy as sa

revision = "0052_bp_source_job_queue_id"
down_revision = "0051_bp_dualwrite_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # env.py sets render_as_batch=True globally, so this renders in batch mode.
    op.add_column("background_processes", sa.Column("source_job_queue_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("background_processes", "source_job_queue_id")
