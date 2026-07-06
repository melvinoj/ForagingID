# ForagingID — Full Read-Only Diagnostic Audit

**Date:** 2026-06-13
**Mode:** Read-only. No file edits (except this report), no migrations, no write-SQL, no pipeline/enrichment runs, no commits.
**Scope:** All of `app/`, major frontend pages, `data/foragingid.db` (SELECT only), Alembic, deps.
**DB:** `data/foragingid.db` — 240 MB, `alembic_version = 0031_add_workshop_participant_tokens`.

---

## Top Risks (highest priority first)

1. **CRITICAL — 6 toxic species are NOT human-locked (`edibility_verified=0`)**, so automated enrichment is structurally permitted to mutate them: `Conium maculatum` (hemlock, id 130), `Aconitum napellus` (monkshood, id 522), `Sambucus ebulus` (310), `Lupinus polyphyllus` (185), `Iris pseudacorus` (389), `Viscum album` (443). Toxic *writes* are direct/safety-first and the unknown→edible paths are guarded, so live data is currently correct — but these deadly species lack the lock that every other toxic record should carry. `species` table.
2. **WARNING — Guest-reachable unauthenticated write: `POST /api/recorded-walks` and `POST /api/recorded-walks/audio-upload`** are in the coarse guest whitelist (`app/main.py:206-211`) with **no per-route identity guard** (`app/api/recorded_walks.py` does not import `identity`). Any ngrok guest can create walk rows and upload arbitrary audio files (storage/spam vector).
3. **WARNING — Active curator-equivalent guest token exists.** `guest_tokens` id=2 has `participant_id=NULL` → resolves to **curator (user_id=1, is_guest=False)** per `identity.py:70-76`. It is `is_active=1`, expiring `2026-06-13 16:00` (today). Anyone holding that token over the tunnel is a full curator.
4. **WARNING — git is degraded:** `.git/index` mmap fails repeatedly (`unable to map index file: Operation timed out`). `git status`/`commit` are unusable from the shell. This plausibly shares a root cause with the known `/api/dev/log` PermissionError and would break snapshot commits / End Session if it persists. `.git/index` (204 KB, last written 2026-06-12 19:46).
5. **WARNING — iNaturalist API token almost certainly expired.** `.env` last modified 2026-06-11 09:02; iNat JWTs live ~24 h. With it expired, identification silently degrades to single-source (PlantNet only) and **dual-API auto-approve can never fire**. `app/main.py:90-95` warns at boot.
6. **INFO — Data drift: 19 `approved` observations have `species_id = NULL`** and **3 `approved` rows are `identification_status='below_threshold'`** (not `identified`). These are approved-but-unlinked / approved-but-unidentified, a card-count vs map-pin discrepancy source. `observations` table.
7. **INFO — "Fix 5" counts:** 13,045 total observations / 11,481 geotagged (1,564 without coords). Map-eligible = 1,223; map-eligible AND geotagged = 1,207. `observations` table.
8. **INFO — Undocumented status value in data:** `review_status='not_applicable'` (1 row) is not in the documented status model (CLAUDE.md lists pending/needs_review/approved/manually_verified/rejected). `observations`.
9. **INFO — ~9 vestigial zero-row tables** (model-defined, no live reader/writer): `workshop_sites`, `session_attendees`, `session_species`, `sources`, `tags`, `observation_tags`, `locations`, `species_resources`, `recorded_walk_observations`.
10. **INFO — Oversized frontend files:** `index.html` 8,222 LOC, `scan.html` 6,076, `review.html` 5,552, `species.html` 3,519, `lists.html` 2,719, `settings.html` 2,487 — all single-file inline-script pages.

**Safety bottom line:** every code-level safety invariant HOLDS (dual-API auto-approve, fungi-never-auto-approve, AI draft toxic-block, EMA provenance, lock gate). The data is currently safe. The single genuine safety *gap* is structural, not realized: deadly-toxic species missing the `edibility_verified` lock (Risk 1).

---

## §0 — Inventory & Versions

