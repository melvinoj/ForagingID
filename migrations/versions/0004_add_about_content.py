"""add about_content single-row table + seed copy

Additive only — creates the about_content table (id always 1) and seeds the
initial About-page copy with INSERT OR IGNORE so re-runs never clobber edits.
Idempotent.

Revision ID: 0004_add_about_content
Revises: 0003_add_species_recipes_notes
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_about_content"
down_revision: Union[str, None] = "0003_add_species_recipes_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FULL_DESCRIPTION = """ForagingID is a foraging intelligence platform built around two connected ideas: that knowing what a plant is and knowing the plant itself are completely different things — and that your photographs, past and present, already contain more knowledge than you realise.

Every time you photograph a plant, you're adding to a personal archive that builds itself. Old photos you took without thinking — walks, holidays, hedgerows half-noticed — become dated, geolocated observations the moment they enter the system. Going forward, that archive grows with intention. Over time it becomes something genuinely rare: a living map of your own land, your own season, your own eye. That accumulation is exciting. It can shape not just what you know but how you look.

Most identification tools — Google Lens, iNaturalist, PlantNet — answer one question: what species is this? They give you a name and move on. ForagingID does something different. Every observation belongs to a specific plant, in a specific place, at a specific moment. Come back in October to the same elder you photographed in June flower, and ForagingID holds both moments — the gesture of the plant across its whole seasonal arc, its flowering and fruiting, its dying back and reseeding. Not as a category, static image or label, but as a presence in movement — plants are always changing as they go through their cycles.

This is the core of the Goethean method: exact, patient observation of the plant as it actually is. The app is built around that principle from the ground up. Observations dated and geolocated. Seasonal recipes tied to what's actually present now. Phenological patterns emerging from your own archive over years. The explicit Goethean layer makes that visible and teachable, but the orientation is already there in the structure.

Knowing a plant more deeply also means tasting it — gaining the confidence, through experience and through workshops, to cook with what lives in your local terroir. ForagingID holds a recipe bank written in a forager's voice, tied to season and place. It facilitates exploration of medicinal and tonic uses alongside the culinary. The relationship with a plant deepens through the palate as much as through the eye.

The archive is local and personal. Your foraging spots are sensitive, almost sacred data — exact GPS coordinates of where your chanterelles fruit, where your elderflower hedge is at its best in the third week of May. ForagingID keeps that knowledge yours. Nothing is shared without explicit consent.

What the app currently holds: around [SPECIES_COUNT] confirmed species and [OBSERVATION_COUNT] dated and geolocated observations across Sheffield and the Peak District, the southern Black Forest, and the Gresgen/Swiss border. Load your own photos and the archive becomes tailored to your area — your hedgerows, your seasons, your land. A recipe bank written in a forager's voice. Medicinal preparations. Walk planning that routes you through your own historical finds. A heatmap that shows you where life concentrates in your landscape.

What it's becoming: an installable field companion that works offline, tells you what's edible within 200 metres right now and in season this week. It sparks curiosity by inviting you to explore different layers of a plant's context — culinary, medicinal, ecological, perceptual. And it gives practical outputs: sharable walks routed through your own finds, and booklets of the species in your world that you can take into workshops or hand to participants.

ForagingID is built by Melvin Jarman, Sheffield-based forager, chef, and educator. It is a tool for learning your land."""


_SNAPPY_SUMMARY = """ForagingID turns your photographs into a living archive of the plants in your world. Unlike identification apps that give you a name and move on, ForagingID helps you get to know individual plants — returning to the same elder across seasons, building a personal map of your land, your hedgerows, your recipes. It connects field observation to kitchen confidence, from the Goethean practice of patient seeing to the pleasure of cooking with what grows nearby. A tool for foragers, educators, and anyone who wants to know their landscape more deeply."""


def _has_table(bind, table: str) -> bool:
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "about_content"):
        op.create_table(
            "about_content",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("full_description", sa.Text(), nullable=True),
            sa.Column("snappy_summary", sa.Text(), nullable=True),
        )
    # Seed the single row. INSERT OR IGNORE so existing edits are never clobbered.
    bind.execute(
        sa.text(
            "INSERT OR IGNORE INTO about_content (id, full_description, snappy_summary) "
            "VALUES (1, :full, :snappy)"
        ),
        {"full": _FULL_DESCRIPTION, "snappy": _SNAPPY_SUMMARY},
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "about_content"):
        op.drop_table("about_content")
