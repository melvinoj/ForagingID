"""Add phenological fields to species table

Phase 10.6 — Section 5: Phenological Schema.

Adds four additive, nullable columns to the species table:

  flower_months  VARCHAR(50)  — CSV months e.g. "4,5,6,7"
  fruit_months   VARCHAR(50)  — CSV months e.g. "8,9,10"
  leaf_months    VARCHAR(50)  — CSV months e.g. "3,4,5,6"
  peak_season    TEXT         — free-text harvest note

All nullable with no defaults — existing rows unaffected.
Fallback logic (photo_taken_at month proxy) used when all four are NULL.
render_as_batch=True for SQLite compatibility.

Revision ID: 0007_add_phenological_fields
Revises: 0006_conditional_edibility_schema
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_add_phenological_fields"
down_revision: Union[str, None] = "0006_conditional_edibility_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("species")}

    new_cols = [
        ("flower_months", sa.String(50)),
        ("fruit_months",  sa.String(50)),
        ("leaf_months",   sa.String(50)),
        ("peak_season",   sa.Text()),
    ]

    missing = [(name, typ) for name, typ in new_cols if name not in existing_cols]

    if missing:
        with op.batch_alter_table("species", recreate="auto") as batch_op:
            for col_name, col_type in missing:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("species", recreate="auto") as batch_op:
        for col_name in ("peak_season", "leaf_months", "fruit_months", "flower_months"):
            try:
                batch_op.drop_column(col_name)
            except Exception:
                pass
