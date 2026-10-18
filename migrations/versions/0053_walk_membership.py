"""Walk membership by route proximity — per-walk rule columns on saved_walks

A saved walk's members are no longer only the observations stored at save time:
confirmed observations within buffer_m of the saved line, taken on or after
members_since, join it when it is loaded (app/services/walk_membership.py).
These columns hold the per-walk rule; membership itself is computed, never stored.

  buffer_m          FLOAT     distance from the line in metres; NULL = default (25 m)
  members_since     DATETIME  photos taken on/after this join; NULL = the walk's created_at
  excluded_obs_json TEXT      JSON list of observation ids removed from the walk by hand
  accepted_obs_json TEXT      JSON list of OLDER observation ids accepted from the
                              "older photos near this route" review list

All nullable, no server_default, no backfill — NULL means "use the default", so
existing walks behave exactly as the defaults say without a data write.

Revision ID: 0053_walk_membership
Revises: 0052_bp_source_job_queue_id
"""
from alembic import op
import sqlalchemy as sa

revision = "0053_walk_membership"
down_revision = "0052_bp_source_job_queue_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("saved_walks", sa.Column("buffer_m", sa.Float(), nullable=True))
    op.add_column("saved_walks", sa.Column("members_since", sa.DateTime(), nullable=True))
    op.add_column("saved_walks", sa.Column("excluded_obs_json", sa.Text(), nullable=True))
    op.add_column("saved_walks", sa.Column("accepted_obs_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("saved_walks", "accepted_obs_json")
    op.drop_column("saved_walks", "excluded_obs_json")
    op.drop_column("saved_walks", "members_since")
    op.drop_column("saved_walks", "buffer_m")
