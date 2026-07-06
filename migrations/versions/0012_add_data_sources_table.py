"""add data_sources registry table + seed list

Phase 11a — Data Sources registry. Tracks external foraging data sources
(label, URL, data types, scope, region, status) and their reachability. This is
registry + reachability only; no scraping logic. Seeds the agreed source list,
deduped by URL (the list contained two repeats). Existing rows are never
overwritten — INSERT OR IGNORE on the unique url.

Revision ID: 0012_add_data_sources_table
Revises: 0011_add_enrichment_review_flag
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_add_data_sources_table"
down_revision = "0011_add_enrichment_review_flag"
branch_labels = None
depends_on = None


# label, url, data_types(JSON), species_scope, region, notes
_SEED = [
    ("Forager Chef", "https://foragerchef.com", '["culinary"]', "both", "Global", None),
    ("Urban Outdoor Skills (Pascal Baudar)", "https://urbanoutdoorskills.com", '["culinary","folklore"]', "plants", "Global", None),
    ("Wild Food UK", "https://www.wildfooduk.com", '["culinary","id_notes"]', "plants", "UK", None),
    ("Wild Foodie", "https://wildfoodie.co.uk", '["culinary","folklore"]', "plants", "UK", None),
    ("Wildlife Trusts Explorer", "https://www.wildlifetrusts.org/wildlife-explorer", '["id_notes"]', "both", "UK", None),
    ("First Nature", "https://www.first-nature.com", '["id_notes"]', "both", "UK", "Covers plants and fungi"),
    ("Botanical.com (Mrs Grieve)", "https://www.botanical.com", '["medicinal","folklore"]', "plants", "Global", None),
    ("Henriette's Herb", "https://www.henriettes-herb.com", '["medicinal","folklore"]', "plants", "Global", None),
    ("HerbCal.de", "https://www.herbcal.de", '["phenology"]', "plants", "Europe", None),
    ("PFAF", "https://pfaf.org", '["culinary","medicinal"]', "plants", "Global", "Already live as API integration"),
]


def upgrade() -> None:
    bind = op.get_bind()
    existing = {t[0] for t in bind.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()}

    if "data_sources" not in existing:
        op.create_table(
            "data_sources",
            sa.Column("id",               sa.Integer,  primary_key=True, autoincrement=True),
            sa.Column("label",            sa.Text,     nullable=False),
            sa.Column("url",              sa.Text,     nullable=False, unique=True),
            sa.Column("data_types",       sa.Text,     nullable=True),
            sa.Column("species_scope",    sa.Text,     nullable=True),
            sa.Column("region",           sa.Text,     nullable=True),
            sa.Column("status",           sa.Text,     nullable=False, server_default="active"),
            sa.Column("notes",            sa.Text,     nullable=True),
            sa.Column("last_tested",      sa.DateTime, nullable=True),
            sa.Column("last_test_status", sa.Text,     nullable=False, server_default="untested"),
            sa.Column("created_at",       sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

    # Seed (idempotent on unique url). Safe to run even if the table pre-existed.
    for label, url, data_types, scope, region, notes in _SEED:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO data_sources "
                "(label, url, data_types, species_scope, region, status, notes, last_test_status) "
                "VALUES (:label, :url, :data_types, :scope, :region, 'active', :notes, 'untested')"
            ),
            {"label": label, "url": url, "data_types": data_types,
             "scope": scope, "region": region, "notes": notes},
        )


def downgrade() -> None:
    op.drop_table("data_sources")
