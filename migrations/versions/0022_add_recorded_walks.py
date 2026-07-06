"""Add recorded_walks and recorded_walk_observations tables

Revision ID: 0022_add_recorded_walks
Revises:     0021_add_batch_state_to_scan_sessions
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision      = "0022_add_recorded_walks"
down_revision = "0021_add_batch_state_to_scan_sessions"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Tables may already exist if create_all ran before migration — skip gracefully.
    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))}
    if "recorded_walks" in existing and "recorded_walk_observations" in existing:
        return

    op.create_table(
        "recorded_walks",
        sa.Column("id",                 sa.Integer,  primary_key=True),
        sa.Column("name",               sa.String(200), nullable=False),
        sa.Column("started_at",         sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at",           sa.DateTime(timezone=True), nullable=True),
        sa.Column("distance_m",         sa.Float,    nullable=True),
        sa.Column("duration_s",         sa.Integer,  nullable=True),
        sa.Column("elevation_gain_m",   sa.Float,    nullable=True),
        sa.Column("elevation_loss_m",   sa.Float,    nullable=True),
        sa.Column("track_points_json",  sa.Text,     nullable=False, server_default="[]"),
        sa.Column("audio_note_path",    sa.String(500), nullable=True),
        sa.Column("created_at",         sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "recorded_walk_observations",
        sa.Column("id",              sa.Integer, primary_key=True),
        sa.Column("recorded_walk_id", sa.Integer, sa.ForeignKey("recorded_walks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("observation_id",  sa.Integer, nullable=False),
        sa.Column("encountered_at",  sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("recorded_walk_observations")
    op.drop_table("recorded_walks")
