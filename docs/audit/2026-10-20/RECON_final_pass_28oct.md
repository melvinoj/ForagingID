# RECON: final audit pass (15b, 15, 16, 17), 28 Oct 2026

Read-only recon. The only writes this session were step 0 (below) and one CHANGELOG backlog line. Line numbers are as of HEAD `bd02133`. Batches shift them, so prompt B should cut by function name or anchor comment, not by line number.

**Tooling facts that change every test plan:**
- **pytest is not installed.** It is not in the venv or in requirements.txt. The 36 `tests/*.py` files are plain scripts: run each with `~/foragingid-venv/bin/python tests/<file>.py`.
- **node is not installed**, but JavaScriptCore (`jsc`) is. The tests already use it (`tests/test_batch7_escaping.py:18`), so JS can be executed in tests, not just grepped.
- **Every app/ save reloads uvicorn.** Check `/api/processes/active` right before each one.

---

## Step 0 results

| Step | Result |
|---|---|
| 0a Walk 5 republish | **Not published.** `POST /api/experience/publications/1/plan` returned no blockers, problems or failures, but **64 species, not 66** (59 stops, 202 photo files, 34 recipes). The gap is explained by two photos at stop 28: 24430 (Taraxacum sect. Taraxacum, genus card 530 deleted today) and 24429 (Dandelion, sent to Review in 0b). 24429 is Dandelion's only walk-5 photo, so Dandelion leaves the page until 24429 is approved again. Changes vs the live page: added Chicory and Turkey-tail; removed Anthemis tinctoria and Polyporus versicolor (the 11b merges). The publish commit also removes the unused site-root `photos/` (244 files, 31 MB). The expected count failed, so the public publish is held for Melvin (decision 1). |
| 0b obs 24429 | Changed from approved to `needs_review`, label `dandelion_check`, reviewer note "13% — check T. officinale vs Hyoseris / other look-alike". Snapshot `db_20261028_042247`. Read back by id: observation_edits 22040–22042 (human). Still on card 286. |
| 0c card 286 taste_notes | Cleared "test draft" to NULL. The only history rows were `ai_approved:human` (609 wrote "test draft"), and `app/models/species.py:1030` says that is not a human lock. Wrote history row 3785 (old "test draft", new NULL, changed_by human, note "Melvin 28 Oct: clear test draft"). Read back by id. `ai_approved_fields_json` / `ai_generated_fields_json` still list taste_notes; this is harmless because displays read the value. |
| Backlog | Route-line zoom/drag bug added to CHANGELOG Current State under a new `### Backlog`. The next End Session block must carry it. |

---

## Batch 15b: walk

None of 15b is built. The map layer is Leaflet (no D3 involved).

