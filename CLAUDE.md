# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Start Protocol

**At the start of EVERY session, before doing anything else:**

1. Run `pwd` and confirm the working directory is `/Users/melvinjarman/ForagingID`. If it isn't, **stop and flag this to the user** before proceeding — do not assume the documented location is correct.
2. Read `CHANGELOG.md` in this directory
3. Report the **## Current State** block to the user
4. Confirm what's next (from the "Pending / next" list in Current State)

When the user says **"Continue on ForagingID"**, always start with this protocol.

```
pwd check → Read CHANGELOG.md → report Current State → confirm next step
```

---

## Git Protocol (Code has full git access as of 25 June 2026)

Single commit point: all commits flow through End Session (rewrites CHANGELOG + DB snapshot + commit, coupled). No loose mid-session commits that skip the snapshot — an orphaned commit breaks the "snapshot before writes" guarantee.
Exception: deliberate per-step checkpoint commits during multi-file refactors (e.g. the canonical-helper task) are fine, but only after each step is confirmed clean, and each should still be preceded by a DB snapshot if it touches data.
"Committed to git" is NOT verification. Write-verification discipline is unchanged and more important now: re-query specific rows by ID after every DB write, before relying on the result. A committed state looks authoritative even when the UPDATE never landed.
Destructive git operations get the same stop-and-confirm gate as destructive DB operations. Code must not run reset --hard, force-push, branch deletion, or history rewrites unprompted. DB snapshots cover data, not the code tree — a bad reset --hard with uncommitted work loses work no snapshot can restore.

---

## Session End Protocol

When the user is done working or says "End session":

1. Call `POST /api/dev/end-session` with:
   - `current_state`: a fresh ## Current State block (build status, completed prompts, pending, known issues)
   - `session_summary`: brief description of what was built this session

This single API call:
- Rewrites `## Current State` in CHANGELOG.md
- Appends a session-end entry to `## History`
- Creates a git commit + DB snapshot
- Runs `git push origin main` — best-effort: logs a warning and continues on failure (network/wifi issues never block End Session). Check the `git_push` field in the response, or run `POST /api/dev/git-push` manually to retry.

Alternatively the user can press **"End session"** in Settings.

---

## Log Entry Protocol

After completing each user prompt, call:

```
POST /api/dev/log
{
  "prompt_summary": "Brief description of what was built",
  "features_built": ["Feature A", "Feature B"],
  "fixes_applied": ["Bug X fixed"],
  "files_changed": ["app/api/foo.py", "frontend/bar.html"],
  "pending": ["Item not yet done"]
}
```

---

## Project Overview

| Item | Value |
|------|-------|
| Type | Local-first FastAPI + SQLite |
| Frontend | Plain HTML/JS in `frontend/` |
| Backend | Python FastAPI, `app/` |
| DB | `data/foragingid.db` (SQLite) — **not** `app/foragingid.db` |
| Venv | `venv/` |
| Run | `source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app` |
| Port | 8000 (default) |

**Key directories:**
- `app/api/` — FastAPI routers (one file per feature area)
- `app/models/` — SQLAlchemy models
- `app/services/` — Business logic services
- `app/integrations/` — External API clients (PlantNet, iNaturalist, Claude, etc.)
- `frontend/` — HTML pages + `static/js/`
- `photos/pipeline2/` — P2 (Syncthing/Takeout) copies — project-local, HD-independent
- `uploads/` — Browser-uploaded pending photos
- `snapshots/` (in `/Users/melvinjarman/ForagingID/snapshots/`, project-local) — DB snapshots
- `/Volumes/DIGIERA/Pictures/` — photo archive (year folders 2013–2026, consolidated June 2026); HD-dependent, used as P2 rescan source

**Tech stack:**
- FastAPI + SQLAlchemy async + aiosqlite
- No framework on frontend — vanilla ES2020+, no bundler
- PlantNet + iNaturalist APIs for plant/fungi ID
- Anthropic Claude (`claude-sonnet-4-6` default) for enrichment AI drafts
- OpenAI Whisper for encounter audio transcription (optional)

---

## Pipeline Architecture

There are two import pipelines, sharing identification logic but differing in approval rules.

### Pipeline 1 — Syncthing (P1)
Watches `~/Documents/PhoneForaging/` via `syncthing._auto_scan_loop()` (started at lifespan). Source files are **read-only**; each is copied to `photos/pipeline2/` before a DB record is created (Option B copy-on-ingest, migration 0021).

**Routing:** dual-API agreement ≥ `upload_auto_approve_threshold` → `approved`; everything else → `needs_review`. **P1 never auto-rejects on confidence** — only `not_plant` pre-filter rejections are valid rejections.

Session state written to `scan_sessions` (pipeline=1). In-memory `_state` dict in `syncthing.py` tracks the live session; frontend polls `/api/syncthing/status` every 2 s while active, 15 s when idle.

### Pipeline 2 — File Upload / Takeout Batch (P2)
Browser drag-drop or Rescan → Process Delta flow. Files go to `uploads/`. Heavy batch processing uses `POST /api/scan/process-delta` with an SSE progress stream (`GET /api/scan/progress/{session_id}`).

