"""Add recorded_walk_id to foraging_sessions — enables GPS timestamp-match for location suggestions

Revision ID: 0034_add_recorded_walk_to_foraging_sessions
Revises:     0033_unique_observation_file_hash
Create Date: 2026-06-14

Tier 4. Foraging sessions need to reference the timestamped GPS track (recorded_walks)
so post-foray location suggestions can be generated for text-only encounters that
captured no coordinates.

ForagingSession.walk_id → saved_walks (curated walk, no timestamps) remains.
The new recorded_walk_id → recorded_walks (raw GPS track with {lat,lng,ts} points).
A session can have one or both or neither; they serve different purposes.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0034_add_recorded_walk_to_foraging_sessions"
down_revision = "0033_unique_observation_file_hash"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("foraging_sessions") as batch_op:
        batch_op.add_column(sa.Column("recorded_walk_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_foraging_sessions_recorded_walk",
            "recorded_walks",
            ["recorded_walk_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("foraging_sessions") as batch_op:
        batch_op.drop_constraint("fk_foraging_sessions_recorded_walk", type_="foreignkey")
        batch_op.drop_column("recorded_walk_id")
