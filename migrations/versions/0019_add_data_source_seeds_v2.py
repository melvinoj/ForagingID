"""add data_sources registry entries — v2 seed batch

Adds 5 new entries to the data_sources registry:
  - Food Plants International   (future edibility source, plants)
  - FAO Wild Edible Fungi       (future edibility source, fungi)
  - ITIS                        (future name-validation source)
  - GBIF                        (link-out, occurrence/distribution)
  - Falling Fruit               (link-out, crowdsourced edible locations)

Wild Food UK and Woodland Trust were already seeded in 0012; this migration
uses INSERT OR IGNORE so it is safe to re-run.

Revision ID: 0019_add_data_source_seeds_v2
Revises: 0018_add_encounter_field_recipes
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_add_data_source_seeds_v2"
down_revision = "0018_add_encounter_field_recipes"
branch_labels = None
depends_on = None

# label, url, data_types(JSON), species_scope, region, status, notes
_SEED = [
    (
        "Food Plants International",
        "https://www.foodplantsinternational.com",
        '["culinary"]',
        "plants",
        "Global",
        "pending",
        "35,000+ edible plant species. Future edibility data source (plants). "
        "Not yet integrated — no fetcher built.",
    ),
    (
        "FAO Wild Edible Fungi",
        "https://www.fao.org/3/i3480e/i3480e.pdf",
        '["culinary"]',
        "fungi",
        "Global",
        "pending",
        "FAO authoritative reference on wild edible fungi edibility and safety. "
        "Future edibility data source (fungi). Not yet integrated — no fetcher built.",
    ),
    (
        "ITIS — Integrated Taxonomic Information System",
        "https://www.itis.gov",
        '["id_notes"]',
        "both",
        "Global",
        "pending",
        "US government taxonomic name authority. Future name-validation source. "
        "Not yet integrated — no fetcher built.",
    ),
    (
        "GBIF — Global Biodiversity Information Facility",
        "https://www.gbif.org",
        '["id_notes"]',
        "both",
        "Global",
        "active",
        "Species occurrence and distribution data. Link-out only.",
    ),
    (
        "Falling Fruit",
        "https://fallingfruit.org",
        '["culinary"]',
        "plants",
        "Global",
        "active",
        "Crowdsourced edible-plant location map, 1M+ locations. Link-out only.",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    for label, url, data_types, scope, region, status, notes in _SEED:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO data_sources "
                "(label, url, data_types, species_scope, region, status, notes, last_test_status) "
                "VALUES (:label, :url, :data_types, :scope, :region, :status, :notes, 'untested')"
            ),
            {
                "label": label,
                "url": url,
                "data_types": data_types,
                "scope": scope,
                "region": region,
                "status": status,
                "notes": notes,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    urls = [row[1] for row in _SEED]
    for url in urls:
        bind.execute(
            sa.text("DELETE FROM data_sources WHERE url = :url"),
            {"url": url},
        )
