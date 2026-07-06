"""add encounters table

Encounters capture in-field notes, audio memos, and Goethean observation prompts
linked to a confirmed species. Single-tenant for now (user_id always 1);
list_id and workshop_session_id are reserved nullable FKs for Phase 11a.3+.

Revision ID: 0010_add_encounters_table
Revises: 0009_add_scan_session_duplicate_count
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_add_encounters_table"
down_revision = "0009_add_scan_session_duplicate_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {t[0] for t in op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "encounters" not in existing:
        op.create_table(
            "encounters",
            sa.Column("id",                  sa.Integer,  primary_key=True, autoincrement=True),
            sa.Column("user_id",             sa.Integer,  nullable=False,   server_default="1"),
            sa.Column("species_id",          sa.Integer,  sa.ForeignKey("species.id"), nullable=True),
            sa.Column("observation_id",      sa.Integer,  sa.ForeignKey("observations.id"), nullable=True),
            sa.Column("list_id",             sa.Integer,  nullable=True),
            sa.Column("workshop_session_id", sa.Integer,  nullable=True),
            sa.Column("encounter_date",      sa.DateTime, nullable=False),
            sa.Column("latitude",            sa.Float,    nullable=True),
            sa.Column("longitude",           sa.Float,    nullable=True),
            sa.Column("location_name",       sa.Text,     nullable=True),
            sa.Column("audio_path",          sa.Text,     nullable=True),
            sa.Column("text_note",           sa.Text,     nullable=True),
            sa.Column("sketch_path",         sa.Text,     nullable=True),
            sa.Column("prompt_stage",        sa.Text,     nullable=True),
            sa.Column("prompt_response",     sa.Text,     nullable=True),
            sa.Column("research_visible",    sa.Boolean,  nullable=False,   server_default="1"),
            sa.Column("created_at",          sa.DateTime, nullable=False,   server_default=sa.func.now()),
        )
        op.create_index("ix_encounters_user_id",        "encounters", ["user_id"])
        op.create_index("ix_encounters_species_id",     "encounters", ["species_id"])
        op.create_index("ix_encounters_encounter_date", "encounters", ["encounter_date"])


def downgrade() -> None:
    op.drop_index("ix_encounters_encounter_date", "encounters")
    op.drop_index("ix_encounters_species_id",     "encounters")
    op.drop_index("ix_encounters_user_id",        "encounters")
    op.drop_table("encounters")
