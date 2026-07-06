"""add notification_dismissals (seasonal return notifications)

Phase 11b — per-species-per-season dedup for seasonal return notifications. A row
records that the user dismissed a given species' return for a given season_key
(e.g. "2026:fruit"), so it never re-nags within that season.

Idempotent: guarded CREATE so it no-ops on a DB where init_db()'s create_all
already bootstrapped the table, then stamps head.

Revision ID: 0015_add_notification_dismissals
Revises: 0014_add_encounter_transcript
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_add_notification_dismissals"
down_revision = "0014_add_encounter_transcript"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {t[0] for t in op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "notification_dismissals" not in existing:
        op.create_table(
            "notification_dismissals",
            sa.Column("id",           sa.Integer,  primary_key=True, autoincrement=True),
            sa.Column("user_id",      sa.Integer,  nullable=False, server_default="1"),
            sa.Column("species_id",   sa.Integer,  sa.ForeignKey("species.id"), nullable=False),
            sa.Column("season_key",   sa.String(40), nullable=False),
            sa.Column("dismissed_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "species_id", "season_key", name="uq_notif_dismissal"),
        )
        op.create_index("ix_notif_dismissal_species", "notification_dismissals", ["species_id"])


def downgrade() -> None:
    op.drop_index("ix_notif_dismissal_species", "notification_dismissals")
    op.drop_table("notification_dismissals")