### LOC by area
| Area | LOC |
|---|---|
| `app/api/` (38 routers) | 18,752 |
| `app/services/` (16) | 5,979 |
| `app/integrations/` (15) | 3,691 |
| `app/models/` (21) | 1,231 |
| `app/adapters/` (ema_clinical) | 321 |
| `app/` root (config/database/main) | 593 |
| Frontend HTML+JS | 34,535 |

Largest routers: `scan.py` 2,514 · `culinary.py` 2,870 · `observations.py` 1,013 · `reidentify.py` 954 · `dev.py` 815 · `trust.py` 796 · `edibility.py` 762 · `syncthing.py` 752 · `audit.py` 744.
Largest service: `enrichment.py` 1,897.
Largest frontend: `index.html` 8,222, `scan.html` 6,076, `review.html` 5,552.

### Python / deps (venv, Python 3.9.6)
fastapi 0.115.5 · starlette 0.41.3 · SQLAlchemy 2.0.36 · aiosqlite 0.20.0 · alembic 1.14.0 · pydantic 2.10.3 · uvicorn 0.32.1 · anthropic 0.104.1 · httpx 0.27.2 · numpy 2.0.2 · pillow 11.0.0 · pillow_heif 0.21.0 · requests 2.32.5.
- **Python 3.9.6** is near EOL (security support ends Oct 2025) — pins the codebase to the `toISOString()` date gotcha already in memory. Not urgent but worth a planned bump.
- No flagrant security-vuln pins observed in the key set. `requests 2.32.5`, `pillow 11.0.0` are current-ish.

### Alembic
- **Single head: `0031_add_workshop_participant_tokens`.** DB `alembic_version` matches (`0031`).
- Chain is **linear 0001→0031** with no branches/multiple heads (verified the full `revision`/`down_revision` graph).
- **No model↔migration drift detected** at the structural level: every `noqa` model import is present in `app/main.py:34-45` (foray_session, notes, data_source, walk, scan_session, encounter, personal_list, notification, recorded_walk, SpeciesResource, process, workshop). `create_all` will see all metadata.

### Git
- **`.git/index` is unreadable from the shell** — `fatal: .git/index: unable to map index file: Operation timed out`, reproducible across retries. The file exists (204,485 bytes, 2026-06-12 19:46). Filesystem is the internal APFS data volume at 97% capacity (7.5 GB free).
- Last reachable commit: `682f96d2 2026-06-12 17:15:00 snapshot: 2026-06-12 17:14:55`.
- `git status` / dirty-file listing could not be produced (read-only — not fixed). **The app's own snapshot mechanism depends on `git commit` working; if this mmap failure is persistent rather than a transient lock, snapshots and End Session commits will fail.** Likely linked to §6 `/api/dev/log` PermissionError.

---

## §1 — Schema Audit

### Row counts (38 tables)
| Table | Rows | | Table | Rows |
|---|--:|---|---|--:|
| observations | 13,045 | | enrichment_sources | 12,880 |
| observation_edits | 13,529 | | processing_logs | 26,309 |
| species | 542 | | culinary_info | 542 |
| culinary_info_history | 404 | | species_ai_drafts | 2,099 |
| species_candidates | 9,146 | | species_recipes | 121 |
| data_sources | 32 | | encounters | 13 |
| scan_sessions | 15 | | background_processes | 11 |
| job_queue | 35 | | app_settings | 10 |
| recorded_walks | 7 | | map_notes | 3 |
| species_edibility_conditions | 3 | | guest_tokens | 2 |
| workshop_participants | 2 | | personal_lists | 1 |
| personal_list_species | 1 | | saved_walks | 1 |
| species_lookalikes | 1 | | about_content | 1 |
| **Zero-row:** foraging_sessions, locations, notification_dismissals, observation_tags, recorded_walk_observations, session_attendees, session_species, sources, species_resources, tags, workshop_sites | 0 | | | |

### FK integrity — all clean
- `observations.species_id` dangling: **0**
- `encounters.species_id` dangling: **0**
- `encounters.observation_id` dangling: **0**
- `culinary_info.species_id` dangling: **0**

