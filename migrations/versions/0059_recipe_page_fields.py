"""species_recipes: summary, recipe_type, hide_from_public, website_url (25 Oct 2026)

Recipes page in the app + Recipes tab on the public walk page (Melvin, 25 Oct
2026). Additive; nothing dropped. `title` already exists (backfilled by
scripts/recipe_fields_backfill.py, not here).

  summary          one-line preview (~120 chars), curator-editable
  recipe_type      drink | ferment | condiment | preserve | main | side | sweet |
                   other; NULL shows as "Other"
  hide_from_public default 0 — every approved recipe that passes the export
                   gates is public unless the curator hides it
  website_url      optional https link to the full recipe on melvinjarman.co.uk

Revision ID: 0059_recipe_page_fields
Revises: 0058_recorded_walk_shared_with_guests
"""
from alembic import op
import sqlalchemy as sa

revision = "0059_recipe_page_fields"
down_revision = "0058_recorded_walk_shared_with_guests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("species_recipes") as batch_op:
        batch_op.add_column(sa.Column("summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("recipe_type", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("hide_from_public", sa.Boolean(), nullable=False,
                                      server_default=sa.text("0")))
        batch_op.add_column(sa.Column("website_url", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("species_recipes") as batch_op:
        batch_op.drop_column("website_url")
        batch_op.drop_column("hide_from_public")
        batch_op.drop_column("recipe_type")
        batch_op.drop_column("summary")
