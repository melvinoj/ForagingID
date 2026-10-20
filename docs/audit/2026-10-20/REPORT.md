# ForagingID — Deep audit, 20 Oct 2026

Read-only logic audit. **No fixes were made.** Nothing under app/, frontend/, scripts/, migrations/ was edited; no DB writes (all queries run on a `.backup` copy); no external API calls; no commits.

**Labels.** CONFIRMED = verified at the call site or in data by the auditor. SUSPECTED = needs verification; no fix is recommended for these, only what would confirm them.
**Severity.** S0 safety · S1 data integrity · S2 visible bug · S3 tidy/maintainability · S4 cosmetic. Effort S/M/L. "Fix risk" = risk that fixing it breaks something.
**Secrets.** Secret values seen in the DB are never reproduced here; they are referred to by key name only.

Sections 1–8 (top-10, S0 list, matrices, parity tables, proposals, tidy list, rename inventory, SUSPECTED list) are assembled in Phase G from the findings log below.

---

## Findings log

### Phase A — Map

#### A.1 Inventory facts (no severity)

- **Routers:** 39 files in `app/api/`, **288 endpoints** (127 POST, 116 GET, 25 PATCH, 17 DELETE, 3 PUT) + 18 page/utility routes in `app/main.py:327-437`. Full table with auth markers: Appendix A1. Largest routers: culinary.py 34 endpoints, scan.py 25, observations.py 17, encounters.py 16, edibility.py 15.
- **Auth layers** (verified by reading):
  1. Global host-tier middleware `app/main.py:253-289` → `sharing.classify_host()` (`app/api/sharing.py:91-131`). Tiers: `curator` (localhost, `*.local`, loopback/private IP, **and** the ngrok host when `guest_mode_enabled` is OFF), `guest` (ngrok host when guest mode ON), `denied` (anything else → 403). Guest tier: GET/HEAD/OPTIONS only, except POST to `/api/sharing/export-walk`, `/api/encounters`, `/api/recorded-walks`, `/api/recorded-walks/audio-upload` (`main.py:279-285`); pages `/scan /review /settings /workshops` redirect to `/` (`main.py:250`).
  2. Per-endpoint `get_identity()` (`app/api/identity.py:44-98`): token (query `?token=` or Bearer) → curator (participant_id NULL) / participant guest; no token → host check (`is_guest_request`) → curator otherwise.
  3. Curator guards: `require_curator` dependency (`experience.py:64`, router-level on `/api/experience`), `_require_curator(identity)` in `walk.py:191` and `workshop_tokens.py:69`, `_require_owner` in `about.py:52`, and inline `if identity.is_guest: raise 403` (culinary.py, edibility.py, settings.py, notes.py, recorded_walks.py).
  - Mutating endpoints (172): **56** reference `get_identity`/`require_curator` in the handler; **116 rely solely on the host-tier middleware** (heuristic count from AST scan; verified per endpoint in Phase B4).
- **DB tables (DB copy, 20 Oct 12:24):** observations 16,130 · species 709 · culinary_info 708 · culinary_info_history 2,731 · species_ai_drafts 3,073 · species_candidates 20,236 · enrichment_sources 14,951 · observation_edits 19,833 · processing_logs 35,512 · species_recipes 173 · species_edibility_history 143 · saved_walks 4 · recorded_walks 7 · encounters 15 · encounter_photos 2 · scan_sessions 87 · background_processes 190 · job_queue 63 · data_sources 38 · deleted_hashes 18 · app_settings 10 · species_synonyms 8 · species_lookalikes 7 · map_notes 3 · species_edibility_conditions 3 · personal_list_species 3 · guest_tokens 2 · users 2 · workshop_participants 2 · about_content 1 · personal_lists 1 · species_resources 1.
  **Empty (0 rows):** experience_publications, foraging_sessions, session_attendees, session_species, locations, observation_tags, tags, sources, workshop_sites, notification_dismissals, recorded_walk_observations.
- **Alembic:** `alembic heads` → single head `0054_experience_publications`; DB `alembic_version` = `0054_experience_publications`. In sync. 54 revision files, no branches.
- **Background loops / tasks:** `syncthing._auto_scan_loop()` (`main.py:156`, loop at `syncthing.py:500`), `orphan_sweep_loop()` (`main.py:164`, `orphan_sweep.py:193`), enrich-gate worker (`enrich_gate.py:166-178`, lazily started, in-memory queue), queue SSE generator (`queue_api.py:340`), scan SSE loops (`scan.py:2690`, `3142`). Lifespan also runs `recover_stale_jobs()` + `recover_stale_processes()` at start and stops the app's own ngrok on shutdown (`main.py:147-181`). Seasonal-return notifications are computed per request (no loop).
- **Frontend pages (16):** index.html 9,613 LOC · scan.html 6,057 · review.html 5,998 · species.html 4,674 · lists.html 2,727 · settings.html 2,355 · taxonomy.html 1,455 · seasons.html 1,428 · workshops.html 996 · print.html 840 · encounters.html 577 · sightings.html 461 · about.html · landing.html · scratch-filename-test.html.
- **Shared JS (16)** with including pages: site-header.js (12 pages) · pwa.js (9) · guest-mode.js (9) · offline.js (8) · seasonal-returns.js (8) · gps.js (4) · lightbox.js (4) · lists.js (4) · reidentify.js (index, review) · **species-names.js (index, review only)** · walk-record.js (index) · encounter-queue.js + encounters-main.js (encounters) · botanical-overlays-archive.js (lists) · job-status-widget.js (loaded via site-header) · **git-banner.js (no page)**.
- **Templates:** `app/templates/print_pdf.html` (WeasyPrint), `scripts/experience_export/templates/{index,preview,tree}.html`.
- **scripts/:** 32 entries; 14 `migrate_*.py` one-offs dated 25 May–18 Jul (pre-/parallel-to-Alembic), several one-off fix scripts (`fix1_restore_confirmed.py`, `fix_unfiltered_approvals.py`, `scrub_trial_data.py`, `backfill_*`), live tools (`experience_export/`, `walk_straighten_legs.py` 20 Oct, `refresh_plantnet_europe_lists.py` 19 Oct).
- **Largest Python:** culinary.py 3,653 · scan.py 3,367 · enrichment.py 1,985 · reidentify.py 1,184 · syncthing.py 1,131 · experience_export/export.py 1,026 · dev.py 968. Total ~93k LOC across app/frontend/scripts/tests/migrations.
- **Settings registry:** 28 keys in `settings_service._build_registry()`; every one is read by at least one call site (string-literal scan of app/frontend/scripts). DB `app_settings` holds 10 rows, 3 keys **not in the registry**: `auto_approve_threshold` (no reader anywhere — dead), `gdrive_access_token` (read raw by `integrations/gdrive.py`), `obsidian_vault_path` (no string-literal reader found; see A-09).
- **Frontend ↔ endpoint cross-check:** 208 distinct `/api/...` literals in frontend + experience_export. All resolve to a route except dynamically assembled ones (`/api/walk/saves/${id}/${path}` index.html:7232, `/api/processes/` + id, `/api/personal-lists/card/` + id). Endpoints with **no frontend or script caller** (each tail grepped by hand): see A-08.

#### A.2 Findings

