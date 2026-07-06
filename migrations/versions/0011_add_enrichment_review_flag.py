"""add manual enrichment-review flag to culinary_info

Phase 11a.2 — lock down species cards to a single canonical write path. The
species card and Lists enrichment dropdown lose their inline edit/save fields;
the only way to change canonical enrichment data is now the enrichment review
tab. The "Send to review" button sets review_requested=1 so the species surfaces
in that queue regardless of its data confidence. Existing rows default to 0.

Revision ID: 0011_add_enrichment_review_flag
Revises: 0010_add_encounters_table
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_add_enrichment_review_flag"
down_revision = "0010_add_encounters_table"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    rows = op.get_bind().execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def upgrade() -> None:
    cols = _columns("culinary_info")
    if "review_requested" not in cols:
        op.add_column(
            "culinary_info",
            sa.Column("review_requested", sa.Boolean, nullable=False, server_default="0"),
        )
    if "review_requested_at" not in cols:
        op.add_column(
            "culinary_info",
            sa.Column("review_requested_at", sa.DateTime, nullable=True),
        )
    if "review_request_note" not in cols:
        op.add_column(
            "culinary_info",
            sa.Column("review_request_note", sa.Text, nullable=True),
        )


def downgrade() -> None:
    cols = _columns("culinary_info")
    with op.batch_alter_table("culinary_info") as batch:
        if "review_request_note" in cols:
            batch.drop_column("review_request_note")
        if "review_requested_at" in cols:
            batch.drop_column("review_requested_at")
        if "review_requested" in cols:
            batch.drop_column("review_requested")
