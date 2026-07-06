"""Add species_edibility_conditions and species_lookalikes tables

Phase 10.6 — Conditional Edibility Schema.

  species_edibility_conditions — one row per (species, part, preparation, season)
    condition; safe boolean is the safety ruling for that combination.

  species_lookalikes — directed lookalike relationship; application queries both
    directions for bidirectional display.

Both tables are additive. No existing tables modified. render_as_batch=True for
SQLite compatibility.

Revision ID: 0006_conditional_edibility_schema
Revises: 0005_data_trust_columns
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_conditional_edibility_schema"
down_revision: Union[str, None] = "0005_data_trust_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # ── 1. species_edibility_conditions ─────────────────────────────────────
    if "species_edibility_conditions" not in existing_tables:
        op.create_table(
            "species_edibility_conditions",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("species_id", sa.Integer(), sa.ForeignKey("species.id"), nullable=False),
            sa.Column("part", sa.String(30), nullable=False),
            sa.Column("preparation", sa.String(30), nullable=False),
            sa.Column("season", sa.String(20), nullable=False, server_default="any"),
            sa.Column("safe", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.current_timestamp()),
        )
        op.create_index(
            "ix_species_edibility_conditions_species_id",
            "species_edibility_conditions",
            ["species_id"],
        )

    # ── 2. species_lookalikes ────────────────────────────────────────────────
    if "species_lookalikes" not in existing_tables:
        op.create_table(
            "species_lookalikes",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("species_id", sa.Integer(), sa.ForeignKey("species.id"), nullable=False),
            sa.Column("lookalike_species_id", sa.Integer(), sa.ForeignKey("species.id"),
                      nullable=True),
            sa.Column("lookalike_name", sa.String(200), nullable=False),
            sa.Column("distinguishing_notes", sa.Text(), nullable=True),
            sa.Column("toxicity_level", sa.String(20), nullable=False,
                      server_default="caution"),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.current_timestamp()),
        )
        op.create_index(
            "ix_species_lookalikes_species_id",
            "species_lookalikes",
            ["species_id"],
        )
        op.create_index(
            "ix_species_lookalikes_lookalike_species_id",
            "species_lookalikes",
            ["lookalike_species_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "species_lookalikes" in existing_tables:
        op.drop_index("ix_species_lookalikes_lookalike_species_id", "species_lookalikes")
        op.drop_index("ix_species_lookalikes_species_id", "species_lookalikes")
        op.drop_table("species_lookalikes")

    if "species_edibility_conditions" in existing_tables:
        op.drop_index("ix_species_edibility_conditions_species_id",
                      "species_edibility_conditions")
        op.drop_table("species_edibility_conditions")