### Orphan / vestigial tables (model-defined, zero rows, no live writer)
`workshop_sites` (known), `session_attendees`, `session_species`, `tags`, `observation_tags`, `locations`, `recorded_walk_observations`, `species_resources`, `sources`. `sources` is referenced in 5 py files but holds 0 rows (superseded by `enrichment_sources` / `data_sources`). `foraging_sessions` is zero-row but is the FK target for `guest_tokens.workshop_session_id` (Phase 13 forward-wiring — keep).

### Indexes
- `species`: unique on `scientific_name`; indexes on gbif_taxon_id, family, itis_tsn, itis_name_match.
- `observations`: lat, lng, file_hash, species_id; unique on file_path.
- `encounters`: user_id, species_id, encounter_date.
- **Missing-index notes:** `observations.review_status` and `observations.identification_status` are the hottest filter columns (map, species cards, review queue all filter on them) and are **unindexed**. With 13 k rows the full scans are tolerable but this is the first place to add a composite index if list endpoints slow.

### Declared-but-unused columns (sampling)
- `observations.workshop_suitable`, `altitude_m`, `gps_accuracy_m` are populated sparsely / not read in hot paths.
- `encounters.sketch_path`, `prompt_stage`, `prompt_response` appear write-rarely (encounter UI primarily uses audio/transcript/text_note).
(Not exhaustive — flagged as candidates, not confirmed-dead.)

---

## §2 — Data Integrity & Known Discrepancies

### "Fix 5" — total vs geotagged
- Total observations: **13,045**; geotagged (lat AND lng): **11,481**; ungeotagged: **1,564**.
- Map-eligible (`review_status IN ('approved','manually_verified') AND identification_status='identified'`): **1,223**.
- Map-eligible AND geotagged: **1,207** → **16 map-eligible observations have no coordinates** (counted on cards, absent from map).

### Confirmed-observation vs species_id null
| review_status | total | species_id NULL |
|---|--:|--:|
| approved | 1,129 | **19** |
| manually_verified | 97 | 0 |
| needs_review | 1,418 | 1,397 |
| pending | 1,278 | 1,278 |
| rejected | 9,122 | 8,920 |
| not_applicable | 1 | 1 |

→ **19 approved observations are unlinked to a `species` row** (species_primary text only). These contribute to card-count vs map-pin drift.

### Status matrix anomalies
- `approved` + `below_threshold`: **3** (approved but never crossed identification threshold).
- `rejected` + `identified`: 283 (rejected despite a positive ID — expected for not-plant / manual rejects).
- `not_applicable` review_status: **1 row** — value not in documented status model.
- **Invariant `manually_verified ⇒ identified`: HOLDS** (0 violations).

### Duplicates — none
- Duplicate species by `scientific_name`: **0**.
- Duplicate observations by `file_path`: **0** (also UNIQUE-constrained).
- Duplicate `guest_tokens.token`: **0** (UNIQUE-constrained).

### Encounters
- `user_id` distribution: user 1 (curator) = **12**, user 2 (participant "Alice") = **1**. No rows under user_id 1; the participant-scoping write path is exercised once.
- `workshop_session_id`: **all 13 NULL** — session linkage not yet populated (Phase 13.2 territory).

### Tokens / participants
- `guest_tokens`: id=1 → participant 2, no session, active, expires 2026-06-19; id=2 → **participant NULL (curator), no session, active, expires 2026-06-13 16:00** (see Top Risk 3).
- `workshop_participants`: id=1 `__reserved__` (tombstone), id=2 `Alice`.

---

## §3 — Safety Invariants

### (a) Toxic ⇒ edibility_verified=0 — **REFRAMED; structural gap**
The literal invariant as stated is inverted relative to the code's semantics. `edibility_verified=1` is a **human lock** that *prevents* automated overwrite (`enrichment.py:668,717,987`; frontend `species.html:2335` `_EDIBILITY_LOCKED`). So **toxic + verified=1 is the SAFE, locked state** (a human confirmed "toxic" and froze it). 12 of 18 toxic species are correctly locked.
- **Genuine exposure: 6 toxic species are UNLOCKED (`verified=0`)** — `Conium maculatum`, `Aconitum napellus`, `Sambucus ebulus`, `Lupinus polyphyllus`, `Iris pseudacorus`, `Viscum album`. Toxic values are written directly "safety-first" (`enrichment.py:657`) and the unknown→edible paths refuse to run on resolved/locked statuses, so **no live mis-write has occurred** — but these belt-and-braces deadly records lack the lock every toxic record should have. **Status: HOLDS in data, structural gap flagged.**
- No toxic species is marked edible. **HOLDS.**