**Routing:** `file_upload` source always → `needs_review` (no auto-approve regardless of confidence). Confidence-based rejection (below_threshold) IS used here; it is NOT used for P1.

Durable batch state written to `scan_sessions` (pipeline=2) via `scan_sessions.py` service. `is_stalled` is computed at read time: `status='running' AND last_heartbeat > 5 min ago`.

### Shared identification core
`scan._identify_scanned()` handles both pipelines. It:
1. Runs PlantNet and iNaturalist in parallel
2. Merges candidates (score = `min(combined_score, vision_score)` so geo-weighting is ranking-only)
3. Checks dual-API agreement for auto-approve (P1 only)
4. Calls `_upsert_species_card()` → `_enrich_new_species_card()` for new species

`inat_score()` in `integrations/inaturalist.py` submits image to `/v1/computervision/score_image`. Requires a personal Bearer token (`settings.inaturalist_api_token`) — refresh at inaturalist.org/users/api_token if requests start returning empty results.

---

## Observation Status Model

Two orthogonal status fields on `observations`:

| Field | Values |
|---|---|
| `identification_status` | `pending_identification`, `identified`, `below_threshold`, `failed_identification`, `not_plant`, `pending_connection` |
| `review_status` | `pending`, `needs_review`, `approved`, `manually_verified`, `rejected` |

**Critical invariant:** when `review_status = 'manually_verified'`, `identification_status` must be `'identified'`. The map (`/api/map/geojson`) filters on BOTH: `review_status IN ('approved','manually_verified') AND identification_status = 'identified'`. The species card counts on `review_status` only — so any drift between the two fields creates a card-count vs map-pin discrepancy.

The three code paths that set `manually_verified` also upgrade `identification_status`:
- `observations.py` — `correct-species` endpoint
- `reidentify.py` — `confirm-species` endpoint
- `trust.py` — `accept-species` bulk path

---

## DB Schema & Migrations

Schema changes use two mechanisms:

1. **Alembic** for structural changes: `migrations/versions/NNNN_*.py`. Run with `alembic upgrade head`. Current head: `0044_add_species_synonyms`.

2. **Idempotent SQL in `app/database.py` `init_db()`** for data backfills and one-time rescue operations that run on every server start (harmless if rows already updated). Use `INSERT OR IGNORE` / `UPDATE ... WHERE condition` patterns. New columns still go via Alembic — `init_db()` is for data, not schema.

New SQLAlchemy model columns must also be imported (as `noqa` imports) in `app/main.py` so `Base.metadata` picks them up for `create_all`.

---

## Settings System

Runtime settings (thresholds, API source selection, etc.) are stored in the `app_settings` DB table and cached in-process. Access via:

```python
from app.services.settings_service import get_setting
value = get_setting("upload_auto_approve_threshold")  # returns default if no DB override
```

Key settings: `upload_auto_approve_threshold`, `min_identification_confidence`, `api_source_syncthing`, `api_source_file_upload`, `prefilter_pipeline2_green_threshold`.

---

## Snapshot / Restore

Snapshots are created via Settings → "Save snapshot" or `POST /api/dev/snapshot`.

Each snapshot:
- Copies `data/foragingid.db` → `/Users/melvinjarman/ForagingID/snapshots/db_TIMESTAMP.sqlite`
- Creates a `git commit` with message `snapshot: TIMESTAMP`

To restore: Settings → Snapshots → Restore (confirms before acting).

**Always take a snapshot before any bulk data write.**

---

## Code Conventions

- SQLAlchemy async sessions: always `async with AsyncSessionLocal() as session`
- API responses: always JSON; use `ObservationOut` Pydantic models for observations
- Error handling: all exceptions caught at middleware level — endpoints should `raise HTTPException`
- Frontend JS: vanilla ES2020+, no bundler, no framework
- `_esc(str)` for HTML escaping, `_resc(str)` + `.replace(/'/g, "\\'")` for onclick attribute args (apostrophe-safe)
- SSE endpoints use `StreamingResponse` with `text/event-stream`; each event is `data: {json}\n\n`
- `scan_sessions.py` service is the only writer to the `scan_sessions` table — never write directly from routers

## Current Phase

<!-- auto-updated by end-session — do not edit manually -->
—

## Next Steps

<!-- auto-updated by end-session — do not edit manually -->
Awaiting prompt (do not start until explicitly prompted):  Takeout batch: rescan → process delta (operational, not a code task) Roadmap update to v20 Fix 5 total/geotagged count — confirm correct thresholds with Melvin Google Drive token refresh

## Code discipline — mandatory

Before editing any file:
1. Read the relevant section and report exact current HTML/CSS/JS
2. State what you found before stating what you will fix
3. Fix only what was asked — nothing adjacent
4. Verify by reading the edited section again, not by grep
5. Never declare "no fix needed" without showing the evidence
Never apply a CSS change to a shared class without checking every element that uses it
Never confirm a fix is working based on code presence alone — only on observed behaviour

## Code discipline — mandatory

If user puts a ? means i want to to look at all angles and critique what I suggest too - finding the best option - not pleasing me.
I may have ideas, but i want you to critique if necessary, not just implement what i say just because i said it.