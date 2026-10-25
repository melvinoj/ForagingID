"""
guest_access.py — what a workshop participant (guest) device may reach
(batch 8, Melvin 22 Oct 2026). Enforced server-side by the access middleware
(app/main.py), on top of each endpoint's own filter.

  * API reads: deny by default. A guest may GET only the API paths the guest
    pages use (GUEST_GET_API). Curator queues, scan / review data and the raw
    observation lists are refused.
  * Media files: /thumbnails and /uploads-files only for observations that pass
    is_guest_visible_observation (confirmed, scenes included);
    /media/encounters only for encounters encounter_visible_to that guest;
    /media/recorded-walks never (curator recordings); /media/species-resources
    stays open (published curator material).
  * Recorded walks: guests may list / read them, never create one or upload
    its audio (POST /api/recorded-walks and /audio-upload → 403).

The observation and encounter rules themselves live in
app/models/observation.py and app/models/encounter.py — this module only
routes requests to them.
"""
import re
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encounter import Encounter, encounter_visible_to
from app.models.observation import Observation, guest_visible_observation_sql

# GET /api/... paths a guest page needs (map, species, lists, print, encounters,
# landing, about, seasons). Anything else under /api is refused for guests.
GUEST_GET_API = [re.compile(p) for p in (
    r"^/api/me$",
    r"^/api/about$",
    r"^/api/species/?$",
    r"^/api/species/taxonomy-tree$",
    r"^/api/species/lookup$",
    r"^/api/species/.+/(profile|observations|resources)$",
    r"^/api/culinary/(?!ai-draft-review$|enrichment-review$|.+/history$).+$",
    r"^/api/map/(geojson|config|heat)$",
    r"^/api/notes/(geojson|by-species/.+)$",
    r"^/api/walk/saves(/\d+)?$",
    r"^/api/encounters$",
    r"^/api/encounters/field-recipes$",
    r"^/api/encounters/\d+$",
    r"^/api/nearby$",
    r"^/api/find/(recipes|medicinal|in-season)$",
    r"^/api/recipes$",                       # Recipes page (25 Oct 2026) — same gate as species pages
    r"^/api/experience/(critical|publications(/\d+)?)$",
    r"^/api/edibility/(summary|status)/.+$",
    r"^/api/notifications/seasonal-returns$",
    r"^/api/personal-lists/(my-season|card/\d+)$",
    r"^/api/recorded-walks(/\d+)?$",
    r"^/api/timeline/(positions|at)$",
    r"^/api/observations/\d+(/photo)?$",
)]

# Guest writes (the middleware's list; everything else non-GET is refused).
# Batch 8: the Lists PDF (prints the guest's own notes); recorded-walk audio
# upload removed — participant sessions never upload audio. 22 Oct follow-up:
# recorded-walk create removed too — guests never record walks. The endpoints
# in recorded_walks.py also refuse guests (second layer).
GUEST_WRITE_PATHS = frozenset({
    "/api/sharing/export-walk",
    "/api/encounters",
    "/api/lists/pdf",
})

MEDIA_OBS_THUMB = "/thumbnails/"
MEDIA_OBS_FILE = "/uploads-files/"
MEDIA_ENCOUNTERS = "/media/encounters/"
MEDIA_RECORDED_WALKS = "/media/recorded-walks/"
GUEST_MEDIA_PREFIXES = (MEDIA_OBS_THUMB, MEDIA_OBS_FILE, MEDIA_ENCOUNTERS, MEDIA_RECORDED_WALKS)


def guest_api_allowed(method: str, path: str) -> bool:
    """May a guest make this /api request? (Non-/api paths: pages and static
    files are the middleware's business; media goes through guest_media_allowed.)"""
    if method in ("GET", "HEAD"):
        return any(p.match(path) for p in GUEST_GET_API)
    if method == "OPTIONS":
        return True
    return path in GUEST_WRITE_PATHS


def _ends_with(col, rel: str):
    return or_(col == rel, col.endswith("/" + rel, autoescape=True))


async def guest_media_allowed(db: AsyncSession, path: str, identity) -> Optional[bool]:
    """None when `path` is not a guarded media path; else whether this guest may
    fetch the file. Fails closed: a file no visible row points at is refused."""
    prefix = next((p for p in GUEST_MEDIA_PREFIXES if path.startswith(p)), None)
    if prefix is None:
        return None
    rel = path[len(prefix):]
    if not rel or ".." in rel.split("/"):
        return False
    if prefix == MEDIA_RECORDED_WALKS:
        return False
    if prefix in (MEDIA_OBS_THUMB, MEDIA_OBS_FILE):
        col = Observation.thumbnail_path if prefix == MEDIA_OBS_THUMB else Observation.file_path
        hit = await db.scalar(select(Observation.id).where(_ends_with(col, rel))
                              .where(guest_visible_observation_sql(Observation.review_status)).limit(1))
        return hit is not None
    rows = (await db.execute(select(Encounter).where(
        or_(_ends_with(Encounter.audio_path, rel), _ends_with(Encounter.sketch_path, rel))))).scalars().all()
    return any(encounter_visible_to(e, identity) for e in rows)