### (b) Edible only with manual provenance — **HOLDS (data)**
- `culinary_info_history.changed_by` distribution: `ai_approved:human` 349, `ema` 28, `human` 24, `system_retroactive` 2, `manual_fix` 1. **No raw automated source** (`wikidata`/`pfaf`/`ai`/`inat`) appears as a writer in history.
- The one code path that can set `edible`+`verified=True` *without a human* is the fungi two-source agreement path (`enrichment.py:1040-1046`). **Data check: the only edible fungus, `Cantharellus cibarius` (id 403), has `verified=0`** — it did NOT go through the auto-verify path. **HOLDS, but note this is the sole automated edible-write vector** and should be watched if more fungi are enriched.

### (c) No automated overwrite of a locked field — **HOLDS**
- History scan for `changed_by NOT IN (human,approved,manual)` overwriting a prior human/approved value returned only `ai_approved:human|taste_notes` (2 instances on `culinary_info_id=55`). These are **human-approved AI drafts** (the `:human` suffix = a curator clicked approve), i.e. intentional, not an automated breach. `taste_notes` is not a safety field. **No automated source breached a lock.**
- The current gate is confirmed in code: `_maybe_generate_ai_drafts` skips fields with a `changed_by='human'` history row; approve-draft raises 409 on locked fields (per CHANGELOG current-state, consistent with the guards in `enrichment.py:994-1020`).

### (d) Dual-API auto-approve required; fungi always review — **HOLDS**
- `scan.py:1206-1226`: auto-approve requires `use_pn AND use_inat AND same top species AND both scores ≥ threshold`. Single-source path explicitly removed ("Single-source auto-approve removed — see 9.6 fix", `scan.py:1228`).
- Fungi "never auto-approved (iNaturalist only, no second source)" — `scan.py:1195`.

### (e) AI draft gate: toxic blocked, unknown = medicinal-only — **HOLDS**
- `culinary.py:1200` / `:1447`: `_edib_blocked = _edib in ("toxic","inedible","not_edible") or edibility_status is None`. Blocks recipe & taste_notes for toxic/inedible/null.
- `medicinal_notes` is the only field generated for unknown/unsourced species; `claude_draft.py:93` forces the "No traditional medicinal uses recorded…" fallback when no source data. Comment trail `culinary.py:1836-1837` confirms.

### (f) Medicinal: EMA tags only where changed_by='ema'; folklore/clinical separated; disclaimers rendered — **HOLDS**
- `culinary_info.medicinal_clinical`: **28 populated rows; all 28 history writes are `changed_by='ema'`** (0 other writers).
- Clinical vs folklore are separate columns (`medicinal_clinical` vs `medicinal_folklore`/`medicinal_notes`) with **separate disclaimers rendered**: clinical → `species.html:1847` ("Not medical advice… Consult a qualified practitioner…"); folklore → `species.html:1869` ("Traditional and historical material… not a recommendation for use"). Both flagged in-code as "not formally legal-reviewed" — matches the pending DE/EU legal review.

---

## §4 — Security / Access-Control

### Two-layer model
1. **Coarse middleware** (`main.py:188-216`) — fires only when `is_guest_request(request)` is True, i.e. **ngrok-host detection** (`sharing.py:48-61`, matches `.ngrok` in Host or the live tunnel netloc). Blocks `/scan`,`/review`,`/settings` pages; blocks all non-GET methods **except** a 4-path whitelist.
2. **Per-route token identity** (`identity.py`) — token from `?token=` or `Bearer`; resolves curator / participant / anonymous guest.