| Item | Done? | Evidence | Change touches | Test | Risk |
|---|---|---|---|---|---|
| (4) Route line distorts on zoom/drag | backlog | `_drawWalkLayer` index.html:6174–6235 | not in this pass | Melvin reproduces | — |
| (5) Hide GPS recording (UI only) | no | 👣 FAB index.html:2213 (also shown by JS at **5295–5296** `_wrecBtn.style.display='flex'`); quickbar "Record live" 2333–2338 (`_wbsStartRecording`); empty-state "Record live" card 2360–2366 | Hide those three, **including the JS show at 5295–5296**. Touch nothing else (see the keep list below) | Static test: no visible element calls `_wrecToggle`/`_wbsStartRecording`, and the sync/IDB functions are still present | Low. The danger is hiding too much |
| (1a) Edit walk: tap a stop marks the whole stop | no | Stop markers only have a tooltip: 6198–6204. Pin taps work: `handlePinClick` 4642 → `_walkPinToggle` 7528–7535 | Click handler on `stopMk` while `_walkPinSel` is set: put the stop's `obs_ids` (+ `joined_obs_ids` for 7a stops) into `_walkPending.remove`; a second tap unmarks; marked-stop icon style | Static; extract a pure mark/unmark helper and test it in jsc | Medium (tap vs tooltip, stops sit above pins) |
| (1b) Edit walk: lasso | no | `_finishLassoDraw` 4024–4061 only fills the Foraging List; capture-phase listener 3930 | Branch when `_walkPinSel` is set: toggle each pin inside the box; add a Lasso button to the Edit bar | Static | Medium (`_lassoActive` and `_walkPinSel` both live) |
| (2) Loop / One-way label | no | Toggle button 2443–2448; `toggleWalkLoop` 5807; `_syncWalkLoopUi` 5785. `_walkCircular` is read at 13+ sites (6133, 5756, 6015, 6181, 6224, **6672 signature**, 6937, 7064, 7233). Server: PATCH `/saves/{id}/loop` walk.py:413–443 → `walk_route.set_circular` :238; `shown_line` :208–235; tidy :601; reorder :704; export.py:889–895 | One server predicate in walk_route.py (last stop ≤ 300 m from stop 1) plus a read-only label in place of the button. Keep the PATCH endpoint and the stored flag (unread by the UI; derived, not dropped) | New walk_route tests (none exist): 142/149/165/576 m cases | **High for walk 3** if the rule also drives the shown line (decision 2) |
| (3) Start here on every stop | partly | Closed loops only: `_canStartHere` 6578–6589; `start_at` walk_route.py:186–203 raises on an open line; reroute walk.py:473–556 has no order parameter | Closed loop: keep the current rotate. Open line: `start_label` on RerouteBody → `plan_reroute` dry run → Re-route preview. 7a stops → "Renumber first" | Pure order function test; dry-run summary; `_reroute_snapshot` hook | Medium (ORS writes, snapshot, published pages go stale) |
| Empty saved stops: hide + drop | partly | Card text "No confirmed species here now" 6593; saved stops kept on purpose: walk.py:363–367, walk_membership.py:312–318, `renumbered_snapshot` :492–512. Re-route already drops them (walk.py:500–501); the export already skips them (export.py:840) | **Hide on render:** skip non-note saved stops with `species==[]` in `renderWalkPanel` and in `_drawWalkLayer` markers, keeping label numbers. **Drop on Save:** after `walkSaveChanges` (7563–7600), if a stop is now empty, open the Re-route preview (it already lists "Dropped (no species left)"), as the existing add→Re-route chain does at 7591 | Predicate test; `compute` on a walk with one unconfirmed saved obs | Low–medium (a number gap until Re-route) |

**Data (read-only):**
- Loop/One-way under the 300 m rule:
  - walk 1: 149 m, Loop (no route stored)
  - walk 3: stored circular, closed line, **576 m, so the label becomes One-way**
  - walk 4: 165 m, Loop
  - walk 5: 142 m, Loop
- The only empty saved stop today is **walk 5 stop 58** (obs 10176, needs_review). The old "stop 35" example was renumbered by Tidy.
- A stop goes empty in two ways: (a) excluded in Edit walk, or (b) its photo leaves confirmed status. Drop-on-Save only catches (a); hide-on-render covers both.
- 7 recorded_walks rows (June tests), 0 `recorded_walk_observations`.

**Recording: must NOT be touched.**
- "↑ Upload pending walks (N)" (index.html:2475–2479 `wbs-upload`, :2513 `walk-sync-btn`, `_walkUpdateSyncBtn` 8450–8468). This is the only way to flush, and it is manual; there is no `online` listener for walks.
- The IDB store `foragingid_walks/walks` (8334–8403), `_walkSyncPending` 8471–8584.
- The recording IIFEs 8006–9177, walk-record.js (2701), the guards at 4089 / 7909 / 9140–9162.
- The recording-only elements (HUD 2216–2233, modals, live stats 2389–2396). They become unreachable once the start buttons are hidden.
- app/api/recorded_walks.py (7 routes), the main.py media mount, the workshop recorded-walk selector (workshops.html:224, workshop_tokens.py), and the tests.
- sw.js has no recording references. `cache-tiles` (sw.js:349) is sent only by `_wrecCacheArea` (8592), which has no caller, so it is already dead.

**Moot / not moot:**
- **Not moot:** the encounters.html "🎙 Record" tab. It is encounters (voice, photo, typed note), not GPS recording, and stays visible. Its participant hides were already done (see 17-B9).

