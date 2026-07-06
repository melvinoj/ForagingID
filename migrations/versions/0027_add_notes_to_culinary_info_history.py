"""Add notes column to culinary_info_history

Revision ID: 0027_add_notes_to_culinary_info_history
Revises:     0026_add_background_processes
Create Date: 2026-06-06

Additive only — nullable TEXT column.

Used by automated enrichment writers (e.g. fao_fungi+mushroom_observer) to
store source context alongside the field-value change. Human edits leave it NULL.
"""
from alembic import op
import sqlalchemy as sa

revision      = "0027_add_notes_to_culinary_info_history"
down_revision = "0026_add_background_processes"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    with op.batch_alter_table("culinary_info_history") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("culinary_info_history") as batch_op:
        batch_op.drop_column("notes")