### Guest write whitelist (coarse) — `main.py:206-211`
Allowed for ngrok guests: `/api/sharing/export-walk`, `/api/encounters`, `/api/recorded-walks`, `/api/recorded-walks/audio-upload`.
- `/api/encounters` POST has a per-route guard (`encounters.py:131` anonymous-guest → 403; participant token sets user_id + scopes). **OK.**
- **`/api/recorded-walks` POST and `/audio-upload` have NO per-route identity guard** (`recorded_walks.py` does not import `identity`). Any ngrok guest can write walk rows + upload audio. Sub-paths (`/{walk_id}/elevation`, DELETE `/{walk_id}`) are *not* whitelisted so they're correctly blocked. **GAP — Top Risk 2.** Intent per comment is "owner's device syncing via tunnel," but it is unauthenticated.

### identity.py — **fail-closed, verified end-to-end**
- Any lookup exception → anonymous guest (`identity.py:86-89`).
- Expiry + `is_active` enforced in SQL (`:62-67`).
- **Tombstone guard:** `participant.id >= 2` required (`:78`); participant_id=1 falls through to anonymous guest.
- Curator token = `participant_id IS NULL` → user_id=1, is_guest=False (`:70-76`). **This is the mechanism behind the active curator token id=2 (Top Risk 3).** Recommend revoking/expiring stray curator tokens and confirming mint never issues participant_id=NULL unintentionally.

### Curator-only write guards (per-route, confirmed)
`workshop_tokens.py` (`_require_curator`, all mint/list routes), `notes.py:53` (map notes), `culinary.py:878` (foraging-notes PATCH), `settings.py:46-80` (all settings writes), `about.py:52`. Encounters list/read scope by identity (`encounters.py:243-259`).

### GET leak sweep
- `workshop_tokens` GETs are curator-guarded (token-list leak previously fixed — confirmed `_require_curator`).
- `encounters` GET scopes to own user_id for participants, `[]` for anonymous, all for curator.
- **INFO:** `/api/map/geojson` exposes exact observation coordinates and is reachable by guests (landing→map by design). For a foraging app this means **precise spot coordinates are visible to any tunnel guest** — acceptable if intended, but worth a deliberate decision on coordinate fuzzing for sensitive/rare species.

### Secrets
- `.env` present (1,697 B) with PLANTNET_API_KEY, INATURALIST_* , ANTHROPIC_API_KEY, OPENAI_API_KEY, ORS_API_KEY, THUNDERFOREST_API_KEY.
- **`.env` and `.env.*` are gitignored** (`.gitignore:2-3`); `data/foragingid.db` gitignored (`:27`). **No secrets committed.**
- **Expected keys vs present:** all config-referenced keys are present in `.env`. `INATURALIST_API_TOKEN` is present but **likely expired** (24 h JWT, file dated 2026-06-11) — see Top Risk 5. Google Drive token refresh is an outstanding ops item (gdrive integration).

---

## §5 — Dead Code, Orphans, Drift

- **TODO/FIXME/HACK/XXX in `app/`: 0.** Clean.
- **Vestigial tables:** the 9 zero-row model-only tables in §1 (`workshop_sites`, `session_attendees`, `session_species`, `tags`, `observation_tags`, `locations`, `recorded_walk_observations`, `species_resources`, `sources`). `sources` (0 rows, referenced in 5 files) is superseded by `enrichment_sources`/`data_sources` — candidate for retirement once references are confirmed read-only.
- **Backwards-compat redirects** (`main.py`): `/my-season`→`/encounters`, `/upload`→`/scan` — intentional, keep.
- **Integrations with no obvious live caller** (candidates, not confirmed dead): `deepseek_draft.py`, `ollama_draft.py` (alternative LLM backends to `claude_draft.py`), `trompenburg.py` — verify before removing.
- No duplicated-logic hotspots flagged beyond the expected shared identification core (`scan._identify_scanned`) which is intentionally shared by both pipelines.

---

## §6 — Error Handling & Robustness