**A-01 · S0 · CONFIRMED — "Read-only" share link grants full curator access by default.**
- `sharing.py:113-114`: `if ".ngrok" in host: return "guest" if _guest_mode_enabled() else "curator"`.
- `settings_service.py:365-377`: `guest_mode_enabled` default **False**; the DB copy has no override row (`select * from app_settings` → 10 rows, none for this key), so the live value is OFF.
- `start_sharing()` (`sharing.py:161-238`) starts ngrok and never turns guest mode on.
- Settings card copy (`settings.html:523-525`): "Generate a read-only shareable link via ngrok. Guests can view the map, species pages, and plan walks — no editing or access to admin pages."
- Consequence: anyone given the link/QR while the toggle is OFF has curator access to every endpoint, including `POST /api/dev/restore`, `DELETE /api/observations/{id}`, `POST /api/settings/api-key`, `GET /api/settings` (A-02), and all exact coordinates/notes.
- Effort S (start_sharing forces guest mode ON, or the owner's phone uses a curator token instead of a host rule). Fix risk: medium — the owner's phone currently relies on ngrok = curator to record over HTTPS; it needs the token path (which the middleware ignores today, see B4).

**A-02 · S0 · CONFIRMED — `GET /api/settings` returns the DeepSeek API key to any reader, including guests.**
- `settings.py:92-117` `list_settings()` has no guest/identity check and returns `current_value = get_setting(key)` for every registry entry.
- `settings_service.py:147-154`: `deepseek_api_key` is a registry entry with `"hidden": True` — a UI rendering hint only; `get_registry()` (`:406-408`) does not filter it.
- Guest middleware allows all GETs (`main.py:278`); `/api/settings` is not in `_GUEST_BLOCKED_PATHS` (that set holds page paths only, `main.py:250`).
- The DB copy has a non-empty `deepseek_api_key` row (value not reproduced). With A-01, the key is readable by anyone holding the share link.
- (A live local GET to show the field is populated was declined by the permission classifier; the finding rests on the code path plus the DB row.)
- Effort S (drop hidden/secret keys from the response or mask them). Fix risk: low — check settings.html doesn't read the raw value back.

**A-03 · S1 · CONFIRMED — Trust is decided by the client-supplied `Host` header, and LAN = curator with no credential.**
- `_host_only()` (`sharing.py:74-81`) reads `request.headers["host"]`, not the socket peer address.
- Private/loopback IP or `localhost` / `*.local` → curator (`sharing.py:123-130`).
- The server binds `0.0.0.0` (`START_ForagingID.command:73`, `start.sh:52`).
- Any device on the same Wi-Fi gets full curator access (restore, delete, settings, all coordinates) with no token. Any client that can reach the port can also claim curator by sending `Host: localhost`.
- Severity S1 at home; **effectively S0 when the laptop runs on venue/café Wi-Fi during a workshop**.
- Effort M. Fix risk: medium (phone-on-LAN workflows).

**A-04 · S1 · CONFIRMED — API secrets stored in plaintext in the DB, and so in every DB copy.**
- `app_settings` holds `deepseek_api_key` and `gdrive_access_token` (DB copy, values not reproduced).
- Every snapshot (`snapshots/`, 3.3 GB, gitignored `.gitignore:54`), `data/foragingid_backup_20260620_160503.db` (257 MB), `data/foragingid.pre-fix1-20260529_225743.db.bak` (36 MB) and any external backup (`POST /api/dev/backup-external`, dev.py:787) carry them.
- Not in git: `git ls-files` shows no DB other than the 1-byte `your_db.db`.
- Effort M. Fix risk: low.

**A-05 · S3 · CONFIRMED — Stray files in the tree.**
- `your_db.db` (1 byte, **tracked in git**, in the 2ad8a55 "Fresh history start" commit).
- `current.txt` (341 B pip-freeze fragment, **tracked**).
- `frontend/scratch-filename-test.html`, **served** at `/scratch-filename-test` (`main.py:389-394`).
- `frontend/static/js/git-banner.js` (187 LOC, included by no page; `showGitBanner` has no caller).
- `data/foragingid_backup_20260620_160503.db` (257 MB), `data/foragingid.pre-fix1-20260529_225743.db.bak` (36 MB), `data/thumbnails_quarantine/` (10,770 entries). The `._foragingid.db*` AppleDouble files in data/ are from an exFAT copy.
- `ForagingID_Roadmap_June2026_v23.docx` at the root and `docs/ForagingID_Roadmap_June2026_v20.docx` (two roadmap versions).
- Effort S. Fix risk: low. Disk is tight (84% used, 32 GiB free) — matches known backlog "Disk tight".

**A-06 · S3 · CONFIRMED — 11 empty tables, several with live models and endpoints.**
- `foraging_sessions` / `session_species` / `session_attendees` are backed by 11 endpoints in `foray_sessions.py`, all 0 rows.
- `locations`, `tags`, `observation_tags`, `sources`, `workshop_sites`, `notification_dismissals`, `recorded_walk_observations` are all 0 rows but still have models.
- `experience_publications` is 0 rows although the experience export has been built and published (see D3: publication state lives elsewhere — SUSPECTED, check in D3).
- Effort M per area. Fix risk: low–medium.

**A-07 · S3 · CONFIRMED — Settings drift.**
- DB key `auto_approve_threshold` = 0.7 has no reader (only a comment, `scan.py:1350`, uses the name). The live key is `upload_auto_approve_threshold` (also 0.7 in DB; registry default 0.80).
- `gdrive_access_token` and `obsidian_vault_path` are DB rows outside the registry, so they're not visible or editable in the Settings UI and not type-checked.
- Effort S. Fix risk: low.

**A-08 · S3 · CONFIRMED — Endpoints with no caller in frontend/ or scripts/** (tail of each path grepped by hand; dynamic `/api/walk/saves/${id}/${path}` excluded):
- culinary: `POST /api/culinary/backfill-fungi-edibility` (culinary.py:180), `POST /api/culinary/{name}/mark-verified` (:680), `GET /api/enrichment/running` (:3015).
- dev: `GET /api/dev/changelog` (dev.py:218), `GET`/`PUT /api/dev/current-state` (:224/:238), `POST /api/dev/log` (:253, used by Claude Code per CLAUDE.md), `POST /api/dev/git-push` (:738), `POST /api/dev/export-encounters-to-obsidian` (:962).
- edibility: `GET /api/edibility/unknown` (edibility.py:345), `GET /api/edibility/rescan-status` (:618), conditions GET/POST/DELETE (:659/:682/:720), lookalikes GET/POST/DELETE (:739/:766/:804), `PATCH /api/edibility/phenology/{id}` (:894).
- `POST /api/encounters/backfill-photo-bindings` (encounters.py:455).
- experience: all 6 `/api/experience/publications*` + `verify-species` (experience.py:118-228) — no UI yet (Stage C publish panel is pending per CHANGELOG).
- `PATCH /api/sessions/{id}/species/reorder` (foray_sessions.py:360).
- identify: `POST /api/identify/prefilter-failed`, `GET /prefilter-breakdown`, `POST /tier-action`, `GET /test-connection` (identify.py:29/65/133/230).
- `GET /api/ingest/open-folder-picker` (ingest.py:397).
- observations: `GET /api/observations/confirmed-no-gps` (:124), `GET /api/observations/{id}/edits` (:747).
- `POST /api/species/{name}/recipes/{id}/archive` (recipes.py:244).
- `POST /api/recorded-walks/{id}/elevation` (recorded_walks.py:339).
- `POST /api/observations/{id}/retry-confirm` (reidentify.py:841).
- `GET /api/scan/sessions/{id}/retryable-obs` (scan.py:3175).
- `POST /api/syncthing/reprocess` (syncthing.py:580).
- `POST /api/trust/kingdom-audit` (trust.py:525).
- Note: `fungi backfill` and `mark-verified` are safety-adjacent writers with no UI; they still run if called (Phase B3 checks their gates).
- Effort S each to delete; M to decide which are intentional curl-only tools. Fix risk: low.

**A-09 · S3 · SUSPECTED — `obsidian_vault_path` DB row may be unread.**
- No string-literal reader in app/, scripts/ or frontend/. It may be read via a computed key or the config attribute.
- To confirm: trace `dev.py:962` export-encounters-to-obsidian and `app/config.py` for the Obsidian path source.

**A-10 · S4 · CONFIRMED — Version strings disagree.** FastAPI `version="0.1.0"` (`main.py:185`) vs `/health` → `"0.2.0"` (`main.py:438`). Effort S.

### Phase B — Safety-critical logic

#### B1 Identification and routing

**Facts verified (no severity):**
- **Single auto-approve site:** `scan.py:1853-1861` (`obs.review_status = "approved"` under `if _dual_agree` and `if not terminal`).
  - `_dual_agree = _agreement.dual_agree and not force_review` (`scan.py:1744`).
  - `decide_agreement()` (`agreement.py`) requires both APIs used and returning results, the same #1 name in the decision view (raw PlantNet order unless `regional_demotion_affects_auto_approve`, default False, `settings_service.py:90-91`), each ≥ threshold on its own score, and no promotion.
  - `force_review = caller flag OR not is_phone_origin(obs) OR obs_category=='fungi'` (`scan.py:1370-1373`), plus iNat top = Fungi (`:1616-1620`, re-checked at `:1744`).
- **Callers of `_identify_scanned`:**
  - force_review=False (auto-approve eligible if `upload_source='syncthing'`): `syncthing.py:1096` (P1), `bulk_actions.py:210` (bulk retry), `scan.py:866` (reprocess-pending), `scan.py:3222` (single retry).
  - Default flag, but rows are `file_upload` so forced to review anyway: `scan.py:584` (scan_image), `scan.py:3022` (archive scan; rows created with `upload_source="file_upload"` `:2951/:2999`).
  - force_review=True: `scan.py:691` (override-prefilter), `bulk_actions.py:279`, `orphan_sweep.py:171`.
  - `_VALID_UPLOAD_SOURCES = {"file_upload","phone"}` (`scan.py:76`). No code writes `upload_source='syncthing'` outside the P1 ingest.
- **Gates in `_identify_scanned_inner`:**
  - Terminal read once (`:1345`).
  - Missing file (`:1376-1394`, guarded).
  - Kingdom signal (`:1519-1549`): iNat top outside Plantae/Fungi at ≥5% → needs_review/`non_plant`; guarded by `not terminal and not human_corrected`; never deletes.
  - No-candidates (`:1627-1676`, guarded).
  - Disagreement promotion (`:1702-1721`, suggestion only, undone if agreed `:1760-1764`).
  - Min-confidence (`:1791-1829`, guarded).
  - Species set (`:1835-1836`, guarded); single label/notes apply point (`:1931-1937`).
  - Regional demotion fails open (no list → no demotion, `regional_demotion.py:53-66`); with the setting OFF it cannot affect approval.
- **Live thresholds (DB overrides):** `upload_auto_approve_threshold` = 0.7 (registry default 0.80); `min_identification_confidence` = 0.3 (default 0.50).
- **Writers:**
  - `review_status`: 74 assignment sites. Automated: scan.py (21), syncthing.py (`:1004/:1020` → pending), `database.py:125-135` init_db backfill (rejected → needs_review), identify.py tier-action, trust.py kingdom-audit.
  - Human: observations.py, bulk_actions.py, observation_service.py, reidentify.py, trust.py, audit.py, culinary.py send-for-reid.
  - `species_id` / `species_primary`: `species_link.set_observation_species` (`species_link.py:152-153`) plus direct writes in culinary.py rename/merge (`:894, :937, :1164, :1343`) and trust.py bulk-landscape (`:695-696`); init_db relink `database.py:148`.
- **Invariants on the DB copy:**

  ```
  select review_status, identification_status, count(*) from observations group by 1,2;
  ```

  - manually_verified: 130 rows, all `identified`.
  - approved: 2,404 rows, all `identified`.
  - approved/identified with NULL species and non-landscape category: 0.
  - **Card vs map:** species-card total 2,474 (culinary.py:84-97 two-field filter) = map species pins 2,425 + 49 confirmed rows without GPS. Plus 60 landscape pins with no species.
  - The cards-vs-map agreement holds by construction. CLAUDE.md's "2158/2158" figure is stale.

**B1-01 · Decided — not a finding.** Auto-approve has no family- or toxicity-specific veto by design; the high-threshold dual-API agreement is the safeguard for all species (Melvin, 20 Oct 2026). No change proposed.

**B1-02 · S1 · CONFIRMED — Two file-upload (P2) rows were auto-approved and never reviewed.**
- 17052 *Prunella vulgaris* (edible) and 17737 *Genista sagittalis* (caution).
- Each has the log "Auto-approved — both APIs agree" dated 3 Jun 2026, no human review_status edit, `reviewed_at` NULL, and is geotagged, so it's on the map.
- Current code can't reproduce this (`file_upload` → forced review); it's legacy data from before the P2 rule. 18709 had the same log but was later human-approved.
- Effort S. Fix risk: low.

**B1-03 · S1 · CONFIRMED — `POST /api/trust/kingdom-audit?apply=true` demotes human-finalized rows.**
- It selects `review_status IN ("needs_review","approved","manually_verified")` (`trust.py:545`) and on apply sets `needs_review`/`non_plant` and appends notes (`:621-634`) with no `is_terminal_review_status` guard. That breaks the CLAUDE.md predicate rule for automated bulk paths.
- It uses the same ≥5% non-plant signal that `scan.py:1490-1510` documents as wrong 4 out of 4 times.
- It may also do live iNat lookups (docstring `:536-538`). No UI caller (A-08).
- Effort S. Fix risk: low.

**B1-04 · S2 · CONFIRMED — Two conflicting landscape conventions.**
- `POST /api/trust/bulk-landscape` (`trust.py:669-718`, UI caller `scan.html:4159`) sets `review_status='not_applicable'` (a 6th value, not in CLAUDE.md's status model) and clears species without a `species_primary` edit row.
- The documented scene doctrine (observations.py category change + both approve paths) produces `approved` + `identified` + NULL species, which shows as a landscape pin.
- Data: 1 row (8196, syncthing landscape) is `not_applicable`. It's invisible on the map and in every confirmed count.
- Effort S. Fix risk: low.

**B1-05 · S2 · CONFIRMED — `reject-undo` always restores `approved`.**
- `observations.py:810-813` sets `review_status = "approved"` whatever the status was before the reject. The only guard is `review_status == "rejected"` (`:780`).
- From the map UI (`index.html:5017`, the only caller), undoing a reject of a `manually_verified` pin silently downgrades it to `approved` (`human_corrected` is untouched).
- Called directly, it turns any rejected row (5,042 are `rejected/below_threshold`) into `approved` + `below_threshold`, breaking `approved ⇒ identified`.
- Effort S (record and restore the prior status). Fix risk: low.

**B1-06 · S3 · CONFIRMED — Evidence writes escape the terminal guard.**
- `_identify_scanned_inner` states that candidate evidence is written only when not terminal (`scan.py:1335-1340`), but two writes are unguarded:
  - `obs.plantnet_raw_json` (`:1622-1624`).
  - `obs.category_suggested` (`:1616-1618`).
- So a re-identify of a finalized row overwrites the PlantNet evidence its reviewer saw.
- `_upsert_species_card()` (`:1975-1976`) also runs for terminal rows: an API guess the curator rejected can create a stub species card and queue its AI enrichment.
- Effort S. Fix risk: low.

**B1-07 · S3 · CONFIRMED — Threshold docs drift.**
- `syncthing.py:1087` docstring says "dual-agree ≥80% → auto-approved"; the live threshold is 0.70 (DB override).
- The registry entry (`settings_service.py:75`) matches the code; CLAUDE.md doesn't state a number.
- The DB key `auto_approve_threshold` = 0.7 is dead (A-07).
- Effort S.

**B1-08 · Obs 24353 — why the review card says "Lysimachia nemorum 31.9%" while Second Opinion says 46% (report only).**
Evidence: fresh DB copy taken 20 Oct 16:04 local, Melvin's screenshot, and code. Log/edit timestamps are UTC (CLAUDE.md timestamp convention).

*Timeline (processing_logs + observation_edits):*

| When (UTC) | What |
|---|---|
| 19 Oct 16:24:46 and 16:36:06 | Identify (P1/syncthing): "Micromeria douglasii (31.86%) [plantnet] — Review queue — APIs disagree: PN='Micromeria douglasii' (32%) vs iNat='Lysimachia nemorum' (46%)". `top_score` = 0.3186. |
| 20 Oct 10:58:27 | `confirm-species`, source=manual_entry → *Lysimachia nummularia*, `manually_verified` |
| 20 Oct 14:01:48 | `confirm-species`, source=second_opinion, confidence=0.4613 → *Lysimachia nemorum* |
| 20 Oct 14:02:15 | `manually_verified` → `approved` |

*Stored scores for the species involved* (`species_candidates` rows 20978-20986 / 21030-21038, identical across both runs):

| Species | PlantNet | iNat vision | iNat combined (location-weighted) | iNat gate = min |
|---|---|---|---|---|
| Micromeria douglasii | **0.3186** (#1) | — | — | — |
| Lysimachia nummularia | 0.0651 (#2) | 0.0334 | 0.0569 | 0.0334 |
| Lysimachia nemorum | 0.0245 (#9) | **0.4613** | 0.8512 | **0.4613** |

**The card's 31.9% is not a Lysimachia nemorum score at all.** It's PlantNet's score for *Micromeria douglasii*, left over from the first render. CONFIRMED by code:
- The species block reads the **first stored candidate**, not the confirmed species:

  ```js
  const top = candidates[0];
  const score = top.score || 0;
  const pct = (score * 100).toFixed(1);
  // review.html:1860-1863
  ```

  It prints `${top.scientific_name}` with `${pct}%`, and "Also:" is `candidates.slice(1, 3)` (`review.html:1866-1867, 1876-1881`).
  - At render, `candidates[0]` was Micromeria douglasii (`score` = PlantNet 0.3186). For a PlantNet candidate, `score` is PlantNet's own value (`scan.py:1478`). iNat's numbers sit beside it as `inat_vision_score` / `inat_combined_score` and aren't shown (`scan.py:1572-1576`).
- Applying a name rewrites **only** the name and common name. `_sopApply` → `_applyCorrectionName` (`review.html:2462-2465`, `:2714-2744`) does `spNameEl.textContent = sci` and updates `.sp-common`; `.sp-score` and `.sp-alts` are never touched.
  - So after 10:58 the header said "Lysimachia nummularia 31.9%", and after 14:01 "Lysimachia nemorum / Yellow Pimpernel 31.9%". "Also: Lysimachia nummularia, Veronica sublobata" is the stale `candidates[1..2]`.
- The server never stores the chosen species' score. `confirm-species` only logs `body.confidence` (`reidentify.py:944-953`; log line `:950`); `obs.top_score` stays 0.3186 from identify (`scan.py:1783-1785`).

**Second Opinion's 46% is iNat's gating score for Lysimachia nemorum: min(vision 0.4613, combined 0.8512) = the vision score.** CONFIRMED by code:
- Every panel open is a live call; there's no cache (`showSecondOpinion` → `_sopFetch`, `review.html:2273-2281`).
- iNat `.score = gate = min(vision, combined)` (`inaturalist.py:271-283`), passed through as `min(c.score, 1.0)` (`reidentify.py:571-572`).
- Per-species display confidence (`reidentify.py:590-602`): PlantNet and iNat both present → their **average**; one image source → that source's score; GBIF only → fixed 0.50.
- PlantNet only gets its top `_SOP_PER_SOURCE = 5` slots (`reidentify.py:385`, `display_slots(pn_cands, _SOP_PER_SOURCE)` `:565-568`). *L. nemorum* is PlantNet #9, so it gets no PlantNet score here and its confidence is iNat's 0.4613 → **46%** (`review.html:2392`).
- The GBIF tag comes from the GBIF name search on `obs.species_primary` (`reidentify.py:436`, `:574-588`). That shows the panel in the screenshot was reopened after the 14:01 apply (`_sopApply` hides the panel, `:2489-2490`).
- The other rows reproduce exactly from the stored 19 Oct scores:
  - *L. nummularia* 5% = (PN 0.0651 + iNat 0.0334)/2 = 0.049, tagged PN+iNat.
  - *V. sublobata* 4% = PN 0.0367.
  - *V. hederifolia* 3% = PN 0.0292. Its iNat combined 0.0044 is outside iNat's top 5, so it's PlantNet-only.
  - *Stellaria media* 3% = PN 0.0273.

**Inputs: identical; the difference is purely which number each view shows.**
- Same image file (`obs.file_path`).
- PlantNet: project `all`, organ `auto` (scan passes none → `DEFAULT_ORGAN="auto"`, `plantnet.py:41`; Second Opinion `organ="auto"`, `reidentify.py:401`), `nb_results` 30 in both. Lat/lng are passed by both but **not forwarded to PlantNet** (`plantnet.py:221-223`).
- iNat: both send `lat=obs.latitude`, `lng=obs.longitude`, `observed_on=obs.photo_taken_at.date()` (`scan.py:1415-1420`; `reidentify.py:488-493`).

**Related, CONFIRMED (S2) — after a correction, cards and pins name and score the wrong candidate.**
- Each species change strips only the moved-off name from `species_candidates_json` (`species_link.py:28-56`, called at `observation_service.py:88`): Micromeria at 10:58, *L. nummularia* at 14:01.
- The chosen species is never moved to the front. Current JSON: `[0]` = *Veronica sublobata* 0.0367 … *L. nemorum* sits at index 6 with PN 0.0245.
- So a fresh render of this card would read "**Veronica sublobata 3.7%**" while `species_primary` is *Lysimachia nemorum*.
- The map pin's `confidence` reads the same `candidates[0].score` (`map.py:222-229`), so it shows 0.0367 for a *L. nemorum* pin.
- `obs.top_score` (0.3186, Micromeria) still drives the review-queue confidence sort.
- Effort S. Fix risk: low.

*Side note:*
- This row's candidate JSON has no `pn_raw_rank` / `non_european` keys, which today's scan writes on every PlantNet candidate (`scan.py:1474-1475`). So it was written before regional demotion was live.
- The reference list file is dated 19 Oct 19:37 local, after the 18:24 / 18:36 local identifies. Micromeria douglasii is absent from it, so it would now be demoted (PlantNet's raw #1 is kept for display).

**SUSPECTED:** that this card was rendered before 10:58:27 UTC and not reloaded since. That's the only state in which `candidates[0]` = Micromeria and `[1..2]` = *L. nummularia*, *V. sublobata*. To confirm: reload review.html; the 31.9% header should not come back.

#### B2 Edibility / toxicity display-gate matrix

**Rule implementations found (≥9 distinct copies of "may culinary content show?"):**

| # | Rule | Location | Keyed on | Unknown/NULL |
|---|---|---|---|---|
| R1 | `culinary_allowed(sev) = sev == 'none'` + `CULINARY_ALLOWED_SQL` | `app/models/species.py:461-466` | toxicity_severity | fails closed |
| R2 | `_culinaryGate(sev)` | `index.html:5726-5731` | toxicity_severity | fails closed ("⚠ toxicity unknown") |
| R3 | `isToxic = sev in (deadly, toxic)` | `species.html:1726` | toxicity_severity | **fails open** |
| R4 | `sp.toxicity_severity not in ('deadly','toxic')` | `print_pdf.html:306,329,355,380` | toxicity_severity | **fails open** |
| R5 | `toxicity_severity: sp.get(...) or 'none'` | `lists_pdf.py:105` | missing → 'none' | **fails open** |
| R6 | recipe block: `edib in (toxic, inedible, not_edible) or edibility_status is None or not culinary_allowed(sev)` | `culinary.py:1608-1611` and `:1949-1953` (two copies) | both | closed for NULL edibility; `'unknown'` passes |
| R7 | AI draft gate `_NO_CONTENT = (toxic, inedible, not_edible)`; taste/recipe blocked for `None/'unknown'/'unclear'` | `enrichment.py:1293-1296, :1352-1354` and `:1663-1670` (two copies) | **edibility_status only** | 'caution' passes |
| R8 | Bracken name hardcode | `culinary.py:3028-3039`, `enrichment.py:101-110, :1297` | scientific_name | — |
| R9 | Experience gates (`gates.py` rules 1-7) | `scripts/experience_export/gates.py:7-33` | human-confirmed obs + human-verified verdict + severity 'none' + Apiaceae ID-only + human-authored safety text | fails closed |

**Display-gate matrix** (verified by reading each render site):

| Surface | Render site | Culinary content shown | Gate | Unknown severity | `unknown`/NULL edibility (sev 'none') | caution | Look-alike / prep warnings |
|---|---|---|---|---|---|---|---|
| **Map observation pop-up** (pin tap) | `index.html:4612-4750` → `_injectEnrichment` `:4880-4920` | "🍴 Edible Parts" (140 chars) | **NONE** | n/a | shown | shown | both shown first (120 chars). No edibility or ☠ badge in the card (`:4634-4642` badges are Confirmed/Human verified only) |
| Walk panel stop card | `index.html:6370-6410` | badge + curator foraging_notes only | R2 | closed | edibility label | label | **none** (badge only) |
| Walk "Also here" line | `index.html:6414-6425` | badge | R2 | closed | — | caution badge | none |
| Proximity alerts | `index.html:7765-7790` | badge | R2 | closed | label | label | none |
| Near-me list / Find panel | `index.html:3440-3450`, `:9573` | edibility label | none (label only) | — | "unknown" | caution | none |
| Export summary (walk) | payload `index.html:7552-7600` → `POST /api/sharing/export-walk` (`sharing.py:373-376`) | edibility label, culinary_notes (edible_parts / taste / prep methods), recipe | R2 **client-side only**; server renders whatever arrives (`WalkSpecies` model `sharing.py:328-339`) | closed | label + notes + recipe (server R6 only blocks NULL edibility) | shown | **none — the payload model has no warning fields** |
| Species page | `species.html:1722-2060` | culinary fields, taste notes, recipe bank | R3 + server R6 | **open** | culinary fields shown; recipes allowed for 'unknown' (0 approved today) | shown | severity box `:1865-1895` |
| `GET /api/culinary/{name}` / `/api/species/{name}/profile` | `culinary.py:1576-1648`, `:1843-2040` | full `_culinary_to_dict` regardless of toxicity; recipes R6 | R6 | — | — | — | returned |
| Lists screen | `lists.html:1910-1960`, `:1975-2030` | edible parts, recipe (server-blocked for toxic) | **NONE** for edible parts | — | shown | shown | look-alike only if toggle `ct.id_notes`; prep warnings not in field guide |
| Browser print | `print.html:434-470` (field guide), `:471-530` (workshop) | edible parts, recipe | **NONE** for edible parts | — | shown | shown | field guide: look-alike only if `ct.id_notes`, **no prep warnings**; workshop: whole safety block only if `ct.id_notes !== false` (`:487`) |
| PDF (WeasyPrint) | `lists_pdf.py:83-118` + `print_pdf.html:296-385` | parts, recipe, medicinal | R4 + R5 | **open** | shown | shown | field guide: look-alike if `ct.id_notes`, **no prep warnings**; recipe booklet: safety box **only for toxic/deadly** (`:316-328`); workshop: always |
| Personal list card | `personal_lists.py:211-227` | recipe | R1 | closed | shown | shown | — |
| Experience page + preview | `gates.py`, `export.py` | gated per R9 | R9 | closed | no edible label unless human-verified | must be human-verified or build fails | human-authored only |
| Experience verify-species | `experience.py:228-245` | sets edibility_verified | R1 | closed | — | — | — |
| AI generation | `enrichment.py` R7 | taste/recipe drafts | R7 (edibility_status) | — | blocked | **allowed** | — |
| Species chat | `chat.py:89-115` | AI text | prompt warning only (sev) | — | — | — | — (POST is curator-only via middleware) |
| Seasons page | `seasons.html:876-887` | label only | — | — | — | — | — |

**B2-01 · S0 · CONFIRMED — Map pin pop-up shows "🍴 Edible Parts" for toxic and deadly species, with no edibility or ☠ badge.**
- `_injectEnrichment()` (`index.html:4880-4920`) renders `ci.edible_parts` under "🍴 Edible Parts" with no toxicity or edibility check. The detail card (`showDetail`, `:4612-4750`) carries only Confirmed/Human-verified badges.
- Query: toxic/deadly species with non-empty `edible_parts` and confirmed geotagged pins. It's guest-visible and on the map today:
  - *Conium maculatum* (deadly, 2 pins): "Edible Parts: Leaves Edible Uses: Leaves - cooked[105]. Although toxic, plants found in the south of England a…"
  - *Aconitum napellus* (deadly, 14 pins): "Some reports suggest the root is edible if cooked…"
  - *Aconitum lycoctonum* (deadly, 5)
  - *Dryopteris filix-mas* (10): "Young fronds - cooked… flavour resembling asparagus"
  - *Lupinus polyphyllus* (7), *Sambucus ebulus* (4), *Echium vulgare* (4), *Iris pseudacorus* (3), *Ranunculus ficaria* (2), *Lotus corniculatus* (2), *Symphytum asperum* (2), *Thalictrum aquilegiifolium* (1)
- Look-alike/prep warnings do render above it when present.
- The known backlog item ("Raw PFAF text … map species pop-up ~4912") covers formatting only, not the missing gate.
- Effort S (apply R2/R1 and show the ☠ badge). Fix risk: low.

**B2-02 · S0 · CONFIRMED — No app code ever writes `toxicity_severity`, but every severity-keyed gate (R1–R5) treats its default `'none'` as safe.**
- Column `server_default="none"`, NOT NULL (`species.py:197-199`; migration `0039:12`).
- Writers: only the 0039 backfill and direct SQL. `grep -rn toxicity_severity app/` finds reads only, and `edibility.py` (the documented "ONLY permitted writer" of the verdict, `enrichment.py:779-780`) never mentions it.
- Consequences:
  - (a) A curator setting a species to `toxic` via `PATCH /api/edibility/status/{id}` leaves severity `'none'`, so the map, walk, Export summary, personal card, PDF and species page all keep allowing culinary content.
  - (b) Every new species card (`scan.py:2047-2054`) is born "known safe" to the gates, so R1/R2's "fails closed on unknown" branch is dead code.
- Today the data is consistent (all 39 `edibility_status='toxic'` rows have toxic/deadly severity) only because severity was hand-set: e.g. `species_edibility_history` rows on 15 Oct (Atropa 763, Senecio ovatus 719, Dryopteris 58, `changed_by='human'`).
- Effort M (severity must be set with the verdict, or gates must also key on edibility_status). Fix risk: medium (four renderers).

**B2-03 · S0 · CONFIRMED — Printed and exported outputs drop the safety text that doctrine says must be present for hazardous species.**
- Browser-print field guide (`print.html:434-468`) and PDF field guide (`print_pdf.html:296-307`) never print `preparation_warnings`. Look-alike prints only when the `id_notes` content toggle is on.
- Browser-print workshop puts the whole "Safety & edibility" block behind `ct.id_notes !== false` (`print.html:488`), so a user toggle removes it.
- PDF recipe booklet shows a safety box only for toxic/deadly (`print_pdf.html:316-328`). A **caution** species prints its recipe with no warning. Example: *Sambucus nigra* (caution, 2 approved recipes) has prep warning "Raw berries, leaves, stems and bark are toxic…", which isn't printed. Same for *Hypericum perforatum*, *Ajuga reptans* ("digitalis-like compounds"), *Artemisia vulgaris*, *Populus tremula*, *Lysimachia nummularia*.
- The Export summary payload has no warning fields at all (`sharing.py:328-339`).
- Effort M. Fix risk: low.

**B2-04 · S0 · CONFIRMED — Lists screen and browser print show edible_parts for toxic and deadly species.**
- `lists.html:1913, 1948, 2026` and `print.html:447, 517, 528` push `cul.edible_parts` with no toxicity check. Only recipes are protected, server-side by R6.
- A handout including *Conium maculatum* prints "Edible Parts: Leaves … Leaves - cooked…" next to a red "toxic" pill.
- The PDF path does gate this (R4), so browser print and PDF diverge (see D1 parity).
- Effort S. Fix risk: low.

**B2-05 · S0 · CONFIRMED (data) — Mis-classified hazards pass every gate.**
- *Amanita muscaria* (id 155) is `caution` / severity `none` / unverified.
  - Because R7 keys on edibility_status, the AI pipeline generated a **pending taste_notes draft** (2920: "mild, earthy flavor … when parboiled and cooked") and a **pending recipe draft** (2921).
  - If either is approved, R1–R6 all allow it to display.
- *Heracleum mantegazzianum* (giant hogweed, 688) is `unknown`/`none`.
- *Hedera helix* (745) has `edibility_status` NULL / `none`, with edible_parts text "almost certainly not edible…".
- Not a re-raise of "toxic species excluded from AI generation": the exclusion works as written, but these species aren't marked toxic.
- Effort S (curator decisions + reject drafts 2920/2921). Fix risk: none.

**B2-06 · S1 · CONFIRMED — Migration 0039 equated *inedible* with *toxic*, against doctrine ("inedible ≠ toxic").**
- `0039:84-90` set `toxicity_severity='toxic'` for every `inedible` species. Current crosstab: 37 inedible/toxic, 13 inedible/none.
- So 37 inedible species show "☠ toxic" (R2 label) on walk cards, proximity alerts and the experience page. Species set inedible since then stay `none` and get culinary content.
- The known backlog item "Anthriscus caucalis (138) inedible+toxic contradiction" is one instance of this systemic cause.
- Effort S (curator pass over 50 rows). Fix risk: low.

**B2-07 · S1 · CONFIRMED — 31 species carry the human-confirmed lock flag from machine provenance.**

```
select edibility_verified, edibility_verified_by, edibility_status, count(*) from species group by 1,2,3;
```

- `edibility_verified=1` with `verified_by='auto'`: 4 edible (Allium cepa, Allium ursinum, Arctium lappa, Thymus serpyllum; set by init_db `database.py:198-209` from PFAF confidence ≥0.8).
- `'multi-source-tier-a'`: 27 caution (no writer exists in current code; historical). Includes *Amanita citrina*, *Armillaria mellea*, *Coprinus comatus* and *Pimpinella saxifraga* (Apiaceae).
- The doctrine defines the flag as "verdict human-confirmed". The experience gates correctly require `verified_by='human'` (`gates.py:131-133`), but every in-app surface that reads `edibility_verified` treats these as confirmed.
- Effort S. Fix risk: low.

**B2-08 · S1 · CONFIRMED — 48 species have `edibility_status` NULL, outside the documented enum** (edible/caution/toxic/inedible/unknown).
- R6 and R7 block them (NULL check), but R1–R4 allow their culinary content (all are severity `none`).
- 9 of them have edible_parts text (e.g. *Hedera helix*, *Oxalis triangularis*, *Tragopogon dubius*).
- Effort S. Fix risk: low.

**B2-09 · S3 · CONFIRMED — Export summary and PDF re-render client-supplied culinary data without a server re-check.**
- `POST /api/sharing/export-walk` (`sharing.py:373-376`; guest-tier allowed, `main.py:280`) and `POST /api/lists/pdf` (`lists_pdf.py:164`) render whatever `culinary_notes`, `recipe_body` and `profile` the client sends.
- The safety gate exists only in the browser (R2), or defaults open (R5).
- Not exploitable for harm beyond the requester's own document, but it means the server has no single enforcement point.
- Effort M. Fix risk: low.

**B2-10 · S3 · CONFIRMED — Rule drift across the two gate families.**
- Display gates key on `toxicity_severity`; AI-generation and recipe gates key on `edibility_status`.
- So the same species can be culinary-allowed by one family and blocked by the other (e.g. `unknown` edibility: display gates allow edible parts; AI gate blocks taste/recipe drafts). Proposal in D4. Effort M.
- (The app has no Apiaceae culinary rule by decision — Melvin, 20 Oct 2026; settled, not a finding.)

#### B3 Writers of safety fields

**Writer inventory (grep of all assignment / SQL / setattr sites, each read):**

| Field | Writer | Kind | Human-lock respected? |
|---|---|---|---|
| `edibility_status` | `PATCH /api/edibility/status/{id}` (`edibility.py:469-520`) and `PATCH /bulk-status` (`:395-460`) | curator; `_enforce_edibility_write_rules` | yes (rules engine) |
|  | Bracken hardcode `enrichment.py:101-103` → `toxic` | automated, fails safe | n/a (tightening) |
|  | Species merge `culinary.py:1236`, `:1519` → `"_merged_into:<name>"` | curator merge; **non-enum value** (0 rows today) | — |
| `toxicity_severity` | **none in app code** (B2-02); migration 0039 + direct SQL only | — | — |
| `edibility_verified` / `_by` | edibility.py (curator); `experience.py:243-244` verify-species (curator, R1-gated); `enrichment.py:103` (bracken, no `_by`) | | |
|  | `init_db` `database.py:178-216` (every start): `_by='safety_constant'/'human'/'auto'`; unlocks remaining verified rows with NULL `_by` | automated on each start | sets `'auto'` provenance on a flag that means "human-confirmed" (B2-07) |
| `look_alike_warnings`, `preparation_warnings` | `PATCH /api/culinary/{name}/field` (`culinary.py:1656-1712`): curator, history with old/new, `changed_by='human'` | curator | n/a |
|  | PFAF `_apply_pfaf_to_culinary` (`enrichment.py:806-831`): source text, skips `protected_fields` (fields with human history) | automated, verbatim source | yes |
|  | Bracken hardcode `enrichment.py:107-108` | automated | — |
|  | **Rename cascade** `handle_species_rename` (`enrichment.py:321-329`, `:380-383`): sets every field in `_ENRICHMENT_CLEARABLE_FIELDS` to None, including both safety fields | curator-triggered side effect | **no** (B3-01) |
| AI drafts → culinary_info | `approve_ai_draft` (`culinary.py:2345-2470`), `_APPROVABLE = {taste_notes, medicinal_notes, recipe, medicinal_folklore}` | curator | yes (409 on human history, `:2406-2418`) |

- **AI paths writing edibility:** none.
  - Wikidata (`enrichment.py:744-780`) and fungi (`:1089-1150`) only queue pending `SpeciesAIDraft(field_name='edibility_status')`.
- **Fungi auto-verify-edible path (enrichment.py ~1045): status = DISABLED, CONFIRMED.**
  - Guards 1–4 (`:1020-1070`), then "SAFETY: never auto-write species.edibility_status or set edibility_verified" (`:1089-1094`); only a pending draft is added (`:1144-1156`).
  - All 19 pending `edibility_status` drafts read "status=unknown, confidence=0.00. Sources: no source data", so the two fungi sources return nothing.
  - These drafts can never be approved (`edibility_status` is not in `_APPROVABLE`), so they accumulate.

**B3-01 · S0 · CONFIRMED — A species rename silently erases curator-authored safety text, and the human lock then keeps it blank.**
- `handle_species_rename()` sets `look_alike_warnings`, `preparation_warnings`, `taste_notes`, `medicinal_notes`, `edible_parts`, `id_notes`, `recipe` (and more) to None (`enrichment.py:321-329`, `:380-383`).
  - No human-history check, and no per-field history row (only one `_rename_event` row, `:449-456`), so the old text survives only in older history rows.
- The follow-up re-enrich treats fields with `changed_by='human'` history as `protected_fields`, so PFAF won't refill them and the warning stays empty.
- Callers: species rename (`culinary.py:945-951`; curator action on the species page) and trust bulk-reassign (`trust.py:457`, on the source species).
- Exposure (DB copy, history `changed_by='human'`): curator look-alike text on **22** species and preparation warnings on **24**, including the doctrine-locked *Conium maculatum* look-alike.
- Effort S (skip human-history fields in the clear, or carry them over). Fix risk: low.

**B3-02 · S1 · CONFIRMED — AI-draft approval writes history with `old_value=None` even when the field had content.**
- `culinary.py:2429-2437` always writes `old_value=None`. It runs only when no human history exists, but PFAF / placeholder / earlier `ai_approved` text is overwritten with no record of what it replaced.
- Breaks Write Protocol rule 5's intent (old_value NULL only when the field *was* empty).
- Effort S. Fix risk: low.

**B3-03 · S3 · CONFIRMED — Draft rows misstate provenance.**
- `species_ai_drafts.approved_by='human'` appears on **pending** and invalidated drafts (e.g. ids 1680-1688, 3063-3134, all `pending`, `approved_at` NULL).
- The column default reads as a human approval that never happened. The fungi path doesn't set it (`enrichment.py:1144-1153`), so it's a model/DB default.
- Effort S.

**B3-04 · S3 · CONFIRMED — Unapprovable edibility drafts pile up.**
- 19 pending `edibility_status` drafts with "no source data" (above).
- The approve endpoint rejects the field (`culinary.py:2363-2365`), so the curator's way out is reject only.
- Known context: the fungi integrations returning nothing matches the backlog "iNaturalist token expired; Google Drive token invalid; Ollama 'mistral' not installed" family (external source health), unverified for FAO/MO.
- Effort S.

**B3-05 · S2 · CONFIRMED — Safety writes are not tied to the verdict.**
- Setting `edibility_status='toxic'` through the only sanctioned writer leaves `toxicity_severity='none'` (B2-02).
- Setting `inedible` leaves severity untouched in either direction (B2-06).
- The 15 Oct severity changes in `species_edibility_history` (5 rows, `changed_by='human'`) were written outside any endpoint.
- Effort M. Fix risk: medium.

**Known item, new evidence:** "Recipe regenerate + curator recipe writes not toxicity-gated" (backlog).
- `approve_ai_draft` also has no edibility/toxicity check at approve time. A pending recipe draft for a species that has since been reclassified (e.g. *Amanita muscaria* draft 2921, B2-05) is written into `species_recipes` as `approved` (`culinary.py:2439-2465`).

#### B4 Identity matrix (mutating endpoints)

Full per-endpoint matrix: **Appendix A2**. Built by AST scan, then spot-checked by reading handlers (notes.py, recorded_walks.py, culinary.py fungi backfill, about.py, walk.py, encounters.py, settings.py).

**How access actually resolves:**

| Caller | Host tier (middleware) | Mutating endpoints reachable |
|---|---|---|
| localhost / LAN device / `*.local`, no token | curator | **all 172** |
| ngrok link, guest mode OFF (default, A-01) | curator | **all 172** |
| ngrok link, guest mode ON, no token | guest | 4 whitelisted POSTs (`main.py:279-285`); of those, `/api/recorded-walks*` then 403 any guest in the handler, `/api/encounters` 403s anonymous guests only, `/api/sharing/export-walk` is open |
| Participant token on a curator-tier host (LAN, or ngrok with guest mode OFF) | curator | the **116 host-tier-only** endpoints (identity checks never run) |
| Curator token over ngrok, guest mode ON | guest | only the 4 whitelisted paths: the middleware ignores tokens (same root cause as the **known** "/api/me judges guests by host, ignores tokens" item) |

**Counts by router** (mutating only):

| Router | host-tier only | guest→403 in endpoint | scoping only |
|---|---|---|---|
| audit, bulk_actions, chat, data_sources, dev, enrich, foray_sessions, identify, ingest, itis, lists_pdf, notifications, observations, personal_lists, processes, queue_api, recipes, reidentify, resources, scan, sharing, syncthing, trust | 116 total | 0 | 0 |
| about 2 · culinary 22 · experience 4 · recorded_walks 4 · settings 5 · workshop_tokens 6 · walk 8 · edibility 2 · notes 1 | — | 54 | — |
| walk (`POST /api/walk/saves`), encounters (`POST /api/encounters`) | — | — | 2 |

**B4-01 · S1 · CONFIRMED — 116 of 172 mutating endpoints have no identity check; host tier is the only gate.**
- This includes every destructive and administrative endpoint:
  - dev: `POST /api/dev/restore` (dev.py:446), `/end-session`, `/git-push`, `/backup-external`.
  - `DELETE /api/observations/{id}` (observations.py:842, permanent row delete + guarded file delete).
  - All review/approve paths (observations.py, bulk_actions.py, reidentify.py, trust.py, audit.py).
  - Scan and ingest triggers that spend PlantNet/iNat quota (scan.py 13, syncthing.py 2, reidentify.py 6).
  - Safety-data writers outside culinary.py: `POST/DELETE /api/edibility/lookalikes` (edibility.py:766/804), `/conditions` (:682/:720), the whole recipe bank (`recipes.py:139-268`), and `POST /api/species/{name}/chat` (AI spend).
- Whoever reaches the curator tier (A-01, A-03) can do all of it. A participant token gives no restriction there.
- Effort M (one dependency on the 116; most are curator-only by nature). Fix risk: medium (owner's phone flows; Claude Code's `POST /api/dev/log`).

**B4-02 · S3 · CONFIRMED — Guards are inconsistent within the same feature.**
- notes: `POST /api/notes/` guarded (`notes.py:48-54`), `DELETE /api/notes/{id}` not (`:75`).
- edibility: the verdict PATCHes are guarded, but look-alike/condition/phenology writers aren't (edibility.py:624-894).
- culinary: 22/22 guarded, but the recipe bank in `recipes.py` (5) isn't.
- walk.py: 8/9 guarded, but `POST /api/walk/saves` isn't (`walk.py:107-124`, stamps `identity.user_id`).
- Effort S each.

#### B5 Public-output privacy

**What can reach a non-curator:**

| Channel | Who | What is exposed | Gate |
|---|---|---|---|
| Guest-tier GET API | anyone with the ngrok link | **102 of 116 GET endpoints** have no guest or identity check (AST scan; 14 do) | middleware allows all GETs |
| `/thumbnails`, `/uploads-files`, `/media/encounters`, `/media/recorded-walks`, `/media/species-resources` static mounts (`main.py:293-321`) | same | any file by name; originals keep EXIF | none (names are uuid-ish for media, original filenames for uploads) |
| Export summary HTML | whoever receives it | stops, exact GPX/Google links (by design), map-note text | client-side R2 |
| PDF / print handouts | workshop participants | species content (B2) | B2 |
| Experience page (public web) | public | human-confirmed species, route, photos | gates.py R9 + EXIF strip |

**B5-01 · S0 · CONFIRMED — Any guest can read any encounter by id: voice-note transcripts, text notes, exact coordinates, audio links.**
- `GET /api/encounters/{encounter_id}` (`encounters.py:466-477`) has no identity parameter. It returns `_enc_to_dict` with `user_id`, `latitude`/`longitude`, `text_note`, `prompt_response`, `transcript`, `audio_url` (→ `/media/encounters/<file>`, unauthenticated static mount `main.py:310`) and `field_recipe` (`encounters.py:85-121`).
- The list endpoint *is* scoped (`:321-330`), so ids are the only barrier: 15 encounters, sequential ids, 2 users.
- `GET /field-recipes` (`:274`) and `/{id}/photo-candidates` (`:358`) are also unscoped.
- Effort S. Fix risk: low.

**B5-02 · S0 · CONFIRMED — Guests can list and download full-resolution personal photos the app has filed as "not a plant".**
- `GET /api/observations` (`observations.py:246-262`, filters include `review_status`, `prefilter_category`) and `GET /api/observations/{id}/photo` (`:725-741`, serves `obs.file_path` with no status check) need no identity.
- On disk now (DB copy + `os.path.exists`): 2,192 non-confirmed observations with files, including **381 `person_animal`**, 46 `indoor_dark`, 14 `indoor_bright`, 6 `screenshot`, 1,168 `no_plant_signal`.
- `GET /api/scan/prefilter-rejects` (`scan.py:2157`) lists them too. Originals carry EXIF (GPS, time, device).
- Effort S (photo endpoint: confirmed-only for guests; list: curator-only). Fix risk: low.

**B5-03 · S3 · CONFIRMED — Map GeoJSON ships `reviewer_notes` for every pin.**
- `"description": row.reviewer_notes` (`map.py:257`), commented "landscape description" but emitted for all pins.
- 475 confirmed geotagged pins carry notes, 448 of them non-landscape. They're internal audit/system text, e.g. "[Audit] Observation #10540 was manually corrected…", "auto-approve re-review…", "Auto-rejected: iNat kingdom=Insecta…". Guest-visible.
- Effort S.

**B5-04 · S2 · CONFIRMED (absence) — No sensitive-species concept exists anywhere.**
- `grep -rni "sensitive|obscur|redlist|protected_species|fuzz"` over app/ and scripts/experience_export finds no such field, setting or rule.
- Exact coordinates of every confirmed species reach the guest map, the Export summary (GPX/Google links) and the public experience route.
- Whether a published walk includes a protected species (e.g. *Arnica montana*, *Lilium martagon*, both confirmed in this DB) is checked in D3 (`--plan-only` for walk 4). Until then the *impact* is SUSPECTED.
- **Update (session 2, D3):** walk 4's 62 public species include none of the typically protected groups, so there's no exposure on walk 4 today. The design gap remains (see D3).
- Effort M (a curator flag + rounding rule). Fix risk: low.

**B5-05 · S2 · CONFIRMED — Guest-readable internals.**
- `GET /api/dev/changelog` and `/current-state` (dev.py:218/224) return the full CHANGELOG (internal notes, file paths, backlog).
- `GET /api/dev/snapshots` (`:378`) lists snapshot files. `GET /api/queue/list` and `/sse` stream job state.
- `GET /api/identify/test-connection` (identify.py:230) makes a live PlantNet call per request, so guests can trigger external API use.
- `GET /api/sharing/lan-url` (sharing.py:312-322) reveals the LAN IP and hardcodes port 8000.
- Effort S.

**Verified OK (B5):**
- Experience export photos: re-encoded from pixels only (`export.py:190-199`), then verified with exiftool **and** PIL. A GPS tag kills the build (`:901-903`; exiftool present at `/opt/homebrew/bin/exiftool`; `check=True` makes a missing exiftool fail loud).
- Experience export reads no `reviewer_notes`, `text_note` or encounter data (grep).
- Unconfirmed IDs are excluded by gates rule 1 and blocked by rule 7.
- Minor: page files are written before the metadata check (`:897-902`), so a failing build leaves the offending files in `--out`. S3.

### Phase C — Data integrity

DB copy for this phase: fresh `.backup` taken 20 Oct 2026 16:19 local (integrity_check ok; 16,130 observations, 712 species). File checks ran against the live disk.

#### C.1 Facts verified (no severity)

- **Linkage `species_primary` ↔ `species_id`** (script: `normalize_taxon_key(species_primary)` vs `species.name_key`, synonyms honoured):
  - ok 2,469 confirmed + 81 needs_review + 101 rejected; ok-via-synonym 1.
  - both NULL: 60 confirmed (landscape) + 13,403 others.
  - `species_id` without `species_primary`: 0. `species_id` → missing species: 0.
  - Exceptions: C-03 / C-04.
- **name_key:** 0 duplicates; 0 rows where `name_key != normalize_taxon_key(scientific_name)`; 0 duplicates after `collapse_autonym` + normalise. No `_merged_into:` edibility markers present.
- **Orphans:**
  - culinary_info, drafts, culinary history, recipes, edibility history, enrichment_sources, lookalikes, conditions, synonyms, personal-list rows → all 0 orphans.
  - One species (635 *Galium intermedium*) has no culinary_info row.
  - 18 species are referenced by no observation; 100 by no confirmed observation.
  - Audit rows for deleted observations: species_candidates 744 rows / 112 obs, processing_logs 362 / 120 obs (28 May–25 Jun), observation_edits 118 / 112 obs (30 May–5 Jun).
    - Logs are kept by design (delete docstring `observations.py:853`). The candidate/edit residue predates the explicit delete at `observations.py:918`. S4.
- **saved_walks** (4 rows: 1, 3, 4, 5):
  - All `obs_ids_json` / `accepted_obs_json` / `excluded_obs_json` ids exist and are all confirmed (0 deleted, 0 rejected).
  - `route_geojson` is a valid FeatureCollection with one LineString on walks 3, 4, 5, and NULL on walk 1 (known: "Ewden brook circular (id 1) has no saved line").
  - `foragingid` member `{"version": 2, "circular": true, "stop_radius_m": 30, ...}` on all three. Every circular line is closed (first == last coordinate).
  - `straight_ranges` are in bounds: walk 3 `[[58,61],[96,98]]` of 133 coords; walk 4 `[[100,106]]` of 107; walk 5 none.
- **JSON columns:** every `*_json` / `route_geojson` / `common_names*` / `field_recipes` / `species_tags` value parses, except `enrichment_sources.raw_response_json`: 2,050 / 9,052 rows hold raw PFAF HTML ("<!DOCTYPE html…"). Name/content mismatch. S4.
- **Files** (live disk, paths resolved against the project root; a reference = any observation `file_path`/`thumbnail_path`/`confirmed_copy_path`, or encounter audio/sketch):
  - Non-rejected rows with a missing file: 3 (`pending` prefilter screenshots 21212, 21215, 21216). Missing thumbnail: 0. One `needs_review` row has no `thumbnail_path`; one `needs_review` row's `confirmed_copy_path` is missing.
  - On disk but referenced by no row:

    | Folder | Files | Size | Unreferenced files | Unreferenced size |
    |---|---|---|---|---|
    | `uploads/` | 2,667 | 6.07 GB | 103 | 0.22 GB |
    | `photos/pipeline2/` | 1,598 | 3.62 GB | 0 | — |
    | `data/thumbnails/` | 14,980 | 0.27 GB | 103 | <0.01 GB |
    | `photos/confirmed_plants/` | — | — | 139 | 0.45 GB |

  - `data/thumbnails_quarantine/` (10,770) is in A-05.
- **changed_by / edited_by vocabulary.** Every human-lock check in code compares **`changed_by == "human"` exactly**: `culinary.py:1922, 1934, 1944, 2274, 2411`; `enrichment.py:575, 1055, 1205, 1361`; `encounters.py:588`; `ema_clinical.py:251`. The experience export additionally requires `new_value == current value` (`gates.py:30-34`).

  | Table | Value | Rows | Fields / meaning | Lock? |
  |---|---|---|---|---|
  | culinary_info_history | `human` | 148 | curator edits: edibility_status 34, look_alike 29, prep_warnings 24, edible_parts 22, source URL 11, taste 7, medicinal 4, id_notes 3, … plus `_rename_event` 1, `_name_correction` 1 | **LOCK** (per field) |
  |  | `ai_approved:human` | 633 | AI draft approved by curator (`culinary.py:2436`) | non-lock (by design; gates.py excludes it from "human-authored") |
  |  | `human:placeholder_clear` | 36 | 20 Oct placeholder clean-up | non-lock (by design per CHANGELOG) |
  |  | `human_merge` | 12 | `_merge_event` / `_cleanup_event` markers | non-lock (event marker) |
  |  | `manual_fix` | 1 | `_merge_event` | non-lock (event marker) |
  |  | `pfaf_reparse` | 1,777 | traditional_uses, preparation_warnings (1 Jul batch) | non-lock |
  |  | `pfaf` | 52 | **edibility_status** (29 Jun) | non-lock; automated verdict writes before the "structural no-op" |
  |  | `multi-source` | 31 | **edibility_status** (30 Jun) | non-lock; same |
  |  | `ema` | 33 | medicinal_clinical | non-lock |
  |  | `normalization` | 4 | preparation_warnings | non-lock |
  |  | `system_retroactive` / `system_remediation` | 2 / 2 | `_rename_event` / recipe | non-lock |
  | species_edibility_history | `human` | 143 | verdict, verified, severity, taxonomy (15–19 Oct only) | n/a (verdict lock = `edibility_verified`) |
  | observation_edits | `human` | 19,406 | curator | n/a (no lock concept; terminal status is the guard) |
  |  | `audit:*`, `system:*`, `restore:*`, `repair:*`, `backfill*`, `trust:*` | 457 total | named automated/scripted repairs (e.g. `system:fix1_restore` 67, `system_audit` 56, `restore:fix6_rescue_bug` 28, `backfill: confirmed fungal species` 84, `trust:kingdom_audit` 9, `trust:bulk_landscape` 2) | n/a |

- **app_settings keys the code doesn't know:**
  - `auto_approve_threshold` (set 29 May; no reader).
  - `obsidian_vault_path` (set 2 Jun; **no reader — A-09 now CONFIRMED**: `_export_encounters_to_obsidian` writes to `PROJECT_ROOT / "exports" / "encounters"`, `dev.py:897-914`).
  - `gdrive_access_token` (read raw by `integrations/gdrive.py`; outside the registry).
- **experience_publications = 0 rows, explained.**
  - Walk 4 went live on 15 Oct by hand ("Foraging Experience pushed to github.com/melvinoj/foraging-experience (main 14c1f5f)… Re-publish = rerun export, rsync dist/ into the clone, commit, push", CHANGELOG ~800-809).
  - That predates the table (Stage B2, migration 0054). `export.py` never writes it (no INSERT/UPDATE or table reference in `scripts/experience_export/export.py`).
  - The Stage C publish panel that would create rows isn't built (A-08: the six `/api/experience/publications*` endpoints have no caller). Consequence: C-05.

#### C.2 Findings

**C-01 · S1 · CONFIRMED (data) / SUSPECTED (risk) — 131 confirmed observations have no project-local copy of their photo.**
- Query: non-rejected rows with `file_path LIKE '/Users/melvinjarman/Local(unsynced)/PhoneForaging/%'`.
  - approved 468 (104 without `confirmed_copy_path`).
  - manually_verified 60 (27 without).
  - needs_review 2 (1 without); not_applicable 1 (1 without).
- These rows are 27 May–3 Jun; the first `photos/pipeline2/` row is 3 Jun 14:46. So they predate copy-on-ingest and were never back-copied.
- CLAUDE.md's "each is copied to photos/pipeline2/ before a DB record is created" isn't true for them.
- SUSPECTED risk: if that Syncthing folder ever propagates a phone-side delete or rotation, 131 confirmed photos have no other copy. To confirm: check the folder's Syncthing type (send-only / receive-only / send-receive) and the phone's retention.
- Effort S (one-off copy + path update, per Write Protocol). Fix risk: low.

**C-02 · S1 · CONFIRMED — Rejecting an encounter's photo in review deletes the encounter's only copy.**
- Both `encounter_photos` rows point at rejected observations whose files are gone:
  - encounter 14 → obs 21616 (`uploads/097d23cb…_encounter_9cde51b5….jpg`).
  - encounter 15 → obs 21804 (`uploads/46d95f87…_encounter_83aa341c….jpg`).
- `os.path.exists` is False for both.
- Encounter photos are stored in `uploads/` as ordinary observations. The reject flow's guarded deleter treats every `/uploads/` path as deletable (`file_cleanup.py:21`, `_DELETABLE_SEGMENTS = {"/uploads/", "/photos/pipeline2/", "/photos/confirmed_plants/"}`) and has no encounter-binding check.
- So 2 of 2 bindings now point at deleted files.
- Effort S. Fix risk: low.

**C-03 · S2 · CONFIRMED — 5 confirmed observations name a species that has no species row.** They are map pins with no card, edibility or enrichment.
- 21382 *Filipendula vulgaris*.
- 21453, 21454 *Ganoderma applanatum*: a fungus, still filed `plant` (the 20 Oct fungi rule needs a species row to read the kingdom).
- 21950, 22074 *Conyza canadensis*.
- All approved by a human (Jun–Jul edits). `set_observation_species` resolves `species_id` by **exact `scientific_name`** (`species_link.py:59-67`), not `name_key` as CLAUDE.md requires.
- Three more (24347 *Aleuria aurantia*, 24348 *Euphorbia corollata*, 24356 *Ramaria stricta*, all 20 Oct 10:5x UTC) are transiently unlinked:
  - The species row was created 36 ms – 0.3 s after the confirm (species 841-843 `created_at`), by the enrich call fired after confirm.
  - The init_db FK backfill (`database.py:142-160`, also exact-name) relinks them at the next server start.
- Effort S. Fix risk: low.

**C-04 · S2 · CONFIRMED — Obs 21585's species is a common name.**
- `species_primary = 'norway spruce'`, `species_id = 366` (*Picea abies*), `review_status = 'approved'`.
- History: 27 Jun 06:02:21.008 `species_primary NULL→'Picea abies'` + `needs_review→manually_verified`, then **0.18 s later** `species_primary NULL→'norway spruce'` + `needs_review→approved`. Both writes logged `old_value` NULL.
- The species-card count groups by `species_primary` (`culinary.py:84-97`), so it's a separate "norway spruce" group: *Picea abies* shows 46, not 47.
- Similar: 15957 `Taraxacum sect. Taraxacum` → `species_id` 286 *Taraxacum officinale*.
- Cause SUSPECTED: two overlapping submits from the review card, the second carrying the correction box text. Both read the row before the first commit (both `old_value` NULL). To confirm: trace the review.html approve path that sends `corr-<id>` text alongside confirm-species.
- Effort S (data) / M (cause). Fix risk: low.

**C-05 · S1 · CONFIRMED — The saved-walk delete guard can't see the live walk-4 page.**
- `DELETE /api/walk/saves/{id}` refuses only when an `experience_publications` row is `published` (`walk.py:595-600`). There are no rows (C.1), so walk 4 can be deleted, or its route and membership edited, while its page is live on github.com/melvinoj/foraging-experience.
- Same gap for any republish bookkeeping (frozen labels, unpublish).
- Effort S (backfill one row). Fix risk: low.

**C-06 · S1 · CONFIRMED — The edibility verdict audit trail is incomplete and split across two tables.**
- Verdict history lives in `culinary_info_history.field_name='edibility_status'` (13 Jun–2 Jul: human 34, pfaf 52, multi-source 31) and in `species_edibility_history` (table created 12 Jul by migration 0046; first row 15 Oct).
- **379 of the 487 species with a non-`unknown` verdict have no verdict history row in either table.** 14 of 89 `edibility_verified_by='human'` verdicts have none either.
- Origin SUSPECTED: the pre-June automated PFAF/Wikidata derivation and the init_db provenance backfill (`database.py:178-216`) wrote verdicts and flags without history. To confirm: compare against the earliest snapshot in `snapshots/`.
- Effort M (backfill "origin unknown" rows). Fix risk: low.

**C-07 · S3 · CONFIRMED — `resolve_species_id` and the init_db FK backfill look species up by exact `scientific_name`, not `name_key`.**
- `species_link.py:59-67`; `database.py:146-159`. CLAUDE.md rule: "Use name_key … for all species lookups".
- Cause of C-03's permanent cases whenever the typed name differs only in case, autonym or hybrid marker.
- Effort S. Fix risk: low.

**C-08 · S4 · CONFIRMED — Disk residue.**
- 103 unreferenced files in `uploads/` (0.22 GB), 139 in `photos/confirmed_plants/` (0.45 GB), 103 stale thumbnails.
- `photos/confirmed_plants/` is a second full copy of confirmed photos by design (2,103 of 2,540 confirmed rows have one).
- Known context: "Disk tight". Never bulk-delete from uploads/ without a per-file DB check (CLAUDE.md).
- Effort S.

### Phase D — Outputs

#### D1 PDF / print

**Flow.**
- lists.html stores the list (species, modes, photos) in localStorage via `ForagingList` and opens `/lists/print` (print.html).
- print.html fetches `/api/species/` and each `/api/species/{name}/profile` and renders a preview with its own renderers (`_fieldEntry` `:434-468`, `_workshopPage` `:471-530`). It offers:
  - (a) **browser print**: `window.print()` on the preview, or a new window with the same HTML (`print.html:~700-730`);
  - (b) **Download PDF**: POSTs the same profiles plus `base_species`, `toggles`, `cover` and `seasonal_returns` from localStorage to `POST /api/lists/pdf` (`print.html:793-838`).
- The server (`lists_pdf.py:164-245`) flattens the client data (`_flatten_species` `:85-118`), renders `app/templates/print_pdf.html` with Jinja (**autoescape off**, `:20-25`), and runs WeasyPrint with `base_url=file://…/frontend/`.
- lists.html's own on-screen preview is a third renderer (`lists.html:1768-2030`).

**Scratch PDFs.** 9 generated: layout × style. Fixture: *Conium maculatum* (deadly), *Sambucus nigra* (caution, 2 recipes), *Meum athamanticum* (Apiaceae, 3 recipes), *Coprinus comatus* (fungus, caution), *Taraxacum clemens* (no common name), *Acer pseudoplatanus* (longest recipe, 3,695 chars), plus a cover and one seasonal-return item. Profiles came from the local read-only GET endpoints. `generate_pdf()` was called in a separate venv process (`PYTHONDONTWRITEBYTECODE=1`; the server wasn't involved).

| Layout | Pages (6 species) | Time b / h / g (s) | Size b / h / g |
|---|---|---|---|
| field_guide | 3 / 3 / 2 | 2.89 / 1.75 / 1.31 | 1.18 / 1.13 / 1.30 MB |
| workshop | 10 / 10 / 10 | 0.71 / 0.71 / 1.14 | 1.20 / 1.15 / 1.32 MB |
| recipe_booklet | 4 / 4 / 4 | 0.52 / 0.50 / 1.50 | 1.16 / 1.11 / 1.28 MB |

- **Rendering** (pdftoppm PNG contact sheets, checked visually; `pdffonts`; `pypdf` text per page):
  - Fonts: Georgia family embedded; Hiragino Mincho embedded as glyph fallback.
  - All style border images render; no missing images.
  - No blank pages. The workshop layout has two near-empty pages: Seasonal Returns alone on p2 (99 chars), and the Acer recipe spilling onto p9.
  - The final disclaimer always takes its own page.
- **Size** is ~1.1–1.3 MB regardless of content: two large base64 PNG backgrounds are inlined in the template (`print_pdf.html:51, 57`). The PDF never includes species photos.
- **Failure modes:**
  - `import weasyprint` **fails** in the venv when `DYLD_LIBRARY_PATH` is unset at process start (gobject not found).
  - The module-level `os.environ.setdefault("DYLD_LIBRARY_PATH", "/opt/homebrew/lib")` (`lists_pdf.py:15`) *does* rescue it in-process (tested), because `ctypes.util.find_library` reads the variable at call time. The launcher doesn't set it (`grep DYLD START_ForagingID.command` → none).
  - So the PDF works only if nothing imports WeasyPrint before `lists_pdf.py` is imported (SUSPECTED fragile; confirm by grepping for other WeasyPrint importers if one is added).
  - Import failure → 503 with "Check DYLD_LIBRARY_PATH" (`:227-232`).

**PARITY TABLE — browser print (print.html) vs PDF (print_pdf.html):**

| Aspect | Browser print | PDF | Parity |
|---|---|---|---|
| Layout chosen | list modes combined: `field` → `_fieldEntry`; `workshop` (labelled "Recipe Booklet" in lists.html:980) **or** `workshops` → `_workshopPage` (+ field block if `field` also chosen) (`print.html:768-779`) | **first mode only**: `workshops`→workshop, `workshop`→**recipe_booklet**, else field_guide (`print.html:769-771`) | ✗ "Recipe Booklet" prints as workshop pages in the browser but as the recipe booklet in the PDF |
| One page per species | workshop: yes | recipe_booklet: **no** (5 species on p2 in the test); workshop: yes | ✗ vs lists.html preview "one A4 page per species" (`lists.html:403`) |
| ID notes | full text | truncated 220 chars (field guide) | ✗ |
| Look-alike | field guide: full, only if `ct.id_notes`; workshop: inside the safety block | field guide: **truncated to 140 chars** ("…ground e…" for Conium, losing the "tells"); workshop: full; booklet: toxic/deadly only | ✗ |
| Prep warnings | workshop only, and only if `ct.id_notes !== false` (`print.html:488`) | workshop always; booklet toxic/deadly only; field guide never | ✗ (B2-03; booklet omits Sambucus/Coprinus warnings — **confirmed in rendered text**) |
| Edible parts for toxic | shown (no gate) | hidden (`not in ('deadly','toxic')`) | ✗ (B2-04) |
| Recipes | field guide + workshop (key recipe) | booklet + workshop (key recipe); field guide none | ✗ |
| Medicinal | workshop: `medicinal_notes`/`medicinal_folklore` inserted **unescaped** (`print.html:512`) | workshop: notes + clinical tags + disclaimers | ✗ |
| Badges | `edClass` regex pill; no ☠ | pill + ☠ box (booklet only) | ✗ |
| Names rule | Latin first, common second (no "Common (Latin)"; `species-names.js` not loaded) | same | = (both off-rule) |
| Markdown | recipes via `_mdLite` (headings + bold, escaped, `print.html:362-371`); id_notes raw | recipes via server `_mdlite` (`lists_pdf.py:61-82`); id_notes raw: "**Taraxacum clemens**" printed with asterisks; raw PFAF "Edible Parts:" and "[105]" citations | ✗ renderers differ; both leak raw markdown/PFAF (known backlog item: raw PFAF text) |
| Map snapshot | yes, if `ct.map` (`print.html:775`) | **none** (template has no map) | ✗ |
| Seasonal returns | yes | yes (own page in workshop) | = |
| Cover | two variants (`_coverWorkshop` / `_coverField`) | one block | ✗ |
| Photos | thumbnails / banner | none | ✗ |
| Disclaimer | **none** | final safety disclaimer page | ✗ |
| AI / human provenance | not marked | not marked, yet the PDF disclaimer says "Human-created and/or reviewed content is indicated where shown" (`print_pdf.html:398`) | ✗ (D1-03) |
| Styles | CSS via `setPrintStyle` | three styles with background PNGs from `frontend/static/print` | ≈ |

**D1-01 · S0 · CONFIRMED (reproduced in scratch) — `POST /api/lists/pdf` turns request text into live HTML and embeds local files the server can read.**
- `_jinja_env = jinja2.Environment(..., autoescape=False)` with the comment "we control all inputs server-side" (`lists_pdf.py:20-25`). In fact every field comes from the request body (`species[].profile`, `cover`, `seasonal_returns`).
- WeasyPrint resolves `file://` URLs (`base_url=file://…/frontend/`, `:225-226`).
- Scratch test: one profile whose `culinary.id_notes` contained `<b>…</b>`, `<a rel="attachment" href="file://<scratch>/canary.txt">` and `<img src="file://<scratch>/canary.png">`, passed to `generate_pdf()` in a separate process. Result:
  - the tag rendered (no escaping);
  - the PDF carries a **/FileAttachment containing the canary file's bytes** ("AUDIT-CANARY-7731 local file contents");
  - the 192×192 canary image was drawn on the page.
- Any caller that reaches the endpoint can therefore pull any file the server user can read (e.g. `.env`, `data/foragingid.db`, SSH keys) into a PDF.
- The guest tier blocks this POST (`main.py:279-285`), but the curator tier (LAN, A-03; the default share link, A-01) does not.
- Effort S (autoescape on; restrict WeasyPrint's `url_fetcher` to `frontend/static/print`). Fix risk: low (check that `season_str | safe` and `mdlite | safe` are the only intended HTML).

**D1-02 · S2 · CONFIRMED — Browser print and PDF diverge on layout and safety content** (parity table). Highest impact:
- the "Recipe Booklet" mode mismatch;
- the look-alike text cut at 140 chars in the PDF field guide (`print_pdf.html:305`);
- no disclaimer in browser print;
- the browser workshop's unescaped medicinal HTML.
- Effort M. Fix risk: low.

**D1-03 · S2 · CONFIRMED — The PDF disclaimer promises provenance markers that no print output has.**
- "Human-created and/or reviewed content is indicated where shown" (`print_pdf.html:398`), but no AI/human marker exists in `print_pdf.html` or `print.html` (grep for `ai_`, `✦`, `aiFields`).
- Effort S.

**D1-04 · S3 · CONFIRMED — Data quality surfaces in print.**
- *Acer pseudoplatanus*'s "common name" is the taxonomic series "Acer ser. Acer" (printed under the title in all 9 PDFs).
- *Rosa dumalis*'s family is "Rosa sect. Caninae" (export WARNING).
- Known taxonomy-backlog family.
- Effort S.

#### D2 Export summary (`POST /api/sharing/export-walk`)

**Flow.**
- The walk panel builds the payload client-side (`index.html:7552-7600`): per stop, full-block species with `_culinaryGate`-gated edibility, `culinary_notes` (first of edible_parts / taste_notes / preparation_methods) and one recipe (`_summaryRecipe`), plus an `also_here` list for repeat species.
- `_build_walk_html` (`sharing.py:513-607`) escapes everything (`_h`, `_md_inline` escapes before formatting, `:406-416`) and returns standalone HTML with a print button.
- GPX and the Google link are separate buttons in the walk panel (`index.html:2377`, `:6601-6625`); they aren't part of the HTML.

**Checks:**
- Gates: client-side only (B2-09). No look-alike/prep warnings and no safety disclaimer in the output (B2-03). Edibility badge colours exist only for edible/toxic/inedible/medicinal; caution/unknown render grey (`sharing.py:385-390`).
- Names rule:
  - full blocks: Latin (italic), then common, then extra commons (`:497-503`), which matches the app's stop cards;
  - repeat lines: "Common (*Latin*)" or *Latin* (`:545-546`), per the rule.
- Repeat-species lines: "Also here: … (see stop N)" with the toxicity warning kept (`:539-551`). The warning badge is **always red** (`#dc2626`), including "⚠ toxicity unknown", which is amber in the full block (`:465`) and in the app. S4.
- `n_species` counts unique names across full blocks and repeats (`:517-518`) — correct.
- Footer already says "Generated by LandMemory" (`:604`) and GPX `creator="LandMemory"` (`index.html:6677`) — see Phase F.
- **GPX** (`walkDownloadGpx`, `index.html:6664-6688`): valid GPX 1.1 element order (metadata, wpt*, trk); XML-escaped; full line as the track (`_walkLinePoints` uses the saved geometry, else stops + closing point if circular); one waypoint per stop named "Stop <label>" with Latin species list. CONFIRMED by reading.
- **Google Maps link** (`_buildMapsUrls`, `:6601-6625`): 10 points sampled evenly by distance along the line (origin + 8 waypoints + destination; circular → destination = start), `travelmode=walking`, and a UI note pointing to GPX for the exact track. CONFIRMED by reading.
  - SUSPECTED: Google's documented Maps-URLs limit is up to 9 waypoints on desktop/app but **3 in mobile browsers**, so on a phone browser the link may drop 5 of the 8 waypoints. To confirm: open the link in a mobile browser for walk 4.

**D2-01 · S4 · CONFIRMED** — Repeat-line warning badge colour mismatch (above). Effort S.

#### D3 Experience export (`scripts/experience_export`)

**Pipeline** (`export.py`, read in full for these stages):
1. Load walk + `walk_membership.compute` (app service) from the DB opened `?mode=ro` (`--db`).
2. Gate observations (`gates.obs_passes`: confirmed + identified + human-confirmed).
3. Per-species badge (`gates.edibility_badge`, `gates.py:160-184`) and safety texts (`:187-198`, human-authored only).
4. Recipes (approved, one per species, dedupe, never medicinal).
5. Blockers (rule 7) and the plan print.
6. Taxonomy tree from `frontend/taxonomy.html` with 10 anchored `TREE_PATCHES` (`export.py:228-300`; each must match its expected count or `die()`; banned strings `fetch(`, `/api/`, `/thumbnails`, `/species?s=`, `/static/` checked after patching).
7. App styles copied by anchored regex from tokens.css, species.html, lists.html and **index.html's JS source** (`app_styles.py:60-101`, `StyleDrift` on any count ≠ 1).
8. Photos re-encoded (1200 px main / 400 px thumb), EXIF-free, verified by exiftool + PIL.
9. Write index.html, preview.html and tree.html to `--out`, and for `--default` a full mirror at `w/<slug>/`.

**Runs** (scratch DB copy 16:19; `--out` to scratch; no network):
- `--plan-only --walk-id 4` → **BUILD FAILED: species 277 *Rosa dumalis* is 'edible' but not human-verified**. Walk 4 is currently not republishable as-is.
- A scratch-only harness that collects instead of raising GateError (monkeypatch in `<scratch>/tools/d3_plan_all.py`; no repo code touched):
  - Only that one rule-2 error.
  - 139 member observations, 136 pass, 3 fail.
  - 62 species: edible 29, caution 13, apiaceae 6, toxic 4, inedible 2, none 8. 1 AI-agreed-only (*Stellaria graminea*, toxicity none, not a blocker).
  - 31 stops: `…21, 21a, 22…26☠, 26a, 26b, 27, 28`, 4 with ☠.
  - 19 recipes included (14 `ai_generated`), 15 excluded.
  - Tree 58 placed, 4 not placed.
- Full build: 39 s; **58.2 MB** output (photos 29 MB + an identical 30 MB mirror under `w/ruemmelsbuehl/`); 242 images (121 × 1200×900 avg 207 KB, 121 × 400×300 avg 38 KB); GPS tags exiftool 0 / PIL 0; files with any EXIF 0.
- **Deterministic:** a second build gave byte-identical output (490 files, `shasum` diff empty).

**Page checks** (built files only; no browser, per CLAUDE.md):
- CDN assets carry SRI + `crossorigin`: leaflet 1.9.4 css/js (unpkg, sha256), d3 7.8.5 (cdnjs, sha384).
- Tiles load directly from OSM, OpenTopoMap and Esri, with attribution strings present. Third-party requests from visitors' browsers: the Datenschutz page should cover them (not checked; external).
- `index.html`: `lang="en"`, viewport, `<title>`, canonical `https://melvinoj.github.io/foraging-experience/`. **No meta description or Open Graph tags.**
- Legal: `impressum_url` / `datenschutz_url` / `contact_url` on melvinjarman.co.uk are present in the page data (the CHANGELOG "Impressum placeholder" item is resolved).
- Accessibility: main and gallery images get `alt` = common or Latin name, decorative thumbnails `alt=""`, 27 `aria-`/`role=` uses, `:focus-visible` outline.
- Mobile layout and the 500 px preview card **can't be verified here**:
  - preview.html is a fixed `height: 500px; overflow: hidden` grid (`templates/preview.html:13-27`), so over-long text is clipped silently with no build-time check (SUSPECTED risk; confirm by viewing preview.html at 500 px).
  - Its hero uses the 1200 px photo (`photos/93.jpg`, ~200 KB) where the 400 px thumb would do (S4).
- Coordinates: stop lat/lng at full precision and the full route line (107 vertices) are in `window.DATA` (by design; the pending CHANGELOG item already plans a "exact route public" warning).
- **B5-04 settled for walk 4:** none of the species on the route (62 listed in the plan) belongs to the groups typically protected under Germany's BArtSchV (orchids, *Arnica*, *Lilium martagon*, gentians, *Carlina*, *Daphne*, *Lycopodium*). This is the auditor's reading; confirm against the official list before a workshop route that includes, e.g., *Arnica montana* (confirmed elsewhere in this DB). The design gap (no sensitivity concept) stands.

**PARITY TABLE — app gates vs experience gates (`gates.py`):**

| Rule | In-app surfaces (B2) | Experience page (`gates.py`) |
|---|---|---|
| Observations counted | approved / manually_verified + identified | + **human-confirmed** only (rule 1); AI-agreed-only toxic/unknown = build blocker (rule 7) |
| Edible label | edibility_status shown when severity 'none' (R2) | only `edibility_verified=1 AND _by='human'`; otherwise **build fails** (rule 2) |
| Unknown toxicity | R1/R2 closed, R3/R4/R5 open | closed |
| Toxic / deadly | ☠ label, culinary hidden (where gated) | ☠ badge, no recipe, warning always (fallback sentence verbatim from print_pdf.html) |
| Apiaceae | no rule (**settled**) | ID card only (**settled**) |
| Recipes | approved; R6 blocks toxic/inedible/NULL edibility | approved, ≤1 per species, never medicinal prep, only with a human-verified edible/caution verdict |
| Medicinal | species page, print, PDF | never |
| Look-alike / prep text | any source (PFAF, AI-approved, human) | **human-authored only** (latest history row `changed_by='human'` and equal to current) |
| Caution reason | shown where printed | dropped unless human-authored (D3-01) |
| Names | mixed (C-04; print Latin-first) | `display_common_name` (names rule) |

**D3-01 · S0 · CONFIRMED (built page) — Caution species are published as "Edible with caution" with no reason, two of them alongside recipes.**
- In `window.DATA` (scratch build of walk 4): 13 caution species, **12 with `safety: {}`**.
- *Hypericum perforatum* ("Edible with caution" + AI recipe "St. John's Wort Flower Mead Syllabub…") and *Sambucus nigra* ("Edible with caution" + "Elderflower Brasil") carry no warning. Both have preparation_warnings in the DB (photosensitivity / "raw berries, leaves, stems and bark are toxic"), but these are PFAF-sourced, and gates.py publishes only curator-authored safety text (`gates.py:187-198`).
- Two doctrines collide: "warnings must be present for hazardous species" vs "safety text is curator-authored only".
- Needs a curator decision: author the 12 caution texts, or keep caution species' recipes off the page until a human-authored warning exists.
- Effort S (rule) + curator writing. Fix risk: low.

**D3-02 · S2 · CONFIRMED — `--plan-only` and the plan API stop at the first GateError.**
- `gates.edibility_badge` raises (`gates.py:175-180`); the per-species loop (`export.py:665-673`) has no collect step; `__main__` reports the one error (`:1019-1025`).
- The plan therefore never shows the rest of the publication, and `POST /api/experience/publications/{id}/plan` (`experience.py:186-215`) inherits this. A curator must fix and re-run once per unverified species.
- Effort S. Fix risk: low.

**D3-03 · S3 · CONFIRMED — Coupling: the export reads the app's styles from `frontend/index.html`'s JS source by regex.**
- E.g. the exact minified ternary `${edib==='edible'?'#…':…}` (`app_styles.py:89-91`).
- Any reformat or split of index.html (cf. the Phase E split proposal) fails the export build loudly (`StyleDrift`), so an app UI refactor blocks publishing until the anchors are updated.
- Loud, not silent: correct failure mode, real maintenance cost. Effort M (move shared tokens to `tokens.css`).

**D3-04 · S3 · CONFIRMED — The `--default` build writes a full second copy of every photo under `w/<slug>/`.** That's 30 MB of 58 MB, re-committed to the public repo on every republish. Effort S.

**D3-05 · S3 · CONFIRMED (known pending item, new evidence) — Stop labels have drifted since publication.**
- The plan now yields 31 stops with joined labels `21a`, `26a`, `26b`.
- CHANGELOG 20 Oct says walk 4 "now 28 stops 1–28" and "12a→11a (id 4)".
- Freezing labels at publish is already pending ("Freeze stop labels at publish time").

#### D4 Improvement proposals (no fixes; ranked by value / effort)

| # | Proposal | Benefit | Cost | Risk |
|---|---|---|---|---|
| P1 | **One server-side safety gate** that every output asks: `culinary_allowed` + verdict + severity coupling, keyed on *both* edibility_status and toxicity_severity, returning {badge, may_show_culinary, required_warnings}. Map pop-up, walk panel, species page, Export summary, PDF/print, personal card and the experience gates all consume it. The PDF and Export summary re-check server-side instead of trusting the payload. | Closes B2-01..04, B2-09/10, D1-02, D3-01 in one place; ends the R1–R9 drift | M (one module + 9 call sites; renderers keep their HTML) | Medium: four renderers change at once; needs a fixture test per surface |
| P2 | **Set `toxicity_severity` with the verdict** in `PATCH /api/edibility/status` (toxic → at least 'toxic'; inedible → curator chooses), and treat "never assessed" as unknown rather than the 'none' default (nullable column, or a `toxicity_assessed` flag) | Fixes B2-02 / B2-06 at the root; makes "fails closed" real | S–M (migration + one endpoint + a curator pass over ~490 rows) | Medium: gates go stricter until the curator pass completes (intended) |
| P3 | **Escape by default in the PDF**: autoescape on, explicit `| safe` only for `mdlite` / `season_str`, and a WeasyPrint `url_fetcher` limited to `frontend/static/print` | Closes D1-01 | S | Low |
| P4 | **One markdown renderer**: species.html `_renderMd`, print.html / lists.html `_mdLite`, `lists_pdf._mdlite`, `sharing._md_snippet` → one Python renderer (server) + one JS module (`static/js/md.js`) with the same rules (escape first; headings, bold, italic, lists), also used for id_notes / PFAF clean-up | Consistent recipes; no raw `**` / "[105]" in handouts (known backlog) | S–M | Low |
| P5 | **Names helper everywhere**: load `species-names.js` in species.html, lists.html, print.html, seasons.html and sightings.html, and use `display_common_name` in `lists_pdf._flatten_species` | Names rule consistent in handouts | S | Low |
| P6 | **Consistent badges**: one badge spec (colour + text) for edible / caution / inedible / toxic / deadly / unknown, exported once (tokens.css), read by app, PDF, Export summary and the experience export (also removes D3-03's JS-regex extraction) | Visual + safety consistency; less export fragility | M | Low |
| P7 | **Plan reports all blockers**: collect GateErrors (rule 2) into the plan instead of raising on the first | One curator pass instead of N | S | Low |
| P8 | **Publication bookkeeping**: backfill the walk-4 `experience_publications` row; make the export (or a small `publish` step) record slug / commit / labels | Delete guard works (C-05); frozen labels (D3-05) | S | Low |
| P9 | **Deterministic builds**: already byte-identical (verified). Keep it by pinning Pillow and recording the DB snapshot name in the plan | Reproducible publishes | S | None |
| P10 | **Drop the full mirror copy** for the default walk (redirect or a small index only under `w/<slug>/`) | −30 MB per publish in a public repo | S | Low (old links keep working if a redirect page stays) |
| P11 | **Close the guest-readable data paths** (B5-01/02/03/05, A-02) with one "guest-safe" response filter per router | Privacy | M | Low |

<!-- PHASE-FINDINGS-INSERT-ABOVE -->

---

## Appendices

### Appendix A1 — Endpoint inventory (288 routes in app/api)

Auth markers are a heuristic AST scan of each handler body: `get_identity` / `require_curator` / `host` (is_guest_request/classify_host) / `checks.is_guest`. **Every route is additionally behind the global host-tier middleware** (main.py:253-289). Per-endpoint verification of mutating routes is in the Phase B4 identity matrix.

| # | Method | Path | file:line | handler | auth markers in handler |
|---|---|---|---|---|---|
| 1 | GET | `/api/about` | about.py:96 | get_about | — |
| 2 | PUT | `/api/about` | about.py:106 | update_about | get_identity |
| 3 | POST | `/api/about/regenerate-summary` | about.py:127 | regenerate_summary | get_identity |
| 4 | GET | `/api/audit/checks` | audit.py:70 | list_checks | — |
| 5 | GET | `/api/audit/run` | audit.py:76 | run_audit | — |
| 6 | POST | `/api/audit/send-to-review` | audit.py:525 | audit_send_to_review | — |
| 7 | POST | `/api/audit/reject` | audit.py:596 | audit_reject | — |
| 8 | POST | `/api/audit/reenrich-common-name` | audit.py:674 | audit_reenrich_common_name | — |
| 9 | POST | `/api/bulk/review` | bulk_actions.py:70 | bulk_review | — |
| 10 | POST | `/api/bulk/retry-identify` | bulk_actions.py:185 | bulk_retry_identify | — |
| 11 | POST | `/api/bulk/unlock-prefilter` | bulk_actions.py:227 | bulk_unlock_prefilter | — |
| 12 | POST | `/api/species/{species_name:path}/chat` | chat.py:38 | species_chat | — |
| 13 | GET | `/api/connections/qr` | connections.py:19 | generate_qr | — |
| 14 | GET | `/api/species/` | culinary.py:74 | list_species | — |
| 15 | POST | `/api/culinary/backfill-fungi-edibility` | culinary.py:180 | backfill_fungi_edibility | get_identity, checks.is_guest |
| 16 | GET | `/api/culinary/ai-draft-review` | culinary.py:378 | ai_draft_review_queue | — |
| 17 | GET | `/api/culinary/enrichment-review` | culinary.py:429 | enrichment_review_queue | — |
| 18 | POST | `/api/culinary/transcribe-audio` | culinary.py:526 | transcribe_culinary_audio | get_identity, checks.is_guest |
| 19 | POST | `/api/culinary/{species_name:path}/request-review` | culinary.py:585 | request_enrichment_review | get_identity, checks.is_guest |
| 20 | POST | `/api/culinary/{species_name:path}/clear-review` | culinary.py:620 | clear_enrichment_review | get_identity, checks.is_guest |
| 21 | POST | `/api/culinary/{species_name:path}/approve-enrichment` | culinary.py:643 | approve_enrichment | get_identity, checks.is_guest |
| 22 | POST | `/api/culinary/{species_name}/mark-verified` | culinary.py:680 | mark_species_verified | get_identity, checks.is_guest |
| 23 | POST | `/api/culinary/{species_name:path}/send-for-reid` | culinary.py:701 | send_species_for_reid | get_identity, checks.is_guest |
| 24 | GET | `/api/culinary/{species_name:path}/history` | culinary.py:742 | culinary_field_history | — |
| 25 | POST | `/api/species/rename` | culinary.py:795 | rename_species | get_identity, checks.is_guest |
| 26 | POST | `/api/species/{species_name:path}/rename` | culinary.py:810 | rename_species_by_name | get_identity, checks.is_guest |
| 27 | PATCH | `/api/species/{species_name:path}/preferred-common-name` | culinary.py:995 | set_preferred_common_name | get_identity, checks.is_guest |
| 28 | PATCH | `/api/species/{species_name:path}/common-names` | culinary.py:1027 | edit_common_names | get_identity, checks.is_guest |
| 29 | PATCH | `/api/species/{species_name:path}/foraging-notes` | culinary.py:1088 | set_foraging_notes | get_identity, checks.is_guest |
| 30 | POST | `/api/species/merge` | culinary.py:1279 | merge_species | get_identity, checks.is_guest |
| 31 | GET | `/api/culinary/` | culinary.py:1537 | list_enriched_species | — |
| 32 | GET | `/api/culinary/{species_name:path}` | culinary.py:1577 | get_culinary_profile | — |
| 33 | PATCH | `/api/culinary/{species_name:path}/field` | culinary.py:1656 | correct_culinary_field | get_identity, checks.is_guest |
| 34 | PATCH | `/api/culinary/{species_name:path}/taste-notes` | culinary.py:1755 | edit_taste_notes | get_identity, checks.is_guest |
| 35 | GET | `/api/species/{species_name:path}/observations` | culinary.py:1804 | species_observations | — |
| 36 | GET | `/api/species/{species_name:path}/profile` | culinary.py:1844 | species_profile | get_identity, checks.is_guest |
| 37 | POST | `/api/culinary/{species_name:path}/enrich` | culinary.py:2227 | enrich_species_now | get_identity, checks.is_guest |
| 38 | POST | `/api/species/{species_name:path}/drafts/{field}/approve` | culinary.py:2345 | approve_ai_draft | get_identity, checks.is_guest |
| 39 | POST | `/api/species/{species_name:path}/drafts/{field}/reject` | culinary.py:2494 | reject_ai_draft | get_identity, checks.is_guest |
| 40 | POST | `/api/drafts/generate` | culinary.py:2695 | generate_drafts | get_identity, checks.is_guest |
| 41 | POST | `/api/drafts/bulk-generate` | culinary.py:2719 | bulk_generate_drafts | get_identity, checks.is_guest |
| 42 | POST | `/api/enrichment/run` | culinary.py:2872 | start_enrichment_run | get_identity, checks.is_guest |
| 43 | GET | `/api/enrichment/status/{job_id}` | culinary.py:2997 | get_enrichment_status | — |
| 44 | GET | `/api/enrichment/running` | culinary.py:3015 | get_running_job | — |
| 45 | GET | `/api/drafts/backfill-counts` | culinary.py:3278 | get_backfill_counts | — |
| 46 | GET | `/api/drafts/prompt-defaults` | culinary.py:3497 | get_prompt_defaults | — |
| 47 | POST | `/api/drafts/backfill` | culinary.py:3595 | start_draft_backfill | get_identity, checks.is_guest |
| 48 | GET | `/api/data-sources` | data_sources.py:123 | list_data_sources | — |
| 49 | POST | `/api/data-sources` | data_sources.py:129 | create_data_source | — |
| 50 | PATCH | `/api/data-sources/{source_id}` | data_sources.py:158 | update_data_source | — |
| 51 | DELETE | `/api/data-sources/{source_id}` | data_sources.py:191 | delete_data_source | — |
| 52 | POST | `/api/data-sources/{source_id}/test` | data_sources.py:199 | test_data_source | — |
| 53 | GET | `/api/dev/changelog` | dev.py:218 | get_changelog | — |
| 54 | GET | `/api/dev/current-state` | dev.py:224 | get_current_state_endpoint | — |
| 55 | PUT | `/api/dev/current-state` | dev.py:238 | update_current_state | — |
| 56 | POST | `/api/dev/log` | dev.py:253 | append_log | — |
| 57 | POST | `/api/dev/snapshot` | dev.py:287 | create_snapshot | — |
| 58 | GET | `/api/dev/snapshots` | dev.py:378 | list_snapshots | — |
| 59 | POST | `/api/dev/restore` | dev.py:446 | restore_snapshot | — |
| 60 | GET | `/api/dev/snapshot-changelog` | dev.py:502 | snapshot_changelog | — |
| 61 | POST | `/api/dev/end-session` | dev.py:605 | end_session | — |
| 62 | POST | `/api/dev/git-push` | dev.py:738 | git_push | — |
| 63 | GET | `/api/dev/backup-external-status` | dev.py:777 | backup_external_status | — |
| 64 | POST | `/api/dev/backup-external` | dev.py:787 | backup_external | — |
| 65 | POST | `/api/dev/export-encounters-to-obsidian` | dev.py:962 | export_encounters_to_obsidian | — |
| 66 | GET | `/api/edibility/review-queue` | edibility.py:131 | edibility_review_queue | — |
| 67 | GET | `/api/edibility/species` | edibility.py:249 | list_edibility_species | — |
| 68 | GET | `/api/edibility/unknown` | edibility.py:345 | list_unknown_edibility | — |
| 69 | PATCH | `/api/edibility/bulk-status` | edibility.py:395 | bulk_set_edibility_status | get_identity, checks.is_guest |
| 70 | PATCH | `/api/edibility/status/{species_id}` | edibility.py:469 | set_edibility_status | get_identity, checks.is_guest |
| 71 | GET | `/api/edibility/rescan-status` | edibility.py:618 | rescan_status | — |
| 72 | POST | `/api/edibility/rescan` | edibility.py:624 | rescan_unknown_edibility | — |
| 73 | GET | `/api/edibility/conditions/{species_id}` | edibility.py:659 | get_conditions | — |
| 74 | POST | `/api/edibility/conditions` | edibility.py:682 | add_condition | — |
| 75 | DELETE | `/api/edibility/conditions/{condition_id}` | edibility.py:720 | delete_condition | — |
| 76 | GET | `/api/edibility/lookalikes/{species_id}` | edibility.py:739 | get_lookalikes | — |
| 77 | POST | `/api/edibility/lookalikes` | edibility.py:766 | add_lookalike | — |
| 78 | DELETE | `/api/edibility/lookalikes/{lookalike_id}` | edibility.py:804 | delete_lookalike | — |
| 79 | GET | `/api/edibility/summary/{species_id}` | edibility.py:823 | get_edibility_summary | — |
| 80 | PATCH | `/api/edibility/phenology/{species_id}` | edibility.py:894 | set_phenology | — |
| 81 | POST | `/api/encounters` | encounters.py:140 | create_encounter | get_identity |
| 82 | GET | `/api/encounters/pending-transcripts` | encounters.py:259 | pending_transcripts | — |
| 83 | GET | `/api/encounters/field-recipes` | encounters.py:275 | list_field_recipes | — |
| 84 | GET | `/api/encounters` | encounters.py:306 | list_encounters | get_identity, checks.is_guest |
| 85 | GET | `/api/encounters/{encounter_id}/photo-candidates` | encounters.py:359 | photo_candidates | — |
| 86 | POST | `/api/encounters/{encounter_id}/bind-photo` | encounters.py:421 | bind_photo | — |
| 87 | POST | `/api/encounters/backfill-photo-bindings` | encounters.py:455 | backfill_photo_bindings | — |
| 88 | GET | `/api/encounters/{encounter_id}` | encounters.py:467 | get_encounter | — |
| 89 | PATCH | `/api/encounters/{encounter_id}/coordinates` | encounters.py:491 | set_encounter_coordinates | — |
| 90 | DELETE | `/api/encounters/{encounter_id}` | encounters.py:521 | delete_encounter | — |
| 91 | POST | `/api/encounters/{encounter_id}/transcribe` | encounters.py:542 | transcribe_encounter | — |
| 92 | POST | `/api/encounters/{encounter_id}/extract` | encounters.py:643 | extract_encounter | — |
| 93 | POST | `/api/encounters/{encounter_id}/suggestions/{suggestion_id}/{action}` | encounters.py:676 | resolve_suggestion | — |
| 94 | PATCH | `/api/encounters/{encounter_id}/field-recipe` | encounters.py:747 | save_field_recipe | — |
| 95 | DELETE | `/api/encounters/{encounter_id}/field-recipe` | encounters.py:769 | delete_field_recipe | — |
| 96 | POST | `/api/encounters/reading-note` | encounters.py:787 | save_reading_note | — |
| 97 | GET | `/api/enrich/status` | enrich.py:95 | enrich_status | — |
| 98 | GET | `/api/enrich/last-run-table` | enrich.py:111 | last_run_table | — |
| 99 | POST | `/api/enrich/run` | enrich.py:220 | enrich_run | — |
| 100 | POST | `/api/enrich/resume` | enrich.py:228 | enrich_resume | — |
| 101 | POST | `/api/enrich/re-enrich-empty` | enrich.py:301 | re_enrich_empty | — |
| 102 | GET | `/api/experience/publications` | experience.py:118 | list_publications | router-dep require_curator |
| 103 | GET | `/api/experience/publications/{pub_id}` | experience.py:124 | get_publication | router-dep require_curator |
| 104 | POST | `/api/experience/publications` | experience.py:134 | create_publication | require_curator, router-dep require_curator |
| 105 | PATCH | `/api/experience/publications/{pub_id}` | experience.py:156 | patch_publication | router-dep require_curator |
| 106 | POST | `/api/experience/publications/{pub_id}/plan` | experience.py:186 | plan_publication | router-dep require_curator |
| 107 | POST | `/api/experience/verify-species` | experience.py:228 | verify_species | router-dep require_curator |
| 108 | GET | `/api/experience/critical` | experience.py:279 | critical_hazards | router-dep require_curator |
| 109 | GET | `/api/find/in-season` | find.py:36 | find_in_season | — |
| 110 | GET | `/api/find/recipes` | find.py:163 | find_recipes | — |
| 111 | GET | `/api/find/medicinal` | find.py:241 | find_medicinal | — |
| 112 | GET | `/api/sessions` | foray_sessions.py:106 | list_sessions | — |
| 113 | POST | `/api/sessions` | foray_sessions.py:122 | create_session | — |
| 114 | GET | `/api/sessions/{session_id}` | foray_sessions.py:146 | get_session | — |
| 115 | PATCH | `/api/sessions/{session_id}` | foray_sessions.py:196 | update_session | — |
| 116 | DELETE | `/api/sessions/{session_id}` | foray_sessions.py:215 | delete_session | — |
| 117 | POST | `/api/sessions/{session_id}/auto-populate` | foray_sessions.py:226 | auto_populate | — |
| 118 | POST | `/api/sessions/{session_id}/species` | foray_sessions.py:310 | add_species | — |
| 119 | DELETE | `/api/sessions/{session_id}/species/{species_id}` | foray_sessions.py:348 | remove_species | — |
| 120 | PATCH | `/api/sessions/{session_id}/species/reorder` | foray_sessions.py:360 | reorder_species | — |
| 121 | POST | `/api/sessions/{session_id}/attendees` | foray_sessions.py:383 | add_attendee | — |
| 122 | DELETE | `/api/sessions/{session_id}/attendees/{attendee_id}` | foray_sessions.py:402 | remove_attendee | — |
| 123 | POST | `/api/identify/prefilter-failed` | identify.py:29 | prefilter_failed_observations | — |
| 124 | GET | `/api/identify/prefilter-breakdown` | identify.py:65 | prefilter_breakdown | — |
| 125 | POST | `/api/identify/tier-action` | identify.py:133 | prefilter_tier_action | — |
| 126 | GET | `/api/identify/test-connection` | identify.py:230 | test_plantnet_connection | — |
| 127 | GET | `/api/identify/queue` | identify.py:296 | review_queue | — |
| 128 | GET | `/api/identify/stats` | identify.py:339 | identification_stats | — |
| 129 | GET | `/api/ingest/default-folder` | ingest.py:86 | get_default_folder | — |
| 130 | GET | `/api/ingest/recent-folders` | ingest.py:92 | get_recent_folders | — |
| 131 | POST | `/api/ingest/scan` | ingest.py:109 | trigger_scan | — |
| 132 | GET | `/api/ingest/status` | ingest.py:126 | scan_status | — |
| 133 | GET | `/api/ingest/pipeline-stats` | ingest.py:131 | pipeline_stats | — |
| 134 | GET | `/api/ingest/db-summary` | ingest.py:226 | db_summary | — |
| 135 | POST | `/api/ingest/send-to-review` | ingest.py:343 | send_to_review | — |
| 136 | GET | `/api/ingest/open-folder-picker` | ingest.py:397 | open_folder_picker | — |
| 137 | POST | `/api/itis/backfill` | itis.py:58 | start_backfill | — |
| 138 | GET | `/api/itis/backfill/status` | itis.py:125 | backfill_status | — |
| 139 | POST | `/api/itis/lookup/{name:path}` | itis.py:135 | lookup_one | — |
| 140 | POST | `/api/itis/accept-rename/{name:path}` | itis.py:167 | accept_rename | — |
| 141 | POST | `/api/lists/pdf` | lists_pdf.py:164 | generate_pdf | — |
| 142 | GET | `/api/map/config` | map.py:48 | map_config | — |
| 143 | GET | `/api/map/geojson` | map.py:105 | map_geojson | — |
| 144 | GET | `/api/map/heat` | map.py:266 | map_heat | — |
| 145 | GET | `/api/nearby` | nearby.py:64 | nearby | — |
| 146 | GET | `/api/notes/geojson` | notes.py:22 | notes_geojson | — |
| 147 | POST | `/api/notes/` | notes.py:48 | create_note | get_identity, checks.is_guest |
| 148 | DELETE | `/api/notes/{note_id}` | notes.py:75 | delete_note | — |
| 149 | GET | `/api/notes/by-species/{species_name}` | notes.py:85 | notes_by_species | — |
| 150 | GET | `/api/notifications/seasonal-returns` | notifications.py:35 | seasonal_returns | — |
| 151 | POST | `/api/notifications/seasonal-returns/dismiss` | notifications.py:63 | dismiss_seasonal_return | — |
| 152 | GET | `/api/observations/confirmed-no-gps` | observations.py:124 | confirmed_no_gps | — |
| 153 | GET | `/api/observations/location-review` | observations.py:169 | location_review_queue | — |
| 154 | GET | `/api/observations` | observations.py:246 | list_observations | — |
| 155 | GET | `/api/observations/stats` | observations.py:375 | observation_stats | — |
| 156 | GET | `/api/observations/label-counts` | observations.py:411 | label_counts | — |
| 157 | GET | `/api/observations/prefilter-categories` | observations.py:425 | list_prefilter_categories | — |
| 158 | GET | `/api/observations/{observation_id}` | observations.py:447 | get_observation | — |
| 159 | PATCH | `/api/observations/{observation_id}/review` | observations.py:455 | update_review | — |
| 160 | PATCH | `/api/observations/{observation_id}/correct` | observations.py:513 | correct_species | — |
| 161 | PATCH | `/api/observations/{observation_id}/suggest` | observations.py:569 | set_species_suggested | — |
| 162 | PATCH | `/api/observations/{observation_id}/category` | observations.py:595 | set_category | — |
| 163 | PATCH | `/api/observations/{observation_id}/notes` | observations.py:647 | update_notes | — |
| 164 | PATCH | `/api/observations/{observation_id}/coordinates` | observations.py:668 | set_coordinates | — |
| 165 | GET | `/api/observations/{observation_id}/photo` | observations.py:728 | serve_observation_photo | — |
| 166 | GET | `/api/observations/{observation_id}/edits` | observations.py:747 | get_edit_history | — |
| 167 | POST | `/api/observations/{observation_id}/reject-undo` | observations.py:769 | reject_undo | — |
| 168 | DELETE | `/api/observations/{observation_id}` | observations.py:842 | delete_observation | — |
| 169 | GET | `/api/personal-lists/my-season` | personal_lists.py:92 | get_my_season | — |
| 170 | POST | `/api/personal-lists/my-season/species` | personal_lists.py:158 | add_species_to_my_season | — |
| 171 | DELETE | `/api/personal-lists/my-season/species/{species_id}` | personal_lists.py:185 | remove_species_from_my_season | — |
| 172 | GET | `/api/personal-lists/card/{species_id}` | personal_lists.py:212 | get_personal_card | — |
| 173 | GET | `/api/processes/active` | processes.py:55 | get_active_processes | — |
| 174 | POST | `/api/processes/{process_id}/pause` | processes.py:82 | pause_process | — |
| 175 | POST | `/api/processes/{process_id}/cancel` | processes.py:101 | cancel_process | — |
| 176 | POST | `/api/processes/{process_id}/dismiss` | processes.py:118 | dismiss_process | — |
| 177 | GET | `/api/processes/cancellable-types` | processes.py:161 | list_cancellable_types | — |
| 178 | POST | `/api/queue/enqueue` | queue_api.py:283 | enqueue | — |
| 179 | GET | `/api/queue/list` | queue_api.py:324 | list_jobs | — |
| 180 | GET | `/api/queue/sse` | queue_api.py:329 | sse_stream | — |
| 181 | PATCH | `/api/queue/{job_id}` | queue_api.py:362 | patch_job | — |
| 182 | POST | `/api/queue/{job_id}/cancel` | queue_api.py:464 | cancel_job | — |
| 183 | POST | `/api/queue/{job_id}/pause` | queue_api.py:469 | pause_job | — |
| 184 | POST | `/api/queue/{job_id}/resume` | queue_api.py:492 | resume_job | — |
| 185 | POST | `/api/queue/{job_id}/move-to-top` | queue_api.py:515 | move_to_top | — |
| 186 | POST | `/api/queue/kill-all` | queue_api.py:538 | kill_all_jobs | — |
| 187 | GET | `/api/species/{species_name:path}/recipes` | recipes.py:93 | list_recipes | — |
| 188 | POST | `/api/species/{species_name:path}/recipes` | recipes.py:139 | add_recipe | — |
| 189 | PATCH | `/api/species/{species_name:path}/recipes/{recipe_id}` | recipes.py:178 | edit_recipe | — |
| 190 | POST | `/api/species/{species_name:path}/recipes/{recipe_id}/set-preferred` | recipes.py:223 | set_preferred_recipe | — |
| 191 | POST | `/api/species/{species_name:path}/recipes/{recipe_id}/archive` | recipes.py:244 | archive_recipe | — |
| 192 | POST | `/api/species/{species_name:path}/recipes/regenerate` | recipes.py:268 | regenerate_recipe | — |
| 193 | POST | `/api/recorded-walks` | recorded_walks.py:172 | create_recorded_walk | get_identity, checks.is_guest |
| 194 | GET | `/api/recorded-walks` | recorded_walks.py:244 | list_recorded_walks | — |
| 195 | GET | `/api/recorded-walks/{walk_id}` | recorded_walks.py:271 | get_recorded_walk | — |
| 196 | POST | `/api/recorded-walks/{walk_id}/elevation` | recorded_walks.py:339 | enrich_elevation | get_identity, checks.is_guest |
| 197 | DELETE | `/api/recorded-walks/{walk_id}` | recorded_walks.py:360 | delete_recorded_walk | get_identity, checks.is_guest |
| 198 | POST | `/api/recorded-walks/audio-upload` | recorded_walks.py:385 | upload_audio_note | get_identity, checks.is_guest |
| 199 | POST | `/api/observations/{observation_id}/reidentify` | reidentify.py:221 | reidentify_observation | — |
| 200 | POST | `/api/observations/{observation_id}/second-opinion` | reidentify.py:399 | second_opinion | — |
| 201 | POST | `/api/observations/{observation_id}/retry-identify` | reidentify.py:690 | retry_identify | — |
| 202 | POST | `/api/observations/{observation_id}/retry-confirm` | reidentify.py:841 | retry_confirm | — |
| 203 | POST | `/api/observations/{observation_id}/confirm-species` | reidentify.py:916 | confirm_species | — |
| 204 | GET | `/api/species/lookup` | reidentify.py:1029 | species_lookup | — |
| 205 | POST | `/api/observations/{observation_id}/gbif-check` | reidentify.py:1127 | gbif_uk_check | — |
| 206 | GET | `/api/species/{species_name:path}/resources` | resources.py:40 | list_resources | — |
| 207 | POST | `/api/species/{species_name:path}/resources` | resources.py:54 | add_resource | — |
| 208 | POST | `/api/species/{species_name:path}/resources/upload` | resources.py:77 | upload_resource | — |
| 209 | DELETE | `/api/species/{species_name:path}/resources/{resource_id}` | resources.py:124 | delete_resource | — |
| 210 | POST | `/api/scan/caffeinate/start` | scan.py:132 | caffeinate_start | — |
| 211 | POST | `/api/scan/caffeinate/stop` | scan.py:160 | caffeinate_stop | — |
| 212 | GET | `/api/scan/caffeinate/status` | scan.py:188 | caffeinate_status | — |
| 213 | GET | `/api/scan/inat-token-status` | scan.py:204 | inat_token_status | — |
| 214 | POST | `/api/scan` | scan.py:231 | scan_image | — |
| 215 | GET | `/api/scan/{obs_id}/status` | scan.py:624 | scan_status | — |
| 216 | POST | `/api/scan/{obs_id}/override-prefilter` | scan.py:665 | override_prefilter | — |
| 217 | POST | `/api/scan/recheck-threshold` | scan.py:705 | recheck_threshold | — |
| 218 | POST | `/api/scan/reprocess-pending` | scan.py:779 | reprocess_pending | — |
| 219 | GET | `/api/scan/prefilter-rejects` | scan.py:2157 | list_prefilter_rejects | — |
| 220 | POST | `/api/scan/sessions` | scan.py:2206 | create_scan_session | — |
| 221 | GET | `/api/scan/sessions/all` | scan.py:2228 | list_all_sessions | — |
| 222 | GET | `/api/scan/available-folders` | scan.py:2235 | available_folders | — |
| 223 | GET | `/api/scan/sessions` | scan.py:2262 | list_recent_sessions | — |
| 224 | GET | `/api/scan/lifetime-breakdown` | scan.py:2269 | lifetime_breakdown | — |
| 225 | GET | `/api/scan/p2-stats` | scan.py:2282 | p2_stats | — |
| 226 | POST | `/api/scan/rescan` | scan.py:2315 | rescan_folder | — |
| 227 | POST | `/api/scan/process-delta` | scan.py:2471 | process_delta | — |
| 228 | POST | `/api/scan/scan-archive` | scan.py:2615 | scan_archive | — |
| 229 | GET | `/api/scan/archive-progress/{job_id}` | scan.py:2672 | archive_progress | — |
| 230 | GET | `/api/scan/progress/{session_id}` | scan.py:3100 | scan_progress | — |
| 231 | GET | `/api/scan/sessions/{session_id}/retryable-obs` | scan.py:3175 | get_session_retryable_obs | — |
| 232 | POST | `/api/scan/{obs_id}/retry-id` | scan.py:3195 | retry_identification | — |
| 233 | POST | `/api/scan/pause/{session_id}` | scan.py:3233 | pause_session | — |
| 234 | DELETE | `/api/scan/sessions/{session_id}` | scan.py:3295 | delete_session | — |
| 235 | GET | `/api/settings/api-meta` | settings.py:45 | api_meta | host |
| 236 | GET | `/api/settings/api-status` | settings.py:54 | api_status | host |
| 237 | GET | `/api/settings/api-status/{api_id}` | settings.py:63 | api_status_one | host |
| 238 | POST | `/api/settings/api-key` | settings.py:75 | save_api_key | get_identity, checks.is_guest |
| 239 | GET | `/api/settings` | settings.py:93 | list_settings | — |
| 240 | PUT | `/api/settings/{key}` | settings.py:121 | update_setting | get_identity, checks.is_guest |
| 241 | DELETE | `/api/settings/{key}` | settings.py:141 | reset_setting_endpoint | get_identity, checks.is_guest |
| 242 | GET | `/api/settings/synthesis-sources` | settings.py:205 | get_synthesis_sources | — |
| 243 | POST | `/api/settings/synthesis-sources` | settings.py:219 | add_synthesis_source | get_identity, checks.is_guest |
| 244 | DELETE | `/api/settings/synthesis-sources/{domain:path}` | settings.py:247 | remove_synthesis_source | get_identity, checks.is_guest |
| 245 | POST | `/api/sharing/start` | sharing.py:161 | start_sharing | — |
| 246 | POST | `/api/sharing/stop` | sharing.py:248 | stop_sharing | — |
| 247 | GET | `/api/sharing/status` | sharing.py:271 | sharing_status | — |
| 248 | GET | `/api/me` | sharing.py:298 | me | host |
| 249 | GET | `/api/sharing/lan-url` | sharing.py:313 | lan_url | — |
| 250 | POST | `/api/sharing/export-walk` | sharing.py:373 | export_walk | — |
| 251 | GET | `/api/syncthing/status` | syncthing.py:309 | syncthing_status | — |
| 252 | GET | `/api/syncthing/rejected` | syncthing.py:375 | list_rejected | — |
| 253 | POST | `/api/syncthing/process` | syncthing.py:522 | syncthing_process | — |
| 254 | POST | `/api/syncthing/reprocess` | syncthing.py:580 | syncthing_reprocess | — |
| 255 | GET | `/api/species/taxonomy-tree` | taxonomy.py:121 | get_taxonomy_tree | — |
| 256 | GET | `/api/timeline/positions` | timeline.py:213 | timeline_positions | — |
| 257 | GET | `/api/timeline/at` | timeline.py:322 | timeline_at | — |
| 258 | GET | `/api/trust/stats` | trust.py:53 | trust_stats | — |
| 259 | GET | `/api/trust/confidence-review` | trust.py:202 | confidence_review | — |
| 260 | POST | `/api/trust/accept-species` | trust.py:305 | accept_species | — |
| 261 | POST | `/api/trust/bulk-send-to-review` | trust.py:343 | bulk_send_to_review | — |
| 262 | POST | `/api/trust/bulk-reassign` | trust.py:411 | bulk_reassign | — |
| 263 | POST | `/api/trust/kingdom-audit` | trust.py:525 | kingdom_audit | — |
| 264 | POST | `/api/trust/bulk-landscape` | trust.py:669 | bulk_landscape | — |
| 265 | POST | `/api/trust/bulk-clear-culinary` | trust.py:736 | bulk_clear_culinary | — |
| 266 | POST | `/api/walk/ors-route` | walk.py:52 | ors_route | — |
| 267 | POST | `/api/walk/saves` | walk.py:107 | save_walk | get_identity |
| 268 | GET | `/api/walk/saves` | walk.py:132 | list_walks | — |
| 269 | GET | `/api/walk/saves/{walk_id}` | walk.py:239 | get_walk | — |
| 270 | PATCH | `/api/walk/saves/{walk_id}/membership` | walk.py:269 | set_walk_membership | get_identity, require_curator |
| 271 | POST | `/api/walk/saves/{walk_id}/accept` | walk.py:293 | accept_obs | get_identity, require_curator |
| 272 | POST | `/api/walk/saves/{walk_id}/exclude` | walk.py:336 | exclude_obs | get_identity, require_curator |
| 273 | POST | `/api/walk/saves/{walk_id}/renumber` | walk.py:368 | renumber_walk | get_identity, require_curator |
| 274 | PATCH | `/api/walk/saves/{walk_id}/loop` | walk.py:392 | set_walk_loop | get_identity, require_curator |
| 275 | POST | `/api/walk/saves/{walk_id}/reroute` | walk.py:433 | reroute_walk | get_identity, require_curator |
| 276 | POST | `/api/walk/saves/{walk_id}/reorder` | walk.py:537 | reorder_walk | get_identity, require_curator |
| 277 | DELETE | `/api/walk/saves/{walk_id}` | walk.py:583 | delete_walk | get_identity, require_curator |
| 278 | POST | `/api/workshop/participants/find-or-create` | workshop_tokens.py:75 | find_or_create_participant | get_identity, require_curator |
| 279 | POST | `/api/workshop/participants` | workshop_tokens.py:98 | create_participant | get_identity, require_curator |
| 280 | POST | `/api/workshop/tokens` | workshop_tokens.py:112 | mint_token | get_identity, require_curator |
| 281 | POST | `/api/workshop/sessions` | workshop_tokens.py:149 | create_session | get_identity, require_curator |
| 282 | PATCH | `/api/workshop/sessions/{session_id}` | workshop_tokens.py:173 | update_session | get_identity, require_curator |
| 283 | GET | `/api/workshop/sessions` | workshop_tokens.py:199 | list_sessions | get_identity, require_curator |
| 284 | GET | `/api/workshop/sessions/{session_id}/location-suggestions` | workshop_tokens.py:267 | location_suggestions | get_identity, require_curator |
| 285 | GET | `/api/workshop/participants/{participant_id}/history` | workshop_tokens.py:339 | participant_history | get_identity, require_curator |
| 286 | GET | `/api/workshop/participants` | workshop_tokens.py:414 | list_participants | get_identity, require_curator |
| 287 | GET | `/api/workshop/tokens` | workshop_tokens.py:480 | list_tokens | get_identity, require_curator |
| 288 | POST | `/api/workshop/tokens/{token_id}/revoke` | workshop_tokens.py:513 | revoke_token | get_identity, require_curator |

### Appendix A2 — Identity matrix: every mutating endpoint (172)

Endpoint check = what the handler itself enforces (AST scan of handler body, spot-checked by reading). **All rows are additionally behind the host-tier middleware** (main.py:253-289): curator tier (localhost, LAN, ngrok with guest mode OFF) reaches every row; guest tier reaches only rows marked **yes** in the last column.

| Method | Path | file:line | Endpoint check | Guest-tier write allowed by middleware |
|---|---|---|---|---|
| PUT | `/api/about` | about.py:106 | guest→403 (endpoint) | no (403) |
| POST | `/api/about/regenerate-summary` | about.py:127 | guest→403 (endpoint) | no (403) |
| POST | `/api/audit/send-to-review` | audit.py:525 | HOST-TIER ONLY | no (403) |
| POST | `/api/audit/reject` | audit.py:596 | HOST-TIER ONLY | no (403) |
| POST | `/api/audit/reenrich-common-name` | audit.py:674 | HOST-TIER ONLY | no (403) |
| POST | `/api/bulk/review` | bulk_actions.py:70 | HOST-TIER ONLY | no (403) |
| POST | `/api/bulk/retry-identify` | bulk_actions.py:185 | HOST-TIER ONLY | no (403) |
| POST | `/api/bulk/unlock-prefilter` | bulk_actions.py:227 | HOST-TIER ONLY | no (403) |
| POST | `/api/species/{species_name:path}/chat` | chat.py:38 | HOST-TIER ONLY | no (403) |
| POST | `/api/culinary/backfill-fungi-edibility` | culinary.py:180 | guest→403 (endpoint) | no (403) |
| POST | `/api/culinary/transcribe-audio` | culinary.py:526 | guest→403 (endpoint) | no (403) |
| POST | `/api/culinary/{species_name:path}/request-review` | culinary.py:585 | guest→403 (endpoint) | no (403) |
| POST | `/api/culinary/{species_name:path}/clear-review` | culinary.py:620 | guest→403 (endpoint) | no (403) |
| POST | `/api/culinary/{species_name:path}/approve-enrichment` | culinary.py:643 | guest→403 (endpoint) | no (403) |
| POST | `/api/culinary/{species_name}/mark-verified` | culinary.py:680 | guest→403 (endpoint) | no (403) |
| POST | `/api/culinary/{species_name:path}/send-for-reid` | culinary.py:701 | guest→403 (endpoint) | no (403) |
| POST | `/api/species/rename` | culinary.py:795 | guest→403 (endpoint) | no (403) |
| POST | `/api/species/{species_name:path}/rename` | culinary.py:810 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/species/{species_name:path}/preferred-common-name` | culinary.py:995 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/species/{species_name:path}/common-names` | culinary.py:1027 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/species/{species_name:path}/foraging-notes` | culinary.py:1088 | guest→403 (endpoint) | no (403) |
| POST | `/api/species/merge` | culinary.py:1279 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/culinary/{species_name:path}/field` | culinary.py:1656 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/culinary/{species_name:path}/taste-notes` | culinary.py:1755 | guest→403 (endpoint) | no (403) |
| POST | `/api/culinary/{species_name:path}/enrich` | culinary.py:2227 | guest→403 (endpoint) | no (403) |
| POST | `/api/species/{species_name:path}/drafts/{field}/approve` | culinary.py:2345 | guest→403 (endpoint) | no (403) |
| POST | `/api/species/{species_name:path}/drafts/{field}/reject` | culinary.py:2494 | guest→403 (endpoint) | no (403) |
| POST | `/api/drafts/generate` | culinary.py:2695 | guest→403 (endpoint) | no (403) |
| POST | `/api/drafts/bulk-generate` | culinary.py:2719 | guest→403 (endpoint) | no (403) |
| POST | `/api/enrichment/run` | culinary.py:2872 | guest→403 (endpoint) | no (403) |
| POST | `/api/drafts/backfill` | culinary.py:3595 | guest→403 (endpoint) | no (403) |
| POST | `/api/data-sources` | data_sources.py:129 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/data-sources/{source_id}` | data_sources.py:158 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/data-sources/{source_id}` | data_sources.py:191 | HOST-TIER ONLY | no (403) |
| POST | `/api/data-sources/{source_id}/test` | data_sources.py:199 | HOST-TIER ONLY | no (403) |
| PUT | `/api/dev/current-state` | dev.py:238 | HOST-TIER ONLY | no (403) |
| POST | `/api/dev/log` | dev.py:253 | HOST-TIER ONLY | no (403) |
| POST | `/api/dev/snapshot` | dev.py:287 | HOST-TIER ONLY | no (403) |
| POST | `/api/dev/restore` | dev.py:446 | HOST-TIER ONLY | no (403) |
| POST | `/api/dev/end-session` | dev.py:605 | HOST-TIER ONLY | no (403) |
| POST | `/api/dev/git-push` | dev.py:738 | HOST-TIER ONLY | no (403) |
| POST | `/api/dev/backup-external` | dev.py:787 | HOST-TIER ONLY | no (403) |
| POST | `/api/dev/export-encounters-to-obsidian` | dev.py:962 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/edibility/bulk-status` | edibility.py:395 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/edibility/status/{species_id}` | edibility.py:469 | guest→403 (endpoint) | no (403) |
| POST | `/api/edibility/rescan` | edibility.py:624 | HOST-TIER ONLY | no (403) |
| POST | `/api/edibility/conditions` | edibility.py:682 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/edibility/conditions/{condition_id}` | edibility.py:720 | HOST-TIER ONLY | no (403) |
| POST | `/api/edibility/lookalikes` | edibility.py:766 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/edibility/lookalikes/{lookalike_id}` | edibility.py:804 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/edibility/phenology/{species_id}` | edibility.py:894 | HOST-TIER ONLY | no (403) |
| POST | `/api/encounters` | encounters.py:140 | anon guest→403; participants allowed | **yes** |
| POST | `/api/encounters/{encounter_id}/bind-photo` | encounters.py:421 | HOST-TIER ONLY | no (403) |
| POST | `/api/encounters/backfill-photo-bindings` | encounters.py:455 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/encounters/{encounter_id}/coordinates` | encounters.py:491 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/encounters/{encounter_id}` | encounters.py:521 | HOST-TIER ONLY | no (403) |
| POST | `/api/encounters/{encounter_id}/transcribe` | encounters.py:542 | HOST-TIER ONLY | no (403) |
| POST | `/api/encounters/{encounter_id}/extract` | encounters.py:643 | HOST-TIER ONLY | no (403) |
| POST | `/api/encounters/{encounter_id}/suggestions/{suggestion_id}/{action}` | encounters.py:676 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/encounters/{encounter_id}/field-recipe` | encounters.py:747 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/encounters/{encounter_id}/field-recipe` | encounters.py:769 | HOST-TIER ONLY | no (403) |
| POST | `/api/encounters/reading-note` | encounters.py:787 | HOST-TIER ONLY | no (403) |
| POST | `/api/enrich/run` | enrich.py:220 | HOST-TIER ONLY | no (403) |
| POST | `/api/enrich/resume` | enrich.py:228 | HOST-TIER ONLY | no (403) |
| POST | `/api/enrich/re-enrich-empty` | enrich.py:301 | HOST-TIER ONLY | no (403) |
| POST | `/api/experience/publications` | experience.py:134 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/experience/publications/{pub_id}` | experience.py:156 | guest→403 (endpoint) | no (403) |
| POST | `/api/experience/publications/{pub_id}/plan` | experience.py:186 | guest→403 (endpoint) | no (403) |
| POST | `/api/experience/verify-species` | experience.py:228 | guest→403 (endpoint) | no (403) |
| POST | `/api/sessions` | foray_sessions.py:122 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/sessions/{session_id}` | foray_sessions.py:196 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/sessions/{session_id}` | foray_sessions.py:215 | HOST-TIER ONLY | no (403) |
| POST | `/api/sessions/{session_id}/auto-populate` | foray_sessions.py:226 | HOST-TIER ONLY | no (403) |
| POST | `/api/sessions/{session_id}/species` | foray_sessions.py:310 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/sessions/{session_id}/species/{species_id}` | foray_sessions.py:348 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/sessions/{session_id}/species/reorder` | foray_sessions.py:360 | HOST-TIER ONLY | no (403) |
| POST | `/api/sessions/{session_id}/attendees` | foray_sessions.py:383 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/sessions/{session_id}/attendees/{attendee_id}` | foray_sessions.py:402 | HOST-TIER ONLY | no (403) |
| POST | `/api/identify/prefilter-failed` | identify.py:29 | HOST-TIER ONLY | no (403) |
| POST | `/api/identify/tier-action` | identify.py:133 | HOST-TIER ONLY | no (403) |
| POST | `/api/ingest/scan` | ingest.py:109 | HOST-TIER ONLY | no (403) |
| POST | `/api/ingest/send-to-review` | ingest.py:343 | HOST-TIER ONLY | no (403) |
| POST | `/api/itis/backfill` | itis.py:58 | HOST-TIER ONLY | no (403) |
| POST | `/api/itis/lookup/{name:path}` | itis.py:135 | HOST-TIER ONLY | no (403) |
| POST | `/api/itis/accept-rename/{name:path}` | itis.py:167 | HOST-TIER ONLY | no (403) |
| POST | `/api/lists/pdf` | lists_pdf.py:164 | HOST-TIER ONLY | no (403) |
| POST | `/api/notes/` | notes.py:48 | guest→403 (endpoint) | no (403) |
| DELETE | `/api/notes/{note_id}` | notes.py:75 | HOST-TIER ONLY | no (403) |
| POST | `/api/notifications/seasonal-returns/dismiss` | notifications.py:63 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/observations/{observation_id}/review` | observations.py:455 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/observations/{observation_id}/correct` | observations.py:513 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/observations/{observation_id}/suggest` | observations.py:569 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/observations/{observation_id}/category` | observations.py:595 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/observations/{observation_id}/notes` | observations.py:647 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/observations/{observation_id}/coordinates` | observations.py:668 | HOST-TIER ONLY | no (403) |
| POST | `/api/observations/{observation_id}/reject-undo` | observations.py:769 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/observations/{observation_id}` | observations.py:842 | HOST-TIER ONLY | no (403) |
| POST | `/api/personal-lists/my-season/species` | personal_lists.py:158 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/personal-lists/my-season/species/{species_id}` | personal_lists.py:185 | HOST-TIER ONLY | no (403) |
| POST | `/api/processes/{process_id}/pause` | processes.py:82 | HOST-TIER ONLY | no (403) |
| POST | `/api/processes/{process_id}/cancel` | processes.py:101 | HOST-TIER ONLY | no (403) |
| POST | `/api/processes/{process_id}/dismiss` | processes.py:118 | HOST-TIER ONLY | no (403) |
| POST | `/api/queue/enqueue` | queue_api.py:283 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/queue/{job_id}` | queue_api.py:362 | HOST-TIER ONLY | no (403) |
| POST | `/api/queue/{job_id}/cancel` | queue_api.py:464 | HOST-TIER ONLY | no (403) |
| POST | `/api/queue/{job_id}/pause` | queue_api.py:469 | HOST-TIER ONLY | no (403) |
| POST | `/api/queue/{job_id}/resume` | queue_api.py:492 | HOST-TIER ONLY | no (403) |
| POST | `/api/queue/{job_id}/move-to-top` | queue_api.py:515 | HOST-TIER ONLY | no (403) |
| POST | `/api/queue/kill-all` | queue_api.py:538 | HOST-TIER ONLY | no (403) |
| POST | `/api/species/{species_name:path}/recipes` | recipes.py:139 | HOST-TIER ONLY | no (403) |
| PATCH | `/api/species/{species_name:path}/recipes/{recipe_id}` | recipes.py:178 | HOST-TIER ONLY | no (403) |
| POST | `/api/species/{species_name:path}/recipes/{recipe_id}/set-preferred` | recipes.py:223 | HOST-TIER ONLY | no (403) |
| POST | `/api/species/{species_name:path}/recipes/{recipe_id}/archive` | recipes.py:244 | HOST-TIER ONLY | no (403) |
| POST | `/api/species/{species_name:path}/recipes/regenerate` | recipes.py:268 | HOST-TIER ONLY | no (403) |
| POST | `/api/recorded-walks` | recorded_walks.py:172 | guest→403 (endpoint) | **yes** |
| POST | `/api/recorded-walks/{walk_id}/elevation` | recorded_walks.py:339 | guest→403 (endpoint) | no (403) |
| DELETE | `/api/recorded-walks/{walk_id}` | recorded_walks.py:360 | guest→403 (endpoint) | no (403) |
| POST | `/api/recorded-walks/audio-upload` | recorded_walks.py:385 | guest→403 (endpoint) | **yes** |
| POST | `/api/observations/{observation_id}/reidentify` | reidentify.py:221 | HOST-TIER ONLY | no (403) |
| POST | `/api/observations/{observation_id}/second-opinion` | reidentify.py:399 | HOST-TIER ONLY | no (403) |
| POST | `/api/observations/{observation_id}/retry-identify` | reidentify.py:690 | HOST-TIER ONLY | no (403) |
| POST | `/api/observations/{observation_id}/retry-confirm` | reidentify.py:841 | HOST-TIER ONLY | no (403) |
| POST | `/api/observations/{observation_id}/confirm-species` | reidentify.py:916 | HOST-TIER ONLY | no (403) |
| POST | `/api/observations/{observation_id}/gbif-check` | reidentify.py:1127 | HOST-TIER ONLY | no (403) |
| POST | `/api/species/{species_name:path}/resources` | resources.py:54 | HOST-TIER ONLY | no (403) |
| POST | `/api/species/{species_name:path}/resources/upload` | resources.py:77 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/species/{species_name:path}/resources/{resource_id}` | resources.py:124 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/caffeinate/start` | scan.py:132 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/caffeinate/stop` | scan.py:160 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan` | scan.py:231 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/{obs_id}/override-prefilter` | scan.py:665 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/recheck-threshold` | scan.py:705 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/reprocess-pending` | scan.py:779 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/sessions` | scan.py:2206 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/rescan` | scan.py:2315 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/process-delta` | scan.py:2471 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/scan-archive` | scan.py:2615 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/{obs_id}/retry-id` | scan.py:3195 | HOST-TIER ONLY | no (403) |
| POST | `/api/scan/pause/{session_id}` | scan.py:3233 | HOST-TIER ONLY | no (403) |
| DELETE | `/api/scan/sessions/{session_id}` | scan.py:3295 | HOST-TIER ONLY | no (403) |
| POST | `/api/settings/api-key` | settings.py:75 | guest→403 (endpoint) | no (403) |
| PUT | `/api/settings/{key}` | settings.py:121 | guest→403 (endpoint) | no (403) |
| DELETE | `/api/settings/{key}` | settings.py:141 | guest→403 (endpoint) | no (403) |
| POST | `/api/settings/synthesis-sources` | settings.py:219 | guest→403 (endpoint) | no (403) |
| DELETE | `/api/settings/synthesis-sources/{domain:path}` | settings.py:247 | guest→403 (endpoint) | no (403) |
| POST | `/api/sharing/start` | sharing.py:161 | HOST-TIER ONLY | no (403) |
| POST | `/api/sharing/stop` | sharing.py:248 | HOST-TIER ONLY | no (403) |
| POST | `/api/sharing/export-walk` | sharing.py:373 | HOST-TIER ONLY | **yes** |
| POST | `/api/syncthing/process` | syncthing.py:522 | HOST-TIER ONLY | no (403) |
| POST | `/api/syncthing/reprocess` | syncthing.py:580 | HOST-TIER ONLY | no (403) |
| POST | `/api/trust/accept-species` | trust.py:305 | HOST-TIER ONLY | no (403) |
| POST | `/api/trust/bulk-send-to-review` | trust.py:343 | HOST-TIER ONLY | no (403) |
| POST | `/api/trust/bulk-reassign` | trust.py:411 | HOST-TIER ONLY | no (403) |
| POST | `/api/trust/kingdom-audit` | trust.py:525 | HOST-TIER ONLY | no (403) |
| POST | `/api/trust/bulk-landscape` | trust.py:669 | HOST-TIER ONLY | no (403) |
| POST | `/api/trust/bulk-clear-culinary` | trust.py:736 | HOST-TIER ONLY | no (403) |
| POST | `/api/walk/ors-route` | walk.py:52 | HOST-TIER ONLY | no (403) |
| POST | `/api/walk/saves` | walk.py:107 | identity for scoping only (no guard) | no (403) |
| PATCH | `/api/walk/saves/{walk_id}/membership` | walk.py:269 | guest→403 (endpoint) | no (403) |
| POST | `/api/walk/saves/{walk_id}/accept` | walk.py:293 | guest→403 (endpoint) | no (403) |
| POST | `/api/walk/saves/{walk_id}/exclude` | walk.py:336 | guest→403 (endpoint) | no (403) |
| POST | `/api/walk/saves/{walk_id}/renumber` | walk.py:368 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/walk/saves/{walk_id}/loop` | walk.py:392 | guest→403 (endpoint) | no (403) |
| POST | `/api/walk/saves/{walk_id}/reroute` | walk.py:433 | guest→403 (endpoint) | no (403) |
| POST | `/api/walk/saves/{walk_id}/reorder` | walk.py:537 | guest→403 (endpoint) | no (403) |
| DELETE | `/api/walk/saves/{walk_id}` | walk.py:583 | guest→403 (endpoint) | no (403) |
| POST | `/api/workshop/participants/find-or-create` | workshop_tokens.py:75 | guest→403 (endpoint) | no (403) |
| POST | `/api/workshop/participants` | workshop_tokens.py:98 | guest→403 (endpoint) | no (403) |
| POST | `/api/workshop/tokens` | workshop_tokens.py:112 | guest→403 (endpoint) | no (403) |
| POST | `/api/workshop/sessions` | workshop_tokens.py:149 | guest→403 (endpoint) | no (403) |
| PATCH | `/api/workshop/sessions/{session_id}` | workshop_tokens.py:173 | guest→403 (endpoint) | no (403) |
| POST | `/api/workshop/tokens/{token_id}/revoke` | workshop_tokens.py:513 | guest→403 (endpoint) | no (403) |
