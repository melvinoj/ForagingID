"""add personal lists (My Season standing list)

Phase 11a.3 — server-side standing personal species lists. A personal list is the
"workshop-of-one": same machinery as a multi-participant workshop list, differing only
in member count. Membership rows reference species read-only by ID.

Idempotent: guarded CREATE so it no-ops on a DB where init_db()'s create_all already
bootstrapped the tables, then stamps head.

Revision ID: 0013_add_personal_lists
Revises: 0012_add_data_sources_table
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_add_personal_lists"
down_revision = "0012_add_data_sources_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {t[0] for t in op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "personal_lists" not in existing:
        op.create_table(
            "personal_lists",
            sa.Column("id",          sa.Integer,  primary_key=True, autoincrement=True),
            sa.Column("user_id",     sa.Integer,  nullable=False, server_default="1"),
            sa.Column("slug",        sa.String(60),  nullable=False),
            sa.Column("name",        sa.String(200), nullable=False),
            sa.Column("is_standing", sa.Boolean,  nullable=False, server_default="0"),
            sa.Column("created_at",  sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at",  sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "slug", name="uq_personal_list_user_slug"),
        )
        op.create_index("ix_personal_lists_user_id", "personal_lists", ["user_id"])

    if "personal_list_species" not in existing:
        op.create_table(
            "personal_list_species",
            sa.Column("id",         sa.Integer,  primary_key=True, autoincrement=True),
            sa.Column("list_id",    sa.Integer,  sa.ForeignKey("personal_lists.id"), nullable=False),
            sa.Column("species_id", sa.Integer,  sa.ForeignKey("species.id"), nullable=False),
            sa.Column("added_at",   sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("list_id", "species_id", name="uq_list_species"),
        )
        op.create_index("ix_pls_list_id",    "personal_list_species", ["list_id"])
        op.create_index("ix_pls_species_id", "personal_list_species", ["species_id"])


def downgrade() -> None:
    op.drop_index("ix_pls_species_id", "personal_list_species")
    op.drop_index("ix_pls_list_id",    "personal_list_species")
    op.drop_table("personal_list_species")
    op.drop_index("ix_personal_lists_user_id", "personal_lists")
    op.drop_table("personal_lists")
