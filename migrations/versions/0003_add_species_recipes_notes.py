"""add species_recipes.notes for rename/review flagging

Additive only — adds a nullable TEXT column. Idempotent.

Revision ID: 0003_add_species_recipes_notes
Revises: 0002_add_obs_species_id
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_species_recipes_notes"
down_revision: Union[str, None] = "0002_add_obs_species_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "species_recipes", "notes"):
        op.add_column(
            "species_recipes",
            sa.Column("notes", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "species_recipes", "notes"):
        with op.batch_alter_table("species_recipes") as batch:
            batch.drop_column("notes")
