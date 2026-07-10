"""Add species_edibility_history table (audit trail for the edibility verdict)

New standing history table for species.edibility_status (and room for
edibility_verified later, via the `field` column). No writer has ever logged
edits to this field before this migration — PATCH /api/edibility/status/{id}
and PATCH /api/edibility/bulk-status (app/api/edibility.py) are updated
alongside this migration to insert into it.

Forward-only: does NOT backfill existing edibility_status changes. Those
predate this table and live only as unstructured entries in
culinary_info_history and CHANGELOG.md from one-off curator sessions — not
reconstructed here.

Idempotent guarded CREATE — same pattern as 0044_add_species_synonyms
(no-ops if init_db()'s create_all already bootstrapped the table from the
SpeciesEdibilityHistory model / app/main.py noqa import), then stamps head.

This is a CREATE TABLE, not an ALTER — batch_alter_table (Alembic's SQLite
ALTER-emulation shim) isn't needed here; op.create_table is already
SQLite/Postgres-portable on its own. Matches 0044's own approach.

Revision ID: 0046_add_species_edibility_history
Revises:     0045_add_species_taxonomy_lineage
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0046_add_species_edibility_history"
down_revision = "0045_add_species_taxonomy_lineage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {t[0] for t in op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "species_edibility_history" not in existing:
        op.create_table(
            "species_edibility_history",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("species_id", sa.Integer, sa.ForeignKey("species.id"), nullable=False),
            sa.Column("field", sa.String(30), nullable=False),
            sa.Column("old_value", sa.Text, nullable=True),
            sa.Column("new_value", sa.Text, nullable=True),
            sa.Column("changed_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("changed_by", sa.String(100), nullable=False, server_default="human"),
            sa.Column("note", sa.Text, nullable=True),
        )
        op.create_index(
            "ix_species_edibility_history_species_id",
            "species_edibility_history",
            ["species_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_species_edibility_history_species_id", table_name="species_edibility_history")
    op.drop_table("species_edibility_history")
