"""Add foraging_sessions, session_species, session_attendees tables

Revision ID: 0024_add_foraging_sessions
Revises:     0023_add_itis_fields_to_species
Create Date: 2026-06-04

Additive only — three new tables for the Session/Foray model.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0024_add_foraging_sessions"
down_revision = "0023_add_itis_fields_to_species"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))}

    if "foraging_sessions" not in existing:
        op.create_table(
            "foraging_sessions",
            sa.Column("id",                 sa.Integer,     primary_key=True),
            sa.Column("name",               sa.String(200), nullable=False),
            sa.Column("status",             sa.String(20),  nullable=False, server_default="draft"),
            sa.Column("walk_id",            sa.Integer,     sa.ForeignKey("saved_walks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("location_override",  sa.Text,        nullable=True),
            sa.Column("session_date",       sa.String(10),  nullable=True),   # ISO date YYYY-MM-DD
            sa.Column("facilitator_notes",  sa.Text,        nullable=True),
            sa.Column("created_at",         sa.DateTime,    server_default=sa.func.now()),
            sa.Column("updated_at",         sa.DateTime,    server_default=sa.func.now()),
        )

    if "session_species" not in existing:
        op.create_table(
            "session_species",
            sa.Column("id",            sa.Integer, primary_key=True),
            sa.Column("session_id",    sa.Integer, sa.ForeignKey("foraging_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("species_id",    sa.Integer, sa.ForeignKey("species.id",           ondelete="CASCADE"), nullable=False),
            sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("source",        sa.String(20), nullable=False, server_default="manual"),
            sa.Column("added_at",      sa.DateTime, server_default=sa.func.now()),
        )

    if "session_attendees" not in existing:
        op.create_table(
            "session_attendees",
            sa.Column("id",            sa.Integer, primary_key=True),
            sa.Column("session_id",    sa.Integer, sa.ForeignKey("foraging_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name",          sa.Text,    nullable=False),
            sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_table("session_attendees")
    op.drop_table("session_species")
    op.drop_table("foraging_sessions")
