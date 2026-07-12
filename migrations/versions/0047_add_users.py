"""Add users principal table (multi-tenancy groundwork)

Canonical principal/account table. id=1 is reserved for the curator
(role='curator'); workshop participants map to workshop_participants.id
(id >= 2, role='participant').

Additive ONLY — this migration does NOT add a FK from any other table
(encounters, personal_lists, notification_dismissals, observations, …) to
users. Those come in a later supervised migration.

Idempotent guarded CREATE — same pattern as 0044_add_species_synonyms and
0046_add_species_edibility_history: no-ops if init_db()'s create_all already
bootstrapped the table from the User model (app/models/user.py) via the
app/main.py noqa import, then stamps head.

This is a CREATE TABLE, not an ALTER — batch_alter_table isn't needed;
op.create_table is SQLite/Postgres-portable on its own.

Revision ID: 0047_add_users
Revises:     0046_add_species_edibility_history
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0047_add_users"
down_revision = "0046_add_species_edibility_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {t[0] for t in op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("role", sa.Text, nullable=False, server_default="participant"),
            sa.Column("display_name", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("users")