- **Bare `except:`: 0.** Good.
- **`except Exception`: 250 occurrences.** Most are deliberate graceful-degradation (external APIs, EXIF parsing). Swallowed (`except Exception: pass`-style) clusters worth noting: `sharing.py` (ngrok subprocess lifecycle — acceptable), `utils/exif.py:83,90` (EXIF best-effort — acceptable), `integrations/inaturalist.py:301,310` and `mushroom_observer.py:95` (API best-effort — acceptable but masks token-expiry vs network-error distinction), `api/audit.py:173,209,346`, `api/observations.py:34,240`.
- **Unhandled external-API failures:** PlantNet/iNat are wrapped and degrade to single-source. iNat `inat_score` swallows errors and returns empty — **an expired token is indistinguishable from "no results,"** which is exactly how dual-source ID silently disables (the boot warning in `main.py:90` is the only signal).
- **`/api/dev/log` PermissionError (known):** the endpoint writes `CHANGELOG.md` via `changelog_service.append_history_entry` → `CHANGELOG_PATH.write_text` (`changelog_service.py:96`). CHANGELOG.md is `-rw-r--r--` owned by the user (writable), so the failure is **not** static file permissions. **It most likely shares the same root cause as the `.git/index` mmap timeout (§0)** — a filesystem/locking problem on this volume — surfacing whenever the log/snapshot path also touches git. Logging-only, no data impact, but it points at a real FS-health issue.
- **P1/P2 SQLite single-writer contention:** both pipelines write through `scan_sessions.py` (the documented sole writer to `scan_sessions`) and the shared `_identify_scanned` core. The contention surface is real (P1 auto-scan loop in `syncthing._auto_scan_loop` + P2 `process-delta` can run concurrently, both writing `observations`). aiosqlite serializes within one connection but cross-session writes rely on SQLite's database-level lock; under concurrent P1+P2 a `database is locked` is possible. No WAL/timeout tuning observed in `config.py` — worth confirming `PRAGMA busy_timeout`/WAL is set.
- **Async hygiene:** no obviously unawaited coroutines surfaced; `_auto_scan_loop` is launched via `asyncio.create_task` and cancelled on shutdown (`main.py:115-117`). Whisper/heavy ML is **not** imported at module load (hosted Whisper API via `whisper-1`), so no sync-blocking model load in the async path.

---

## §7 — Performance

- **Boot is light:** lifespan = `init_db` + `load_settings_from_db` + iNat token warn + `recover_stale_jobs` + launch auto-scan loop (`main.py:106-115`). No module-level `import whisper`/`torch`; numpy/pillow are the heaviest imports and are unavoidable for thumbnails. The three referenced startup fixes (stale-job recovery, iNat token boot-warn, settings preload) are present and confirmed.
- **Map endpoint — no N+1:** `map.py:105-211` issues a small fixed set of set-based queries (species pins, landscape pins, one enrichment join, in-season set) and assembles in Python. Good.
- **Hot-path index gaps:** `observations.review_status` / `identification_status` unindexed (§1). At 13 k rows fine; add a composite index if review/species-list latency grows.
- **Frontend weight:** `index.html` 8,222 LOC and `scan.html` 6,076 are large single-file pages with big inline scripts — first-paint and parse cost on mobile/tunnel. No bundler by design; candidate for code-splitting if guest mobile performance matters.

---

## §8 — CHANGELOG Reconciliation

| Pending item | Status | Evidence |
|---|---|---|
| Human-lock gates in AI-draft path | **DONE** | `enrichment.py:994-1020` history guard; approve 409 (per current-state). No automated lock breach in history (§3c). |
| EMA clinical tags committed (28 species) | **DONE** | 28 `medicinal_clinical` rows, all `changed_by='ema'` (§3f). |
| ESCOP + Commission E reference-only in data_sources | **DONE** | `data_sources` = 32 rows incl. the two reference entries (per history 471/472). |
| Folklore backfill run (medicinal_notes) | **OPEN** | Not re-run this audit; backfill is operator-triggered. |
| EMA chip spot-check in app | **OPEN** | Manual/visual task — not verifiable read-only. |
| Disclaimer DE/EU legal review (before Oct) | **OPEN** | Disclaimers render but in-code marked "not formally legal-reviewed" (`species.html:1845,1867`). |
| `/api/dev/log` PermissionError fix | **OPEN** | Reproduced concern; likely FS/git-index root cause (§6, §0). |
| Phase 13.2 Workshops UI | **OPEN** | No workshops UI page; `foraging_sessions` 0 rows, encounters.workshop_session_id all NULL. |
| Fix 5 total/geotagged count | **OPEN** | 13,045 total / 11,481 geotagged; 16 map-eligible lack coords (§2). |
| Takeout batch rescan → process-delta | **OPEN (ops)** | Operational, not run. |
| Roadmap update to v20 | **OPEN** | Documentation task. |
| Google Drive token refresh | **OPEN (ops)** | gdrive integration present; token not validated here. |
| iNaturalist token refresh | **OPEN (ops)** | `.env` token likely expired (§4, Top Risk 5). |
| DIGIERA archive scan | **OPEN (ops)** | HD-dependent rescan source; not run. |

