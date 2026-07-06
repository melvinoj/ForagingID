# ForagingID — Development Protocols
*Last updated: May 2026*

These are the rules Claude Code must follow in every session. Read this file before touching any code.

---

## Session Start Protocol

Every Claude Code session, in this order:

1. `cat docs/protocols.md` — read this file
2. `cat docs/current_phase.md` — read what's in scope
3. `cat docs/architecture.md` — read structural constraints
4. Implement **only** what's in current scope. Do not reach ahead into future phases.

---

## Architecture Constraints

### Database
- SQLite through Phase 12. Postgres migration is Phase 13 via Alembic.
- **Nothing built now should increase the cost of the Phase 13 migration.**
- Use `render_as_batch=True` in all Alembic migrations (SQLite compatibility).
- Never use raw `ALTER TABLE` — always use Alembic migrations.

### species_id / species_primary discipline
- `observations.species_id` is the **source of truth** FK — use this for all joins in map.py, ingest.py, culinary.py.
- `species_primary` is a **display cache only** — synced from species_id, kept for the 121 read-sites.
- **Every write of `species_primary` must also set `species_id`.** A missed write desyncs silently.
- Rename and merge operations must be true UPDATEs — never delete and re-insert.

### API Routing
- **Plants** → PlantNet + iNaturalist
- **Fungi** → iNaturalist + Mushroom Observer only (never PlantNet)
- **Auto-approve** → BOTH APIs must independently return the same species at or above threshold. One confident source is never enough. This is an edibility-safety rule.

### Map endpoints
- `/api/map/geojson` — viewport-bounded pins only (takes bbox + zoom params)
- `/api/map/heat` — full archive, lightweight, for heatmap and walk-building
- Do not add server-side clustering until observation count requires it.

---

## Code Discipline

- Work in order. Confirm each fix or workstream before moving to the next.
- Additive only where specified — do not refactor working code while fixing a bug.
- Do not touch unrelated files. Scope is explicit in current_phase.md.
- If a fix requires touching a file not in scope, flag it and confirm before proceeding.

---

## Safety Rules

- **Auto-approve is an edibility-safety concern.** Do not loosen confidence thresholds or approval logic without explicit instruction.
- **Foraging spot data is sensitive.** No coordinates or location data should be exposed in any shared or multi-user context without explicit opt-in.
- Species card edibility gating must not be bypassed.

### Edibility model & locking doctrine

- **The verdict lives in `species.edibility_status`** — one of `edible | caution | toxic | inedible | unknown`. This is the only field any display or handout reads. "Deadly" is **not** a separate value: deadly species are `toxic`, with severity expressed in `preparation_warnings`.
- **`species.edibility_verified` is an independent lock flag**, meaning "verdict human-confirmed; automated sources must not overwrite." It is **never** read as an edible/safe signal anywhere. (The old "toxic → `edibility_verified=0`" note is retired — it described an ingest-time default, not a toxic marker.)
- **Edibility is human-confirmed only.** The lock is set solely by curator/human action; no scan, auto-ID, threshold, or enrichment path sets it for plants. Sole automated exception: the bracken hardcode (`Pteridium aquilinum` → `toxic`), which is protective.
- **Fungi edibility always routes to review** — never auto-verified-edible. The fungi two-source auto-verify path was removed; it now queues an unverified suggestion for manual confirmation.
- **Culinary/recipe generation:** only `edible`/`caution` generate culinary content; `toxic`/`inedible` generate nothing; `unknown` → medicinal-notes only. `preparation_warnings` is injected into generation, with a mandatory safety caveat whenever a warning or per-part conditions exist (lead with the warning; never use a part outside `edible_parts`).

---

## WiFi-Dependent Tasks (do not run offline)

- `git push --set-upstream origin main` — offsite backup (one-time, credentials saved)
- `python scripts/enrich.py` — picks up Wikidata gaps from rate-limited sessions
- Syncthing sync folder uploads
- Bulk archive folder uploads (Into the Wild, Archive, 2013/2014 etc.)

---

## Pending Human Review (not Claude Code tasks)

- 15 AI medicinal notes drafts in Enrichment tab at /review
- Obs 8771 — Rümmelesbühl photo needs manual plant ID
- Low-confidence review queue items from bulk 2015 upload