**Shared-element trace list for prompt B** (CLAUDE.md point 4):
- `_walkRouteLayer` (`_drawWalkLayer`, `_exitWalkMode`, `loadSavedWalk`/`_walkBuildSeq`)
- `renderMarkers` / `_walkSelIcon` / `pinsGroup` / `_applyLayer`
- `handlePinClick`, `map.on('click')` 4087, the lasso handlers 3913–4061
- `_walkPinSel` / `_walkPending` / `_walkPinSelExit` / `_walkPendingClear`
- `_syncWalkSaveBtn` / `_syncWalkPinsBtn`, `_applyShownLine`, `_syncWalkLoopUi`
- **`_walkCircular`, including `_walkRouteSig` 6671.** The derived value must be identical at save and load, or the header loses the walk name and `_onSavedRoute` turns false, which disables every saved-walk action.
- Server: `shown_line`, `start_at`, `plan_reroute`, `walk_membership.compute` / `renumbered_snapshot`.

---

## Batch 15: P4 / P5 / P15

`frontend/static/js/core/` does not exist.

| Item | Done? | Evidence | Change touches | Test | Risk |
|---|---|---|---|---|---|
| **P4** one markdown renderer | no | Python: `lists_pdf.py:106 _mdlite` (PDF), `sharing.py:540/552 _md_inline/_md_snippet` (walk card). JS: `print.html:365 _mdLite`, `lists.html:1810 _mdLite`, `species.html:4468 _renderMd`. Plain-text strippers kept on purpose: `export.py:156 recipe_teaser`, `species.py:771 _md_plain` (+ JS twin index.html ~6354). Raw recipe bodies: `encounters-main.js:1426`, `seasons.html:1382`. The citation-strip regex appears 7 times (`lists_pdf.py:174`, `print.html:493/560`, `lists.html:1951/1988/2056/2066`) | new `app/services/markdown.py` + `static/js/md.js`; lists_pdf, sharing, print_pdf.html CSS (ul/ol/em), print, lists, species | Golden cases run through Python **and** md.js in jsc on the same inputs, compared byte for byte; scratch PDFs | Medium output drift: 140/260 recipes have lists, 68 have italics |
| **P5** names helper | **mostly done** (21 Oct: `sentence_case_name`/`display_common_name`, `species-names.js`) | Still open: **`lists_pdf.py:178` ignores `preferred_common_name`** (the PDF name differs from the app); `personal_lists.py:71`, `seasonal_returns.py:65` (duplicate), `find.py:89/204/287`, `edibility.py:271`. JS: `index.html:6521/6726/7927/7220`, `lists.html:1159`, `encounters-main.js:570/1305/1416`, `seasons.html:1372`, `review.html:1962` (unescaped). Leave `reidentify.py` candidate names as they are | `display_common_name` on the server; new `spPickCommon` in species-names.js; load species-names.js in seasons and encounters | Extend `test_names_and_species_views.py` (jsc) | Low |
| **P15** shared JS core | **partly**: safety-gate.js (batch 5) + warnings (batch 6) done; esc/md not | 27 escape definitions in 22 files, in 4-char / 5-char / textContent variants (table in the 15 agent notes, summarised below). One frontend gate copy is left: `species.html:3883` | `esc.js` + `md.js`; delete each page's copy one page at a time | Rewrite the `test_batch7_escaping` helpers to load esc.js and re-run the hostile-string onclick tests | **High if done naively** |

**Real bug found (P4): the PDF silently drops content.** `_mdlite` renders only the first line of a `#` block, so 5 approved recipes lose text in the PDF:

| Recipe | Species | What the PDF loses |
|---|---|---|
| 53 | 101 | subtitle |
| **125** | 486 | the **whole ingredient list** |
| 198 | 487 | subtitle |
| 206 | 228 | "*Serves 4*" |
| 234 | 424 | subtitle |

Browser print and Lists show a literal `## …` for the same input.

**Apostrophe trap (P15).** The onclick pattern `_esc(x).replace(/'/g,"\\'")` only works with the 4-char escaper. A 5-char escaper turns `'` into `&#39;` first, the attribute decodes it back to `'`, and the handler breaks (an injection path).
- Sites at risk: `index.html:4748, 4760, 4789, 9556, 9581`; `species.html:1882, 3297`; `settings.html:1994`; 16 `_resc(...).replace` sites in review.html.
- The core therefore needs `esc` (5-char) **and** `jsArg` (a quoted JS-string argument), and every onclick site must be converted explicitly.
- Also: `_esc(0)` returns '' on index, print and scan but "0" elsewhere.
- A page-level `function _esc` overrides the global set by esc.js, so delete each local copy rather than layering.
- esc.js **must** be in APP_SHELL. Without it, the page breaks offline.

