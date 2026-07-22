"""Pass B Phase 1 — additive columns on background_processes (dual-write groundwork)

Adds six NULLABLE columns to background_processes so that a later phase can
dual-write job_queue's shape onto bp rows (Pass B store-merge). This phase is
schema-only: NO code reads or writes these columns, NO behaviour changes.

Columns mirror job_queue (migration 0028) exactly in type/intent:
  queue_position  INTEGER   -- job_queue ordering; bp had none
  payload         TEXT      -- JSON string for rerun; TEXT for SQLite+Postgres safety
  created_at      DateTime  -- enqueued-vs-started distinction; bp had started_at only
  ended_at        DateTime  -- terminal timestamp; bp had updated_at only
  label           TEXT      -- fixed job name (distinct from bp.detail, the mutating step)
  error_text      TEXT      -- unbounded error; mirrors job_queue.error_message

All six are nullable (existing rows have no values). NOTHING is NOT NULL and no
server_default is applied, so no table rewrite is forced.

error handling: bp.error stays VARCHAR(512), UNTOUCHED. We add error_text (TEXT)
rather than widen error. In SQLite VARCHAR(512) and TEXT share TEXT affinity, so
widening is a functional no-op, but alter_column would force a batch table-recreate
(full rewrite); add_column is a native ALTER TABLE ADD COLUMN (no rewrite). Adding
error_text keeps the whole migration native-ADD and strictly additive. Phase 2
dual-write targets error_text; a later phase may retire error once reads repoint.

status: no change. background_processes.status is free-text VARCHAR(16) with no
CHECK/enum, so 'queued' is already a storable value — no DDL needed to admit it.

Revision ID: 0051_bp_dualwrite_columns
Revises: 0050_add_triage_keep
"""
from alembic import op
import sqlalchemy as sa

revision = "0051_bp_dualwrite_columns"
down_revision = "0050_add_triage_keep"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("background_processes", sa.Column("queue_position", sa.Integer(), nullable=True))
    op.add_column("background_processes", sa.Column("payload", sa.Text(), nullable=True))
    op.add_column("background_processes", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("background_processes", sa.Column("ended_at", sa.DateTime(), nullable=True))
    op.add_column("background_processes", sa.Column("label", sa.Text(), nullable=True))
    op.add_column("background_processes", sa.Column("error_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("background_processes", "error_text")
    op.drop_column("background_processes", "label")
    op.drop_column("background_processes", "ended_at")
    op.drop_column("background_processes", "created_at")
    op.drop_column("background_processes", "payload")
    op.drop_column("background_processes", "queue_position")
