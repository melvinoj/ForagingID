"""Publish-as-experience Stage B2 — experience_publications

One row per published (or draft) experience page for a saved walk. Additive:
a new table only, no change to any existing table or row.

  saved_walk_id        FK saved_walks.id, ON DELETE SET NULL (nullable). FKs are
                       ON in this app; the walk DELETE route refuses while a row is
                       'published' (409), deletes 'draft' rows itself, and keeps
                       'unpublished' rows as history with saved_walk_id NULL.
  slug                 unique, [a-z0-9-]+ (validated in app/api/experience.py)
  is_default           at most one true — partial unique index (WHERE is_default = 1)
                       plus the router clears the old default before setting a new one
  overrides_json       per-walk overrides for scripts/experience_export (title/intro/where,
                       hide_species_ids, more_walks); slug comes from the slug column
  status               'draft' | 'published' | 'unpublished'
  published_at / unpublished_at / published_commit
  public_species_json  snapshot of what was public at publish time
  created_by, created_at, updated_at  (UTC, like every DB audit column)

Revision ID: 0054_experience_publications
Revises: 0053_walk_membership
"""
from alembic import op
import sqlalchemy as sa

revision = "0054_experience_publications"
down_revision = "0053_walk_membership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experience_publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("saved_walk_id", sa.Integer(),
                  sa.ForeignKey("saved_walks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("overrides_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("unpublished_at", sa.DateTime(), nullable=True),
        sa.Column("published_commit", sa.String(64), nullable=True),
        sa.Column("public_species_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("status IN ('draft','published','unpublished')", name="ck_experience_pub_status"),
    )
    op.create_index("ux_experience_publications_slug", "experience_publications", ["slug"], unique=True)
    op.create_index("ix_experience_publications_saved_walk_id", "experience_publications", ["saved_walk_id"])
    # At most one default: SQLite partial unique index (supported since 3.8).
    op.create_index("ux_experience_publications_one_default", "experience_publications", ["is_default"],
                    unique=True, sqlite_where=sa.text("is_default = 1"))


def downgrade() -> None:
    op.drop_index("ux_experience_publications_one_default", table_name="experience_publications")
    op.drop_index("ix_experience_publications_saved_walk_id", table_name="experience_publications")
    op.drop_index("ux_experience_publications_slug", table_name="experience_publications")
    op.drop_table("experience_publications")
