"""add observations.species_id FK (additive) + backfill by scientific_name

Additive only: species_primary remains the display cache. species_id is the
new canonical FK, backfilled from the existing scientific_name match. Rows
whose species_primary has no matching Species row get species_id = NULL.

Idempotent: skips the ADD COLUMN if the column already exists (a fresh DB
built by Base.metadata.create_all already has it).

Revision ID: 0002_add_obs_species_id
Revises: 0001_baseline
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_obs_species_id"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def _has_index(bind, table: str, index: str) -> bool:
    insp = sa.inspect(bind)
    return index in {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # Nullable ADD COLUMN is natively supported by SQLite — use a plain
    # ALTER (no batch table-recreate) so this is fast and non-destructive
    # even if another connection has the DB open.
    if not _has_column(bind, "observations", "species_id"):
        op.add_column(
            "observations", sa.Column("species_id", sa.Integer(), nullable=True)
        )

    if not _has_index(bind, "observations", "ix_observations_species_id"):
        op.create_index(
            "ix_observations_species_id", "observations", ["species_id"]
        )

    # Backfill by exact scientific_name match. Rows with no matching Species
    # row are left NULL.
    op.execute(
        """
        UPDATE observations
        SET species_id = (
            SELECT s.id FROM species s
            WHERE s.scientific_name = observations.species_primary
        )
        WHERE species_primary IS NOT NULL
          AND species_id IS NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, "observations", "ix_observations_species_id"):
        op.drop_index("ix_observations_species_id", table_name="observations")
    if _has_column(bind, "observations", "species_id"):
        with op.batch_alter_table("observations") as batch:
            batch.drop_column("species_id")
