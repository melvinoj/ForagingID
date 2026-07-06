"""Add species.toxicity_severity + backfill deadly/toxic classification

Revision ID: 0039_add_toxicity_severity
Revises:     0038_name_key_not_null_unique
Create Date: 2026-06-17

Schema + data only — no render/template changes. Adds a structured severity
field the safety-render rebuild will read, so DEADLY species can be styled
distinctly from merely TOXIC ones (today the only signal is free-text in
preparation_warnings, which is fragile).

Column: species.toxicity_severity  String(20)  NOT NULL  default 'none'
Allowed values: 'none' | 'toxic' | 'deadly'

Backfill (single transaction):
  - 'deadly' for exactly four named species (lethal, commonly confused with
    edibles): Conium maculatum, Aconitum napellus, Taxus baccata,
    Helleborus foetidus.
  - 'toxic' for every other species with edibility_status in ('toxic',
    'inedible') not already set to 'deadly'.
  - all others remain 'none'.

Guard: if the four deadly names do not each match exactly one row, the
migration raises and the whole transaction rolls back (no partial state).
"""
from alembic import op
import sqlalchemy as sa

revision      = "0039_add_toxicity_severity"
down_revision = "0038_name_key_not_null_unique"
branch_labels = None
depends_on    = None

_DEADLY = [
    "Conium maculatum",
    "Aconitum napellus",
    "Taxus baccata",
    "Helleborus foetidus",
]


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add the column NOT NULL with a 'none' default so existing rows are
    #    valid immediately. SQLite-safe via batch_alter_table.
    with op.batch_alter_table("species") as batch_op:
        batch_op.add_column(
            sa.Column(
                "toxicity_severity",
                sa.String(20),
                nullable=False,
                server_default="none",
            )
        )

    # 2. Mark the four deadly species by exact scientific_name.
    res = bind.execute(
        sa.text(
            "UPDATE species SET toxicity_severity = 'deadly' "
            "WHERE scientific_name IN (:n0, :n1, :n2, :n3)"
        ),
        {f"n{i}": name for i, name in enumerate(_DEADLY)},
    )

    # 2a. Guard — every deadly name must have matched exactly one row.
    #     If not, raise to roll back the entire transaction (no partial write).
    deadly_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM species WHERE toxicity_severity = 'deadly'")
    ).scalar()
    if deadly_count != len(_DEADLY):
        found = bind.execute(
            sa.text(
                "SELECT scientific_name FROM species WHERE toxicity_severity = 'deadly'"
            )
        ).scalars().all()
        missing = sorted(set(_DEADLY) - set(found))
        raise RuntimeError(
            f"Deadly backfill matched {deadly_count} rows, expected {len(_DEADLY)}. "
            f"Missing/unmatched: {missing}. Rolling back."
        )

    # 3. Mark remaining toxic/inedible species as 'toxic' (never overwrite
    #    the four already set to 'deadly').
    bind.execute(
        sa.text(
            "UPDATE species SET toxicity_severity = 'toxic' "
            "WHERE edibility_status IN ('toxic', 'inedible') "
            "AND toxicity_severity = 'none'"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("species") as batch_op:
        batch_op.drop_column("toxicity_severity")