**Do not move safety-gate.js into core/.** It would break `app_styles.py:28`, 6 tests, sw.js:49 and 7 script tags, for no gain.

**Internal order:**
1. P4-py (markdown.py + PDF/sharing + print_pdf CSS; server only)
2. P5-py
3. esc.js + md.js + jsc tests
4. Small pages one at a time: print, lists, recipes, sightings, workshops, settings, seasons, then the static/js IIFEs
5. species.html
6. review.html, then scan.html
7. index.html last

---

## Batch 16: index.html split (boundary plan only, not built)

**Current state:** 9,813 lines (E-08 said 9,613).
- The only `<style>` block is lines 22–1928.
- Body HTML is 1929–2692, with 125 inline handlers (~90 global names).
- External scripts 2693–2705; the only inline `<script>` is 2706–9804 (7,097 lines); tail scripts 9805–9811.
- Tokenizer scan: 389 top-level names (275 functions, 80 let, 29 const, 5 var). The only duplicate is `_haversineM` (5737 and 7851, identical bodies). 50 names are used across the proposed boundaries.

**Target files:** verbatim content, no wrapper, classic `<script src>` tags at the same position and in the same order.

| # | File | From (today) | Lines |
|---|---|---|---|
| css | `static/css/index.css` | 23–1927 (keep the 4-space indent: `app_styles.py:72` anchors on it) | 1,905 |
| 1 | `static/js/index/map-core.js` | 2707–3680 (minus line 3357) | 974 |
| 2 | `…/pins-filters.js` | 3681–4639 | 959 |
| 3 | `…/detail-card.js` | 4640–5250 (`showDetail`, `_injectEnrichment`) | 611 |
| 4 | `…/walk-build.js` | 5251–6331 (contains `_walkEdibBadge` 6003, the export's regex target) | 1,081 |
| 5 | `…/walk-panel.js` | 6332–6842 (`renderWalkPanel`, `_recipeMdPlain`) | 511 |
| 6 | `…/walk-saved.js` | 6843–7829 (saved walks, Edit walk) | 987 |
| 7 | `…/walk-alerts.js` | 7830–8005 | 176 |
| 8 | `…/recording.js` | 8006–9177. **Kept, because 15b hides the UI only.** The name avoids a clash with `static/js/walk-record.js`. Its IIFE wraps `window._exitWalkMode` and `window.openSidebar`; order is preserved | 1,172 |
| 9 | `…/search-notes-find.js` | 9178–9803 (holds the `setLayer` monkey-patch and Init; must load last) | 626 |

**Hazards:**
1. **The only synchronous cross-file forward reference** is `map.on('zoomend', _rescaleNotePins)` at 3357 (map-core). `_rescaleNotePins` is declared at 9360, so after the split this throws a ReferenceError and aborts map-core. Fix: a separate prep commit that moves the line to just after 9363. Handler order is unchanged, and the move also removes a latent TDZ error on `noteGroup`.
2. No TDZ reads were found.
3. The `setLayer` reassignment works across classic scripts.
4. Error isolation changes: after the split, a throw stops only its own file, so later files still run and a later error message can mislead.

**Dependants that must change in the same batch:**
- `app_styles.py`: repoint the 9 CSS rules to index.css and `_walk_badges` to walk-build.js. It fails loudly (`StyleDrift`) if missed.
- `sw.js`: bump the version and add the new files to APP_SHELL.
- **12 test files read index.html.** Add one shared helper that returns index.html + index.css + `index/*.js` in load order, plus one guard test (every file is in a tag, in the right order, and in APP_SHELL).
- export.py: no code dependency.

**Static checks Code can run:**
- Byte-equal: re-inline the new files over the prep commit and compare byte for byte.
- Boundary rescan: zero synchronous cross-file forward references, zero TDZ reads, brace depth 0 at every file end.
- `app_styles.load()` runs clean.
- All test files pass.

**Melvin's live checks** (E-08 list plus 2 new):
1. Map loads with no console errors.
2. Tapping a pin opens the detail card with enrichment.
3. Building a walk gives the route, panel and badges.
4. A saved walk loads, and Edit walk works.
5. Export summary works.
6. Recording: confirm there is no recording UI.
7. The Find tab, note panel and search work.
8. Offline reload works after one online load.
9. **New:** zooming resizes the note pins (this checks the moved line 3357).
10. **New:** guest/phone view on the LAN.

**Prerequisites:** 15b and 15 must land first (both edit index.html). P6 is optional and not built.

---

## Batch 17: tidy

### 17-A (E-07, E-09, E-12, A-05…A-10, rename group 1, UA)

| Item | Status | Evidence | Change | Test / risk |
|---|---|---|---|---|
| E-07 Python dead | still dead (6) | `hashing.py:18`, `encounter_extract.py:111`, `gdrive.py:162`, `inaturalist.py:439`, `enrich_gate.py:163`, `pipeline_lock.py:85`. The 7th (`_copy_to_confirmed`) is already removed | delete | py_compile + import smoke / low |
| E-07 JS dead | all 26 still dead | scan.html ×8 (1997–3782), index.html ×7 (2817, 3036, 4360, 4374, 6404, 6991, 9535), review ×3, lists ×3, seasons:492, print:647, settings:1286, species:1936, encounters-main:961 | delete | Re-run the zero-reference scan / low (risk of deleting a neighbouring block) |
| E-07 other | still present | `git-banner.js` (unloaded); `scratch-filename-test.html` + route `main.py:460-465` + the EXEMPT entry at `test_batch5:346`; unused deps geopy/piexif/aiofiles (`requirements.txt:19/37/41`); 14 `scripts/migrate_*.py` | delete (decision 14) | low |
| E-09 CLAUDE.md | stale ×7 | Alembic head 0050 → **0059_recipe_page_fields** (:177); "migration 0021" (:107); `phone_foraging_dir` "stale path" (now correct) (:107); "2158/2158" (:155); uploads 88% → 85.9% (13,945/16,230) (:89); pipeline2 "P2 (Syncthing/Takeout)" → all 1,708 rows are syncthing (:88); "claude-sonnet-4-6 default" → DeepSeek only since D1 (:97); Current Phase/Next Steps June-era (:250-258) | doc edit | read-back / none |
| E-09 other docs | stale | `docs/architecture.md:50` (fungi → "iNat + Mushroom Observer", but the code is iNat only, scan.py:1276); `docs/current_phase.md` (3 Jun; `dev.py:628` still rewrites it); comments `syncthing.py:1087` ≥80% (live 0.7), `config.py:130/139` "git-tracked", `.claude/launch.json:3`, `scan.py:1356` auto_approve_threshold | edit | none |
| E-12 / P17 logs | not done, worse | No filter or rotation anywhere. `START_ForagingID.command:26-27/73-76` uses `tee -a`. **69 MB / 27 files.** The current log is 95,276 lines, of which 92,263 are access lines (`/api/processes/active` 19,481, `/api/queue/list` 19,408, `/health` 9,848). 18 `[TIMING]` prints (9 main.py, 9 database.py) | `logging.Filter` on `uvicorn.access` (drop 2xx/304 on the polling paths only); `[TIMING]` behind `LOG_TIMING`; prune in the launcher | Unit-test the filter with fake LogRecords / low |
| A-05 stray | all present | Tracked: `your_db.db`, `current.txt`, root roadmap v23 docx, `docs/…v20.docx`. Untracked in data/: 2 old DBs (257 MB + 36 MB), `._foragingid.db*` ×3, `thumbnails_quarantine/` (10,768). Data volume 93% used | `git rm` the tracked junk; the data/ deletions are Melvin's (permanent delete) | — |
| A-06 empty tables | 11 (set changed) | Now includes `species_edibility_conditions`; `experience_publications` now has rows | Document only | — |
| A-07 + A-09 settings | drifted | Dead rows: `auto_approve_threshold`, `obsidian_vault_path`, `enrichment_backend`, `anthropic_model`. `gdrive_access_token` is read (keep) | **DB DELETE of 4 rows** (snapshot, diagnostic, delete, read back by key) | — |
| A-08 no-caller endpoints | mostly still uncalled | `backfill-fungi-edibility` and the publications endpoints are now called. Still uncalled: `mark-verified` (culinary.py:741, a safety-adjacent writer), `trust/kingdom-audit`, `retry-confirm`, conditions/lookalikes ×3, identify ×4, `dev/*` tools … | Delete only `mark-verified` | low |
| A-10 versions | still differ | `main.py:194` 0.1.0 vs `:509` /health 0.2.0 | one `APP_VERSION = "0.2.0"` | — |
| Rename group 1 | 10 places + 4 in the DB | `print_pdf.html:5` (title), **`:436` disclaimer** (new), `lists_pdf.py:358` and `print.html:872` (PDF filename), `review.html:6487` (shared-photo filename), `main.py:192` (/docs title), `start.sh:42`, `about.py:34` (About AI prompt). About text in the DB: `about_content` id 1, `full_description`, 4 occurrences. `settings.html:667` backup path is a real path, so leave it | edit; Melvin edits the About text in the About editor | Scratch PDF + pdftotext / none. Leave the localStorage keys alone |
| UA contacts | 7 strings | `pfaf.py:35` (`foragingid@local`, unreachable), `wikidata.py:28` (`github.com/foragingid`, not Melvin's account), `trompenburg.py:32`, `culinary_links.py:59`, `fao_fungi.py:152`, `data_sources.py:210`, `scripts/gbif_vernacular_backfill.py:26` | One `HTTP_USER_AGENT` constant in config.py | grep + import smoke / low |

### 17-B (accumulated items)

| # | Item | Status | Evidence | Change | Test / risk |
|---|---|---|---|---|---|
| 1 | Lists "Lookalike warnings" toggle | dead on purpose (batch 6 prints warnings always; commit 49f9926) | `lists.html:1217`, drawn 1323–1336, `toggleSection` 1287 only stores the pref. "Edibility conditions" is dead too (never printed) | Swap the checkbox for fixed text "Always printed"; conditions → "Not printed" | static test; **must not re-gate the warnings** |
| 2 | Reload banner on a new version | no | sw.js:16 v17, `skipWaiting` :222, `clients.claim` :261, `/sw.js` served no-store (main.py:495). pwa.js only registers the worker. pwa.js is not loaded on encounters, workshops, taxonomy, seasons or print | pwa.js: `controllerchange` (only when a controller existed at load) → "New version available — Reload" bar, never an auto-reload; `reg.update()` on visibilitychange; add pwa.js to encounters and workshops | Static test; phone check is Melvin's / auto-reload must never happen (it could kill a recording or a note) |
| 3 | `thumbnail` on `/api/species/` | missing | `culinary.py:74-167 list_species`; `species.html:1697-1712` fetches the whole `/api/map/geojson` for thumbs | One bulk query (no N+1) for the highest-confidence thumb under the two-field filter; species.html reads `item.thumbnail` (keep geojson for select mode :1877). **The `SPECIES_CACHE` rename to `-3` is mandatory** (cache-first, 7-day TTL, sw.js:30/74) | App-client test: field present, from a confirmed obs only, NULL when there is none |
| 4 | scan.html loadPrefilterThreshold | **bug** | `scan.html:1803-1816` calls `list.find` on `{settings:[…]}` (settings.py:141); the empty catch swallows the error and `#pf-threshold-note` stays blank. The siblings at :4617 and :4856 do it right | `(list.settings \|\| []).find(...)` | static test / very low |
| 5 | Device list self-refresh | partly | `settings.html:1668-1691` reloads only after its own add (:1709) or revoke (:1721) | Poll every 5 s while a link is unused and the page is visible (stop after ~10 min) + refresh on visibilitychange | static test / low |
| 6 | POST /api/recorded-walks open to guests | **already done** (b1138f0) | `guest_access.py:61-66` refuses it; `recorded_walks.py:181-182` refuses it too; `tests/test_recorded_walk_guest_refusal.py`. The table does have `user_id` (:198) | none. Optional: `data-guest-hide` on `#wbs-upload` / `#walk-sync-btn` | — |
| 7 | Dead `_merged_into` check | confirmed dead | `scripts/verdict_sweep_drafts.py:67-68` (+ docstring :11); 0 rows in the DB; nothing writes it | delete | none |
| 8 | End Session stacks "## Current State" | **bug, root cause found** | `app/services/changelog_service.py:56-102`: the span starts at the exact `## Current State` line and ends at the next `## ` line. A body that began with `## Current State — 22 Oct…` (commit 731da51) became the next run's end boundary. The header strip (:83-87) only removes an exact header. Headings now at CHANGELOG lines 1, 59, 114, 165, 205 | Match `^## Current State` (bare or dated) as inside the section, end at the first other `## ` (History); strip a dated header from incoming bodies; same in `get_current_state` | New `tests/test_changelog_service.py` on a temp file / medium (it eats text if wrong). **Without a prior CHANGELOG edit, the next End Session silently deletes the 4 stale blocks** (decision 29) |
| 9 | Record-tab Photo button for participants | **already done** (b1138f0) | `encounters.html:426-428` `data-guest-hide`; `guest-mode.js:35` | none. It is the encounters Record tab, so hiding GPS recording didn't make it moot | — |

**Moot / closed by this recon:**
- 17-B6 and 17-B9 are already done.
- `cache-tiles` / `_wrecCacheArea` is already dead.
- Nothing became moot because of the recording hide, since the encounters Record tab is separate.

---

## Build order for prompt B

Rules for every step:
- Check `/api/processes/active` before every app/ save.
- DB snapshot before any data write; read back by id.
- Shared-element trace (CLAUDE.md point 4) for each index.html change.
- **No sw.js edits until the final step.**
- Checkpoint commit after each batch, once its tests pass.

**Batch 17** (first)
1. Docs: CLAUDE.md (head 0059 + the 6 other items), architecture.md:50, current_phase.md (decision 15), stale comments.
2. Small code: scan.html:1803; delete `_merged_into`; Lists toggles; device-list poll; `APP_VERSION`; `HTTP_USER_AGENT`; dead Python/JS/git-banner/scratch page/deps (decision 14); delete `mark-verified`.
3. Logs: access filter, `LOG_TIMING`, launcher prune.
4. Rename group 1 strings (the disclaimer name only after Melvin confirms; About text by Melvin).
5. `/api/species/` thumbnail plus species.html (the cache rename waits for the final step).
6. Reload banner in pwa.js (+ encounters and workshops tags).
7. CHANGELOG one-time archive of the stale blocks (decision 29), then the `changelog_service` fix + test.
8. DB: snapshot, then delete the 4 dead `app_settings` rows, then read back.
9. Run all tests, then checkpoint commit.

**Batch 15**
1. markdown.py + PDF/sharing + print_pdf CSS, with golden tests and scratch PDFs of recipes 53, 125, 198, 206, 234.
2. P5 server picks + `lists_pdf.py:178`.
3. esc.js + md.js + `spPickCommon`, with jsc tests.
4. Small pages one at a time.
5. species.html.
6. review.html, then scan.html.
7. index.html (5 esc copies, 5 onclick sites → `jsArg`, name picks).
8. Run all tests, then checkpoint commit.

**Batch 15b**
1. Hide recording (3 entry points + the JS show at 5295).
2. Empty stops: hide on render, drop on Save via the Re-route preview, drop on Renumber.
3. Loop/One-way predicate + label (keep the PATCH endpoint and the stored flag).
4. Start here on every stop (open line → reroute dry run).
5. Edit walk: stop tap + lasso.
6. Run all tests, then checkpoint commit.

**Final**
- **One sw.js bump**: `CACHE_VERSION` v17→v18, `SPECIES_CACHE` → `foragingid-species-3`, APP_SHELL adds `esc.js`, `md.js`, `species-names.js`.
- Update `test_batch5_safety_gate.py:355` (it asserts "foragingid-v17").
- Run all tests, then commit.
- Melvin's live checks per batch (15b list in REPORT.md row 15b, minus item 4; 15: scratch PDFs + pages; 17: reload banner on the phone, device list, Lists toggles).

**Batch 16** is a separate prompt after these land: prep commit (move line 3357), then the split, then byte-equal + rescan, then Melvin's 10 checks.

---

## Decisions for Melvin (recommended default in **bold**)

1. **Walk 5 republish.**
   - The plan is clean, but it gives 64 species, not 66: Dandelion is off until 24429 is approved, and 24430 was a deleted genus photo. It also removes the unused site-root `photos/` (244 files).
   - **Publish now with Front page ticked; Dandelion returns at the next republish once 24429 is confirmed.** Alternative: review 24429 first, then publish (65).
2. **Loop/One-way threshold: 300 m, label only.** The shown line keeps following the stored line's shape (`is_closed`), so no walk's distance or published page changes. Walk 3 (576 m) is labelled One-way but keeps its closed line. Alternative: the rule also drives `shown_line`, which cuts walk 3's line.
3. **Empty walk stops: dropped on Save (via the Re-route preview) and hidden on render; Renumber drops them too.**
4. **Start here from a middle stop of a one-way walk: order k…N, then k−1…1 (all stops kept),** through the Re-route preview. Alternative: k…N only.
5. **Edit walk gestures: tapping a stop marks it for removal only; the lasso toggles** (adds non-members, removes members).
6. **Recording hide: keep visible the "Upload pending walks" buttons, the Recorded walks list and 📥 GPX import.** Before shipping, open the app on the phone and upload any pending walks.
7. **Hide the walk-upload buttons from guests (`data-guest-hide`): yes** (cosmetic; the server already refuses).
8. **Markdown dialect: one superset renderer** (escape first, headings line by line, ul/ol, bold/italic, code, links as text only, no raw HTML). **Accept the handout drift** (lists and italics start rendering in Lists, print and PDF), checked with scratch PDFs of recipes 53, 125, 198, 206, 234.
9. **esc.js and md.js live flat in `static/js/` (no `core/`); safety-gate.js stays where it is.**
10. **Escaping: a 5-char `esc` (null → '', 0 → "0") plus a separate `jsArg` for onclick handlers, converted site by site;** `_resc` stays as an alias until review.html is migrated.
11. **Render the encounters recipe body through md.js; the seasons 200-character teaser stays plain text.**
12. **Server name picks (find, personal_lists, seasonal_returns, edibility, lists_pdf) use `display_common_name`: yes.**
13. **Batch 16: do it, after 15b and 15, as 8–9 JS files + 1 CSS file** (recording kept as `index/recording.js`), **with a separate prep commit for line 3357, strictly verbatim** (no dedupe or cleanup in the same commit), **and add the new and already-missing index scripts to APP_SHELL.** Alternatives: 3 coarse files, or defer.
14. **E-07: delete all the dead code (6 Python, 26 JS, git-banner.js, scratch page + route, 3 deps); move the 14 `migrate_*.py` to `scripts/archive/`.**
15. **Delete `docs/current_phase.md` and `_update_current_phase_doc` from end-session** (CHANGELOG is the source of truth).
16. **Logs: filter 2xx/304 access lines for `/api/processes/active`, `/api/queue/list`, `/health`, `/api/syncthing/status` and the scan-stats polls; keep the newest 10 logs.**
17. **A-05: `git rm` `your_db.db`, `current.txt` and the v20 docx; keep roadmap v23. You copy the two old data/ DBs (293 MB) and `thumbnails_quarantine/` to DIGIERA and delete them in Finder** (a permanent delete, so it's yours).
18. **A-06 empty tables: document only, no drop.**
19. **A-07/A-09: delete the 4 dead `app_settings` rows** (`auto_approve_threshold`, `obsidian_vault_path`, `enrichment_backend`, `anthropic_model`) after a snapshot.
20. **A-08: delete only `POST mark-verified`; keep the other uncalled endpoints.**
21. **A-10: one `APP_VERSION = "0.2.0"`.**
22. **Rename group 1: PDF title + `landmemory-list.pdf`, shared-photo filename, /docs title, start.sh banner, About AI prompt → LandMemory. PDF disclaimer (`print_pdf.html:436`): change the product name only, after you confirm. About text: you edit it in the About editor.**
23. **User-Agent: one constant, `LandMemory/0.2 (+https://github.com/melvinoj/ForagingID)`, with no email.**
24. **Lists page: the "Lookalike warnings" row reads "Always printed"; "Edibility conditions" reads "Not printed".**
25. **Reload banner: a prompt only (you tap Reload, never automatic); also add it to encounters and workshops.**
26. **Species-list thumbnail: the highest-confidence confirmed photo** (same as the map today).
27. **Device list: poll only while a pairing link is unused, plus refresh when the page becomes visible.**
28. **Remove the dead `_merged_into` check.**
29. **CHANGELOG: before the End Session fix lands, move the 4 stale dated "## Current State" blocks unchanged into `## Archive`** (headings demoted, as was done once before, CHANGELOG:2109), after checking that every "Scope added (keep)" item is carried in the top block. Without this, the fixed End Session would silently delete them.
30. **Tests stay plain scripts (no pytest dependency); JS tests use jsc.**
31. **`scripts/dev/walkthrough_check.py`** drives a browser, which conflicts with the CLAUDE.md no-browser rule, but CHANGELOG lists it as Code's. **Default: Code does not run it; you run it after UI batches.** If you want Code to run it on the scratch setup, add that exception to CLAUDE.md.