---

## §9 — Phase 13 Readiness

- **Migration head includes 0031** and the guest-token tables exist: `workshop_participants` (2 rows, incl. `__reserved__` tombstone id=1) and `guest_tokens` (2 rows). `alembic_version='0031'`. ✅
- **13.1 (token layer + scoping + curator guards): WIRED.** `identity.py` resolver (fail-closed, tombstone guard), `encounters.py` scoping (anonymous→403/[], participant→own, curator→all), curator-only guards on foraging-notes/notes/settings/workshop-tokens. Live proof: participant "Alice" (user_id 2) owns 1 encounter; curator owns 12.
- **13.1a (workshop token mint/list): WIRED.** `workshop_tokens.py` POST/GET participants + tokens, all `_require_curator`-guarded. One participant token and one curator token live.
- **13.2 (Workshops UI + session linkage): STUBBED.** No workshops front-end page; `foraging_sessions` table empty (0 rows); `encounters.workshop_session_id` populated nowhere (all NULL). `guest_tokens.workshop_session_id` FK→`foraging_sessions` is forward-wired but unused.

---

## Prioritised Remediation List

### CRITICAL
1. **Lock the 6 unguarded toxic species** — set `edibility_verified=1` for `Conium maculatum`, `Aconitum napellus`, `Sambucus ebulus`, `Lupinus polyphyllus`, `Iris pseudacorus`, `Viscum album` so no enrichment path can ever touch them (snapshot first per CLAUDE.md).

### WARNING
2. **Add a per-route identity guard to `/api/recorded-walks` POST + `/audio-upload`** (reject anonymous guests, or token-scope), or remove them from the `main.py` guest whitelist.
3. **Revoke/expire stray curator token `guest_tokens` id=2** (participant_id=NULL) and audit the mint path to ensure curator tokens are never issued to participants.
4. **Diagnose the `.git/index` mmap timeout** (FS health on the 97%-full volume; check for stale `.git/index.lock`, run `git fsck` once readable) — this blocks snapshots/End-Session commits and is the probable root of the `/api/dev/log` PermissionError.
5. **Refresh the iNaturalist API token** (and re-validate the Google Drive token) — without it, dual-API auto-approve cannot fire and ID silently degrades to PlantNet-only.

### INFO
6. Reconcile the **19 approved + species_id NULL** and **3 approved + below_threshold** observations (link to species or downgrade status) to remove card-vs-map drift.
7. Re-examine the **16 map-eligible observations missing coordinates** ("Fix 5") and confirm intended geotagged/total denominators with Melvin.
8. Normalise the lone **`not_applicable` review_status** row to a documented status value.
9. Add a composite index on `observations(review_status, identification_status)` before review/species-list latency becomes an issue.
10. Decide on **guest coordinate exposure** for `/api/map/geojson` (fuzz sensitive-species coordinates if needed).
11. Retire vestigial zero-row tables (`workshop_sites`, `session_attendees`, `session_species`, `tags`, `observation_tags`, `locations`, `recorded_walk_observations`, `species_resources`, `sources`) after confirming no read paths.
12. Plan a Python 3.9→3.11+ bump (3.9 security-EOL) and the matching `toISOString()` date-handling cleanup.
13. Complete the **DE/EU disclaimer legal review** before October and remove the "not formally legal-reviewed" caveat.

---

*End of report. No changes were made to the application, database, or git state during this audit; only this file was written.*
