# ForagingID — Architecture
*Last updated: May 2026*

---

## Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite (through Phase 12) → Postgres + PostGIS (Phase 13)
- **Frontend**: Vanilla JS
- **Migrations**: Alembic with `render_as_batch=True` (SQLite compatible, Postgres ready)
- **Running**: Local MacBook, `http://127.0.0.1:8000`
- **Repo**: `github.com/melvinoj/ForagingID`
- **Start**: `cd ~/Documents/ForagingID && source venv/bin/activate && python run.py`

---

## Long-Range Architecture Decision

**Option B — hosted multi-tenant platform with Postgres + PostGIS.**

SQLite continues through Phases 10–12. Postgres migration is Phase 13 via Alembic.
**Nothing built in the interim should increase the cost of that migration.**

---

## Database

### Key discipline — species_id / species_primary

- `observations.species_id` — real FK, source of truth, use for all joins
- `species_primary` — display cache only, synced from species_id, kept for 121 read-sites
- Every write of `species_primary` must also set `species_id` or the cache desyncs silently
- Rename and merge are always true UPDATEs — never delete and re-insert

### Migration rules

- Never use raw `ALTER TABLE` — always Alembic
- Always use `render_as_batch=True` for SQLite compatibility
- Alembic is already in place — Phase 13 Postgres migration is a layer change, not a rewrite

---

## Identification Pipeline

### API routing
- **Plants** → PlantNet + iNaturalist
- **Fungi** → iNaturalist + Mushroom Observer only (never PlantNet)

### Auto-approve rule (edibility-safety critical)
- Auto-approve triggers **only** when BOTH APIs independently return the same species at or above the confidence threshold
- One confident source alone never auto-approves
- If APIs disagree or only one returns a result → review queue, no exceptions

### Pre-filter
- Rejects non-plant/fungi images before identification APIs are called

---

## Ingestion Pipelines

- **Pipeline 1**: Syncthing folder sync from `~/Documents/PhoneForaging/` (phone photos, GPS intact)
- **Pipeline 2**: Browser folder upload

---

## Map Endpoints

- `/api/map/geojson` — viewport-bounded pins only (takes bbox + zoom params)
- `/api/map/heat` — full archive, lightweight, for heatmap and walk-building
- Server-side clustering deferred until observation count requires it

### Base layers
Standard, Satellite, Terrain, Geology, Soil pH, Land use

### Features
Pins / Clusters / Heatmap / Walk layers; ORS foot-hiking routing; save/recall walks; Google Maps export; note pins

---

## Phase 13 Multi-Tenancy (future)

Three user types — design for all three from the start:
- **Melvin** — admin, full access, reference implementation
- **Workshop clients** — time-limited guest access, read-only or Goethean game mode, no spot data
- **Other foragers** — private silo, full app, own data, optional sharing opt-in

### Privacy rules (first-class concern)
- Foraging spots are sensitive — explicit opt-in for any sharing
- Granular sharing: species presence only (10km grid square), never exact coordinates
- Default: every user's data completely private and siloed
- GDPR compliance required (European users)

---

## Key File Locations

| What | Where |
|------|-------|
| Project root | `~/Documents/ForagingID` |
| Database | `~/Documents/ForagingID/foraging.db` |
| Identification service | `app/services/identification.py` |
| Map API | `app/api/map.py` |
| Ingest API | `app/api/ingest.py` |
| Culinary/rename logic | `app/api/culinary.py` |
| Frontend | `frontend/index.html` |
| Migrations | `migrations/` |
| Alembic config | `alembic.ini` |
