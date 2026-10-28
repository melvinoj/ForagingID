## Current State

28 Oct 2026, afternoon (closing the session that ended from Settings at 15:09 without a full End Session)

### Session summary
Pre-split fixes (182f5e6), batch 16 index.html split (prep 0cf780e, split 2b49db7), Part A held items (3403705: removeFromList via lmJsArg, sw v20 caches tokens.css + site-header.css, loadFeatures timer guard). REPORT.md section 9 status marks corrected and CLOSEOUT_28oct.md added (Part B). Batches 9 and 10 shipped in snapshot commit b1138f0 (22 Oct) without a Built entry — recorded in History now. The 15:09 Settings End Session collapsed this block to one line; content restored from 2b49db7.

### Build
- Alembic head 0059. Service worker foragingid-v20 (tokens.css + site-header.css now in APP_SHELL), species cache foragingid-species-3.
- Tests: 47 files in tests/, all pass at 3403705 (plain scripts, no pytest; JS via jsc).
- Batch 16: static/css/index.css + 9 static/js/index files, verbatim; tests/index_source.py re-inlines the page (byte-equal to the prep commit).

### Next (order)
1. Safety batch (CLOSEOUT_28oct.md section 4): items 1–4 done (4498f88). **Resume at item 5** (B5-03 reviewer notes curator-only on every guest-reachable path, test as guest), then 6–10, report with ≤3 Melvin checks, End Session. CLAUDE.md workflow change done (Step 0).
3. Melvin, phone: tap "Upload pending walks (N)" if shown; one reload per device.
4. Live checks below before any further index work.

### Open decisions (Melvin)
- None (section 4 decisions = Claude.ai defaults, Melvin 28 Oct).

### Backlog
- Walk route line distorts, then disappears after zooming in and dragging, until the walk is reloaded (REPORT.md batch 15b item 4). Melvin reproduces first; no fix from code reading alone.
- lists.html addSessionSpecies still uses the old escape-then-apostrophe pattern (safety batch item 10).

### Settled (Melvin)
- All recon defaults accepted 28 Oct, with: Loop threshold 600 m label only; PDF disclaimer name only; UA LandMemory/0.2 (+https://melvinjarman.co.uk); recording UI hidden only.
- Merges only via merge_species_cards; no genus cards, ever; 879 Bryonia dioica toxic/toxic; 136 orphan-marked.
- 28 Oct: POST mark-verified stays the 410 stub (writes nothing). New walks stay built as loops (the 600 m rule is the label only). Lists dropdown wired back (▾ on each selected-species row → toggleExpand), not removed.
- 28 Oct: device list — ✕ on every entry (live paired device = revoke + remove; revoked device / unused link = delete the entry), app confirm dialog. Auto-prune only revoked devices and links unused after 7 days, on every list load; never a paired device for being offline.

### Rules learned
- Any app/ save reloads uvicorn — check /api/processes/active right before each save.
- Escaping is 5-char now: inline-handler string args must use lmJsArg, never escape-then-replace(/'/).
- Python str.splitlines() splits on U+2028 — use split("\n") when reading jsc JSON output.
- Static files are served from disk: a sw.js bump is live as soon as it is written.
- End Session from Settings rewrites Current State with its one-line summary: it drops every section here. Use the chat End Session block.

### Unverified live
Rule (CLAUDE.md, 28 Oct): one list, grouped by batch, each line = the symptom to look for. Melvin reports bugs from normal use; this maps them to a batch. Entries leave only when Melvin reports them checked or they are superseded.
- **Safety batch 28 Oct, items 1–4 (4498f88 + sw v21):** Lists 🌿 Returns shows Off by default; at 10, Digitalis purpurea shows ☠ deadly + look-alike/preparation lines in Lists, print and PDF (missing = gate miss). Species page for Sambucus nigra: the ground-elder and 3 Brill links carry "⚑ may not be this species"; a guest phone never shows them; printing the species page drops them. Workshop page (Lists / print / PDF) prints each warning once, in the Safety & edibility box. Elder's "Compost Cosmetic Dye…" sits under "Other uses", not "Medicinal preparations". After sw v21: any console "SafetyGate.seasonalReturn is not a function" = stale safety-gate.js.
- **Part A held items (3403705, 28 Oct):** Lists × on shepherd's purse / St John's wort / lady's smock removes the wrong row or nothing → lmJsArg miss. Offline map page loses header styling → sw v20 not caching tokens.css / site-header.css. Console "loadFeatures is not defined" after a resize during map load → timer guard miss.
- **Batch 16 index.html split (2b49db7, 28 Oct):** after one reload — any console "X is not defined" on the map page = a load-order miss; pin tap gives no detail card / no enrichment; build a walk → no route, panel or edibility badges; saved walk won't load; Edit walk stop tap / ⬚ Lasso / Start here / Loop label / stop 58 hidden / Tidy route order misbehave; Export summary broken; recording UI visible; Find tab, note panel or search broken; offline reload after one online load fails (index.css + index/*.js precache); note pins don't resize on zoom (moved zoomend line); zoom + drag a walk breaks; phone/guest view over the share link broken; no reload banner after the sw bump.
- **Device list (182f5e6, 28 Oct):** Settings → Curator devices shows more than "Melvino's"; ✕ opens a browser popup instead of the in-app dialog, or Cancel / click outside / Esc don't close it; the live device's dialog doesn't say "Revoke and remove". (Don't confirm on your only signed-in phone — ✕ there cuts it off at once.)
- **Lists dropdown (182f5e6, 28 Oct):** ▾ on a selected-species row doesn't open fill status + Include in PDF (Warnings "Always printed", Conditions "Not printed"); unticking a section doesn't remove it from the preview; ▾ doesn't rotate when open.
- **Batches 17, 15, 15b + sw v18 (5830833, 94afbbe, 0f47e98, 536b7e7, 28 Oct):** pre-filter note wrong on scan.html; Lists fixed rows; device list self-refresh; Large/List thumbnails; reload banner; PDF/print recipes 125/206 missing text; apostrophe names break any converted button; preferred common names not shown; Loop label; Start here; stop 58 visible; Edit walk stop tap + lasso; any recording UI visible; upload button missing.
- **Walk 5 republish (site 28f9e80, 28 Oct):** live walk 5 page or the collection page broken / wrong front page.
- **Rename to genus (28 Oct):** renaming a card to a genus doesn't show the refusal message.
- Tool note: scripts/dev/walkthrough_check.py drives a browser on a scratch :8765 — Melvin runs it; Code's own pass is scripts/dev/smoke_pass.py (evidence only).

### Melvin's review queue
- 11b_review (28). genus_reid (6). bryony_check (8229). hazard_review cards (18) + 17052, 17737. 22 recipes needing a title. Five rejected photos restored in July (15958, 15970, 21333, 21673, 21799). Warning review cards. Text tidy-up (352 edible_parts / 689 id_notes). 347 Takeout person_animal rejects (mount DIGIERA). Draft #3252 Amaranthus hybridus. data/ old DBs (293 MB) + thumbnails_quarantine/ → copy to DIGIERA, delete in Finder.

## History

### 2026-10-28 16:29
**Safety batch item 4: traditional/other uses in their own Other uses section (CLOSEOUT section 4 #5)**

**Built:**
- Lists + browser print workshop page: Other uses section for traditional_uses (same toggles as before), omitted when empty; Medicinal preparations = medicinal notes + folklore only
**Fixed:**
- Elder's PFAF 'Compost Cosmetic Dye…' no longer printed under Medicinal preparations
**Files:** `frontend/lists.html`, `frontend/print.html`, `tests/test_safety_batch_28oct.py`, `tests/test_batch7_escaping.py`
**Pending:**
- PDF never printed traditional_uses — unchanged (no Other uses section in PDF)
- Unverified live: elder workshop page shows Other uses below Medicinal preparations

### 2026-10-28 16:29
**Safety batch item 3: workshop page prints one full safety box per species, repeats dropped (CLOSEOUT section 4 #4)**

**Built:**
- Lists, browser print and PDF workshop layout: warnings only in the Safety & edibility box (always rendered, full text); no repeat before Foraging / Recipe
**Fixed:**
- Workshop page printed the look-alike + preparation warnings up to 3 times
- _printCulinaryWarnings removed from lists.html and print.html (no callers left)
**Files:** `frontend/lists.html`, `frontend/print.html`, `app/templates/print_pdf.html`, `tests/test_safety_batch_28oct.py`, `tests/test_batch8_guest_and_culinary_warnings.py (Fix B workshop asserts updated to one copy)`, `tests/test_batch5_safety_gate.py`, `tests/test_batch6_warnings.py (pass identity to get_culinary_profile)`
**Pending:**
- Unverified live: a workshop page for Sambucus nigra in Lists / print / PDF shows each warning once, in the safety box

### 2026-10-28 16:23
**Safety batch item 2: source-link species check (CLOSEOUT section 4 #2)**

**Built:**
- app/services/source_links.py: one rule — a culinary link is flagged when neither title nor URL names the species (scientific, display common name, synonyms)
- /api/species/{name}/profile and /api/culinary/{name}: links carry flagged; guests never receive a flagged link
- species.html: flagged links shown to curator with a flag, hidden in print
- docs/audit/2026-10-20/flagged_links_28oct.md: 345 of 455 links flagged on 132 species (129 Brill generic)
**Fixed:**
- Elder no longer shows the ground-elder page or Brill curriculum/day-camp/scout pages to guests or in print
**Files:** `app/services/source_links.py`, `app/api/culinary.py`, `frontend/species.html`, `tests/test_safety_batch_28oct.py`, `docs/audit/2026-10-20/flagged_links_28oct.md`
**Pending:**
- Known false positives (Ground elder on Goutweed, Garlic Mustard on Hedge Garlic, Cow parsley on Keck): fix by setting preferred common name; rule not widened (all common names would let wrong-species pages through)
- No deletion — cleanup of flagged links is a curator decision

### 2026-10-28 16:20
**Safety batch item 1: Seasonal Returns through the SafetyGate, default Off (CLOSEOUT section 4 #1)**

**Built:**
- GET /api/notifications/seasonal-returns: every entry carries its server safety decision
- seasonal_return_gate / gate_seasonal_returns (Python) + SafetyGate.seasonalReturn (JS twin): handout badge + handout warnings; toxic/deadly without both dropped; missing decision = toxicity unknown
- PDF re-decides Seasonal Returns safety by name (payload safety ignored); template prints badge + warnings
- Lists + print render SR through the gate; Returns select default Off; localStorage keys _v2 (old '10' and ungated cache not read)
- scripts/dev/smoke_pass.py (scratch APFS clone, port 8001, evidence only)
**Fixed:**
- Digitalis purpurea (#3 live) and Dryopteris filix-mas (#8) no longer print 'in season' without the skull badge and warnings
**Files:** `app/services/seasonal_returns.py`, `app/api/notifications.py`, `app/api/lists_pdf.py`, `app/templates/print_pdf.html`, `frontend/static/js/safety-gate.js`, `frontend/lists.html`, `frontend/print.html`, `tests/test_safety_batch_28oct.py`, `scripts/dev/smoke_pass.py`
**Pending:**
- Unverified live: Lists Returns select shows Off; choosing 10 shows Digitalis with skull badge + look-alike/preparation lines in Lists, print and PDF
- Notification bell (seasonal-returns.js, owner-only in-app) not gated — not in item scope

### 2026-10-28 16:07
**Step 0 workflow change (Melvin 28 Oct): CLAUDE.md smoke-pass exception (scratch APFS clone, port 8001, DATABASE_URL), batch handoff rule, CONTEXT HANDOFF RULE; Current State Browser checks replaced by one Unverified live list grouped by batch**

**Built:**
- CLAUDE.md: Headless smoke pass exception
- CLAUDE.md: Batch handoff rule
- CLAUDE.md: CONTEXT HANDOFF RULE
- CHANGELOG Current State: Unverified live list (all prior check content kept)
**Files:** `CLAUDE.md`, `CHANGELOG.md`
**Pending:**
- Melvin: confirm the CLAUDE.md diff before Step 1
- scripts/dev/smoke_pass.py not written yet (first thing in Step 1)
- Resume at: Step 1 item 1 Seasonal Returns, after Melvin confirms Step 0

### 2026-10-28 16:05
**Snapshot** — End of session — Closing 28 Oct session: Part A held items done (3403705, unverified live); batches 9 and 10 shipped in snapshot commit b1138f0 (22 Oct) without a Built entry; REPORT.md section 9 status corrections applied 28 Oct; docs/audit/2026-10-20/CLOSEOUT_28oct.md added; Current State restored after the Settings End Session collapsed it
DB: `snapshots/db_20261028_160501.sqlite`

### 2026-10-28 16:05
**Session ended** — Closing 28 Oct session: Part A held items done (3403705, unverified live); batches 9 and 10 shipped in snapshot commit b1138f0 (22 Oct) without a Built entry; REPORT.md section 9 status corrections applied 28 Oct; docs/audit/2026-10-20/CLOSEOUT_28oct.md added; Current State restored after the Settings End Session collapsed it

### 2026-10-28 15:43
**REPORT.md section 9 table: status marks corrected per CLOSEOUT_28oct.md (Melvin approved) — 1b, 4-11, 11b, 15, 15b, 16, 17 done; 12 partly; 13 superseded**

**Fixed:**
- REPORT.md section 9 first-column status for 16 batch rows (report text only)
**Files:** `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/CLOSEOUT_28oct.md`
**Pending:**
- CLOSEOUT_28oct.md section 4 decisions (Seasonal Returns gate first)
- Part A live checks

### 2026-10-28 15:21
**Held items (Part A): removeFromList via lmJsArg, sw v20 caches tokens.css + site-header.css, loadFeatures 200 ms timer load-order guard. Checkpoint commit 3403705.**

**Built:**
- sw.js APP_SHELL: /static/css/tokens.css + /static/css/site-header.css; CACHE_VERSION foragingid-v20
**Fixed:**
- lists.html × remove button: removeFromList(${lmJsArg(name)}) replaces escape-then-apostrophe pattern (decision 10)
- map-core.js moveend refetch: loadFeatures read at timer fire, skipped if pins-filters.js not loaded yet (resize during load)
**Files:** `frontend/lists.html`, `frontend/static/sw.js`, `frontend/static/js/index/map-core.js`, `tests/test_held_items_28oct.py`, `tests/test_batch7_escaping.py`, `tests/test_batch15_esc_names.py`, `tests/test_batch5_safety_gate.py`
**Pending:**
- Melvin live checks: Lists × on shepherd's purse / St John's wort / lady's smock; sw v20 activates and offline map page keeps header styling; resize during map load → no loadFeatures ReferenceError
- lists.html addSessionSpecies still uses the old escape-then-apostrophe pattern (not in scope)
- Part B closeout report docs/audit/2026-10-20/CLOSEOUT_28oct.md

### 2026-10-28 15:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261028_150904.sqlite`

### 2026-10-28 15:09
**Session ended** — Session ended from Settings page

### 2026-10-28 13:24
**Batch 16: frontend/index.html split into index.css + 9 static/js/index files (verbatim), prep commit 0cf780e first**

**Built:**
- static/css/index.css (index.html 23-1932) + static/js/index/{map-core,pins-filters,detail-card,walk-build,walk-panel,walk-saved,walk-alerts,recording,search-notes-find}.js, same position and order as the old inline block
- tests/index_source.py: re-inlines the split page (byte-equal to the prep commit); test_batch16_index_split guard test
- sw.js foragingid-v19; APP_SHELL + index.css, 9 index files, and 9 already-missing index scripts
**Fixed:**
- Prep 0cf780e: zoomend -> _rescaleNotePins registered after its declaration (only sync cross-file forward reference)
- app_styles.py reads index.css + walk-build.js
- Tests read index.html re-inlined; gate scan skips the split files (scanned via index.html); esc scan is recursive
**Files:** `frontend/index.html`, `frontend/static/css/index.css`, `frontend/static/js/index/*.js`, `frontend/static/sw.js`, `scripts/experience_export/app_styles.py`, `tests/index_source.py`, `tests/test_batch16_index_split.py`, `13 tests routed through index_source`, `CHANGELOG.md`
**Pending:**
- Melvin: batch 16 live checks (CHANGELOG Browser checks), after one reload
- Residual: resize during load -> possible one-off 'loadFeatures is not defined' from the 200 ms refetch timer

### 2026-10-28 13:08
**Pre-split fixes (phase 1): device list ✕ + auto-prune, Lists dropdown wired back, settled items recorded**

**Built:**
- Settings device list: red ✕ on every entry with in-app confirm dialog; DELETE /api/sharing/devices/{id} (live paired = revoke + remove, revoked/unused link = delete entry)
- Auto-prune of dead curator entries on every list load: revoked devices + pairing links unused after 7 days; paired-but-offline devices never pruned
- Lists: ▾ on each selected-species row opens the toggleExpand dropdown (fill status + Include in PDF)
**Fixed:**
- Live prune ran: guest_tokens 2, 3, 4 (all revoked) deleted; 5 (paired, last used 22 Oct) kept — snapshot db_20261028_100138
- CHANGELOG: mark-verified 410 stub kept, new walks stay loops, Lists dropdown wired — moved to Settled
**Files:** `app/api/sharing.py`, `frontend/settings.html`, `frontend/lists.html`, `tests/test_device_list_remove_prune.py`, `tests/test_lists_toggle_expand.py`, `CHANGELOG.md`
**Pending:**
- Melvin: live check device list ✕ dialog + Lists ▾ dropdown
- Lists removeFromList still uses the old escape-then-apostrophe pattern (apostrophe names) — not touched

### 2026-10-28 10:01
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261028_100138.sqlite`

### 2026-10-28 09:59
**Snapshot** — before re-route of saved walk 4
DB: `snapshots/db_20261028_095904.sqlite`

### 2026-10-28 09:46
**Walk 5 republished: obs 24429 approved (Melvin), plan 65 species / 59 stops / 35 recipes, published with Front page at site commit 28f9e80**

**Built:**
- Walk 5 Morning sunshine Gresgen to Adelsberg republished as featured walk (site 28f9e80)
**Fixed:**
- obs 24429 needs_review -> approved via PATCH review (edits 22043-22045, snapshot db_20261028_094315)
- Site-root photos/ (244 files) removed in the publish commit
**Files:** `~/foraging-experience: index.html, preview.html, w/morning-sunshine-gresgen-to-adelsberg/*, walks.json, photos/ removed`
**Pending:**
- Melvin: open the live walk 5 page and the collection page in own browser

### 2026-10-28 09:43
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261028_094315.sqlite`

### 2026-10-28 09:36
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261028_093618.sqlite`

### 2026-10-28 09:36
**Session ended** — Session ended from Settings page

### 2026-10-28 09:10
**Final pass build (prompt B): batches 17, 15, 15b + one sw.js bump**

**Built:**
- Batch 17 tidy (5830833)
- Batch 15 markdown/esc/names (94afbbe)
- Batch 15b walk (0f47e98)
- sw v18 (536b7e7)
**Fixed:**
- PDF recipe content loss (5 recipes)
- scan.html prefilter threshold
- End Session stacked Current State blocks
- 4 dead app_settings rows deleted (snapshot db_20261028_082151)
**Files:** `see commits 5830833 94afbbe 0f47e98 536b7e7`
**Pending:**
- Walk 5 republish: approve 24429 first
- Upload pending phone walks
- Live walkthrough checks for 17/15/15b in CHANGELOG Browser checks
- toggleExpand (Lists dropdown opener) held
- mark-verified 410 stub held

### 2026-10-28 08:07
**Final audit pass combined recon (15b, 15, 16, 17) + step 0 small items**

**Built:**
- RECON_final_pass_28oct.md: per-item tables, build order 17 to 15 to 15b with one sw.js bump, batch 16 split plan, 31 decisions
**Fixed:**
- obs 24429 to needs_review, label dandelion_check, reviewer note (edits 22040-22042); snapshot db_20261028_042247
- card 286 taste_notes test draft cleared to NULL (history 3785, human)
- CHANGELOG Current State: Backlog entry for walk route-line zoom/drag bug
**Files:** `docs/audit/2026-10-20/RECON_final_pass_28oct.md`, `CHANGELOG.md`
**Pending:**
- Walk 5 republish held: plan clean but 64 species not 66 (Dandelion only on 24429, now in Review) - Melvin decides
- Melvin answers the 31 decisions, then prompt B

### 2026-10-28 04:20
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261028_042023.sqlite`

### 2026-10-28 04:20
**Session ended** — Session ended from Settings page

### 2026-10-28 04:13
**Merged 845 Taraxacum campylodes into 286 Taraxacum officinale via merge_species_cards (Melvin 28 Oct)**

**Built:**
- batch11b_data.py merge --note option
**Fixed:**
- 845 merged into 286: obs 24429, suggestion on 16083, 2 drafts, 8 history rows, 5 enrichment sources moved; synonym row 15; id_notes conflict kept 286 text, 845 text in history 3783; card 845 deleted
**Files:** `scripts/batch11b_data.py`
**Pending:**
- Melvin: check photo 24429 (13%, suggestion Hyoseris radiata)
- 286 taste_notes reads "test draft"

### 2026-10-28 04:03
**354 Crocus and 530 Taraxacum sect. Taraxacum treated like Usnea (Melvin 28 Oct)**

**Built:**
- bryony_genus_28oct.py genus step takes --cards; rejected photos stay rejected
**Fixed:**
- Photos 8198, 15957, 24430 to Review (genus_reid, <name> — identify to species), species cleared
- 19704 (rejected) suggestion cleared
- Cards 354 and 530 deleted by the step G route (7 drafts, 13 history, 47 enrichment sources, 2 culinary_info); 653 cards; 0 non-species cards or live photos left
**Files:** `scripts/bryony_genus_28oct.py`
**Pending:**
- Melvin: Review genus_reid (6 photos) + bryony_check (8229)

### 2026-10-28 04:00
**Species-rank guard: no genus cards, ever (Melvin 28 Oct)**

**Built:**
- taxonomy.is_species_rank_name / require_species_rank / NonSpeciesNameError (one definition)
- new_species_card + set_observation_species refuse non-species names; main.py maps to HTTP 400 code not_species_rank
- Refused before any write: confirm/correct (update_observation_status), retry-confirm, rename (in place, new card, onto existing), merge keep, trust bulk-reassign
- Bulk approve skips; promotable_suggestion returns None for non-species
- Scan: non-species top name -> needs_review genus_reid, no species, no card, never auto-approved
- trigger_ai_drafts makes no card for a non-species name
**Files:** `app/services/taxonomy.py`, `app/models/species.py`, `app/services/species_link.py`, `app/services/observation_service.py`, `app/api/bulk_actions.py`, `app/api/trust.py`, `app/api/reidentify.py`, `app/api/culinary.py`, `app/api/scan.py`, `app/services/enrichment.py`, `app/main.py`, `tests/test_species_rank_guard.py`
**Pending:**
- Melvin: decide 354 Crocus and 530 Taraxacum sect. Taraxacum (both now refused on re-approve/rename-onto)
- Melvin: live check — rename a card to a genus shows the refusal message

### 2026-10-28 03:52
**Bryony / Usnea / Salix (Melvin 28 Oct): 8229 to Review (bryony_check); 879 Bryonia dioica toxic/toxic verified + Melvin look-alike and preparation warnings verbatim; Usnea/Salix photos to Review (genus_reid), cards 880/881 deleted (step G route); 136 Bryonia syriaca orphan-marked; genus-card census + no-genus-card guard proposal (not built)**

**Built:**
- scripts/bryony_genus_28oct.py (dry run default, snapshot + read-back per step)
**Fixed:**
- 879 verdict toxic/toxic verified human
- 879 look_alike_warnings + preparation_warnings human verbatim
- 880 Usnea / 881 Salix deleted, photos 17033/17046/24062 to Review
- 136 orphan-marked
**Files:** `scripts/bryony_genus_28oct.py`
**Pending:**
- No-genus-card guard: build after Melvin approves the proposal
- Decide 354 Crocus and 530 Taraxacum sect. Taraxacum (non-species cards with photos)
- Melvin: Review bryony_check (8229), genus_reid (3)

### 2026-10-28 03:27
**Rename onto an existing name now merges through merge_species_cards (no more _merged_into: soft-delete); CHANGELOG Browser checks restored**

**Built:**
- culinary._auto_merge_into delegates to species_merge.merge_species_cards (source card deleted, all species-keyed rows re-keyed, text/verdict rules, synonym row)
**Fixed:**
- Rename-onto-existing no longer writes edibility_status _merged_into: marker
- Current State: Browser checks block restored; Oxalis grandis 3493 dropped from review queue
**Files:** `app/api/culinary.py`, `tests/test_batch11b_merge.py`, `CHANGELOG.md`
**Pending:**
- Commit at End Session

### 2026-10-28 03:22
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261028_032253.sqlite`

### 2026-10-28 03:22
**Session ended** — Session ended from Settings page

### 2026-10-28 03:17
**Audit batch 11b BUILD — data and taxonomy (Melvin's decisions 27–28 Oct; DECISIONS_11b_2026-10-27.md). Snapshot before every write step (11 snapshots db_20261028_0300xx–031236, backup API, no git commit); every changed row read back by id.**

**Built:**
- app/services/species_merge.py merge_species_cards — the ONE merge routine: re-keys observations (id/name/suggestion), candidates, drafts, recipes, edibility history/conditions, lookalikes (both cols), synonyms (+ discard name), session/list/dismissal rows (deduped), encounters, sources, enrichment_sources, species_resources (by name), map note tags, walk waypoints, walk override files, experience_publications ids; TEXT RULE (human side wins, else accepted name; loser in a history row); VERDICT RULE (toxic wins, human-verified beats unverified, conservative among equals); deletes the discard card. POST /api/species/merge now calls it (no more _merged_into soft-delete)
- A: 7 merges — 704→457, 758→757, 412→708, 608→589, 103→531, 600→749, 200→82; 704 first alone and read back clean; synonym rows 9–14 added (412's existing row 8 kept); 103's human edible_parts kept on 531; walk 5 published snapshot ids re-keyed (704→457, 608→589)
- B: 8410 → Lepista nuda, 21950/22074 → Erigeron canadensis (spelling only); 187's 5 photos → Hypericum perforatum (manually_verified)
- C: 151 cards set to GBIF family / own-name genus / empty kingdom filled (343 history rows, changed_by=human); 332 stays Fungi; 0 cards left with a non-family family, empty genus or empty kingdom
- D: 12 corrections via update_observation_status (18398 scene; 8229 Bryonia dioica; 19809 Carpinus betulus; 24068/24069 Larix decidua; 8408 Populus tremula; 8263 Parthenocissus quinquefolia; 17033/17046 Usnea; 21713 Oxalis stricta; 18828 Dryopteris affinis; 24062 Salix); no hazard second tap needed; new cards 878 Parthenocissus (toxic/toxic, human), 879 Bryonia dioica, 880 Usnea, 881 Salix
- D: 28 photos to Review, label 11b_review, reviewer note naming the suggestion; 24 with a promotable species_suggested, 21252 Arctium note only, 9477/20893/8370 no suggestion
- E: 22 G3-held drafts rejected (reason recorded); 3160 Chenopodium pratericola released
- F: 43 English names (the other cards in the list were merged or deleted)
- G: 87 cards deleted with their species-keyed rows (253 drafts, 8 recipes, 155 verdict-history, 3 conditions, 918 enrichment caches, 87 culinary_info + 238 history, 1 lookalike); 48 rejected photos → species_id NULL; 6 stale suggestions on confirmed photos cleared; 148/583/740/808/826 kept, orphan-marked; toxic (136, 477, 581, 686, 843) and 22 European reference cards kept
- H: 882 Pastinaca sativa (new_species_card, Apiaceae) caution/none human + Melvin's preparation warning verbatim; 877 Rubus pedatifolius edible/none human
- tests/test_batch11b_merge.py (7 tests); full suite 35 files pass
**Fixed:**
- Rename no longer keeps the old family/genus: culinary._reset_lineage_for_new_name re-resolves lineage through the GBIF write-gate (family left empty if GBIF fails, genus from the name), history rows changed_by=system:rename
- CLAUDE.md merge rule now points at species_merge.merge_species_cards
**Files:** `app/services/species_merge.py`, `app/api/culinary.py`, `scripts/batch11b_data.py`, `tests/test_batch11b_merge.py`, `CLAUDE.md`
**Pending:**
- Melvin: 28 photos in Review under 11b_review
- Walk 5 republish: list then shows 457 Trametes versicolor and 589 Cota tinctoria once (67 → 66 species)
- New bare cards 879 Bryonia dioica, 880 Usnea, 881 Salix have no verdict/enrichment (confirm path's background AI drafts not run) — scoped enrichment + verdicts
- _auto_merge_into (rename onto an existing name) still soft-deletes via edibility_status '_merged_into:' — route it through merge_species_cards

### 2026-10-25 19:57
**Audit batch 12 + A-04 + batch 11 leftovers: plan collects all blockers, walk 4 publication row, stop renumbering in the plan, orphan root photos removal, secrets in .env, Group B retired, bracken text fill-only**

**Built:**
- Plan shows stop renumbering vs the live page (stop_changes)
- Publish commit removes unreferenced site-root photos/; plan lists it under Removed from site
- Secrets read from environment/.env only; Settings writes .env
**Fixed:**
- D3-02: GateErrors collected as blockers (badge blocked); build still writes nothing
- C-05: experience_publications #2 for walk 4 (rummelsbuhl-foray, ed3b4d9, 2026-10-21 17:00:10 UTC, not default)
- A-04: deepseek key moved to .env; deepseek_api_key and gdrive_access_token blanked in app_settings (snapshot db_20261025_195040)
- Startup Group B human stamp retired (0 rows today)
- Bracken constant fills only empty fields; differing text -> review card
**Files:** `scripts/experience_export/export.py`, `app/services/experience_publish.py`, `app/api/experience.py`, `frontend/static/js/walk-publish.js`, `app/config.py`, `app/services/settings_service.py`, `app/services/api_dashboard.py`, `app/api/settings.py`, `app/database.py`, `app/services/enrichment.py`, `scripts/batch12_data.py`, `scripts/dev/walkthrough_check.py`, `tests/test_batch12_publish_secrets.py`, `tests/test_batch4_a02_d1_01.py`
**Pending:**
- Melvin: rotate the DeepSeek key (new key in Settings, revoke old)
- Saved walks have no edit guard while published (by design; plan shows changes)
- Old snapshots still hold the old DeepSeek key and Drive token (not edited, per decision)

### 2026-10-25 18:58
**Audit batch 11 verdict trail: new-card helper, no startup auto lock, bracken via shared writer; data B2-08/B2-07/C-06**

**Built:**
- new_species_card() in app/models/species.py used by all 5 creation paths
- _write_verdict(changed_by=...) shared by the bracken safety constant
- scripts/batch11_verdict_trail.py (dry run / snapshot / write / read-back)
**Fixed:**
- B2-08: no card is born with a NULL verdict; 13 NULL -> unknown (history 2259-2271, system:never_assessed)
- B2-07: init_db no longer writes verified_by=auto; 583 -> human (2272); 148/149 unlocked (2273-2276)
- C-06: 60 origin_unknown verdict rows (2277-2336)
- Bracken: verdict row + verified_by=safety_constant, never re-stamps a human lock
**Files:** `app/models/species.py`, `app/api/edibility.py`, `app/services/enrichment.py`, `app/services/species_link.py`, `app/api/culinary.py`, `app/api/scan.py`, `app/database.py`, `scripts/batch11_verdict_trail.py`, `tests/test_batch11_verdict_trail.py`
**Pending:**
- Startup Group B still stamps human on unfingerprinted verified rows with no provenance (flagged)
- Bracken branch still overwrites edible_parts/preparation_warnings without history (flagged)

### 2026-10-25 18:30
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261025_183015.sqlite`

### 2026-10-25 18:30
**Session ended** — Session ended from Settings page

### 2026-10-25 17:44
**Fixed 25 Oct walkthrough bugs: saved-walk load (_animating), Find->Make? walk filter, reviewer_notes in Review list; walk panel/species list UI; H12 script; re-run**

**Fixed:**
- leaflet.heat updates guarded on layer._map (_heatSetOptions/_heatSetLatLngs/_heatRemove, _recalcHeatMax checks _map); walks 4/5 load with no error
- showDiscoverView remembers the open walk id (_discoverWalkId) so Make? opens /recipes?walk=N
- ObservationOut.reviewer_notes (blanked for guests in get_observation)
- walk panel buttons wrap labels; species list Latin names wrap at spaces only (phone Latin column 112px); heading clears the nav chip below 1080px
- walkthrough_check.py: _publish_panel dismisses leftover Background jobs cards and waits for the Walk stats tab
**Files:** `frontend/index.html`, `frontend/species.html`, `app/api/observations.py`, `scripts/dev/walkthrough_check.py`, `tests/test_walkthrough_fixes_25oct.py`
**Pending:**
- B06 tidy on walk 3 refused by members-unchanged guard after B05 picked a different pin (needs eyes)
- E05b script error in the no-ngrok path
- Melvin: check walk panel buttons at 1280px and species list at 390px

### 2026-10-25 16:52
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261025_165228.sqlite`

### 2026-10-25 16:52
**Session ended** — Session ended from Settings page

### 2026-10-25 12:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261025_124705.sqlite`

### 2026-10-25 12:47
**Session ended** — Session ended from Settings page

### 2026-10-25 11:53
**Recipes page in the app + Recipes tab (all public recipes) on the public walk page; recipe title/summary/type/hide/website fields (Alembic 0059) with backfill**

**Built:**
- Alembic 0059_recipe_page_fields: species_recipes.summary, recipe_type, hide_from_public (default 0), website_url — applied live after snapshot db_20261025_113127
- Shared rules in app/models/species.py: recipe_title_source (own/heading/line), recipe_summary_line (skips safety/hazard/medicinal/cited sentences), propose_recipe_type (dish noun), recipe_plant_parts, recipe_website_url_ok (https melvinjarman.co.uk); recipe_display_title skips section headings and 'Recipe:'/'Title:' labels (JS twin _recipeTitle in step; 0 live display titles changed)
- Backfill (scripts/recipe_fields_backfill.py, dry run first): 25 titles from headings, 22 'needs a title' left empty, 252 summaries, types 133 (38 corrected after the rule was tightened, snapshot db_20261025_114548); read back by id vs snapshot, 0 mismatches, bodies unchanged
- GET /api/recipes (CULINARY_ALLOWED_SQL, non-medicinal, approved; safety map via new safety_for_species_bulk, identical to per-species for all 243 species; 0.4 s) + guest allowlist; PATCH recipe: summary/type/hide/website, validated, curator only
- frontend/recipes.html: views in season now / season / walk / type / species / plant part / A–Z / recent; search; image-free tiles with ⚠ caution and warnings; tile -> /species?s=…&recipe=id#recipe-card-id; nav link
- species.html: linked recipe opens (all seasons, expanded, outlined); curator inline edit on each recipe card
- Find -> Make? opens /recipes (?walk=<open walk>); _findRecipes removed (/api/find/recipes kept, no UI caller)
- Export: build_recipe_bank (export gates, not hidden, titled; teaser only, curator warnings, link); Recipes tab rewritten with filters; leak check (no body text in the tab data); plan lists recipe_bank (count, new since the page on the site, full list, not-public reasons); publish panel shows it; preview card links to index.html#recipes
- Counts: app 245 recipes (15 caution); public tab 208 (43 not public: 20 needs title, 8 Apiaceae, 7 no edible claim, 4 toxic, 4 caution withheld)
**Fixed:**
- Recipe titles taken from '## Ingredients'-type headings (latent; none live)
**Files:** `migrations/versions/0059_recipe_page_fields.py`, `app/models/species.py`, `app/api/recipes.py`, `app/api/walk.py`, `app/api/culinary.py`, `app/services/safety_gate.py`, `app/services/guest_access.py`, `app/services/experience_publish.py`, `app/main.py`, `frontend/recipes.html`, `frontend/species.html`, `frontend/index.html`, `frontend/static/js/site-header.js`, `frontend/static/js/walk-publish.js`, `frontend/static/sw.js`, `scripts/recipe_fields_backfill.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `scripts/experience_export/templates/preview.html`, `tests/test_recipes_page.py`, `tests/test_batch5_safety_gate.py`, `tests/test_batch8_guest_and_culinary_warnings.py`, `RECON_recipes_page_25oct.md`
**Pending:**
- Melvin: 22 recipes need a title (list in RECON_recipes_page_25oct.md); recipe 258 (Laetiporus, walk 5 stop teaser) shows 'Always cook well…' as its dish until titled
- Melvin: review types (113 Other) and summaries on the species cards
- Browser walkthrough H (Recipes); CLAUDE.md Alembic head now 0059
- No commit (Melvin)

### 2026-10-25 11:20
**22184 approved as Rubus pedatifolius (Melvin: yew and holly dismissed)**

**Built:**
- 22184 -> Rubus pedatifolius via confirm-species, hazard_ack Ilex aquifolium (GATE, iNat #2 2%) + Taxus baccata (DEEP, iNat #7 0.17%) as Melvin dismissed them; manually_verified/identified, label cleared; edits 21758-21763, processing_log 75411; confirmed copy exists. Snapshot db_20261025_111959 (backup API, no commit)
- New bare species card 877 Rubus pedatifolius created by the confirm path: edibility_status NULL, severity unknown (fails closed; audit B2-08 generator)
**Pending:**
- Card 877 Rubus pedatifolius needs enrichment + a verdict (born NULL, B2-08)
- No commit (Melvin)

### 2026-10-25 11:18
**Hazard rule simplified: GATE/DEEP tiers in one predicate, human decisions stand, Review hazard block replaced by a Status filter; Melvin's decisions 24525/24471/24469 applied (22184 held)**

**Built:**
- hazard_candidates.py: GATE tier = top 3 of any source or >= 5% in any source (hit['gate'], entry_gates); gating_hazards()/deep_hazards() return nothing for a photo a human has decided (is_undecided_by_human). Auto-approve still blocked at any rank (scan.py unchanged)
- Gate callers moved to gating_hazards: check_hazard_ack (approve/correct/confirm-species/retry-confirm), bulk approve, Data Trust accept, publish panel, Review card red line, Review filter
- Review: Hazard candidate block removed from Critical (/api/experience/critical returns walk items only; badge counts walk items only); Status filter option 'Hazard candidates' (review_status=hazard_candidates); DEEP tier shows one grey line 'Also listed deep in <source>: <name> <score>' (HazardAck.deepLineHtml); ObservationOut.hazard_deep
- Decisions via confirm-species (edited_by human): 24525 -> Verbascum thapsus (edits 21740-21745; foxglove now DEEP, ack passed for the record), 24471 -> Chaerophyllum hirsutum (21746-21751), 24469 -> Chaerophyllum hirsutum (21752-21757); all manually_verified/identified, confirmed copies exist. Snapshot db_20261022_223012 (backup API, no commit)
- Red line now on 29 of 376 queue cards (47 in the Hazard candidates filter incl. 18 AI-approved); 58 queue cards carry the grey line
**Fixed:**
- Old any-rank rule red-lined and gated cards with a hazard at rank 8+ / <1%; decided photos could still be gated on re-correction
**Files:** `app/services/hazard_candidates.py`, `app/api/observations.py`, `app/api/experience.py`, `app/api/bulk_actions.py`, `app/api/trust.py`, `frontend/review.html`, `frontend/static/js/hazard-ack.js`, `frontend/static/sw.js`, `tests/test_hazard_candidates.py`, `tests/test_batch5_safety_gate.py`
**Pending:**
- 22184 held: yew is DEEP (iNat #7, 0.17%); the gating hazard is holly Ilex aquifolium (iNat #2, 2%) - Melvin to confirm holly dismissed before approving as Rubus pedatifolius
- Reopened check: beyond the 18 + 17052/17737, 10176 (census 21 Oct) and 22131 (19 Oct non-European misID) were Melvin-directed sends to Review - not restored; 15958, 15970, 21333, 21673, 21799 were Melvin rejections reopened by system:p1_transport_restore 18 Jul - not restored, Melvin decides
- Pastinaca sativa: still no card - Melvin decides card + verdict
- Browser walkthrough D additions; no commit (Melvin)

### 2026-10-25 10:49
**Website review: latest-walk preview and public walk catalogue**

**Built:**
- Root index now lists all published walks newest first; root preview links to latest published walk.
- Publish and unpublish regenerate and verify catalogue, root preview, tree alias and walks.json in the same public-site commit.
- Legacy public root walk preserved at its own URL; public footer privacy link corrected.
**Fixed:**
- No-op publishing remains idempotent; missing preview blocks publication and live mismatch is explicitly reported.
- Public site 400907f pushed and live bytes verified; 64 species / 59 stops shown for latest walk.
**Files:** `app/services/experience_catalogue.py`, `app/services/experience_publish.py`, `app/api/experience.py`, `frontend/static/js/walk-publish.js`, `scripts/experience_export/config.json`, `tests/test_experience_catalogue.py`, `tests/test_stage_c_publish.py`
**Pending:**
- 25 isolated catalogue/publisher tests pass; local app publishing UI has not been browser-tested under the repo rule. Melvin should check the next real publish updates the collection and /b together.
- Publisher source changes remain in the working tree for the normal End Session commit. Existing unrelated dirty files were preserved.

### 2026-10-22 22:15
**Hazard review follow-up: 8262 corrected to Chaerophyllum hirsutum; recon of the 20:06 hazard_review write, walk stops, Pastinaca; audit pass 2 recon (batches 11-13)**

**Built:**
- 8262 corrected Anthriscus sylvestris -> Chaerophyllum hirsutum (species 57, toxic) via confirm-species, hazard_ack 'Chaerophyllum aureum,Chaerophyllum villarsii'; manually_verified/identified; edits 21737-21739, processing_log 75273; snapshot db_20261022_221455 (commit cfc06b53)
- Recorded: the 22 Oct 20:06 hazard_review write ran (changed_by hazard_review:22oct) but had no History entry: 18 rows -> needs_review + label hazard_review (read back by id); 17579/16763/16782 wrongly sent then reverted 20:06:24 (fully restored); 8262 was left needs_review with no species change - fixed here
- Walks: no stop emptied, no species lost; photos off stops: walk 4 stop 3 (17737), stop 7 (9434 Tanacetum); walk 5 stop 51 (21227+21246 Pimpinella major), stop 53 (24195)
- Pastinaca sativa: no species card, so is_hazard_species/hazard index never sees it; named as candidate on 27 photos (16 approved, 1 manually_verified 21778, 8 needs_review, 2 rejected)
- Audit pass 2 recon: fixed B2-06 (data), B3-05, B2-09; mostly fixed C-06 (60 species without verdict history, was 379); open B2-07 (148,149,583), B2-08 (12 NULL, 4 creators born NULL), C-05 (walk 4 no publication row), D3-05, D3-02 (rule-2 GateError still aborts plan), D3-04 (mirror now every publish), B4-01/B4-02 (defence in depth only), A-04
**Fixed:**
- 8262 species correction that the hazard review write missed
**Pending:**
- Melvin: Pastinaca sativa card + verdict/severity decision
- Melvin decisions: C-06 marker backfill, B2-07 3 locks, C-05 walk-4 row vs republish, D3-05 freeze labels, D3-04 redirect, B4-01 still worth it, A-04 Keychain vs .env
- Code (no decision): B2-08 born-unknown at 4 creators + 12 backfill; D3-02 collect GateErrors
- Melvin works hazard_review cards, then republishes walk 5 with Front page ticked

### 2026-10-22 22:14
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261022_221455.sqlite`

### 2026-10-22 22:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261022_220927.sqlite`

### 2026-10-22 22:09
**Session ended** — Session ended from Settings page

### 2026-10-22 21:40
**Foxglove #24507 safety (correct + diagnose + hazard-candidate rule + archive report + card fixes); publish = front page by default + preview.html from the front-page walk; publish-panel bulk confirm; batch 9/10 data writes B1-02 and C-01**

**Built:**
- #24507 corrected to Digitalis purpurea via confirm-species (manually_verified, species 376)
- Hazard candidates: one predicate (app/services/hazard_candidates.py + species.is_hazard_species); any source, any rank, raw lists, name_key + synonyms
- Hazard blocks auto-approve (decide_agreement hazard=True; label hazard_candidate)
- Review Critical section lists undecided hazard-candidate rows (76 today)
- Review card: red ☠ line per hazard species above the name, excluded from Also:
- Approve as another species needs a second tap naming the hazard (hazard_ack; server 409 backstop in update_observation_status + retry-confirm; bulk approve and trust accept skip hazard rows)
- Archive report: HAZARD_ARCHIVE_REPORT_2026-10-22.md (399 rows; scripts/hazard_archive_report.py)
- Card: confidence chip from the shown % (confClass), sp-name/date ink colour, ITIS amber 'may be a newer name' when GBIF matched EXACT
- Publish: front_page tick (default on) in the confirm; unticked rebuilds root preview.html from the front-page publication or stops
- export.py preview_choice: hero non-toxic with photo from the walk, teasers = walk's gated recipes, fails otherwise; preview_* config keys removed
- Publish panel: Select / Select all / Confirm selected (one PATCH at a time, summary); hazard rows own tap only
**Fixed:**
- Syncthing 'below threshold' reason now shows PN and iNat scores (was '90% < 70%')
**Files:** `app/services/hazard_candidates.py`, `app/models/species.py`, `app/services/agreement.py`, `app/api/scan.py`, `app/api/observations.py`, `app/api/reidentify.py`, `app/api/bulk_actions.py`, `app/api/trust.py`, `app/api/experience.py`, `app/services/observation_service.py`, `app/services/experience_publish.py`, `frontend/review.html`, `frontend/index.html`, `frontend/scan.html`, `frontend/static/js/hazard-ack.js`, `frontend/static/js/reidentify.js`, `frontend/static/js/walk-publish.js`, `frontend/static/sw.js`, `scripts/experience_export/export.py`, `scripts/experience_export/config.json`, `scripts/hazard_archive_report.py`, `tests/test_hazard_candidates.py`, `tests/test_stage_c_publish.py`, `tests/test_batch5_safety_gate.py`, `tests/test_second_opinion_merge.py`, `HAZARD_ARCHIVE_REPORT_2026-10-22.md`
**Pending:**
- Melvin republishes walk 5 (Front page ticked)
- Browser walkthrough additions (D, B, F)
- Review the 399-row hazard archive report
- 17052 / 17737 back in Review (17737 is walk 4 stop 3)

### 2026-10-22 21:11
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261022_211159.sqlite`

### 2026-10-22 21:11
**Session ended** — Session ended from Settings page

### 2026-10-22 17:27
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261022_172648.sqlite`

### 2026-10-22 17:26
**Session ended** — Session ended from Settings page

### 2026-10-22 17:13
**Encounters Record tab: audio recording hidden for participant devices (curator keeps it)**

**Built:**
- encounters.html: voice row data-guest-hide (rec-voice-row)
- encounters-main.js: recToggle returns on guest-mode
**Fixed:**
- Participants no longer offered audio the server refuses
**Files:** `frontend/encounters.html`, `frontend/static/js/encounters-main.js`, `tests/test_batch8_guest_and_culinary_warnings.py`
**Pending:**
- Browser check walkthrough E
- Record tab Photo button still shown to participants (server refuses participant photo binding)
- No commit (Melvin)

### 2026-10-22 16:46
**Batch 8: guest visibility + guest notes; Fix A (redraft eligibility); Fix B (look-alike + prep warnings with all culinary content)**

**Built:**
- Fix A: redraft-medicinal only for empty/placeholder medicinal_notes (medicinal_notes_redraftable), never curator text, no pending draft
- Fix B: SafetyGate.culinaryWarnings / culinary_warnings (look-alike + preparation) on species culinary/taste/recipes/field recipes, Lists panel, workshop foraging+recipe (Lists, print, PDF), experience Recipes tab, Find, encounter field recipes, personal card; no repeat where the species block sits beside (map pop-up, Export summary, field-guide entries, PDF booklet, experience plant panel)
- Guest access: deny-by-default guest API allowlist + media gate (app/services/guest_access.py, middleware); is_guest_visible_observation predicate; observation detail/photo, profile thumbnails, recorded walks, timeline, encounter photos filtered
- Encounters: shared_with_guests (Alembic 0057, default off), encounter_visible_to rule, curator Share with guests toggle, participant-notes curator tab
- Guest notes: guest-notes.js on species page + walk stops; text only (audio/photo refused for participants); own notes in Lists/print/PDF
**Fixed:**
- Guest GET to curator APIs and unconfirmed photo/audio files closed
- Guest PDF was refused by the middleware — now allowed
**Files:** `app/main.py`, `app/services/guest_access.py`, `app/models/observation.py`, `app/models/encounter.py`, `app/models/species.py`, `app/services/ai_placeholder.py`, `app/api/culinary.py`, `app/api/encounters.py`, `app/api/observations.py`, `app/api/personal_lists.py`, `app/api/recorded_walks.py`, `app/api/timeline.py`, `app/api/lists_pdf.py`, `app/api/sharing.py`, `app/api/find.py`, `app/templates/print_pdf.html`, `migrations/versions/0057_encounter_shared_with_guests.py`, `frontend/static/js/safety-gate.js`, `frontend/static/js/guest-notes.js`, `frontend/static/js/encounters-main.js`, `frontend/static/sw.js`, `frontend/species.html`, `frontend/index.html`, `frontend/lists.html`, `frontend/print.html`, `frontend/encounters.html`, `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `tests/test_batch8_guest_and_culinary_warnings.py`, `tests/test_enrichment_scope_and_recipe_warnings.py`, `tests/test_batch5_safety_gate.py`, `RECON_batch8_22oct.md`
**Pending:**
- Browser checks (walkthroughs A, B, C, E, G)
- Encounters Record tab still offers audio to participants (server refuses)
- POST /api/recorded-walks still open to guests (no owner column)
- No commit (Melvin)

### 2026-10-22 16:01
**Re-draft medicinal notes button on Scan → Backfill, beside Fungi edibility, through the scope picker + dry run**

**Built:**
- scan.html: 💊 Re-draft medicinal notes button + _redraftMedicinal() (lmScopedDryRunConfirm, JSON body {}, status shows count / not queued, refreshes job list)
**Files:** `frontend/scan.html`, `tests/test_enrichment_scope_and_recipe_warnings.py`
**Pending:**
- Browser check (walkthrough F)
- No commit (Melvin)

### 2026-10-22 15:57
**Walk 5 tidy applied (crossings 3→0, 11.5→7.6 km); enrichment scope picker + per-run cap + scoped resume; handout rule accepts curator look-alike; prep warning travels with every recipe**

**Built:**
- Tidy route order on Morning sunshine walk (id 5): 13 legs changed, crossings 3→0, 11499→7609 m, members unchanged (snapshot db_20261022_132801)
- app/services/enrichment_scope.py: one scope resolver (walk / Current list / all, no default, no scope = 400), cap 25 walk species first, remaining reported
- Scope on /api/enrich/run, re-enrich-empty, /api/enrichment/run, /api/drafts/backfill (all fields incl. id_notes names filter, one cap across field=all), redraft-medicinal (dry run added, species_ids optional), backfill-fungi-edibility (dry run + button)
- enrichment_run saves its scoped species list in the bp payload; resume stays within it; old unscoped resume rows are never resumed
- dry-run.js scope picker modal (lmScopedDryRunCheck / lmScopedDryRunConfirm) on every bulk button; dry run shows scope + queued + remaining
- safety_decision: caution species prints culinary content on handouts with curator prep OR look-alike warning (11 species move withheld→shown)
- SafetyGate.recipeWarning + recipe_prep_warning (Python twin): prep warning next to recipes on species recipe bank, species + encounter field recipes, Lists panel/print, browser print, PDF (booklet + workshop), Export summary, experience page, Find → What can I make? (find.py now serves safety)
**Fixed:**
- Removed CHANGELOG placeholder line in the older 22 Oct block
**Files:** `app/services/enrichment_scope.py`, `app/services/enrichment_plan.py`, `app/services/background_processes.py`, `app/services/safety_gate.py`, `app/api/enrich.py`, `app/api/culinary.py`, `app/api/encounters.py`, `app/api/find.py`, `app/api/lists_pdf.py`, `app/api/sharing.py`, `app/models/species.py`, `app/templates/print_pdf.html`, `frontend/static/js/dry-run.js`, `frontend/static/js/safety-gate.js`, `frontend/static/js/encounters-main.js`, `frontend/static/sw.js`, `frontend/scan.html`, `frontend/review.html`, `frontend/settings.html`, `frontend/species.html`, `frontend/index.html`, `frontend/lists.html`, `frontend/print.html`, `frontend/encounters.html`, `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `tests/test_enrichment_scope_and_recipe_warnings.py`, `tests/test_enrichment_safety.py`, `tests/test_batch5_safety_gate.py`, `CHANGELOG.md`
**Pending:**
- Browser checks (walkthrough A, B, C, F additions)
- Decide: redraft-medicinal button (endpoint scoped, no button yet)
- Pimpinella major/saxifraga (Apiaceae) now print culinary content on Lists/print/PDF via curator look-alike — confirm
- No commit (Melvin)

### 2026-10-22 13:28
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261022_132801.sqlite`

### 2026-10-22 13:18
**Snapshot** — End of session — Context-warning hook + ctx status line (config only; thresholds 400k/500k); CLAUDE.md context + End Session block rules; Step 1 recon for enrichment scope / handout rule / prep warnings with recipes (RECON_enrichment_scope_22oct.md). Settled: 'Current list' scope; encounter field recipes carry prep warnings. No app/ changes.
DB: `snapshots/db_20261022_131852.sqlite`

### 2026-10-22 13:18
**Session ended** — Context-warning hook + ctx status line (config only; thresholds 400k/500k); CLAUDE.md context + End Session block rules; Step 1 recon for enrichment scope / handout rule / prep warnings with recipes (RECON_enrichment_scope_22oct.md). Settled: 'Current list' scope; encounter field recipes carry prep warnings. No app/ changes.

### 2026-10-22 13:16
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261022_131618.sqlite`

### 2026-10-22 13:16
**Session ended** — Session ended from Settings page

### 2026-10-22 13:04
**Context-warning hook + status line (config only, no app/ changes)**

**Built:**
- scripts/dev/context_check.py: UserPromptSubmit hook warns at 120k / limit above 150k; --statusline prints ctx ~Nk; one shared context_tokens helper
- settings.local.json hook + statusLine (not committed)
- CLAUDE.md rule: follow CONTEXT WARNING/LIMIT notes first
**Files:** `scripts/dev/context_check.py`, `.claude/settings.local.json`, `CLAUDE.md`
**Pending:**
- Confirm the hook fires on the next prompt

### 2026-10-22 13:02
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261022_130213.sqlite`

### 2026-10-22 13:02
**Session ended** — Session ended from Settings page

### 2026-10-22 12:59
**22 Oct: Part A, the toxic medicinal round (25 approved, 91 rejected). Part B, enrichment safety: a network circuit breaker and resume, no destructive writes on fetch failure, drafts kept beside each other instead of replaced, fill-only-when-empty plus review cards for warning and ID fields, Wikidata batched at 50, one shared AI draft gate, a dry run on every enrichment button. data_confidence restored for the 380 species lowered by bp 203.**

**Built:**
- net_health circuit breaker: a run pauses as 'paused — no network', resumes when the network is back, and resumes from the last completed species
- A failed fetch never lowers data_confidence, never clears a field, never replaces sources_json
- Bulk re-enrich option removed; bulk runs never invalidate pending drafts; Regenerate puts the new version beside the old one and the old one is retired only on approve
- preparation_warnings, look_alike_warnings, edible_parts, id_notes, seasonal_peak: filled only when empty; changed source text becomes a review card
- Wikidata batched at 50 names per request, with a URL length guard and per-chunk failure sentinel
- draft_gate.save_ai_draft: the one pre-save check for AI drafts (no-use, chat phrasing, no edible parts, toxic culinary, deadly internal use), strips a leading 'None known' line from recipes, counts skips
- enrichment_plan dry-run summary + dry-run.js confirm on every enrichment / backfill / regenerate / repopulate button
**Fixed:**
- data_confidence restored from db_20261021_210339 for 380 culinary_info rows lowered during bp 203 (2 changed since, ci 118 and 139, left alone); snapshot db_20261022_125857; all 380 read back by id
**Files:** `app/services/net_health.py`, `app/services/draft_gate.py`, `app/services/enrichment_plan.py`, `app/services/enrichment.py`, `app/services/background_processes.py`, `app/integrations/wikidata.py`, `app/integrations/pfaf.py`, `app/integrations/inaturalist.py`, `app/integrations/trompenburg.py`, `app/models/species.py`, `app/api/culinary.py`, `app/api/enrich.py`, `app/api/recipes.py`, `frontend/review.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/species.html`, `frontend/index.html`, `frontend/static/js/dry-run.js`, `frontend/static/sw.js`, `tests/test_enrichment_safety.py`, `tests/test_batch5_safety_gate.py`, `tests/test_route_order_and_warning_review.py`
**Pending:**
- Melvin: browser walkthrough of the dry-run confirms, two-version drafts, and the paused-no-network label
- A fresh enrichment run (bp 203 has no resume point)
- Auto-enrich after a species-ID correction is not dry-run gated (_sopApply, _retryApprove, _corrSaveFromLookup, saveCorrection)
- Not committed

### 2026-10-22 07:31
**AI draft census applied (Melvin 22 Oct decisions) through the existing approve / edit-approve / reject routes**

**Built:**
- Optional {reason} body on POST /api/species/{name}/drafts/{field}/reject (verdict_drafts.record_rejection_reason); test added
**Fixed:**
- 307 approved, 19 edited-then-approved (18 recipes: 'None known' first line removed; 2723 St John's wort interaction sentence), 199 rejected with 'Melvin census 22 Oct: ...' reasons, 141 kept pending (116 toxic-medicinal, 23 non-European, 3493 Oxalis grandis, 3714 refused)
- History #3403-3728 (326 rows, ai_approved:human); species_recipes #177-271 (95); snapshot db_20261022_072924
**Files:** `app/api/culinary.py`, `tests/test_route_order_and_warning_review.py`, `docs/audit/2026-10-22/draft_census/apply_plan.json`, `docs/audit/2026-10-22/draft_census/apply_dryrun.md`, `docs/audit/2026-10-22/draft_census/toxic_medicinal_round.md`
**Pending:**
- 3714 Picea orientalis medicinal: approve refused (PFAF lists uses) - a G1 'no specific medicinal uses' draft the pattern missed
- Toxic medicinal round (116 drafts)
- Not committed (End session)

### 2026-10-22 06:36
**Curator text: Daucus carota (9) edible_parts written via PATCH /api/culinary/{name}/field (species-page path)**

**Fixed:**
- Daucus carota edible_parts = Melvin verbatim (274 bytes); history #3402 changed_by human, old_value = the 5443-char PFAF text; is_curator_authored True; snapshot db_20261022_063521
**Pending:**
- Not committed (End session)

### 2026-10-22 06:18
**Diagnosed + repaired the offline enrichment run bp 203 (killed by an app/ reload at 575/638)**

**Fixed:**
- 285 AI drafts on 140 species restored invalidated -> pending (pending before the run, discarded by re_enrich with no replacement because the laptop was offline); every column now equals the pre-run snapshot
- Ononis spinosa (605) preparation_warnings restored from snapshot db_20261021_210339 (the run had written PFAF 'None known'); history #3401 changed_by='snapshot_restore' (not human); draft 3633 approvable again
**Pending:**
- Snapshot before repair: db_20261022_061757
- Not restored (by decision): confidence scores (382 lowered), Populus nigra + Pimpinella saxifraga prep text, Ononis/Daucus edible_parts, 26 sources_json
- Enrichment run: Wikidata batch 414 bug; re-run only online, consider re_enrich off
- Not committed (End session)

### 2026-10-22 06:06
**Route order by geometry (tidy) + review cards for every unreviewed warning + post-batch-7 UI fixes (sharing section, signed-out vs offline)**

**Built:**
- walk_route.tidy_order (NN + 2-opt), crossing_legs, order_length_m; plan_reroute keeps stored legs walked backwards (geometry + dashes reversed)
- POST /api/walk/saves/{id}/tidy: dry run (crossings, legs changed, estimate) -> Re-route snapshot, ORS on new legs only, refuses if members change, read-back; walk 5 dry run 3->0 crossings, 13 legs, est 7.06 km (was 11.5)
- POST /api/walk/tidy-order; Build walk + regroup use it (NN fallback offline), sequence guard
- Map: Tidy route order button on loaded saved walks
- scripts/import_warning_review_drafts.py (renamed): both warning fields, every verdict, live cards; 140 drafts written (ids 3564-3703), snapshot db_20261021_210339
- look_alike_warnings joins CURATOR_DRAFT_FIELDS; Remove endpoint (human history row, never deadly); 409 if field changed since drafting (approve + remove); Review queue walk species first + walk badge
- Settings: 'Your devices & sharing', share URL/Copy/QR removed, Sharing on/off status; participant /join links built on the share URL
- 401 vs offline: one SIGNED_OUT_TEXT; 401 JSON for fetch, HTML for navigation, no-store; offline.js signed-out banner + stop pinging; SW bypasses /health, v10; outbox keeps items on 401, no replay loop
**Fixed:**
- Frangula alnus (628) queues its field text, PFAF text kept in context
- SW cached /health 200 masked real outages
- Workshops/Lists participant links pointed at localhost when minted on the laptop
**Files:** `app/services/walk_route.py`, `app/api/walk.py`, `app/api/culinary.py`, `app/models/species.py`, `app/services/access.py`, `app/main.py`, `app/api/sharing.py`, `app/api/workshop_tokens.py`, `frontend/index.html`, `frontend/review.html`, `frontend/settings.html`, `frontend/workshops.html`, `frontend/lists.html`, `frontend/static/js/offline.js`, `frontend/static/js/encounter-queue.js`, `frontend/static/sw.js`, `scripts/import_warning_review_drafts.py`, `tests/test_route_order_and_warning_review.py`, `tests/test_signed_out_vs_offline.py`, `tests/fixtures/walk5_stops.json`, `tests/test_experience_gates.py`, `tests/test_batch7_access.py`, `tests/test_batch5_safety_gate.py`
**Pending:**
- Re-run the bulk enrichment job f4d95b3f (killed by an app/ reload during this work)
- Tidy walk 5 (Melvin, in the app)
- Re-route/Tidy snapshot path commits the whole tree (git add -A)
- Not committed (End session)

### 2026-10-21 20:45
**Batch 7: access gated by the token layer (localhost / curator device / participant) + source-text escaping sweep**

**Built:**
- One access middleware (app/services/access.py resolve_access): localhost = local Host AND loopback peer AND no X-Forwarded-For; curator devices https-only; participants guest (cookie Secure on https only); no device -> 'Ask Melvin for a link' 401, no data/API
- One-time /join/<token>: atomic claim, separate cookie secret (sha256 stored), clean redirect, 'Link already used' on reuse
- Settings > Share with Guests: Curator devices list/add (localhost only, link + QR)/revoke; guest-mode toggle and setting removed
- Migration 0056_device_tokens (name, claimed_at, session_hash, last_used_at; expires_at nullable)
- Workshops/Lists participant links -> /join/<token>
**Fixed:**
- review.html:1962 common names escaped + reviewer-notes textarea, file path/name, thumbnails, error text
- print.html medicinal notes/folklore and ID notes escaped
- Inline-handler quote escaping: review 17, index 9, species 2, lists 2 sites
- species.html called undefined _resc (resources list always failed)
- ?token=/Bearer no longer credentials; /api/workshop/tokens can't mint or list curator tokens
- Stale duplicate Current State block removed from CHANGELOG
**Files:** `app/services/access.py`, `app/main.py`, `app/api/sharing.py`, `app/api/identity.py`, `app/api/workshop_tokens.py`, `app/api/connections.py`, `app/models/workshop.py`, `app/services/settings_service.py`, `migrations/versions/0056_device_tokens.py`, `frontend/settings.html`, `frontend/workshops.html`, `frontend/lists.html`, `frontend/review.html`, `frontend/index.html`, `frontend/species.html`, `frontend/print.html`, `tests/test_batch7_access.py`, `tests/test_batch7_escaping.py`, `tests/test_batch4_a02_d1_01.py`, `CHANGELOG.md`
**Pending:**
- Melvin: pair phone via Settings > Add device (ngrok must be running)
- Browser checks in walkthroughs B/D/E/F
- Not committed (End session)
- CLAUDE.md Alembic head now 0056 (batch 17)

### 2026-10-21 19:56
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261021_195616.sqlite`

### 2026-10-21 19:56
**Session ended** — Session ended from Settings page

### 2026-10-21 19:42
**Cleared stale orphan markers on Ambrosia confertiflora (808, live needs_review photo, human-verified) and Hypericum humifusum (810, human-verified). Snapshot snapshots/db_20261021_194150.sqlite first. norway spruce (685) left marked. Read back by ID: 808/810 orphaned_at NULL, 685 unchanged.**

**Fixed:**
- Stale orphan markers cleared on 808 and 810
**Pending:**
- Session code changes still uncommitted

### 2026-10-21 19:39
**Orphan cards data write: DB snapshot snapshots/db_20261021_193804.sqlite (backup API, no git commit), 44 species orphan-marked (orphaned_at 2026-10-21 17:38:51 UTC), 72 pending drafts on the 67 orphan cards set to invalidated with invalidated_reason in generation_context_json. Read back by ID: 44/44 marked, 72/72 invalidated; verdict queue 33 -> 5.**

**Fixed:**
- 44 phantom species cards orphan-marked; 72 drafts on orphan cards invalidated (redraftable if a card becomes live)
**Pending:**
- Stale orphan markers on live/reference cards not cleared: Ambrosia confertiflora 808, Hypericum humifusum 810, norway spruce 685
- Code changes from this session still uncommitted

### 2026-10-21 19:33
**Orphan species cards: shared orphan rule (live observation / reference card), GC on every reject path, queues filtered, kingdom gate at card creation. Code only — no data written, nothing committed.**

**Built:**
- species_link: species_has_live_observation / species_is_reference / species_is_listable predicates (single definition; SQL text form for the sweep script)
- Orphan rule: marked only if no non-rejected obs (species_id/primary/suggested) AND not a reference card; rejected rows no longer count as backing
- refresh_orphan_markers on reject paths (update_observation_status, bulk review, audit reject, identify tier reject, both prefilter rejects) and un-reject paths (status helper, bulk, undo, audit send-to-review, identify send-to-review, trust bulk/kingdom send, scan below-threshold suggestion)
- Verdict sweep plan(), verdict-draft queue, edibility review-queue / species / unknown lists show only live-or-reference cards
- scan.py kingdom gate: no card when iNat files the top name outside Plantae/Fungi (logged as species_card_skipped); unknown kingdom keeps today's behaviour
**Fixed:**
- Cards created for a rejected photo's guess were never orphan-marked (GC only ran on move-off and counted rejected rows)
**Files:** `app/services/species_link.py`, `app/services/observation_service.py`, `app/services/prefilter.py`, `app/api/bulk_actions.py`, `app/api/audit.py`, `app/api/identify.py`, `app/api/observations.py`, `app/api/trust.py`, `app/api/edibility.py`, `app/api/scan.py`, `scripts/verdict_sweep_drafts.py`, `tests/test_orphan_cards.py`, `tests/test_verdict_drafts.py`
**Pending:**
- Data dry run reported: 67 cards would be orphan-marked (44 new), 8 reference cards protected, 72 pending drafts on them, verdict queue 33 -> 5. Awaiting Melvin's go (snapshot first)
- Stale orphan markers on live/reference cards (Ambrosia confertiflora 808, Hypericum humifusum 810, norway spruce 685) not cleared

### 2026-10-21 19:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261021_190913.sqlite`

### 2026-10-21 19:09
**Session ended** — Session ended from Settings page

### 2026-10-21 19:05
**Republished walk 4 (Rümmelsbühl foray) to melvinoj/foraging-experience (ed3b4d9)**

**Built:**
- Walk 4 build: 63 species, 31 stops (4 with skull), 244 images; rule 1b, batch 6 warnings, sentence-case names
**Fixed:**
- Photos EXIF/GPS-free: exporter check 0, exiftool GPS 0 + EXIF/XMP/IPTC 0, PIL 0 of 244
- Live index, index.html, preview.html, tree.html + 3 sampled photos: HTTP 200, byte-identical to the build
**Files:** `(separate repo) foraging-experience: index.html, tree.html, preview.html, photos/ (+36, 4 replaced)`
**Pending:**
- w/walk-4 mirror built but not published (not part of the previous publish)
- Taxonomy warning: 277 Rosa dumalis family Rosa sect. Caninae (data, 11b)

### 2026-10-21 18:54
**1b rule 1b (AI-agreed harmless species shown on published walks) + walk 4 plan diff (stopped for OK); read-only diagnosis of 88 zero-pin species rows**

**Built:**
- gates.ai_agreed_included (safety_decision level none/caution) = not unconfirmed_hazard; obs_passes takes the species row; plan labels AI-agreed shown/blocker
- tests: rule 1b in test_experience_gates.py (2)
**Files:** `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `tests/test_experience_gates.py`
**Pending:**
- Walk 4 republish: awaiting Melvin OK on the plan diff (12 added, 5 badge changes, recipes 12/76 withheld, 99 added)
- Zero-pin species: fixes proposed, nothing applied; no species delete path exists

### 2026-10-21 18:28
**Common names in sentence case (shared helpers) + species page Large / Grid / List view toggle**

**Built:**
- sentence_case_name + display_common_name (server), spCommon / spCommonList + spNameHtml/Text (species-names.js)
- Routed: species grid + header, map pop-up, walk stop card, lasso, proximity, near-me, find, search, walk diary, Lists, browser print, PDF, Export summary, review cards, re-identify candidates, seasonal returns
- species.html Large / Grid / List toggle: one data set, shared badge (_spEdibBadge -> SafetyGate), sortable List (safety: deadly, toxic, unknown, caution, edible, not edible), select mode in all views, remembered view, lazy thumbnails from /api/map/geojson, phone layout drops family
- tests/test_names_and_species_views.py (10, JS executed via JavaScriptCore)
**Files:** `app/models/species.py`, `app/api/lists_pdf.py`, `app/api/sharing.py`, `frontend/static/js/species-names.js`, `frontend/species.html`, `frontend/index.html`, `frontend/lists.html`, `frontend/print.html`, `frontend/review.html`, `frontend/static/js/reidentify.js`, `frontend/static/js/seasonal-returns.js`, `tests/test_names_and_species_views.py`
**Pending:**
- Not routed: seasons.html, encounters-main.js (pages don't load species-names.js), scan.html (labels only)
- review.html:1962 renders the joined common names unescaped (pre-existing)
- Browser checks 52-63 (Melvin; numbering overlaps batch 6's 52-61)

### 2026-10-21 16:26
**E-14 cleanup: real human history rows (current text) for the 10 remaining placeholder-marker fields**

**Fixed:**
- Snapshot db_20261021_162623
- 6 preparation_warnings via approve of marker_confirm drafts 3181/3194/3202/3209/3223/3232 -> history 3390-3395 (106, 27, 94, 50, 97, 347)
- 605 taste_notes, 373 taste_notes/medicinal_notes/recipe via species-page field path -> history 3396-3399
- Read-back: all 10 byte-identical to pre-write text, old=new=current, curator-authored; 0 fields with a marker as latest row; 11 marker rows kept as audit trail
- Keck 106 now has a curator caution warning: handout-withheld caution species 26 -> 25
**Pending:**
- Browser checks 50-61 (Melvin)

### 2026-10-21 16:26
**Snapshot** — Before E-14 cleanup: real human history rows (current text) for the 10 remaining placeholder-marker rows (Melvin, 21 Oct); Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_162623.sqlite`

### 2026-10-21 16:24
**Aspen 97 edible + edible_parts; batch 6 (B2-03 + E-14): one shared warnings helper on every surface, handout rule for caution, no truncation, DB refuses placeholder markers; Oenanthe crocata 653 curator look-alike**

**Built:**
- species_warnings / handout_warnings / is_placeholder_marker in app/models/species.py, served as safety.warnings + safety.handout_warnings
- safety_decision handout_culinary_allowed + handout_label ('⚠ caution — warning not yet reviewed'); experience rule 8 uses it
- SafetyGate.warnings / handoutWarningsHtml / handoutCulinary / handoutRecipes / handoutBadge
- Map pop-up, walk stop card, proximity alert, species page: full warnings, uncurated text labelled
- Lists, browser print, PDF, Export summary, experience page: curator-only warnings always printed, uncut; PDF + Export summary warnings from the DB
- Migration 0055: triggers refuse placeholder markers (applied to live DB)
- SW v9 + species cache renamed foragingid-species-2
- tests/test_batch6_warnings.py (10)
**Fixed:**
- 97 Populus tremula inedible->edible/none verified human (edibility history 2229), edible_parts (culinary history 3388); recipe #48 shown again
- Map pop-up 120-char cut, PDF 140-char cut, id_notes toggle hiding warnings, booklet caution warnings missing
- 653 Oenanthe crocata look_alike_warnings curator text (culinary history 3389), replaces the (set) marker lock
- Snapshots db_20261021_160140, db_20261021_162146, db_20261021_162236
**Files:** `app/models/species.py`, `app/services/safety_gate.py`, `app/api/sharing.py`, `app/api/lists_pdf.py`, `app/templates/print_pdf.html`, `frontend/static/js/safety-gate.js`, `frontend/index.html`, `frontend/lists.html`, `frontend/print.html`, `frontend/species.html`, `frontend/static/sw.js`, `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `migrations/versions/0055_refuse_placeholder_markers.py`, `tests/test_batch6_warnings.py`, `tests/test_batch5_safety_gate.py`, `tests/test_experience_gates.py`
**Pending:**
- E-14 cleanup: dry run reported, no write — 6 prep marker rows have pending marker_confirm drafts 3181/3194/3202/3209/3223/3232; 4 non-warning marker rows (552, 561, 562, 611) need a decision
- 26 caution species withheld on handouts until a curator warning exists
- Browser checks 50-61 (Melvin)
- CLAUDE.md alembic head says 0050; actual 0055

### 2026-10-21 16:22
**Snapshot** — Before Oenanthe crocata (653) curator look_alike_warnings (Melvin addendum 21 Oct 16:15, E-14); Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_162236.sqlite`

### 2026-10-21 16:21
**Snapshot** — Before migration 0055 (E-14: triggers refuse placeholder markers; no row changes), batch 6; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_162146.sqlite`

### 2026-10-21 16:01
**Snapshot** — Before Aspen (97) verdict edible/none + curator edible_parts (Melvin, 21 Oct); Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_160140.sqlite`

### 2026-10-21 15:58
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261021_155835.sqlite`

### 2026-10-21 15:58
**Session ended** — Session ended from Settings page

### 2026-10-21 15:56
**Census chunks 12-16 (final round) applied: 123 verdicts (81 DEFAULT keep+verify incl. 277 Rosa dumalis), text 402/25, names 391 Blackcurrant / 217 Nodding catchfly, draft #3063 rejected; walk 4 build gate passes; census summary**

**Built:**
- docs/audit/2026-10-20/verdict_census/chunk_12-16_decisions.md (with census summary)
**Fixed:**
- Batch 5 regression: experience export app_styles.py read the walk badge colours/shape from index.html _culinaryGateBadge; now reads static/js/safety-gate.js (same values) - walk 4 build gate (plan-only) passes
- Snapshot db_20261021_155418.sqlite; edibility history 1887-2228; culinary history 3384-3387; read-back 0 mismatches
- Census: 633 species - edible 355, inedible 143, toxic 81, deadly 12, caution 40; not human-verified 3 (2 no-card + 479); badge mismatches 0 among carded species
**Files:** `scripts/experience_export/app_styles.py`, `docs/audit/2026-10-20/verdict_census/chunk_12-16_decisions.md`
**Pending:**
- 16 species newly hide culinary content incl. recipes #37, #48
- Walk 4 plan: 193 Stellaria graminea AI-agreed only (needs review); republish is Melvin's (1b)
- Batch 11b merges/relinks; batch 6 warnings

### 2026-10-21 15:54
**Snapshot** — Before census chunks 12–16 (final round: Melvin's 123 verdict decisions, 21 Oct) + curator text 402/25 + common names 391/217 + reject draft #3063; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_155418.sqlite`

### 2026-10-21 15:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261021_154755.sqlite`

### 2026-10-21 15:47
**Session ended** — Session ended from Settings page

### 2026-10-21 15:38
**Census chunks 08-11 applied: 179 verdicts (100 DEFAULT keep+verify), curator text for 13 species, 4 common names, obs 10176 (Phyllospadix scouleri) back to Review; 4 merges + GBIF check added to batch 11b**

**Built:**
- docs/audit/2026-10-20/verdict_census/chunk_08-11_decisions.md
- REPORT.md s9 batch 11b: 608<->589, 103<->531, 600<->749, 82<->200, 187 GBIF check
**Fixed:**
- 9 toxic/toxic, 25 inedible/none, 33 caution->edible, 11 caution+text, 314 edible+text, 100 DEFAULT verified
- Names: 501 Suede bolete, 390 Walnut, 172 Peppermint, 187 St John's wort (history 3380-3383)
- Obs 10176 -> needs_review with reason; off species page (632), map, walk 5 membership
- Snapshot db_20261021_153758.sqlite; edibility history 1358-1886; culinary history 3366-3383; read-back 0 mismatches
**Files:** `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/verdict_census/chunk_08-11_decisions.md`
**Pending:**
- Walk 5 stop 35 now empty (not renumbered) - re-check 10176 in Review or renumber
- 106 look-alike kept (new text not written); E-14 placeholder batch 6
- 32 species newly hide culinary content incl. recipes #121, #119, #69
- Census chunks 12-16

### 2026-10-21 15:37
**Snapshot** — Before census chunks 08–11 (Melvin's 179 verdict decisions, 21 Oct) + curator text for 13 species + 4 common-name changes + obs 10176 (Phyllospadix scouleri) back to Review; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_153758.sqlite`

### 2026-10-21 14:54
**Census chunks 04-07 applied: Melvin's 135 verdicts (+3 skipped), curator text for 8 species, 118 verdict drafts rejected with reason; merges + genus/family audit added to batch 11b**

**Built:**
- docs/audit/2026-10-20/verdict_census/chunk_04-07_decisions.md
- REPORT.md s9 batch 11b top of scope: merges 704->457, 758<->757, 708<->412; relink Collybia nuda / Conyza canadensis obs; genus/family audit (e.g. 494 Caprifoliaceae/Dipsacus)
**Fixed:**
- 1 toxic/deadly, 20 toxic/toxic, 54 inedible/none, 43 edible/none, 7 caution/none + text, 10 confirmed as-is
- Curator text history 3356-3365 byte-identical; edibility history 838-1357; snapshot db_20261021_145347.sqlite; read-back 0 mismatches
- Newly hidden culinary: 230 Aquilegia vulgaris (recipe #63), 280 Caltha palustris (recipe #66), 492 Berula erecta, 124, 503
**Files:** `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/verdict_census/chunk_04-07_decisions.md`
**Pending:**
- 494 family/genus deferred to 11b
- Cautions with no served warning: 816/821/820 Macrolepiota, 711 Marasmius (look-alike only), 106/590/603 (prep not curator-authored) - batch 6
- Census chunks 08-16

### 2026-10-21 14:53
**Snapshot** — Before census chunks 04–07 (Melvin's 135 verdict decisions, 21 Oct) + curator text for 743/494/806/816/821/820/711/783 + verdict-draft rejections with reason; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_145347.sqlite`

### 2026-10-21 14:49
**Census chunk_03 applied: Melvin's 45 verdicts, curator warnings for 761/495/832/829, 644 renamed Good King Henry, 44 verdict drafts rejected with reason**

**Built:**
- docs/audit/2026-10-20/verdict_census/chunk_03_decisions.md
**Fixed:**
- 22 -> edible/none, 14 -> inedible/none, 5 -> toxic/toxic, 4 -> caution/none with curator preparation + look-alike warnings
- 644 Blitum bonus-henricus: preferred Good King Henry, EN [Good King Henry, Allgood] ('Fat hen' dropped), history 3355
- Snapshot db_20261021_144853.sqlite; edibility history 658-837; culinary history 3347-3355; read-back 0 mismatches, text byte-identical
**Files:** `docs/audit/2026-10-20/verdict_census/chunk_03_decisions.md`
**Pending:**
- Census chunks 04-16

### 2026-10-21 14:48
**Snapshot** — Before census chunk_03 (Melvin's 45 verdict decisions, 21 Oct) + curator warnings for 761/495/832/829 + 644 common name Good King Henry + verdict-draft rejections with reason; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_144853.sqlite`

### 2026-10-21 14:32
**Census chunk_02 applied (Melvin's 45 verdicts + curator text for 793/817) + optional verdict-draft reject reason + batch 6 scope additions**

**Built:**
- reject_verdict_draft takes an optional {reason}; verdict_drafts.record_rejection_reason stores rejected_reason/rejected_at in generation_context_json (keeps existing context, refuses empty)
- REPORT.md s9 batch 6: walk stop card shows curator look_alike_warnings; map pop-up look-alike uncut
- docs/audit/2026-10-20/verdict_census/chunk_02_decisions.md
**Fixed:**
- chunk_02: 16 confirmed toxic/toxic; 3 -> toxic/deadly; 4 -> toxic/toxic; 14 -> inedible/none; 7 -> edible/none; 817 -> caution/none
- Curator text 793 edible_parts + look_alike_warnings, 817 look_alike_warnings (history 3344-3346, byte-identical)
- Drafts #3240-3251, #3253 rejected with reason; #1685 reason back-filled
- Snapshot db_20261021_143122.sqlite; edibility history 504-657; read-back 0 mismatches
**Files:** `app/api/edibility.py`, `app/services/verdict_drafts.py`, `tests/test_verdict_drafts.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/verdict_census/chunk_02_decisions.md`
**Pending:**
- 817 Meadow Mushroom: caution with no reason on the walk card until batch 6
- Draft #3252 (Amaranthus hybridus) still pending
- Census chunks 03-16

### 2026-10-21 14:31
**Snapshot** — Before census chunk_02 (Melvin's 45 verdict decisions, 21 Oct) + curator text for 793/817 + 13 verdict-draft rejections with reason + #1685 reason back-fill; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_143122.sqlite`

### 2026-10-21 14:18
**One culinary rule (culinary_allowed + CULINARY_ALLOWED_SQL delegate to safety_decision) + census chunk_01: Melvin's 45 verdict decisions applied**

**Built:**
- culinary_allowed(severity, verdict) delegates to safety_decision; CULINARY_ALLOWED_SQL = severity 'none' AND lower(trim(verdict)) in (edible, caution); severity_is_none() is the severity half (experience gates' toxicity_known_safe)
- Callers switched: recipes.py, personal_lists card, find.py (3 queries), experience verify-species, culinary.py recipe bank (x2)
- _write_verdict logs edibility_verified / edibility_verified_by history rows when they change
- docs/audit/2026-10-20/verdict_census/chunk_01_decisions.md
**Fixed:**
- chunk_01: 22 confirmed as-is + human-verified; 376 Foxglove -> toxic/deadly; 6 -> toxic/toxic; 16 -> inedible/none (B2-06; 137 Astrantia relaxed from toxic on Melvin's confirmation); draft #1685 rejected
- Snapshot db_20261021_141729.sqlite; history 382-503 (122 rows); read-back 0 mismatches
**Files:** `app/models/species.py`, `app/api/recipes.py`, `app/api/personal_lists.py`, `app/api/find.py`, `app/api/experience.py`, `app/api/culinary.py`, `app/api/edibility.py`, `scripts/experience_export/gates.py`, `tests/test_verdict_severity.py`, `tests/test_verdict_drafts.py`, `tests/test_batch5_safety_gate.py`, `docs/audit/2026-10-20/verdict_census/chunk_01_decisions.md`
**Pending:**
- Census chunks 02-16 review
- No culinary content changed by chunk_01 (all blocked before and after)

### 2026-10-21 14:17
**Snapshot** — Before census chunk_01 (Melvin's 45 verdict decisions, 21 Oct): 22 confirmed as-is, 1 → toxic/deadly, 6 → toxic/toxic, 16 → inedible/none; reject verdict draft #1685; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_141729.sqlite`

### 2026-10-21 13:28
**Batch 5 follow-up: safety_decision culinary only for edible/caution verdict + severity none; Turkey tail (Trametes versicolor 457) edible_parts + verdict edible verified human**

**Built:**
- safety_decision(): culinary_allowed only when verdict edible/caution AND severity 'none'; unknown/NULL verdict -> level unknown; inedible/other -> blocked, no label (pages show verdict badge); decision now carries 'verdict'
- Walk badges, sheet list, proximity, species grid, Export summary fall back to the verdict badge when blocked without a label; species page says 'verdict is not edible'
- Export summary takes the verdict badge from the DB, never the client
**Fixed:**
- correct_culinary_field: a previously empty field is recorded as old_value NULL, not ''
**Files:** `app/models/species.py`, `app/api/sharing.py`, `app/api/culinary.py`, `frontend/index.html`, `frontend/species.html`, `tests/test_batch5_safety_gate.py`
**Pending:**
- 13 inedible/severity-none species now hide culinary content (0 approved recipes; 9 hold only PFAF 'None known' edible_parts)
- Turkey tail: pending drafts 2953/2954/2955 untouched; no AI drafts triggered
- Other culinary_allowed() callers (recipes.py, personal_lists, find, experience) still key on severity only

### 2026-10-21 13:28
**Snapshot** — Before Turkey tail (Trametes versicolor, 457): edible_parts (curator text) + verdict edible verified human; Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_132826.sqlite`

### 2026-10-21 12:34
**Verdict census (read-only) for the Melvin + Claude review pass: 633 species (= species page count), badge diagnosis after batch 5, census CSV + 16 chunk files**

**Built:**
- docs/audit/2026-10-20/verdict_census/census_all.csv (633 rows)
- chunk_01..16.md: group 1 safety-first 273 (chunks 01-07), group 2 not human-verified 292 (08-14), group 3 human-verified 68 (15-16)
**Files:** `docs/audit/2026-10-20/verdict_census/census_all.csv`, `docs/audit/2026-10-20/verdict_census/chunk_01.md … chunk_16.md`
**Pending:**
- Badge mismatches (data, not display): 55 verdict NULL + severity unknown; 37 inedible + severity toxic (B2-06); 2 obs names with no species card (Collybia nuda, Conyza canadensis)
- Melvin + Claude review pass over the chunks

### 2026-10-21 12:28
**Batch 5 (REPORT s9): B2-01/B2-04 + P1 shared safety gate + B2-09 (server re-check for PDF and walk Export summary)**

**Built:**
- safety_decision() in app/models/species.py: the one rule (culinary only when severity=='none' and verdict not toxic) + labels ☠ deadly / ☠ toxic / ⚠ toxicity unknown / ⚠ caution + curator-authored caution warning
- app/services/safety_gate.py: safety_for_species / safety_by_names (name_key lookup, missing = unknown)
- 'safety' served by /api/culinary/{name}, /api/species/{name}/profile, /api/species/ list rows (no warning)
- frontend/static/js/safety-gate.js: only reader of the served decision; fails closed on missing; in sw.js APP_SHELL, CACHE_VERSION v8
- Map pop-up, walk panel/stop cards/repeat lines/sheet list/proximity, species page + grid badge, Lists, browser print read SafetyGate
- PDF and walk Export summary re-ask the DB by name (B2-09); client severity/culinary text ignored
**Fixed:**
- B2-01: map pop-up no edible parts for deadly/toxic/unknown; label shown
- B2-04: Lists + browser print drop culinary fields and recipes for blocked species; label shown
- species page safety box no longer fails open on missing severity
- species page taste notes re-render after draft approval now gated
- deadly label is '☠ deadly' (was '☠ DEADLY' in walk flow)
**Files:** `app/models/species.py`, `app/services/safety_gate.py`, `app/api/culinary.py`, `app/api/lists_pdf.py`, `app/templates/print_pdf.html`, `app/api/sharing.py`, `frontend/static/js/safety-gate.js`, `frontend/static/sw.js`, `frontend/index.html`, `frontend/species.html`, `frontend/lists.html`, `frontend/print.html`, `tests/test_batch5_safety_gate.py`, `tests/test_batch4_a02_d1_01.py`
**Pending:**
- Melvin browser checks for batch 5 (map pin Conium/Aconitum; walk panel; species page + grid; Lists + browser print + PDF with Conium/Sambucus/Allium; Export summary)
- Phone: /api/species/*/profile is cached cache-first 7 days; old cached profiles show '⚠ toxicity unknown' until Settings → Refresh species cache
- Experience page labels not changed (own gates.py wording)

### 2026-10-21 10:23
**Batch 4 (REPORT s9): A-02 secrets out of /api/settings + guests refused; D1-01 PDF autoescape + restricted WeasyPrint fetching**

**Built:**
- settings registry 'secret' flag + is_secret_setting() predicate; GET /api/settings returns is_set only for secrets (current/default/db_raw null); PUT/DELETE never echo a secret
- Router-level curator-only dependency on every /api/settings route (get_identity: guest host or guest/participant token -> 403)
- lists_pdf: Jinja autoescape=True; |safe only on season_str and mdlite (justified in template comments); _mdlite heading escaped
- WeasyPrint url_fetcher: data: URIs + files under frontend/static, media, photos, uploads (resolved, no ../ escape); everything else refused and logged
**Fixed:**
- A-02: DeepSeek key no longer readable via /api/settings
- D1-01: request HTML no longer live in PDF; local files outside app media roots no longer embeddable
**Files:** `app/services/settings_service.py`, `app/api/settings.py`, `app/api/lists_pdf.py`, `app/templates/print_pdf.html`, `tests/test_batch4_a02_d1_01.py`
**Pending:**
- Melvin live check: Settings page loads, AI key shows as set, API dashboard works; a normal PDF in all 3 styles looks the same (botanical corners present)
- Thunderforest key still in /api/map/config by design (tile keys are browser-visible)

### 2026-10-21 10:13
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261021_101327.sqlite`

### 2026-10-21 10:13
**Session ended** — Session ended from Settings page

### 2026-10-21 09:56
**Amanita rubescens (Blusher, 467): Melvin's preparation + look-alike warnings written verbatim as curator text; caution verdict confirmed by human**

**Fixed:**
- Snapshot db_20261021_095529 (no commit)
- preparation_warnings + look_alike_warnings via PATCH /api/culinary/{name}/field (history 3341, 3342, changed_by human, old_value NULL); byte-identical read-back; is_curator_authored True
- Verdict via edibility._write_verdict: caution, edibility_verified=1, verified_by human, history 380 with Melvin's note; severity none unchanged (severity_for_verdict); no AI-draft trigger
- Experience gates: badge 'Edible with caution', rule 8 caution reason shown, look-alike shown, recipe_allowed True - no recipes stored for 467
**Files:** `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Drafts 2939 (taste) / 2940 (medicinal) left pending as asked
- Melvin browser check: Blusher species page shows both warnings; Edibility Review no longer lists it as unverified
- Do not start batch 4; End Session commits

### 2026-10-21 09:55
**Snapshot** — Before curator-authored safety text + verdict confirmation for Amanita rubescens (467); Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_095529.sqlite`

### 2026-10-21 09:45
**Placeholder refusal markers - class fixed: only 'insufficient' collides with real uses (PFAF Verbena 'insufficient lactation', Vinca 'insufficient blood supply'); replaced with refusal phrases; Verbena re-draft stored (draft 3544)**

**Built:**
- test_placeholder_markers_do_not_collide_with_real_uses
**Fixed:**
- ai_placeholder: bare 'insufficient' -> 'insufficient information/data/source/detail/context'; other markers unchanged (no collisions in 384 PFAF pages + 1,827 other source texts); 0 decisions changed over 3,472 stored drafts
- Verbena officinalis medicinal re-draft (job 66, 1 DeepSeek call): draft 3544 pending, opening contains 'insufficient lactation'
**Files:** `app/services/ai_placeholder.py`, `tests/test_pfaf_fallback_deepseek.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Amanita rubescens recipe draft was discarded as a placeholder earlier (marker unknown, text not kept) - retry only with Melvin's OK
- Melvin: review the 93 pending medicinal drafts (incl. Verbena 3544); Oxalis grandis 3493 refused as-is
- Do not start batch 4; End Session commits

### 2026-10-21 09:39
**Verbena officinalis medicinal re-draft retried (job 65, 1 DeepSeek call) - discarded again; cause: placeholder rule's bare 'insufficient' marker matches PFAF's 'insufficient lactation'**

**Built:**
- ai_placeholder_reason() - names the placeholder rule + marker; _section_ai_draft logs it with the opening sentence on discard (decisions unchanged on 3,472 stored drafts)
**Files:** `app/services/ai_placeholder.py`, `app/services/enrichment.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Melvin: narrow the 'insufficient' refusal marker to 'insufficient information/data/source/detail/context' (0 stored decisions change; exposes Verbena officinalis + Vinca minor), then retry Verbena (1 DeepSeek call)
- Do not start batch 4; End Session commits

### 2026-10-21 09:28
**Live 'no uses' cleanup + 93 DeepSeek medicinal re-drafts (Melvin: go live exactly as rehearsed)**

**Built:**
- POST /api/drafts/redraft-medicinal - curator-only job (job_queue + progress, enrich_gate: refused during ingest/scan, waits for ingest + holds the enrichment slot per species), normal _section_ai_draft path, toxic excluded, results file logs/redraft_medicinal_jq<id>.json
**Fixed:**
- Live: snapshot db_20261021_092222 (no commit); 68 medicinal_notes edits (31 PFAF fill, 9 cleared, 8 toxic cleared, 20 claim sentence removed), history 3273-3340, read-back 0 mismatches; 106 false 'no uses' drafts invalidated; 0 claims left; second run no-op
- Re-draft job 64: 92 pending DeepSeek drafts (PFAF context), 1 failed (Verbena officinalis discarded as placeholder); 1 of 92 still flagged false (Oxalis grandis 3493, borderline); none approved, no field written
**Files:** `app/api/culinary.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`, `docs/audit/2026-10-20/redraft_plan_2026-10-21.json`
**Pending:**
- Melvin: review the 92 new medicinal drafts in Review (each replaces PFAF text on approval); Oxalis grandis 3493 is refused as-is (422) - edit or reject
- Verbena officinalis: re-draft discarded by the placeholder rule - retry with Repopulate (1 DeepSeek call) or check is_ai_placeholder
- Borderline 'does not record specific ... medicinal' sentences in 14 fields - Melvin decides
- Do not start batch 4; End Session commits

### 2026-10-21 09:22
**Snapshot** — Before the live 'no uses' cleanup (68 medicinal_notes edits, 106 draft invalidations, 93 DeepSeek re-drafts); Settings snapshot routine without the git commit — Melvin: End Session commits
DB: `snapshots/db_20261021_092222.sqlite`

### 2026-10-21 09:18
**'No uses' check fixed at the root (shared predicate, anywhere in the text) + combined dry run: 68 fields, 106 drafts, 93 DeepSeek re-drafts counted - rehearsed 0 mismatches, stopped before live write / DeepSeek**

**Built:**
- ai_placeholder: no_medicinal_uses_claim_spans / has_no_medicinal_uses_claim / is_only_no_medicinal_uses_claim / strip_no_medicinal_uses_claims - claim anywhere, narrow negations excluded (part-scoped, further/additional, concessive hedge)
- pfaf_fallback: 'strip' outcome (claim sentence removed, rest verbatim, system:clear_false_default, ai-approved flag kept); false-claim check reads the claim anywhere
- Review / species page: server flag no_uses_only replaces the two JS _MEDICINAL_SUPPRESS regex copies
- scripts/pfaf_fallback_refill.py: combined fields + drafts run; --redraft gated (DeepSeek only with it)
**Fixed:**
- Root cause: is_no_medicinal_uses_statement read the first sentence only - claims after the disclaimer/heading/culinary text were invisible
- PFAF parser: Medicinal Uses opening with 'None known.' + commentary = no data (D3) - only Alchemilla mollis; never written live
**Files:** `app/services/ai_placeholder.py`, `app/services/pfaf_fallback.py`, `app/integrations/pfaf.py`, `app/api/culinary.py`, `frontend/review.html`, `frontend/species.html`, `scripts/pfaf_fallback_refill.py`, `tests/test_pfaf_fallback_deepseek.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`, `docs/audit/2026-10-20/cleanup_dryrun_2026-10-21.md`
**Pending:**
- Melvin OK for live: 68 fields (31 PFAF fill, 9 cleared, 8 toxic cleared, 20 claim removed) + 106 drafts invalidated, then 93 DeepSeek re-drafts (--apply --redraft); snapshot first, no commit
- Melvin decides: hedged meta 'does not record/contain specific ... medicinal' sentences left in 14 fields (borderline list in REPORT)
- Melvin browser checks: Review red flag + 422 on a false draft; true no-uses drafts still hidden; species page PFAF chip
- Do not start batch 4

### 2026-10-21 07:51
**4b live PFAF refill (Melvin 'Go on 4b'): 443 medicinal_notes rows written, read-back 0 mismatches; step 2 false no-uses drafts listed - stopped before any DeepSeek call**

**Fixed:**
- Live refill: 200 PFAF fill (pfaf_fallback), 184 cleared + 59 toxic cleared (system:clear_false_default); history ids 2830-3272; snapshot db_20261021_074733 (backup function, no git commit)
- Read-back: script 443/443 0 mismatches; SQL read-back 2830-3272 0 mismatches; second run writes nothing; 'No known traditional medicinal uses' 346 -> 0
**Files:** `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- NOT MET: 55 AI-approved medicinal_notes still contain 'no traditional medicinal uses' after a disclaimer/heading (43) or after content (12) - opening-only predicate; same rule would give 40 PFAF fill / 8 clear / 7 toxic clear - Melvin decides
- Step 2 awaiting OK: invalidate 45 false no-uses pending drafts (8 toxic) + re-draft 37 non-toxic species via _section_ai_draft = 37 DeepSeek calls
- 41 more pending drafts carry the claim later in the text (not refused by the approve guard, hidden in Review) - extend is_no_medicinal_uses_statement past the disclaimer? Melvin decides
- Melvin browser checks: species page PFAF chip (e.g. Wood Avens, Great Mullein); Review false-draft warning + 422; print/PDF without the PFAF Folklore section
- Do not start batch 4; End Session commits (snapshot taken without commit)

### 2026-10-21 07:47
**Snapshot** — Before 4b live PFAF refill (443 medicinal_notes rows; Settings snapshot routine without the git commit — Melvin: End Session commits)
DB: `snapshots/db_20261021_074733.sqlite`

### 2026-10-21 05:36
**Melvin's answers A-C (21 Oct): PFAF Medicinal Uses into the medicinal draft context + false no-uses approve guard; print/PDF withhold PFAF fallback text; refill rule changes - new dry run 443 rows, rehearsed 0 mismatches, stopped before writing live**

**Built:**
- A: stored_pfaf_medicinal_text() -> pfaf_medicinal_uses in the medicinal_notes context (enrichment, Repopulate, Regenerate); None known passes nothing
- A: is_false_no_uses_claim() - unedited 'no traditional medicinal uses' draft refused on approve (422 + reason) when PFAF lists uses; Review shows such drafts with the reason
- B: print.html / lists.html (_printCulinary) and lists_pdf._flatten_species drop fields in profile.pfaf_fallback_fields (shared is_pfaf_fallback) - print_pdf.html never receives them
- C: pending AI draft no longer blocks the PFAF fill; toxic/inedible default -> cleared, no PFAF text; clears write changed_by='system:clear_false_default'
- refill script: outcome counts + the 13 human-approved AI no-uses texts listed by name
**Fixed:**
- Root cause: enrich_species never passed PFAF Medicinal Uses to the drafter (45 pending + 8 approved false 'no uses' drafts where PFAF lists uses)
**Files:** `app/services/pfaf_fallback.py`, `app/integrations/deepseek_draft.py`, `app/integrations/claude_draft.py`, `app/services/enrichment.py`, `app/api/culinary.py`, `app/api/lists_pdf.py`, `frontend/review.html`, `frontend/print.html`, `frontend/lists.html`, `scripts/pfaf_fallback_refill.py`, `tests/test_pfaf_fallback_deepseek.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`, `docs/audit/2026-10-20/refill_dryrun_2026-10-21.md`
**Pending:**
- Melvin: OK for live 4b - dry run 443 rows: 200 PFAF fill, 184 cleared, 59 toxic cleared, 0 untouched; Settings snapshot first, then apply + read-back by id
- Melvin: print gate uses is_pfaf_fallback, not is_curator_authored (that would withhold all AI-approved medicinal text and historyless PFAF fields from handouts) - confirm
- The '13 approved on 2 June' were approved 27 May (6), 1 Jun (6), 2 Jun (1)
- Melvin browser checks: Review shows false no-uses drafts in red and Approve gives the 422 reason; print/PDF of a PFAF-filled species has no Folklore section; species chip after 4b
- Do not start batch 4

### 2026-10-21 05:21
**Fix before batch 4 (Melvin D1-D5, 21 Oct): every AI call site on DeepSeek + labelled PFAF fallback replacing A5 - steps 1-3 done, step 4 stopped at the dry run (no DB writes)**

**Built:**
- deepseek_draft.ai_backend() - the one AI backend choice; ai_complete() + generate_deepseek_drafts() used by enrichment, Repopulate, Regenerate, chat, About summary, recipe regenerate, encounter extraction
- app/services/pfaf_fallback.py - only writer of PFAF text into an AI field: medicinal_notes <- PFAF Medicinal Uses (changed_by='pfaf_fallback'), retired no-uses default counts as empty (filled or cleared, 'system:undo_A5'); guards: empty, not human-locked, not toxic/inedible, no pending AI text
- PFAF chip 'PFAF text - replace with your own' on species page (Folklore & Historical Uses) and Review AI-draft cards, from pfaf_fallback_fields in profile/queue payloads
- scripts/pfaf_fallback_refill.py - dry run (read-only) / --apply with read-back by id
- tests/test_pfaf_fallback_deepseek.py (12); suite 148/148
**Fixed:**
- D1: Anthropic removed from claude_draft (generator), chat, about, recipes, encounter_extract, culinary Regenerate, enrichment fallbacks, api_dashboard probe; Ollama paths + ollama_draft.py removed; settings enrichment_backend/anthropic_model/ollama_model removed; Anthropic UI text removed (review, settings, about)
- A5: _ensure_medicinal_default + scripts/backfill_medicinal_default.py removed - no path writes 'No known traditional medicinal uses'
- scripts/enrich.py loads DB settings (batch-3b script failure read the old 'anthropic' default)
- CHANGELOG: two 'Anthropic credit empty / top up' pending notes removed
**Files:** `app/integrations/deepseek_draft.py`, `app/integrations/claude_draft.py`, `app/integrations/ollama_draft.py (deleted)`, `app/integrations/encounter_extract.py`, `app/services/pfaf_fallback.py`, `app/services/enrichment.py`, `app/services/ai_placeholder.py`, `app/services/settings_service.py`, `app/services/api_dashboard.py`, `app/models/species.py`, `app/models/encounter.py`, `app/api/culinary.py`, `app/api/chat.py`, `app/api/about.py`, `app/api/recipes.py`, `app/api/encounters.py`, `app/config.py`, `frontend/species.html`, `frontend/review.html`, `frontend/settings.html`, `frontend/scan.html`, `frontend/about.html`, `scripts/enrich.py`, `scripts/pfaf_fallback_refill.py`, `scripts/backfill_medicinal_default.py (deleted)`, `tests/test_pfaf_fallback_deepseek.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`, `docs/audit/2026-10-20/refill_dryrun_2026-10-21.md`
**Pending:**
- Melvin: OK for step 4b refill (dry run 399 rows: 67 -> PFAF text, 273 defaults cleared, 59 toxic untouched; rehearsed on a scratch copy, 0 mismatches) - Settings snapshot first
- Melvin decides: does a pending AI draft count as 'AI text available'? (as built yes - 215 species stay empty, 133 of them have PFAF text)
- Melvin decides: clear the default on the 59 toxic/inedible species? (as built untouched)
- Melvin browser checks: species page chip on a filled species (e.g. Filipendula vulgaris after 4b); Review draft card over PFAF text; species chat answers; About 'Regenerate with AI'; Settings AI group shows DeepSeek only
- Finding: enrich_species never passes pfaf_result to the AI drafter - PFAF Medicinal Uses text never reaches DeepSeek (medicinal_folklore drafts never generated; medicinal drafts say 'no uses' where PFAF lists them)
- Finding: print.html / lists.html print medicinal_notes without the chip
- Do not start batch 4

### 2026-10-21 04:50
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261021_045041.sqlite`

### 2026-10-21 04:50
**Session ended** — Session ended from Settings page

### 2026-10-21 04:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261021_044736.sqlite`

### 2026-10-21 04:47
**Session ended** — Session ended from Settings page

### 2026-10-21 04:44
**Fix pass batch 3b: verdict-draft approve path (one decision per species, writes through the shared verdict writer, refused when the species changed after drafting, never in Approve all) + verdict sweep from stored sources (212 drafts: unknown 175, caution 20, edible 13, toxic 4; 175 lack enough evidence; walk species first). Melvin's 21 Oct decisions: 15957 -> card 530, draft 2335 rejected, 848/849 enriched (21453/21454 -> fungi), 31 P1 person_animal rows rejected.**

**Built:**
- edibility._write_verdict(): one verdict writer for PATCH /api/edibility/status and the verdict-draft approve
- GET /api/edibility/verdict-drafts (walk species first, then confirmed pins; sources with exact quotes; changed-since-draft flag), POST .../{id}/approve (409 when changed after drafting, nothing written), POST .../{id}/reject
- app/services/verdict_drafts.py: proposal rules (stored sources only, PFAF negation-aware poison wording, genus/page-name guard, unknown when thin or conflicting, never deadly from text, never lowers severity) + changes_since()
- scripts/verdict_sweep_drafts.py: dry run default, idempotent, supersedes no-data FAO/MO lookup drafts, read-back by id
- review.html: Edibility Review -> Verdict drafts section (one card per species, verdict + severity selects, note, Approve with confirm, Reject)
- Verdict (edibility_status) drafts removed from AI Draft Review and the species page pending-drafts list
- tests/test_verdict_drafts.py (14)
**Fixed:**
- B3-04: edibility drafts now have an approve path; 18 'no source data' FAO/MO lookups superseded (invalidated)
- Sweep: 212 drafts ids 3240-3451 (snapshot db_20261021_044236 first); read-back 0 mismatches; no species verdict/severity/history changed
- Obs 15957 species_id 286 -> 530 (edit 21104); draft 2335 rejected
- 848/849 enriched via scan._enrich_new_species_card (848 Plantae + PFAF; 849 Fungi); 21453/21454 -> fungi (edits 21105/21106)
- 31 P1 person_animal pre-filter rows rejected (process 195; files kept by the provenance veto)
- A5 false default on 848 undone (medicinal_notes NULL, history 2829 system:undo_A5)
**Files:** `app/api/edibility.py`, `app/api/culinary.py`, `app/services/verdict_drafts.py`, `frontend/review.html`, `scripts/verdict_sweep_drafts.py`, `tests/test_verdict_drafts.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Melvin: reject the 347 Takeout person_animal rows in Review (Status Pending, Pre-filter person_animal, 96 per page, Select all, Reject; deletes the uploads/ copies) — mount DIGIERA first to be sure the originals are there; decide the 3 'keep' rows 21509/21949/22043
- Melvin browser checks: Verdict drafts section (order, quotes, approve/reject, severity select, stale warning + 409); AI Draft Review no longer lists verdict drafts
- Melvin: work the 212 verdict drafts (13 walk species first); reject the junk-card drafts (Betacoronavirus, Maniola jurtina, Arachnocampa, Noctiluca)
- A5 bug: _ensure_medicinal_default ignores PFAF medicinal text -> false 'No known traditional medicinal uses' when AI drafting fails; other affected species not counted
- Not in 3b scope: 394 species with a verdict not verified by a human (edible 239, caution 85, inedible 43, toxic 27) - second sweep if wanted
- Backlog (Melvin 21 Oct): 1,169 'no plant signal' pre-filter rows; ~650 unprocessed 2013 Takeout files
- Next: 1b (Melvin), then batch 4

### 2026-10-21 04:42
**Snapshot** — Before batch 3b verdict sweep: 212 verdict drafts (verdict_sweep), 18 superseded fungi lookup drafts invalidated
DB: `snapshots/db_20261021_044236.sqlite`

### 2026-10-21 04:27
**Snapshot** — Before batch 3b decisions: obs 15957 -> card 530, reject draft 2335, enrich 848/849 (+ 21453/21454 fungi), reject 31 P1 person_animal pre-filter rows
DB: `snapshots/db_20261021_042731.sqlite`

### 2026-10-20 22:28
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261020_222853.sqlite`

### 2026-10-20 22:28
**Session ended** — Session ended from Settings page

### 2026-10-20 22:17
**Fix pass batch 14 part 2: Second Opinion GBIF-only names score-less and last (Melvin's decision); E-04 End-session UTC date parse; B1-08 confirmed species first with its own score (code + 666-row backfill); C-03 confirmed names always get a linked species row (code + 5 rows); C-04 cause confirmed by reproduction, approve promotes only recognised names (code + obs 21585); D1-03 PDF disclaimer false sentence removed; D2-01 repeat-line badge colour; report on the 1,667 pending rows (pre-filter rejects, 2013 batch).**

**Built:**
- reidentify.merge_second_opinion_candidates: GBIF-only = confidence None + name_match_only, sorted after every photo-backed candidate; review.html shows 'name match only', sends confidence null
- dev.git_commit_time_utc(): git %cI -> naive UTC for the encounter export 'since'
- species_link.confirmed_candidate_first() + candidate_own_score(): after a human species change the chosen species is candidates[0] with its best stored image score; top_score follows; curator entry with score None when no API listed it
- species_link.resolve_species_id: exact -> name_key -> registered synonym; ensure_species_row() on every approve path (bare row, severity unknown)
- species_link.promotable_suggestion(): approve (single 409 / bulk skip) promotes species_suggested only if a stored candidate, a species card in use, or a registered synonym; hand-set species clears species_suggested
- review.html: card names species_primary, % only when candidates[0] is that species; _rerenderCard after Second Opinion / Look up / Request ID picks; per-card name-save lock before Approve; server reason shown on failure
- map.py: pin confidence only when candidates[0] is the pin's species
- sharing._toxicity_warning_colors(): one badge colour rule for full block and Also-here line
- scripts/backfill_confirmed_candidate_first.py, scripts/fix_c03_c04_rows.py (dry run default, read-back by id)
- Tests: test_b1_08_confirmed_candidate.py (9), test_species_link_c03_c04.py (9), test_batch14_e04_d1_03_d2_01.py (6), test_second_opinion_merge.py updated (9); fixture b1_08_obs24353.json
**Fixed:**
- Second Opinion obs 24149: Gentiana verna #1, G. vernayi last with no score
- E-04: End session no longer falls back to exporting all encounters on '-0' dates; compares UTC to UTC
- B1-08 data: 666 confirmed rows fixed (snapshot db_20261020_221253 first); observation_edits 20167-21103; read-back 0 mismatches; 24353 now L. nemorum 0.4613
- C-03 data: 21950/22074 -> species 342 (synonym), 21382 -> new 848 Filipendula vulgaris, 21453/21454 -> new 849 Ganoderma applanatum; edits 20161-20165
- C-04 data: 21585 'norway spruce' -> 'Picea abies' (edit 20166); junk species 685 orphan-marked
- C-04 cause CONFIRMED: stale-read approve promoted the typed Look-up text (reproduced on last committed code)
- Threshold recheck skips curator entries; audit check 4 ignores curator entries
- D1-03: removed 'Human-created and/or reviewed content is indicated where shown.' from print_pdf.html
- D2-01: '⚠ toxicity unknown' repeat-line badge amber
**Files:** `app/api/reidentify.py`, `app/api/dev.py`, `app/api/observations.py`, `app/api/bulk_actions.py`, `app/api/trust.py`, `app/api/map.py`, `app/api/scan.py`, `app/api/audit.py`, `app/api/sharing.py`, `app/services/species_link.py`, `app/services/observation_service.py`, `app/templates/print_pdf.html`, `frontend/review.html`, `scripts/backfill_confirmed_candidate_first.py`, `scripts/fix_c03_c04_rows.py`, `tests/test_second_opinion_merge.py`, `tests/test_b1_08_confirmed_candidate.py`, `tests/test_species_link_c03_c04.py`, `tests/test_batch14_e04_d1_03_d2_01.py`, `tests/fixtures/b1_08_obs24353.json`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Melvin browser checks (REPORT section 9, batch 14 part 2 list): Second Opinion 24149 'name match only' row last; card re-render after a pick; 24353 card 46.1% + Also line; Approve right after a Look-up pick; typed common name -> 409 toast; 24353 pin 46%; walk-4 Export summary amber repeat badge; PDF disclaimer; End session encounter export since=UTC
- Melvin decides: obs 15957 (Taraxacum sect. Taraxacum linked to 286 T. officinale; own card 530) relink or rename
- Melvin: enrich new bare species 848 Filipendula vulgaris and 849 Ganoderma applanatum; tap Fungi on 21453/21454 if wanted; reject AI draft 2335 (junk card 685)
- Melvin decides: triage of the 1,667 pre-filter rejects (person_animal 381 first; no_plant_signal 1,169 may hide plants -> unlock = PlantNet quota ~3 days); finish 2013 batch (~650 files never processed: Rescan -> Filter -> Identify with DIGIERA mounted)
- Follow-up (not done): species rename cascade does not rename candidate entries -> renamed species' cards/pins show no %; orphan GC misses a name card when species_primary and species_id disagree
- Next: 1b (Melvin), then 3b

### 2026-10-20 22:12
**Snapshot** — Before batch 14 part 2 data: C-03 link 5 obs (2 bare species rows), C-04 obs 21585 -> Picea abies, B1-08 confirmed species first on 667 rows
DB: `snapshots/db_20261020_221253.sqlite`

### 2026-10-20 21:43
**Fix pass batch 14 (part, moved after batch 3): E-03 Second Opinion 500 on GBIF-only names fixed at the root (one candidate shape for every source, pure merge function); Review nav badge now equals the Review page's default queue via one shared definition.**

**Built:**
- reidentify.py: _sop_entry() — one Second Opinion candidate shape for PlantNet/iNaturalist/GBIF; merge_second_opinion_candidates() pure function used by the endpoint
- observation_counts.REVIEW_QUEUE + review_queue_count(): one definition used by the needs_review list query, stats by_status.needs_review and new stats.review_queue_count
- site-header.js Review badge reads review_queue_count (links /review?status=needs_review)
- tests/test_second_opinion_merge.py (6, recorded fixture tests/fixtures/second_opinion_recorded.json), tests/test_review_queue_count.py (4)
**Fixed:**
- E-03: KeyError 'non_european' -> 500 when GBIF adds a name; live obs 24149 now 200 with GBIF-only Gentiana vernayi included
- Review badge 2,056 (pending+needs_review) -> 389 = the queue's 389
**Files:** `app/api/reidentify.py`, `app/services/observation_counts.py`, `app/api/observations.py`, `frontend/static/js/site-header.js`, `tests/test_second_opinion_merge.py`, `tests/test_review_queue_count.py`, `tests/fixtures/second_opinion_recorded.json`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Melvin browser checks: Second Opinion on obs 24149 renders (GBIF-only row shown); nav Review badge shows the same number as the Review page's Needs review queue
- Decide: GBIF-only names (fixed 0.50) outrank image candidates in Second Opinion (24149: Gentiana vernayi #1) — sort them after image-backed candidates?
- Batch 14 still open: E-04, B1-08, C-03, C-04, D1-03, D2-01
- Next: 1b (Melvin), then 3b

### 2026-10-20 21:32
**Fix pass batch 3 (audit B2-02 + B2-05 data): saving a verdict sets toxicity_severity through one rule with a history row; 'unknown' = never assessed and fails closed; fail-open read sites closed; 155/688/745 -> toxic, drafts 2920/2921 rejected; 230 never-assessed species -> severity unknown. Decisions recorded: species merges allowed via a re-keying merge (CLAUDE.md rule updated when 11b lands); batch 14 moved to run straight after batch 3.**

**Built:**
- severity_for_verdict() in app/models/species.py — the only verdict->severity rule (toxic -> toxic/keeps deadly; edible/caution -> none, refused over a toxic/deadly severity unless explicit; inedible unchanged; unknown -> unknown if it was none; explicit severity must fit the verdict)
- PATCH /api/edibility/status (+ optional toxicity_severity, severity in loud-fail read-back and response), /bulk-status and the bracken safety constant all use it; species_edibility_history row per severity change
- New species default toxicity_severity='unknown' (ORM default)
- Fail-closed: species page culinary/taste/recipe gate (severity must be 'none') + amber 'toxicity not yet assessed' box; print_pdf.html == 'none'; lists_pdf.py missing severity -> 'unknown'
- scripts/backfill_never_assessed_severity.py (dry run default, read-back by id)
- tests/test_verdict_severity.py — 18 tests
**Fixed:**
- B2-02: verdict writes now set toxicity_severity; never-assessed no longer reads as safe
- B2-05 data: Amanita muscaria 155, Heracleum mantegazzianum 688, Hedera helix 745 -> toxic/toxic, verified human (history 144-149); drafts 2920, 2921 rejected
- 230 species severity none -> unknown (history 150-379, changed_by system:never_assessed); snapshot db_20261020_213039 first; read-back 0 mismatches
**Files:** `app/models/species.py`, `app/api/edibility.py`, `app/services/enrichment.py`, `frontend/species.html`, `app/templates/print_pdf.html`, `app/api/lists_pdf.py`, `scripts/backfill_never_assessed_severity.py`, `tests/test_verdict_severity.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Melvin browser checks: ☠ on 155/688/745 pins' walk badges and species pages; a never-assessed species page shows the amber box and no culinary/taste/recipe; walk cards show 'toxicity unknown' for never-assessed species; Edibility review set-verdict still works
- Map pop-up and Lists/browser print still show edible parts for toxic/unknown species until batch 5
- Walk 4: 8 species now badge 'Toxicity unknown' on the experience page; Heracleum sibiricum loses its Carrot-family badge to the unknown badge (gates check unknown first) — decide in 3b/1b
- Next: batch 1b (Melvin), then batch 14 (moved), then 3b

### 2026-10-20 21:30
**Snapshot** — Before batch 3 data: 155/688/745 -> toxic, reject drafts 2920/2921, 232 never-assessed severities -> unknown
DB: `snapshots/db_20261020_213039.sqlite`

### 2026-10-20 21:21
**Fix pass batch 2 (audit E-01/E-02): WAL-safe DB snapshot and restore through the SQLite backup API; new fix-order items from Melvin (20 Oct evening) placed in REPORT.md section 9.**

**Built:**
- app/services/db_snapshot.py: backup_to_file (backup API -> .partial -> journal_mode=DELETE -> quick_check -> rename; side files cleaned), restore_from_file (integrity_check, backup API into the live connection, WAL kept, checkpoint, quick_check), path/hash validators
- POST /api/dev/snapshot uses the backup API in a thread; failure raises before CHANGELOG/commit; response has db_quick_check
- POST /api/dev/restore: only snapshots/db_*.sqlite + hex hashes; integrity check; 409 while a job is running; pre-restore snapshot db_<ts>_prerestore.sqlite; backup-API restore; settings cache reload
- tests/test_db_snapshot.py: 13 tests on throw-away WAL DBs (old bugs reproduced; snapshot holds WAL rows; restore sticks for open connections and after reopen; corrupt/non-DB refused; validators)
**Fixed:**
- E-01: snapshots no longer miss rows still in the WAL
- E-02: restore can no longer be undone by WAL replay; db_path/commit_hash no longer free strings
- CLAUDE.md snapshot/restore and mtime notes updated; manual .backup copy no longer needed (STATUS.md, REPORT section 9 rules)
**Files:** `app/services/db_snapshot.py`, `app/api/dev.py`, `tests/test_db_snapshot.py`, `CLAUDE.md`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Live verification: snapshots db_20261020_211829 + _211916 taken through the new path (integrity ok, counts equal live); restore NOT run live — Melvin may test it on purpose later (it takes a pre-restore snapshot first)
- New in section 9 (not implemented): 3b verdict sweep; batch 5 + deadly/toxic label everywhere; 11b duplicate-species merge (clashes with the 'do not attempt merges' rule — Melvin decides) + GBIF synonym sweep + common-name backfill; 14 + E-03 (obs 24149) + Review badge count 2,080 vs 386; 15b walk batch (Edit-walk tap/lasso, Loop/One-way label, Start here on every stop, route-line zoom/drag bug repro, GPS recording removal)
- Batch 1b (Melvin) still open; next code batch: 3

### 2026-10-20 21:19
**Snapshot** — Batch 2: backup-API snapshot re-check (no side files)
DB: `snapshots/db_20261020_211916.sqlite`

### 2026-10-20 21:18
**Snapshot** — Batch 2: first snapshot through the SQLite backup API (verification)
DB: `snapshots/db_20261020_211829.sqlite`

### 2026-10-20 21:14
**Snapshot** — Before batch 2 (E-01/E-02 WAL-safe snapshot + restore)
DB: `snapshots/db_20261020_211459.sqlite`

### 2026-10-20 21:11
**Fix pass batch 1 (audit D3-01, caution species on the experience page): caution preparation warnings queued as curator-review drafts (approval = curator-authored); experience gate withholds a caution species' recipes until it has an approved warning; B3-02 old_value fix. Decisions from Melvin (20 Oct evening) recorded in REPORT.md section 0: (1) the 19 unknown-origin caution warnings join the 36 PFAF ones in the review queue, the 6 E-14 marker rows are surfaced there for confirmation; (2) B5-01/B5-02 close both (guests: confirmed plant photos only; encounters/voice notes curator-only) — batch 8; (3) A-03: the batch-7 share-link secret also gates LAN access, only localhost without it — batch 7; (4) in-app GPS walk recording can be removed — batch 15b, before the index.html split.**

**Built:**
- Curator-review warning drafts: preparation_warnings is approvable (CURATOR_DRAFT_FIELDS); approve as-is or rewrite writes culinary_info + history changed_by='human' with the real old_value; 409 if the field was hand-edited since queueing, 422 on empty text
- Shared predicate is_curator_authored() in app/models/species.py, used by gates.human_authored and the approve path
- Review queue: origin note per warning draft (PFAF / origin unknown / confirm your text), 'in the field now — replaced' box, warning drafts excluded from Approve all / Approve selected; queue API returns current_text
- Experience gates rule 8: caution species show the approved warning (⚠ Caution box); without one the badge stays but all recipes are withheld; plan prints a 'Caution species' section (kept / withheld) and --plan-json gains 'caution'; pre-write cross-check
- scripts/import_caution_warning_drafts.py (dry run default, idempotent)
- tests/test_experience_gates.py — 21 tests for rule 8, the predicate and the import classifier
**Fixed:**
- B3-02: AI-draft approval history now records the real old_value instead of NULL
- AI regenerate (culinary.py + enrichment.py) no longer invalidates pending warning drafts
- Data: 61 pending preparation_warnings drafts, ids 3178-3238 (36 pfaf, 19 unknown_origin, 6 marker_confirm), after Settings snapshot db_20261020_210754 (commit db9b955e) + snapshots/manual_20261020_210754.db; read back by id, 0 mismatches; no culinary_info or history rows changed
**Files:** `app/models/species.py`, `app/api/culinary.py`, `app/services/enrichment.py`, `frontend/review.html`, `frontend/species.html`, `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `scripts/import_caution_warning_drafts.py`, `tests/test_experience_gates.py`, `docs/audit/2026-10-20/REPORT.md`, `docs/audit/2026-10-20/STATUS.md`
**Pending:**
- Batch 1b (Melvin): review the walk-4 warning drafts (7 PFAF, 2 marker confirmations, 1 unknown-origin: Geranium pyrenaicum), verify Rosa dumalis, then republish Rümmelsbühl foray (id 4)
- Melvin browser checks: review queue shows the 61 warning drafts with origin notes; Approve all skips them; approve one and see it on the species page
- Unknown-origin texts: 16 of 19 read as edible-use text, not warnings (10 cut at 100 chars) — rewrite or reject rather than approve as-is
- Walk 4 plan now: Sambucus nigra keeps recipe 176; recipes 12 (Artemisia vulgaris) and 76 (Hypericum perforatum) withheld until their warnings are approved; build still stops on Rosa dumalis (rule 2)
- New caution species later need a re-run of scripts/import_caution_warning_drafts.py (not automatic)
- Next: batch 2 (E-01/E-02 WAL-safe snapshot/restore)

### 2026-10-20 21:07
**Snapshot** — Before D3-01 batch 1: queue 61 caution preparation_warnings drafts (36 PFAF, 19 unknown origin, 6 E-14 confirmations)
DB: `snapshots/db_20261020_210754.sqlite`

### 2026-10-20 18:06
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_180607.sqlite`

### 2026-10-20 18:01
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_180110.sqlite`

### 2026-10-20 18:00
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_180019.sqlite`

### 2026-10-20 17:59
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_175941.sqlite`

### 2026-10-20 17:59
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_175921.sqlite`

### 2026-10-20 17:58
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_175845.sqlite`

### 2026-10-20 17:57
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_175701.sqlite`

### 2026-10-20 16:59
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261020_165919.sqlite`

### 2026-10-20 16:59
**Session ended** — Session ended from Settings page

### 2026-10-20 11:43
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261020_114350.sqlite`

### 2026-10-20 11:43
**Session ended** — Session ended from Settings page

### 2026-10-20 11:30
**Caffeinate survives reloads (watches uvicorn reloader); AI placeholder clear (10 taste_notes NULL, 14 medicinal_notes -> A5 default) + shared is_ai_placeholder predicate at all AI draft creation points and approve; 11 None known edible_parts cleared + PFAF parser fix; walk stop cards trimmed to name/badge/link/foraging notes; Urtica foraging_notes test cleared**

**Built:**
- app/services/ai_placeholder.py is_ai_placeholder (single source of truth)
- approve rejects unedited placeholder drafts (422)
- server_watch_pid() for caffeinate -w
- caffeinate start adopts an existing caffeinate instead of duplicating
**Fixed:**
- Caffeinate switched off on every uvicorn reload
- 24 AI refusal texts cleared/replaced (history #2793-2816)
- 11 PFAF None known edible_parts cleared (history #2817-2827)
- PFAF parser: Edible Uses None known = no data
- Urtica dioica foraging_notes test cleared (history #2828)
- Walk stop cards: edible-parts hint removed, no emoji prefix
**Files:** `app/utils/caffeinate.py`, `app/api/scan.py`, `app/services/ai_placeholder.py`, `app/services/enrichment.py`, `app/api/culinary.py`, `app/api/recipes.py`, `app/integrations/pfaf.py`, `frontend/index.html`
**Pending:**
- Melvin: stop server and confirm caffeinate exits (pgrep)
- Alchemilla mollis edible_parts None Known skipped: human-locked (no-op save 1 Jun)
- ~100 pending medicinal_notes drafts are refusals: reject in review (can no longer be approved unedited)
- Browser-test walk 4 stop cards

### 2026-10-20 11:25
**Snapshot** — before placeholder/None-known clear + Urtica foraging_notes test clear
DB: `snapshots/db_20261020_112509.sqlite`

### 2026-10-20 11:12
**Walk panel display fixes: diagnosed AI placeholder taste_notes (Achillea nobilis) and Verbascum densiflorum None known (read-only); walk stop cards: PFAF label/citation display cleanup, recipe snippets removed and replaced by curator foraging_notes**

**Built:**
- _walkCleanPfafText display helper (walk stop cards)
- Walk stop cards show species foraging_notes (first ~160 chars) instead of recipe snippets
- /api/culinary/{name} species payload includes foraging_notes (read-only)
**Fixed:**
- Doubled PFAF Edible Parts/Edible Uses labels and numeric citation brackets hidden on walk stop cards
- Raw markdown recipe snippets no longer shown on walk stop cards
**Files:** `frontend/index.html`, `app/api/culinary.py`
**Pending:**
- Melvin: decide placeholder clear (10 taste_notes + 6 medicinal_notes) and changed_by marker
- Close placeholder gap: shared is_ai_placeholder predicate at all draft sites + approve endpoint
- Verbascum densiflorum + 11 other None known edible/caution species: curator-authored edible_parts
- Browser-test walk 3/4 stop cards

### 2026-10-20 10:44
**Jobs queue pop-up made draggable by its header (pointer events), position remembered in localStorage, clamped to viewport; frontend only**

**Built:**
- Draggable job-status widget header
- Remembered widget position with off-screen fallback to default
**Files:** `frontend/static/js/job-status-widget.js`
**Pending:**
- Melvin browser test of drag / retract / restore

### 2026-10-20 10:40
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261020_104015.sqlite`

### 2026-10-20 10:40
**Session ended** — Session ended from Settings page

### 2026-10-20 10:38
**Fungi category: a confirmed observation of a species whose kingdom is Fungi is filed as obs_category 'fungi'; backfilled the 84 confirmed rows filed as plant.**

**Built:**
- app/models/species.py is_fungal_kingdom; app/services/observation_service.py apply_species_category (only plant → fungi, scenes / existing fungi untouched, never back to plant, audit row) — called from update_observation_status (single approve, correct-species, reidentify confirm, trust accept), the bulk approve worker and restore-from-rejected
- Tested on a DB copy: single approve + manually_verified + bulk approve of fungi → fungi with audit rows; plant (Cannabis sativa) and scene rows untouched
**Fixed:**
- Backfill (snapshot db_20261020_103750 first): 84 approved/manually_verified observations of fungal species changed plant → fungi, one observation_edits row each (edited_by 'backfill: confirmed fungal species (Melvin 20 Oct 2026)'); read back by id: 84/84 fungi, 0 remaining, 118 confirmed fungal rows now filed as fungi
**Files:** `app/models/species.py`, `app/services/observation_service.py`, `app/api/bulk_actions.py`, `app/api/observations.py`, `observations (84 rows obs_category)`
**Pending:**
- Not covered by the rule: P1 dual-agree AUTO-approve in scan.py (automated, not a human approve) and needs_review/pending rows (6 fungal rows still plant until approved); lichens (kingdom Fungi, e.g. Pyxine albovirens) now file as fungi
- Melvin: browser check — fungi pins colour, review cards show Fungi
- Stage C publish panel; republish walk 4

### 2026-10-20 10:37
**Snapshot** — before fungi category backfill (confirmed fungal species filed as plant)
DB: `snapshots/db_20261020_103750.sqlite`

### 2026-10-20 10:35
**Melvin browser feedback: Create-from-map sheet retracts while drawing; map 'froze' after building/saving a new walk (walk draw kept map dragging disabled) fixed; fungi filed as plant diagnosed (no change — ingest running, decision needed).**

**Built:**
- 'Create from map': walk bottom sheet slides fully off-screen while the area is drawn (wbs-drawing), back on completion or cancel (_exitLassoSelect)
**Fixed:**
- Map froze after Save walk: _enterWalkMode attaches the rectangle/circle draw (map.dragging.disable) and only a saved-walk load or exit released it; _buildWalkRoute now detaches it once the walk is built ('← Draw new area' re-attaches). Server log: no GET /api/walk/saves/5 between the save and Melvin's reload
**Files:** `frontend/index.html`
**Pending:**
- DECISION Melvin: fungi filed as plant — scan.py:1609-1613 only sets category_suggested='fungi' (by design 'only suggest, never overwrite'); 84 confirmed observations of fungal species (81 approved, 3 manually_verified) have obs_category='plant' vs 34 correct; 198 plant rows carry the fungi suggestion. Options: category follows the confirmed species' kingdom on approve/correct + snapshot-and-backfill the 84; or accept the suggestion at ingest. Fungi were NOT auto-approved (force_review re-checked at scan.py:1737; the 3 approved rows were Melvin's 08:28 bulk approve)
- Parked by Melvin: implausible regional IDs
- Melvin: browser check — Create from map sheet retract; map pans after building/saving a new walk
- Stage C publish panel; republish walk 4

### 2026-10-20 10:31
**Snapshot** — before re-route of saved walk 5
DB: `snapshots/db_20261020_103151.sqlite`

### 2026-10-20 07:51
**Melvin: re-route 'still the same' + circular toggle 'does nothing'. Log: no reroute request since the Save-changes→Re-route chain shipped (his accept came before it); the one toggle click DID switch Rümmelsbühl foray (id 4) to point-to-point (DB circular=0, panel redrawn) — visible change was only the 165 m dashed 28→1 leg. Added start/finish flags in point-to-point.**

**Built:**
- Point-to-point view: 🚩 on the start stop, 🏁 on the finish stop (last saved stop) so the one-way shape is obvious
**Files:** `frontend/index.html`
**Pending:**
- LIVE STATE: Rümmelsbühl foray (id 4) is now point-to-point (2,787 m / 34 min shown) — switch back with the toggle if not intended
- Rümmelsbühl side-stops 21a/26a/26b still side-stops — press ↻ Re-route (no reroute request in the log since the chain shipped)
- Melvin: browser check of flags + Save changes → Re-route chain
- Stage C publish panel; republish walk 4

### 2026-10-20 07:43
**New stops become part of the walk 'as if there all along': Save changes with adds opens the Re-route preview; re-route places far side-stops by cheapest insertion (near ones keep their place along the line); detour rule tightened.**

**Built:**
- walk_route.insert_cheapest: saved stops keep order (stop 1 first); far hand-added side-stops (off_route_m) inserted where they add least straight-line distance; side-stops the line already passes keep their chainage place
- Save changes → when photos were added, goes straight on to the existing Re-route dry-run dialog (cancel keeps side-stops)
- Detour rule: routed > 2× straight + 100 m → dashed straight leg (was 3× + 150 m); real paths here route at 1.3–1.6×
**Files:** `app/services/walk_route.py`, `app/api/walk.py`, `frontend/index.html`
**Pending:**
- Melvin: Rümmelsbühl foray (id 4) still has side-stops 21a/26a/26b live — press ↻ Re-route (DB-copy result: 31 stops 1–31, 26→26a→21a→26b→27 with 26b→27 dashed, 4,542 m / 55 min, members unchanged, other dashed legs kept)
- Browser check of Save changes → Re-route chain
- Stage C publish panel; republish walk 4

### 2026-10-20 07:39
**Fix: 'Save changes' did nothing — no accept/exclude request reached the server. Pending marks were discarded on switching Edit walk off, leaving the button disabled; now kept until saved.**

**Built:**
- _walkPending (add/remove sets) separate from the Edit-walk flag: survives switching Edit walk off; cleared only on save, loading another walk, or leaving walk mode
- walkSaveChanges: never silent — 'Nothing to save …', 'Changes not saved — still marked', or the error message on the status line
**Fixed:**
- Save changes no-op: server log had no POST accept/exclude after the click (page was the current build); leaving Edit walk discarded the marks and disabled the button
- Button count now updates before the pin redraw; name labels bound only on the pins-layer marker inside a guard so a label can't break the redraw
**Files:** `frontend/index.html`
**Pending:**
- Melvin: reload the map page, mark pins, Save changes (with Edit walk on or off) — check the status line
- Stage C publish panel; republish walk 4

### 2026-10-20 07:35
**Edit walk: staged edits (+ pending add / − pending remove on pins) committed by 'Save changes (N)' on loaded walks; floating Add/Remove bar removed; Save walk on a loaded walk no longer makes a copy.**

**Built:**
- Tap in ✎ Edit walk: non-member → pending add (green + disc), member → pending remove (red − disc), tap again → unmarked; pending pins keep their name label
- walk-save-btn → walkSaveClick: loaded saved walk = 'Save changes (N)' (disabled at 0; accept then exclude paths, server read-back + client check against returned members, result on the status line); new walks = 'Save walk' unchanged
- Pending marks are discarded on leaving Edit walk / loading another walk / exiting walk mode (chosen: simple)
**Fixed:**
- Add/Remove bar 'not visible': it was rendered (position:fixed top-centre of the window, z-index 1200, appended to <body>, not the panel) — removed in favour of the in-panel Save changes button
**Files:** `frontend/index.html`
**Pending:**
- Melvin: browser check — + / − marks, Save changes (N) count, status line, undo by re-marking
- Live: Rümmelsbühl foray (id 4) re-routed by Melvin 07:25 (snapshot db_20261020_072552): 28 stops, 2,952 m / 36 min, 6 dashed segments identical, members 136 unchanged
- Stage C publish panel; republish walk 4

### 2026-10-20 07:25
**Snapshot** — before re-route of saved walk 4
DB: `snapshots/db_20261020_072552.sqlite`

### 2026-10-20 07:21
**Walk editing: one '✎ Edit walk' toggle (replaces Show all pins + Select pins); no species cards from pin taps while a saved walk is loaded; names rule 'Common (Latin)' via one helper; circular toggle diagnosed + made one-request-at-a-time with explicit feedback; Rümmelsbühl membership report.**

**Built:**
- ✎ Edit walk: off = walk's own markers only; on = all pins, tap select/deselect, bar Add/Remove/Done; selected pins keep a name label, hover label on desktop; turning off clears selection
- handlePinClick: while a saved walk is loaded, a pin tap never opens the species card (edit on: select; off: name label). Only pin path to showDetail is pin/cluster click → handlePinClick; outside walk mode unchanged
- Walk stop markers: tap/hover label with the stop's species (names rule)
- Names rule: app/models/species.py display_common_name (preferred_common_name, else first EN) used by map pins, walk API names map, critical hazards, export en_name; frontend/static/js/species-names.js spNameHtml/spNameText
- Sites changed: older-photos list, pin labels, stop marker labels, walk panel 'Also here', re-route result message, species filter dropdown, note species-tag dropdown, Export summary 'Also here' (sharing.py), review critical cards + confirm/toast, experience page 'Also here'
- Circular toggle: in-flight guard (button disabled while the PATCH runs) + hint 'Ends at stop N — leg back to stop 1 not drawn' / 'Returns to stop 1'
**Fixed:**
- Circular toggle 'does nothing': server log shows 7 PATCH /loop 200, each followed by the panel redraw (GET /api/walk/saves); four overlapping clicks sent the same value and their responses flipped the view back; on Rümmelsbühl foray (id 4) the visible change is only the 165 m dashed 26→1 leg and ~2.9→~2.7 km. Service worker is network-first (not stale)
**Files:** `frontend/index.html`, `frontend/review.html`, `frontend/static/js/species-names.js`, `app/models/species.py`, `app/api/map.py`, `app/api/walk.py`, `app/api/experience.py`, `app/api/sharing.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`
**Pending:**
- Melvin: browser check — Edit walk on/off, pin taps (no species card), labels (selected + hover), circular toggle feedback, names in panel/older list/critical cards/summary
- Not changed (names rule): sightings.html lightbox link (ObservationOut has no common name), curator-tool toasts in review.html AI-draft/enrichment tabs, scan.html, workshops.html history, species.html internals; experience preview teasers show common name only (space)
- Stage C publish panel; republish walk 4

### 2026-10-20 06:55
**'↻ Re-route through stops' for loaded saved walks: changed legs only via ORS, kept legs keep geometry + dashes, dry run → confirm → snapshot → write → read back.**

**Built:**
- walk_route.plan_reroute / assemble_reroute: legs between stops that were already consecutive keep their stored geometry and dashed flags; legs touching a new side-stop or bridging a dropped empty stop go to ORS in runs (≤50 points, ≤10 requests); a new leg ORS detours on (>3× straight + 150 m) is kept straight and dashed
- POST /api/walk/saves/{id}/reroute {confirm}: dry run (stops before/after, added/dropped, legs kept/routed, ORS requests) — confirm takes a DB snapshot, routes, writes waypoints (1..N, old stop 1 first), line, distance (line length) and time (walk's pace), clears accepted list, reads back by id; any ORS failure writes nothing; result lists photos that newly joined along new legs
- _ors_post shared by the map proxy and re-route
- Frontend '↻ Re-route' button (loaded saved walk, curator): dry-run summary in a confirm dialog, result summary afterwards
**Files:** `app/services/walk_route.py`, `app/api/walk.py`, `frontend/index.html`
**Pending:**
- Melvin: browser check of ↻ Re-route (dialog text, result, line redraw) — verified on a DB copy only, with real ORS calls
- Note: new legs can pull in other confirmed photos by proximity (reported in the result, not auto-excluded)
- Stage C publish panel; republish walk 4

### 2026-10-20 06:51
**Walk editing: older-photo ticks highlight their pins; 'Select pins' mode to add/remove photos as side-stops (accept/exclude paths, any distance); Part 3 re-route design proposed, not built.**

**Built:**
- Check: walk_membership.compute dropped accepted photos beyond the route buffer (and callers never loaded them; accept only took older candidates) — now accepted photos join at any distance, are loaded by id (walk API, export, straighten script), stops carry off_route_m
- POST accept: any confirmed photo with GPS (skipped list with reasons: not confirmed / no GPS / already on the walk); un-excludes first so Add after Remove restores the row exactly
- POST exclude: joined, hand-added or saved-stop photos; un-accepts first so Remove after Add restores the row exactly; saved stops never deleted
- Older-photos list: ticking lights the species' pins (orange rings, own layer above all pins, shown while pins hidden); cleared on close / re-render / other walk / exit
- ◎ Select pins (loaded saved walk, curator): tap toggles selection; on-walk = green ring, off-walk = grey ring, selected = orange; bar 'N selected · Add to walk · Remove from walk · Done' with skip reasons; pins shown while selecting, setting restored on Done
- Stop card: 'N m off route' for side-stops beyond the buffer
**Files:** `app/services/walk_membership.py`, `app/api/walk.py`, `frontend/index.html`, `scripts/experience_export/export.py`, `scripts/walk_straighten_legs.py`
**Pending:**
- Melvin: browser check of tick highlights and Select pins (taps on phone and laptop, bar messages, off-route label)
- DECISION: Part 3 'Re-route through stops' design awaiting OK
- Stage C publish panel; republish walk 4

### 2026-10-20 06:36
**Load-sequence guard in loadSavedWalk; circular / point-to-point toggle for loaded saved walks (persisted, view of the stored line, no ORS); stop-to-line matching made exact (DP) after it crept a rotated loop's seam; little foray (id 3) seam shift repaired.**

**Built:**
- loadSavedWalk: load token checked after every await; a stale load removes only the route layer its own build drew (layers tagged with _walkBuildSeq) — harness over the real function text: 6 interleavings of id 3 then id 4 all end map + panel on id 4
- walk_route.shown_line: point-to-point on a closed line = cut at the last stop; circular on an open line = dashed straight leg back to stop 1; distance/time scaled from the saved figures; set_circular
- PATCH /api/walk/saves/{id}/loop {circular}: only foragingid.circular written, read back by id (line, waypoints, distance unchanged); GET/refresh return `shown`
- Reverse/Start here keyed on the STORED line being a closed loop (work in point-to-point view: reverse = last stop becomes 1)
- Frontend: toggle on a loaded walk calls the endpoint; map, distance, GPX, Google Maps, Export summary use the shown line; title keeps the name; _lastWalkBounds/_lastWalkCircle cleared on load
- Experience export uses shown_line (line, dashes, distance/time, loop_view in plan)
**Fixed:**
- toggleWalkLoop on a loaded walk did nothing (or rebuilt an old drawn area over it)
- walk_route.stop_vertex_indices: greedy earliest-pass match → exact min-distance monotonic assignment (DP); Start here round trips crept the seam one vertex (little foray (id 3) was left rotated by 1 vertex) — 264 exact-coordinate round-trip checks now pass
- little foray (id 3) live seam repaired via reorder (start 2, start back): line identical to the 19 Oct straighten write, stop order original, distance/members unchanged
**Files:** `frontend/index.html`, `app/services/walk_route.py`, `app/services/walk_membership.py`, `app/api/walk.py`, `scripts/experience_export/export.py`, `saved_walks id 3 (route_geojson seam only)`
**Pending:**
- Melvin: browser check — toggle on both walks (little foray (id 3) p2p 3,909 m / 47 min; Rümmelsbühl foray (id 4) p2p 2,731 m / 33 min), Reverse, Start here in both views, ← Saved walks
- Stage C publish panel; republish walk 4

### 2026-10-20 06:35
**Snapshot** — before repairing little foray (id 3) seam shift via reorder
DB: `snapshots/db_20261020_063515.sqlite`

### 2026-10-20 06:27
**Snapshot** — before circular toggle persistence + load-sequence guard
DB: `snapshots/db_20261020_062739.sqlite`

### 2026-10-20 06:23
**Restored '⇄ Reverse' next to '← Saved walks' (no pop-up); diagnoses only for: little foray (id 3) old line not drawing, stop-1 choice, circular toggle on loaded walks.**

**Built:**
- frontend/index.html: #walk-reverse-btn '⇄ Reverse' in the loaded walk's button row (shown via _syncWalkPinsBtn) → walkReorder('reverse'); retested on a DB copy: every start + reverse on ids 3 and 4, 0 problems
**Files:** `frontend/index.html`
**Pending:**
- Part 2: little foray (id 3) old line — geometry from db_20261020_053600 is clean (462 [lng,lat] pairs, no NaN/null/dups); static trace finds no failure on that path. Found: loadSavedWalk has no load-sequence guard (two overlapping loads can leave the map on one walk and the panel on the other; server log shows walk 3 + 4 loads in the same second three times). Proposed: sequence guard + a temporary test row with the old line for a live console check (needs OK)
- Part 4: toggleWalkLoop on a loaded walk only flips _walkCircular (+ breaks the name signature, hides Start here); if an area was drawn earlier in the session it REBUILDS that old area over the loaded walk (_lastWalkBounds never cleared). Proposal awaiting OK
- Melvin: browser check of ⇄ Reverse

### 2026-10-20 05:54
**Loaded-walk panel: '← Saved walks' button back to the saved-walks list; Reverse button removed (Start here covers it, Melvin); Start here runs without a confirm pop-up.**

**Built:**
- frontend/index.html: #walk-saved-btn '← Saved walks' in the loaded walk's button row (shown with Show all pins via _syncWalkPinsBtn) → walkBackToSaved() = _wbsLoadSaved() + scroll to the list
**Fixed:**
- Reverse direction button removed from the panel (server reorder mode 'reverse' kept, no UI)
- Start here: no confirm dialog
**Files:** `frontend/index.html`
**Pending:**
- Melvin: browser check of '← Saved walks' and Start here (no pop-up)
- Stage C publish panel; republish walk 4

### 2026-10-20 05:48
**straight_ranges (multi-range dashed legs) + walk reorder endpoint (Reverse direction / Start here) + little foray (id 3) detour legs straightened; 7a labelling made pass-aware so labels stay coherent after reorder.**

**Built:**
- app/services/walk_route.py (new, pure): straight_ranges() reader (legacy straight_from = [[sf, n-1]]), reverse(), start_at(), straighten_legs(), stop_vertex_indices(); dashes kept per segment so they move with their physical legs
- POST /api/walk/saves/{id}/reorder {mode: reverse | start, stop_label}: curator; no ORS; distance/duration/members unchanged; read back; 7a/note stops refused as a start
- frontend/index.html: _walkStraightRangesOf + multi-range dashed drawing; save writes straight_ranges; '⇄ Reverse direction' button in the membership bar; 'Start here' on saved stops of a loaded circular walk; _refreshSavedWalk adopts the reordered line
- walk_membership.compute: saved-stop chainage follows the walk's pass order; joined (7a) stops on retraced paths take the pass whose neighbouring saved stops are closest; closed-loop seam pass merged for joined stops — labels coherent under every start + reverse (tested all 25 / 19 starts on ids 4 / 3)
- scripts/walk_straighten_legs.py: dry-run by default, refuses if members would change, read-back by id
- experience export: walk_route reader, multi-range dashes on map + preview SVG
**Fixed:**
- little foray (id 3): legs 8→9→10→11 and 16→17→18 straightened (dashed); 13,486 m / 162 min → 4,608 m / 55 min; 462 → 133 vertices; members unchanged (40). Leg 5→6 left routed — obs 24281 (joined 5a) is 4 m off that path
- index.html _walkRepeatSplit comment named a non-existent Python function
**Files:** `app/services/walk_route.py`, `app/services/walk_membership.py`, `app/api/walk.py`, `frontend/index.html`, `scripts/walk_straighten_legs.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `saved_walks id 3 (route_geojson, distance_m, duration_min)`, `dist/ rebuilt`
**Pending:**
- Melvin: browser check — little foray (id 3) line now drawn with 2 dashed stretches; Reverse direction + Start here on both walks; compact repeat lines
- Label change from the pass-aware rule (read-time, no DB write): little foray (id 3) 2a→5a, Rümmelsbühl foray (id 4) 12a→11a — printed sheets / dist pages built earlier show the old labels
- Stage C publish panel; republish walk 4

### 2026-10-20 05:36
**Snapshot** — before straight_ranges + walk reorder + little foray (id 3) detour fix
DB: `snapshots/db_20261020_053600.sqlite`

### 2026-10-20 05:34
**Diagnosis only (no writes): little foray (id 3) route line + 13.5 km, repeat-species report, stop order/numbering logic; proposals awaiting Melvin's OK.**

**Pending:**
- little foray (id 3) line not visible: data valid (LineString 462 vertices, [lng,lat], closed loop) and the loader takes the same saved-geometry branch as id 4 (index.html:5884 → solid polyline at 5985); cause not found statically — needs Melvin's console check
- little foray (id 3) 13.5 km = saved ORS line length (13,436 m); ORS detours on legs 5→6, 8→9→10→11, 16→17→18 (up to 1.3 km north of the stops)
- Stop 1 = southernmost stop on both walks: _clusterStops sorts pins by latitude (index.html:5685), _nnRoute starts at stops[0] (5604); direction = nearest-neighbour from there; ORS follows the given order; saved order is stored in waypoints_json and used as-is on load
- PROPOSAL awaiting OK: straight legs as vertex ranges (straight_ranges, reads old straight_from) + server reorder endpoint (Reverse direction / Start here) that reorders waypoints and reverses/rotates the saved line and ranges; distance kept, no ORS call
- PROPOSAL awaiting OK: little foray (id 3) detour legs → straight dashed ranges, distance recomputed (needs explicit OK — changes the saved figure)
- Fix wrong function name in index.html _walkRepeatSplit comment (species_first_stop does not exist)
- Melvin: earlier report 'one walk doesn't load / no pins' — no cause found in the repeat-line diff; need symptoms if it recurs

### 2026-10-20 05:20
**Walk panel: same species only once per walk (full card at first stop, compact 'Also here … — see stop N' line after, safety badge kept) in the app walk panel and the experience export walk tab; route-line diagnosis (cause not found statically — needs Melvin's console check).**

**Built:**
- frontend/index.html: _walkRepeatSplit(route) — the one JS repeat rule, now used by renderWalkPanel AND exportWalkSummary (replaces the summary's inline loop); _walkEdibBadge() extracted from the stop card so full and compact lines share one badge; compact line keeps ☠ toxic/deadly, ⚠ toxicity unknown or caution, no recipe/edible-parts; repeat-only stops still render
- scripts/experience_export: gates.REPEAT_BADGE_KINDS + repeat_line_badge (deadly/toxic/unknown/caution/apiaceae kept); export.py st['repeat'] per stop (st['species'] unchanged, so hidden check, ☠ flag and per-stop blocker untouched) + pre-write check that no repeat drops a safety badge; template stopBody/alsoHere for stop cards and marker popups; plan-json stops[].repeats
**Fixed:**
- Dryopteris filix-mas on Rümmelsbühl foray (id 4): full card at stop 4 only; stop 6 shows 'Also here: ☠ … — see stop 4'
**Files:** `frontend/index.html`, `scripts/experience_export/export.py`, `scripts/experience_export/gates.py`, `scripts/experience_export/templates/index.html`, `dist/ (rebuilt, gitignored)`
**Pending:**
- Route line missing on Rümmelsbühl foray (id 4) and little foray (id 3): data + API + code path verified correct (saved geometry used, no ORS call in logs); cause not found statically — Melvin to run the console check and paste the result, then fix
- Melvin: browser check of compact repeat lines in the walk panel (unverified live)
- Melvin: browser check review Critical section + badge + chip dot; Stage C
- Daucus carota (Apiaceae) shows no badge on app repeat line (app has no Apiaceae rule — existing DECISION)

### 2026-10-19 21:26
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261019_212625.sqlite`

### 2026-10-19 21:26
**Session ended** — Session ended from Settings page

### 2026-10-19 21:23
**B2 follow-up (safety): hazard blocker per stop as well as per species; red dot on the closed nav chip when critical count > 0.**

**Built:**
- gates.obs_unconfirmed_hazard + export.py per-stop BLOCKER 'hazard at stop <label> not human-confirmed: <species> (obs ...)' — fires even when the species is human-confirmed at another stop; obs missing from the load also blocks (fail closed); per-species blocker kept
- site-header.js/css: #nav-chip-critical-dot on the drawer chip, driven by the same /api/experience/critical count as the ☠ Review badge (curator branch only, hidden at 0); chip aria-label names the count
**Files:** `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `frontend/static/js/site-header.js`, `frontend/static/css/site-header.css`
**Pending:**
- Melvin: browser check review Critical section + badge + chip dot; confirm walk 3 Atropa 22224/22225 + Senecio 22231; Stage C
- export.py opens the DB with mode=ro: a fresh WAL-mode DB copy with no -shm file fails to open (live DB unaffected while the server runs)

### 2026-10-19 21:14
**Publish-as-experience Stage B2: experience_publications table, export --plan-json + hazard blocker, curator-only /api/experience router (publications, plan, verify-species, critical), saved-walk delete guard, critical hazards in review + red nav badge. No publish/push.**

**Built:**
- Migration 0054 experience_publications (slug unique; one default via partial unique index + code; saved_walk_id FK ON DELETE SET NULL) + model, noqa import
- export.py --plan-json (structured plan on stdout) and --db; rule 7 BLOCKER: AI-agreed-only species on route that is toxic/deadly/unknown (or unlinked) fails the full build, plan still prints, nothing written
- app/models/species.py is_toxic_severity() shared predicate; gates.is_toxic uses it
- app/api/experience.py (router-level curator dependency on every route incl. GETs): publications list/get/create/patch, plan (subprocess --plan-json against the app's own DB), verify-species (edible/caution + toxicity none only; 2 history rows; re-read by id), critical (read-time, per observation)
- DELETE /api/walk/saves/{id}: curator check; 409 naming slug if published; drafts deleted with the walk; unpublished kept as history
- review.html: pinned Critical section (above filters/pagination) + red banner; Confirm species = PATCH review manually_verified; Re-identify = existing retry-ID panel; site-header red ☠ count badge on Review (curator only, hidden at 0)
**Fixed:**
- Walk DELETE had no identity check
- index.html walk delete shows the API detail (409 slug) instead of bare HTTP status
**Files:** `migrations/versions/0054_experience_publications.py`, `app/models/experience.py`, `app/main.py`, `app/models/species.py`, `app/api/experience.py`, `app/api/walk.py`, `scripts/experience_export/export.py`, `scripts/experience_export/gates.py`, `frontend/review.html`, `frontend/static/js/site-header.js`, `frontend/static/css/site-header.css`, `frontend/index.html`
**Pending:**
- Melvin: browser-check review Critical section, banner and red nav badge (implemented, unverified live)
- Walk 3: Atropa bella-donna (obs 22224, 22225, stop 13) + Senecio ovatus (22231, stop 16) still AI-agreed only — confirm in review
- C publish panel UI (confirm step warns the exact route is public + unpublish ≠ erasure; AI-agreed review list; verify buttons)
- republish walk 4
- DECISION Melvin: app-side Apiaceae culinary gate
- DECISION Melvin: per-stop hazard gap — toxic species human-confirmed at one stop but AI-agreed-only at another stop shows no ☠ there and raises no blocker
- /api/me is host-based, ignores tokens (participant token on localhost still sees curator nav; endpoints themselves 403)
- CLAUDE.md Alembic head now 0054

### 2026-10-19 21:03
**Snapshot** — before B2 experience_publications migration
DB: `snapshots/db_20261019_210354.sqlite`

### 2026-10-19 21:02
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261019_210216.sqlite`

### 2026-10-19 21:02
**Session ended** — Session ended from Settings page

### 2026-10-19 20:55
**Publish B1 part 2: taxonomy fixes 144/492/Epilobium, Apiaceae genus gate, dashed route + DE text + unknown badge, preview card restructure, strict placeholder check, config cleanup; verified a-e (walk 4 browser check still pending - Melvin chose to build anyway)**

**Built:**
- gates.py: APIACEAE_GENERA - Apiaceae = family OR genus OR first word of scientific name -> ID card only
- gates.py: taxonomy_warnings (family not *aceae / genus vs name) listed as WARNINGs in --plan-only
- index.html: route dashed from straight_from with 'no mapped footpath' tooltip (as app); German title/intro/where lines shown only when filled
- app_styles.py: .badge.unknown shares the warn-badge colours (Apiaceae badge)
- preview.html: card no longer one <a> - photo/title + button links (target=_top), teasers plain text, More walks row outside links ({{CARD_CLASS}}, {{MORE_WALKS}}, hidden when empty); dish names one line with ellipsis; CSS height budget documented (30px slack with More walks)
- export.py: fill() fails if a filled placeholder is missing from a template or a template placeholder is unfilled (index, preview, tree)
**Fixed:**
- DB (snapshot db_20261019_204819): 144 Heracleum sphondylium family Heracleum->Apiaceae, genus NULL->Heracleum; 492 Berula erecta family Berula->Apiaceae, genus NULL->Berula; 162 Epilobium tetragonum family Epilobium->Onagraceae, genus Symphyotrichum->Epilobium; 482 Epilobium palustre family Epilobium->Onagraceae, genus Euthamia->Epilobium. History rows 136-143 (species_edibility_history, changed_by=human). Read back by ID; edibility/toxicity/verification untouched
- config.json: removed walk_id, walk_name, title, intro, preview_where, apiaceae_id_only (+ apiaceae note)
- Placeholder regex now allows digits ({{D3}} - caught by the new check)
**Files:** `data/foragingid.db`, `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `scripts/experience_export/app_styles.py`, `scripts/experience_export/config.json`, `scripts/experience_export/templates/index.html`, `scripts/experience_export/templates/preview.html`
**Pending:**
- Melvin: walk 4 browser check + 500px card measurement
- Melvin: walk 3 - Atropa bella-donna (deadly) and Senecio ovatus are AI-agreed only, so excluded from the page (no warning shown) until human-confirmed
- Heracleum sphondylium 144 / Berula 492 / Epilobium 162, 482: order/class/phylum still NULL - not placed in the tree (GBIF lineage pass)
- B2
- C
- Backlog: GBIF taxonomy pass for 98 family=genus + 12 null-family species
- Backlog: app/ has no Apiaceae rule at all; wikidata.py:41 _LIKELY_EDIBLE_FAMILIES includes Apiaceae (suggestion only) - see B1 part 2 report

### 2026-10-19 20:48
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261019_204819.sqlite`

### 2026-10-19 20:45
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261019_204530.sqlite`

### 2026-10-19 20:45
**Session ended** — Session ended from Settings page

### 2026-10-19 20:05
**Sent 5 suspected non-European misIDs to review via POST /api/audit/send-to-review (snapshot db_20261019_200454 first); traced Ulmus laciniata card 740 (read-only)**

**Fixed:**
- 19805, 19820 (Corylus cornuta), 20572 (Rosa maximowicziana), 21472 (Quercus velutina), 22131 (Ulmus laciniata) -> needs_review, review_label=data_trust, [Audit] dry-run note appended; species unchanged
**Pending:**
- Melvin: correct species in review for the 5 rows (suggested Corylus avellana x2, Rosa arvensis, Quercus rubra, Ulmus glabra)
- Species 740 Ulmus laciniata will be orphaned if 22131 is corrected; species card created by scan _upsert_species_card for a new photo on 17 Jul (no name-level guard against re-creating deleted species)

### 2026-10-19 20:04
**Snapshot** — before sending 5 suspected misIDs to review (19805,19820,20572,21472,22131)
DB: `snapshots/db_20261019_200454.sqlite`

### 2026-10-19 19:46
**PlantNet regional demotion (project stays 'all'): European lists reference file + refresh script, nb-results=30, shared demotion helper in plantnet.identify_image, agreement rule extracted to app/services/agreement.py, setting regional_demotion_affects_auto_approve (default OFF), non-European labels, read-only dry run**

**Built:**
- data/reference/plantnet_europe_species.json (5 European lists, fetch date + source per list)
- scripts/refresh_plantnet_europe_lists.py (catalogue endpoint only, no ID quota)
- app/services/regional_demotion.py: stable re-rank, non_european flag, raw_rank, display_slots (never hides raw top-N)
- PlantNet nb-results=30 (same quota cost; Aconitum napellus now #23 raw -> #8 demoted)
- app/services/agreement.py: decide_agreement() pure rule used by scan
- Setting regional_demotion_affects_auto_approve (default OFF) + reviewer note 'agreement after regional demotion (raw PN #1: X)' when ON
- Labels 'not native to Europe — planted?' on review card, Second Opinion, Retry ID
- species_candidates_json stores rank (demoted) + pn_raw_rank + non_european
**Fixed:**
- scan: agreement now computed before min-confidence check so the agreed species is the one stored/judged
**Files:** `app/integrations/plantnet.py`, `app/services/regional_demotion.py`, `app/services/agreement.py`, `app/services/settings_service.py`, `app/api/scan.py`, `app/api/reidentify.py`, `frontend/review.html`, `scripts/refresh_plantnet_europe_lists.py`, `data/reference/plantnet_europe_species.json`, `tests/test_regional_demotion.py`, `tests/test_agreement.py`, `tests/fixtures/regional_demotion_ab.json`
**Pending:**
- Melvin: browser check of non-European labels (review card, Second Opinion, Retry ID)
- Melvin decides whether to turn regional_demotion_affects_auto_approve ON (dry run: 0 new, 0 lost at 0.7)
- Review approved non-European look-alikes found in dry run: 19805/19820 Corylus cornuta, 20572 Rosa maximowicziana, 21472 Quercus velutina, 22131 Ulmus laciniata
- Demotion surfaces tiny-score European names on non-plant photos (e.g. fungus 24347)

### 2026-10-19 19:24
**Second Opinion routing fix (category-aware sources, override, per-source slots, iNat double-division fix) + PlantNet regional project recon/A-B (read-only)**

**Built:**
- Second Opinion: sources default from obs_category (fungi -> iNat+GBIF, no PlantNet), optional body.sources override honoured incl. PlantNet on fungi
- Second Opinion: per-source top-5 guaranteed slots, explicit per-source empty/error warnings
- review.html: Sources selector, click-time category, accurate loading text, setCategory closes open panel
- [second-opinion] audit log line per call
**Fixed:**
- Second Opinion divided iNat scores by 100 twice (already 0-1 from score_image) - iNat candidates were ~100x too small and always lost the pooled top-10
- Empty Second Opinion now shows recorded warnings instead of 'check API keys'
**Files:** `app/api/reidentify.py`, `frontend/review.html`
**Pending:**
- Melvin live check: category switch closes Second Opinion panel; Sources selector + loading text
- Decide PlantNet project per pipeline (A/B: all vs k-middle-europe/k-northern-europe - no weurope project exists)
- PlantNet uploads of 4.8-8.2 MB photos stall (write timeout x3); iNat ReadError when run concurrently with PlantNet upload
- Correction: reidentify.js disables PlantNet checkbox for fungi (no override there)

### 2026-10-18 09:35
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261018_093543.sqlite`

### 2026-10-18 09:35
**Session ended** — Session ended from Settings page

### 2026-10-18 08:22
**DB fixes (Melvin OK, snapshot db_20261018_081958): archived mismatched recipes 5-8; walk 4 detour legs replaced with straight dashed segments**

**Built:**
- Saved walks: route_geojson.foragingid.straight_from — vertices from that index drawn dashed (no mapped footpath), kept on re-save
**Fixed:**
- Archived species_recipes 5 (Stellaria media, cherry text), 6 (Prunus avium, field mint), 7 (Prunus domestica, wild carrot), 8 (Cardamine flexuosa, plums) via the app archive endpoint — 26 May AI batch used another species context
- Walk 4 line: ORS part kept for stops 1-22 (2.0 km), legs 22-23-24-25-26-1 straight (894 m); distance 6410 -> 2895 m, duration 77 -> 35 min; members unchanged (136); 37 older-photo candidate species dropped (all were along the removed Gresgen detour)
**Files:** `frontend/index.html`, `data/foragingid.db (saved_walks 4, species_recipes 5-8)`
**Pending:**
- Melvin browser check: walk 4 line under all stops with dashed legs 22-26-1, summary, Google link, GPX
- Published experience page draws the line solid (no dashed legs) — dist/ rebuilt, not published
- Remaining 26 May batch drafts 94-105 (taste/medicinal) approved but not live — culinary_info for those species is empty

### 2026-10-18 08:19
**Snapshot** — Before archiving mismatched recipes 5-8 and replacing walk 4 detour legs with straight segments
DB: `snapshots/db_20261018_081958.sqlite`

### 2026-10-18 07:35
**Walk fixes from browser check: summary header/distance/footer, Markdown recipes, recipe rule, repeat species, Google Maps even sampling, GPX download; recon on route line + wrong recipes**

**Built:**
- Export summary: walk name as title, panel distance, footer Generated by LandMemory
- Recipe Markdown rendered safely in summary (_md_snippet: headings, lists, bold/italic, escaped)
- Summary recipe choice curator > own menu > ai_generated, preferred then oldest, no medicinal, same dish never twice (_summaryRecipe); /api/culinary/{name} recipes now include source
- Repeat species in summary: compact Also here line with see stop N (keeps toxic warning)
- Google Maps: 10 points evenly spaced along the whole route line (loop returns to start)
- Download GPX: full route line as track + stops as waypoints (labels incl 7a)
**Fixed:**
- Export summary distance used straight-line stop sum (~2.1 km) instead of panel distance
**Files:** `frontend/index.html`, `app/api/sharing.py`, `app/api/culinary.py`
**Pending:**
- Walk 4 route line: saved ORS geometry follows stops 1-22 (<=37 m) then a 4.3 km detour (2.7 km west via Gresgen) for legs 22-26-1; stops 23/25/26 61-101 m off. Proposed: keep ORS line 1-22, straight dashed legs 22-26-1 (875 m) -> ~2.9 km; needs snapshot + Melvin OK
- Wrong recipes from 26 May AI batch (context of another species): 5 Stellaria media<-cherry, 6 Prunus avium<-field mint, 7 Prunus domestica<-wild carrot (Apiaceae text), 8 Cardamine flexuosa<-plums; propose status=archived; none on published page; needs snapshot + OK
- Melvin browser check: summary, Google link, GPX, line visibility on Outdoors basemap

### 2026-10-18 07:05
**Walk membership — app/ follow-ups saved with Melvin paused**

**Built:**
- Foray session auto-populate uses walk membership (member_obs_ids) instead of obs_ids_json
- Export summary renders the 7a stop label (WalkStop.label; pill-shaped number)
**Files:** `app/api/foray_sessions.py`, `app/api/sharing.py`
**Pending:**
- Melvin to re-run bulk approve for the 23 remaining 17 Oct photos (bp 170 interrupted)
- Live browser check of membership UI on walk 4
- Foray auto-populate not exercised (it writes session_species)

### 2026-10-18 05:58
**Walk membership — frontend + experience export wired (app/ follow-ups held while Melvin is in the app)**

**Built:**
- loadSavedWalk builds stops from GET /api/walk/saves/{id} stops (current species + proximity-joined); legacy waypoint-label path kept as fallback
- Stop labels 7/7a on map markers, stop cards and Export summary payload (label field); joined stops lighter green + dashed card
- Per-species chips: AI-agreed (no human review) and new (+ curator remove)
- Membership row in walk panel: route buffer slider (PATCH), Human-confirmed only filter (per walk, this browser), Renumber stops (confirm), Older photos near this route review with Accept selected / Accept all
- Experience export uses walk_membership.compute (same members and 7a labels as the app)
**Fixed:**
- Experience export build was failing since 16 Oct: app_styles toxic-badge anchor now reads _culinaryGateBadge colours
**Files:** `frontend/index.html`, `scripts/experience_export/export.py`, `scripts/experience_export/app_styles.py`
**Pending:**
- app/ edits held: foray_sessions auto-populate to use membership; sharing.py export-walk to render 7a label
- Melvin to re-run bulk approve for the 23 remaining 17 Oct photos (bp 170 interrupted)
- Live browser check of membership UI on walk 4
- dist/ rebuilt with membership (Rorippa sylvestris new; stop 7 + Capsella/Rorippa, stop 19 + Verbascum) — not published

### 2026-10-18 05:49
**Walk membership by route proximity — backend part 1 (paused: reload interrupted Melvin bulk approve)**

**Built:**
- Migration 0053_walk_membership: saved_walks buffer_m, members_since, excluded_obs_json, accepted_obs_json (snapshot db_20261018_054349 first)
- app/services/walk_membership.py: computed membership (saved stops + confirmed obs within buffer of line taken on/after members_since or accepted; nearest stop within stop radius else new 7a-style stop; older-candidate species list; renumbered_snapshot)
- is_confirmed_observation / is_human_confirmed predicates in app/models/observation.py (human = manually_verified or reviewed_at set; dual-API auto-approve never sets reviewed_at)
- GET /api/walk/saves/{id} returns stops + membership; curator-only PATCH membership, POST accept / exclude / renumber with read-back
**Fixed:**
- Saved-walk species now resolved from current observations (pending item 6, backend side)
**Files:** `migrations/versions/0053_walk_membership.py`, `app/models/walk.py`, `app/models/observation.py`, `app/services/walk_membership.py`, `app/api/walk.py`
**Pending:**
- INCIDENT: walk.py save reloaded server and cancelled Melvin bulk approve bp 170 after 5 of 28 (24258-24261, 24273 approved); remaining 23 not approved — Melvin to re-run
- Frontend: load stops from API, 7a labels, AI-agreed badge, human-confirmed-only filter, older-candidates review, buffer slider, exclude, Renumber stops
- foray_sessions + experience export to use walk_membership (app/ edit held until Melvin paused)
- gps_accuracy_m is never populated (0 rows; Pixel EXIF has no GPSHPositioningError) — accuracy skip is inert

### 2026-10-18 05:43
**Snapshot** — Before walk-membership migration (saved_walks: buffer_m, members_since, excluded/accepted obs)
DB: `snapshots/db_20261018_054349.sqlite`

### 2026-10-18 05:33
**Saved-walk loading UX: side panel (laptop) / peek bar (phone), fit whole walk, other pins hidden + Show all pins, restore on clear; TOOLS Open a saved walk; stop_count fix**

**Built:**
- Loaded saved walk opens as 360px right-hand panel on laptop (.wbs-side), 62px peek bar on phone (.wbs-peek)
- _fitSavedWalk: fitBounds over stops + saved line with padding for panel/peek, maxZoom 18
- Other pins hidden by default on a loaded saved walk (_savedWalkView.hidePins read in _applyLayer); Show all pins toggle in walk export row
- Clear walk restores previous layer + map view
- TOOLS: Open a saved walk (openSavedWalksList)
**Fixed:**
- loadSavedWalk left rectangle-draw attached (map.dragging disabled) when entered via Build a walk — now detached
- fitBounds ran while the 68vh full-width sheet covered the map — now runs after panel layout with matching padding
- wbs-body kept the saved-walks list scroll position so Export summary was off-screen — scrolled to top on load
- GET /api/walk/saves stop_count counted obs_ids (120) not waypoints (26)
**Files:** `frontend/index.html`, `app/api/walk.py`
**Pending:**
- Melvin live check: walk 4 on laptop and at 390px phone width
- Phone handle has no tap-to-open (drag only) — pre-existing
- _wbsLoadSaved hides walk-ors-note and nothing restores it — pre-existing
- Saved walk stop labels still from save time (pending item 6)

### 2026-10-18 05:16
**Publish-as-experience Stage A: read-only recon + plan (no code, no DB writes)**

**Pending:**
- Melvin to answer Stage A open questions before Stage B
- Uncommitted 16 Oct toxic-guard work still awaiting live check + commit

### 2026-10-16 07:05
**Safety follow-up: multi-species stops in export + proximity alerts; backend recipe toxic guard (code-only, no DB writes)**

**Built:**
- culinary_allowed() / CULINARY_ALLOWED_SQL in app/models/species.py — single backend toxic guard (recipes only when toxicity_severity='none', fail closed)
- Walk export schema: WalkStop.species[] (WalkSpecies) — every species per stop, one card with a section each; field-note stops render note text
- Proximity alerts list every species at the stop, each through _culinaryGate
**Fixed:**
- exportWalkSummary dropped all but the first species per stop (toxic Digitalis stop 6, Rhinanthus stop 24 were omitted)
- Proximity alert common-name fallback read entry.common_names (never existed) — now entry.species.common_names
- Recipes now gated on toxicity in GET /api/culinary/{name}, /api/species/{name}/recipes, /api/species/{name}/profile (also feeds lists_pdf), /api/find/recipes, /api/find/medicinal, /api/find/in-season recipe_count, /api/personal-lists/card/{id}
- Export with a field-note stop previously 422'd (missing species_scientific) — note stops now carry note_text
**Files:** `frontend/index.html`, `app/api/sharing.py`, `app/api/culinary.py`, `app/api/recipes.py`, `app/api/find.py`, `app/api/personal_lists.py`, `app/models/species.py`
**Pending:**
- Live browser check: walk 4 export (stops 6/19/24) + proximity alert layout with several species
- WalkRecorder.logProximityEncounter logs only stop.p.id (first obs) per multi-species stop
- Curator recipe write endpoints (POST/PATCH/regenerate) not toxicity-gated; audit recipe check uses edibility only
- iNaturalist token expired (server log)

### 2026-10-16 06:55
**Safety pass: toxic guard gaps in walk flow (code-only, no DB writes)**

**Built:**
- _culinaryGate / _culinaryGateBadge: single shared toxic guard in index.html (allow-list: culinary only when toxicity_severity='none'; toxic/deadly -> ☠ warning; unreadable -> fail closed, '⚠ toxicity unknown')
- GET /api/culinary/{name} returns species.toxicity_severity; _fetchWalkEnrich drops the extra /profile request
- Walk export: toxicity_warning field rendered as badge
**Fixed:**
- Stop-card culinary hint (edible_parts/taste_notes) now gated
- exportWalkSummary sends no culinary/recipe/edibility for blocked species
- Walk sheet list (_wbsRenderLasso) shows ☠ warning instead of edible badge
- Proximity alerts showed pin edibility badge for toxic species — now gated
- Unknown-toxicity species no longer show an edibility badge on stop cards
**Files:** `frontend/index.html`, `app/api/culinary.py`, `app/api/sharing.py`
**Pending:**
- Live browser check of walk 4 (stop cards, sheet list, export, prox alert)
- Export still reads only first species of multi-species stops (Digitalis stop 6, Rhinanthus stop 24 omitted)
- Lasso species outside the walk enrichment show 'toxicity unknown' until enriched

### 2026-10-16 06:46
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261016_064609.sqlite`

### 2026-10-16 06:46
**Session ended** — Session ended from Settings page

### 2026-10-16 06:43
**Pushed Datenschutz footer link to melvinoj/foraging-experience**

**Files:** `(separate repo) foraging-experience: index.html`
**Pending:**
- Check live footer after Pages rebuild

### 2026-10-16 06:39
**CHANGELOG tidied (one Current State block); Datenschutz link added to Foraging Experience export (not pushed)**

**Built:**
- Experience export: config datenschutz_url https://melvinjarman.co.uk/datenschutz; footer Contact · Impressum · Datenschutz (target=_top, same style; placeholder guard like Impressum). Rendered footer checked by running the page code in jsc; only index.html changed
**Fixed:**
- CHANGELOG.md: exactly one ## Current State (session-3 content + its backlog); session_summary fragment moved into the 14:11 History entry; 8 older dated Current State blocks moved unchanged to ## Archive at the end (headings demoted). No-content-lost check passed
**Files:** `CHANGELOG.md`, `scripts/experience_export/config.json`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`
**Pending:**
- Push experience update to melvinoj/foraging-experience after Melvin OK
- End-session paste format: no ## lines except optional plain ## Current State; date as plain text; ### sub-headings; one paste; no current_state:/session_summary: labels

### 2026-10-16 06:27
**Launcher reload scope fixed; CHANGELOG tidy prepared (awaiting OK)**

**Fixed:**
- START_ForagingID.command: uvicorn --reload-exclude $PWD/scripts, $PWD/migrations, $PWD/tests (absolute; uvicorn 0.32.1 ignores --reload-dir for in-project dirs and always watches the repo root - verified against its FileFilter) + --timeout-graceful-shutdown 5. Written via atomic rename so the running launcher is unaffected; takes effect on next launch (unverified live)
**Files:** `START_ForagingID.command`
**Pending:**
- CHANGELOG tidy: one ## Current State block, older dated blocks to ## Archive at end, session_summary into History - prepared, awaiting Melvin OK
- End-session paste must not contain ## headings (use ###); dated ## Current State — <date> headings pile up as stale sections
- Verify new launcher flags on next launch: edit under scripts/ must NOT reload; open tab must not block Ctrl+C beyond ~5 s

### 2026-10-16 06:20
**Caffeinate fix: scan keep-awake can no longer outlive the server; Stop/status act on the real process**

**Fixed:**
- app/api/scan.py: /caffeinate/start runs `caffeinate -dimsu -w <server pid>` (exits with the server on shutdown/crash/--reload); /caffeinate/stop also kills stray `caffeinate -dimsu` from earlier server processes; /caffeinate/status reports the real process (handle or stray)
- app/utils/caffeinate.py keep_awake: `caffeinate -i -w <pid>` (same orphan class)
- frontend/scan.html: button reads /caffeinate/status on page load (was always shown off after a reload)
- VERIFIED by behaviour (pgrep): start -> `caffeinate -dimsu -w 32141` (server worker pid); stop -> none; planted old-style orphan detected by status and killed by stop; -w exits when watched pid dies; keep_awake starts with -w and exits on hard parent exit. UNVERIFIED: end-to-end via a real --reload restart, and the scan page button UI
**Files:** `app/api/scan.py`, `app/utils/caffeinate.py`, `frontend/scan.html`
**Pending:**
- Melvin: open Scan page with keep-awake on -> button should read Keeping awake
- Backlog: --reload restarts the worker on edits outside app/ (scripts/experience_export/export.py) despite --reload-dir app
- Backlog: a long-lived browser connection (SSE/service worker) blocks graceful --reload (Waiting for connections to close) - consider uvicorn --timeout-graceful-shutdown

### 2026-10-15 20:45
**Bug logged: caffeinate keeps Mac awake after Stop (orphaned process)**

**Fixed:**
- Killed orphaned caffeinate -dimsu (pid 13666, started 09:29, parent launchd) — Mac sleeps normally again
**Pending:**
- FIX (app/, needs OK): caffeinate does not turn off. app/api/scan.py /caffeinate/start spawns `caffeinate -dimsu` and keeps the handle only in memory (_caffeinate_proc). After a server restart/reload the handle is lost: the process is orphaned (parent launchd) and /caffeinate/stop returns stopped:false while it keeps running; launcher cleanup + lifespan shutdown do not kill it. Options: start it as `caffeinate -dimsu -w <server pid>` so it exits with the server; stop/status fall back to finding the real process; kill it in lifespan shutdown. Check `pgrep -fl caffeinate` at each session start until fixed

### 2026-10-15 14:12
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261015_141159.sqlite`

### 2026-10-15 14:11
**Session ended** — Session ended from Settings page
Session summary (End-session text; moved from the top of Current State 16 Oct 2026): Walk builder fixes; human verification + re-ID review of two Gresgen walks (~62 species verified, audit trail started, deadly nightshade/male fern/tansy corrected); Foraging Experience export built and published to GitHub Pages (walk map with layers + locate, plants grid, recipe teasers, taxonomy tree, 500px embed card for /b).

### 2026-10-15 14:10
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261015_141051.sqlite`

### 2026-10-15 14:10
**Session ended** — Session ended from Settings page

### 2026-10-15 14:07
**Pushed Foraging Experience update to melvinoj/foraging-experience (4 tabs, plant grid + panel, walk order)**

**Files:** `(separate repo) foraging-experience: index.html, +106 photos`
**Pending:**
- Check live site after Pages rebuild

### 2026-10-15 14:06
**Experience export: species listed in walk order (first stop met) instead of toxic-first**

**Fixed:**
- export.py species sort = first stop on route, then name; toxicity shown on the plant only. Verified: 4 toxic species keep ☠ badge + warning, 0 recipes for toxic species (build also fails if one appears)
**Files:** `scripts/experience_export/export.py`
**Pending:**
- Push only after explicit OK

### 2026-10-15 14:04
**Experience export: tabs Walk · Plants · Recipes · Taxonomy; new Plants grid + filter chips + preview panel**

**Built:**
- Taxonomy tab: existing tree iframe moved unchanged (lazy on first open)
- Plants tab: app species-card grid (400px thumbs), EN/DE/Latin, family, gated badge; chips All/Edible/Caution/Toxic
- Preview panel: main photo + up to 3 more walk photos (800px + 400px thumbs, re-encoded, EXIF-stripped, gated obs only), names, family, months seen on this walk, badge, recipe teaser, toxic warning, look-alike only if human-authored; Esc/scrim close, keyboard open
- export: extra_photos_per_species 3, extra_photo_long_edge 800, months from photo_taken_at
**Files:** `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `scripts/experience_export/config.json`
**Pending:**
- Melvin to check Plants grid/panel + Taxonomy tab live
- Push only after explicit OK (rsync dist/ into /Users/melvinjarman/foraging-experience)

### 2026-10-15 13:52
**Foraging Experience pushed to github.com/melvinoj/foraging-experience (main 14c1f5f)**

**Built:**
- Clone at /Users/melvinjarman/foraging-experience (outside ForagingID); dist/ contents copied: index.html, tree.html, preview.html, photos/ (102); README.md kept from initial commit
**Files:** `(separate repo) foraging-experience`
**Pending:**
- Melvin: enable GitHub Pages (main / root)
- Check live index + preview URLs; add Builder embed on melvinjarman.co.uk/b
- Create Impressum page before go-live
- Re-publish = rerun export, rsync dist/ into the clone, commit, push

### 2026-10-15 13:51
**Experience export: map tile seams (dark lines = real gaps showing container bg)**

**Fixed:**
- Tiles overlap by 0.5px (256.5px !important) with mix-blend-mode normal (plus-lighter would add colours in the overlap); map square corners; container bg dark. Cause: map at fractional pixel position (58vh, non-integer line heights above). Unverified live
**Files:** `scripts/experience_export/templates/index.html`
**Pending:**
- Melvin to refresh and confirm seams gone, then push

### 2026-10-15 13:46
**Experience export: map tile grid-line mitigation; Silene vulgaris EN name; rebuilt (push pending Melvin map check)**

**Fixed:**
- Page img rule scoped away from Leaflet (img:not(.leaflet-container img)); .leaflet-container background set to app deep shell (Leaflet default #ddd shows through sub-pixel tile seams as near-white lines). Evidence: leaflet.css 1.9.4 already forces max-width/padding none !important on tiles and absolute tiles are blockified, so the img rule alone cannot cause seams - cause unconfirmed without a browser
- 164 Silene vulgaris preferred_common_name maidenstears -> Bladder campion (history row 135; snapshot db_20261015_134551)
**Files:** `scripts/experience_export/templates/index.html`, `data/foragingid.db`
**Pending:**
- Melvin to refresh and confirm map grid lines gone
- Then push to melvinoj/foraging-experience + GitHub Pages steps

### 2026-10-15 13:45
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_134551.sqlite`

### 2026-10-15 13:41
**Experience export: self-canonical on index.html; removed ☠ subtitle sentence**

**Built:**
- config canonical_url https://melvinoj.github.io/foraging-experience/ used for index.html canonical (switch to subdomain later)
**Fixed:**
- index.html no longer canonicalises to /b
- Walk subtitle now: Numbered stops follow the walk.
- preview.html noindex confirmed (already present), no canonical
**Files:** `scripts/experience_export/config.json`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`
**Pending:**
- Push only after explicit OK

### 2026-10-15 13:39
**Experience export: dist/preview.html embed card for melvinjarman.co.uk/b**

**Built:**
- preview.html: static (no JS), fixed 500px, no scroll; hero photo, build-time SVG route drawing (no tiles), species/stops/km stats, 3 recipe teasers (2 under 400px wide), whole card + button link to index.html target=_top
- Preview obeys gates: teasers from gated recipes only, hero must have photo and must not be toxic; build fails otherwise
- config: preview_where, preview_hero_species_id, preview_recipe_ids
**Files:** `scripts/experience_export/templates/preview.html`, `scripts/experience_export/export.py`, `scripts/experience_export/config.json`
**Pending:**
- index.html canonical points to /b, which will host the preview card, not the full page - Melvin to decide
- Verify preview fit at 500px live; push only after explicit OK

### 2026-10-15 13:37
**Experience export fixes: tree failed-to-load diagnosed + fixed; plain stop markers; base-layer switcher + locate me; contact URL**

**Built:**
- Map: Standard (OSM) / Satellite (Esri World Imagery) / Topo (OpenTopoMap) layer switcher using the app _baseLayers definitions, keyless; Locate me control (navigator.geolocation, drawn on map only, nothing stored/sent)
- Stop markers/cards plain numbered; toxic shown only on the plant badge; subtitle now: ☠ marks poisonous plants — look, don't pick.
**Fixed:**
- Plants tab Failed to load: taxonomy.html layout() class-tier redistribution throws unless all 6 full-collection classes (Magnoliopsida, Bryopsida, Polypodiopsida, Liliopsida, Pinopsida, Florideophyceae) exist; walk has 4 (no Bryopsida/Florideophyceae). Reproduced under jsc with DOM stubs; fixed with anchored export patch skipping that block (flag __EXPORT_SKIP_CLASS_REDISTRIBUTION__). jsc run now: 51 species badge, 97 nodes, 4 toxic labels, 0 NaN transforms
- contact_url -> https://melvinjarman.co.uk/contact (CTA + footer, target=_top)
**Files:** `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `scripts/experience_export/config.json`
**Pending:**
- Melvin to verify tree + map live
- Hostinger embed iframe needs allow=geolocation for Locate me
- Push only after explicit OK

### 2026-10-15 13:28
**Experience export restyled to the app look (build-time extraction, fail-loud anchors); OSM tiles kept, no Thunderforest key**

**Built:**
- scripts/experience_export/app_styles.py: copies tokens.css :root verbatim, 18 top-level rules (walk-panel stop card/num/species/common/meta/recipe strip, walk-header; species.html species-card family, warn/toxic badges, list headings), shell colours from species.html (#2a3330) and lists.html (#1e2b28), walk-panel badge colours read from renderWalkPanel JS; each anchor must match exactly once (StyleDrift)
- index template: dark app shell, Georgia display serif for names/headings, stop cards in walk-panel layout (sci name, common EN/DE, badge), species cards, recipe teasers in walk-panel recipe strip, 44px touch targets
- tree.html: taxonomy variables mapped to app palette; toxic nodes var(--app-toxic)
**Files:** `scripts/experience_export/app_styles.py`, `scripts/experience_export/export.py`, `scripts/experience_export/templates/index.html`, `scripts/experience_export/templates/tree.html`
**Pending:**
- Melvin to check the restyled preview in his browser (not verified live)
- Push only after explicit OK

### 2026-10-15 13:23
**Experience export adjustments + DB: Galium album verified, GBIF lineage backfill for 7 species; snapshot db_20261015_132210**

**Built:**
- gates: page-level apiaceae_id_only (all Apiaceae = look-alike/ID cards, no edible label, no recipe; build fails if violated)
- recipes: Friture Sauvage (Melvin own menu) allowed; source priority curator > own menu > ai_generated; same dish never shown twice
- disclaimer_override (web wording) in config
**Fixed:**
- 183 Galium album verified human (status already edible)
- Genus corrected 134 Stellaria->Polygonum, 233 Scorzoneroides->Hypochaeris (GBIF conflict gate)
- GBIF lineage via app/integrations/gbif.enrich_species_taxonomy for 58,134,233,293,329,488,710 - all EXACT; tree now 51/51 placed
- History rows for verification, genus and lineage fields
**Files:** `data/foragingid.db`, `scripts/experience_export/gates.py`, `scripts/experience_export/export.py`, `scripts/experience_export/config.json`
**Pending:**
- Melvin: approve web disclaimer wording
- Melvin: review preview; push only after explicit OK
- Impressum page to be created before go-live

### 2026-10-15 13:22
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_132210.sqlite`

### 2026-10-15 13:09
**Experience export: Impressum URL + host page set; links open in top window for the Hostinger embed**

**Built:**
- config: host_page_url https://melvinjarman.co.uk/b, impressum_url https://melvinjarman.co.uk/impressum
- canonical link to host page; CTA/Contact/Impressum target=_top
**Files:** `scripts/experience_export/config.json`, `scripts/experience_export/templates/index.html`, `scripts/experience_export/export.py`
**Pending:**
- Impressum page must exist on melvinjarman.co.uk before go-live
- Push to melvinoj/foraging-experience only after explicit OK

### 2026-10-15 13:02
**Foraging Experience static export built (walk 4 Rümmelsbühl foray) - dist/ preview only, not pushed**

**Built:**
- scripts/experience_export/: export.py, gates.py (single gate module), config.json, templates/index.html + tree.html
- dist/index.html: Walk (Leaflet 1.9.4 app SRI, saved route, 26 numbered stops, 4 red ☠ stops), Plants (taxonomy tree iframe + species cards), Recipes (19 teasers), footer disclaimer verbatim from print_pdf.html
- dist/tree.html: frontend/taxonomy.html style+script reused at build time with 9 anchored patches (fail if anchor count changes); d3 7.8.5 with sha384 SRI
- Photos: 51 species x (1200px + 400px), re-encoded from pixels, exiftool + PIL: 0 GPS, 0 EXIF
**Fixed:**
- dist/ added to .gitignore
**Files:** `scripts/experience_export/export.py`, `scripts/experience_export/gates.py`, `scripts/experience_export/config.json`, `scripts/experience_export/templates/index.html`, `scripts/experience_export/templates/tree.html`, `.gitignore`
**Pending:**
- Impressum URL placeholder - Melvin to supply; do not publish until set
- Melvin to review preview + teasers (Sambucus raw line, florid old recipes 130/136/137, caution-species recipes Artemisia/Sambucus/H. perforatum)
- Apiaceae: Aegopodium shows Edible, Anthriscus sylvestris shows Edible with caution (both human-authored edible_parts) - confirm
- Galium album 183 never reviewed (missed from my Rümmelsbühl table) - shows For identification
- 7 species lack class/order lineage - not in tree (in list)
- Push to melvinoj/foraging-experience only after explicit OK

### 2026-10-15 10:52
**Genista re-ID + final Rümmelsbühl verifications; snapshot db_20261015_105153**

**Fixed:**
- obs 17889 Genista tinctoria -> Genista sagittalis (correct-species); 21621 stays G. tinctoria
- 585 Genista tinctoria verified human (status already caution/none - unchanged)
- 214 Leucanthemum vulgare, 208 Knautia arvensis verified human as-is (edible)
- kingdom Plantae on 142 Thymus polytrichus, 319 Rubus gratus; 5 history rows
**Files:** `data/foragingid.db`

### 2026-10-15 10:51
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_105153.sqlite`

### 2026-10-15 10:44
**Rümmelsbühl foray (saved_walks id 4) review applied: snapshot db_20261015_104334 -> 8 re-IDs (correct-species) -> 10 status changes + 41 human verifications -> family/name fixes**

**Fixed:**
- Re-ID: 21910->H. perforatum, 9442->Knautia arvensis, 22146->Atriplex patula, 17760->Leucanthemum vulgare, 9430/9431/17687->Thymus pulegioides, 22178->Rubus fruticosus
- Status: 58 Dryopteris toxic/toxic; 194 Tanacetum caution; 98 Artemisia vulgaris caution; 35 Carex + 380 Briza inedible/none; 701 Atriplex patula edible; 677, 702 Hypericum caution; 710 Rosa villosa edible; 794 Sparassis crispa edible
- 41 species verified human; 52 edibility history rows
- Families: 58 Dryopteridaceae, 134 Polygonaceae, 329 Fagaceae, 488 Pinaceae, 293/319/710 Rosaceae (710 kingdom Plantae), 142 Lamiaceae, 273 Asteraceae; names: 210 EN Nottingham catchfly, 329 DE Rotbuche (Blutbuche removed), 341 DE Moschus-Malve (Abelmoschus, Indische Hibiscus-Malve removed); 13 history rows
**Files:** `data/foragingid.db`
**Pending:**
- Hold 585 Genista tinctoria: obs 17889 (iNat G. sagittalis 0.951) + 21621 - Melvin to recheck photos
- Leucanthemum vulgare (214) edible unverified; Knautia arvensis (208) edible unlocked_for_review - Melvin to decide
- Cleanup backlog: zero-obs cards 108, 491, 744, 810 (+ any others listed)
- Kingdom NULL on 142 Thymus polytrichus, 319 Rubus gratus

### 2026-10-15 10:43
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_104334.sqlite`

### 2026-10-15 10:37
**Re-ID obs 17188 Anthriscus caucalis -> Daucus carota (correct-species path); Hypericum perforatum (229) edible -> caution, human-verified; snapshot db_20261015_103654**

**Fixed:**
- obs 17188 now Daucus carota, species_id 9, identified, manually_verified
- species 229 Hypericum perforatum: edibility_status caution, toxicity none, verified=1 by human; 2 species_edibility_history rows (reason: photosensitivity)
**Files:** `data/foragingid.db`
**Pending:**
- Card 138 Anthriscus caucalis keeps 1 obs; inedible+toxic contradiction still open (Melvin)
- Backlog cleanup: cards 810, 108 have 0 obs
- saved_walks id 3 waypoint labels are stale (canadensis, humifusum, caucalis) - stored at save time

### 2026-10-15 10:36
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_103654.sqlite`

### 2026-10-15 10:33
**Re-ID obs 24234 Hypericum humifusum -> Hypericum perforatum via correct-species path; snapshot db_20261015_103337**

**Fixed:**
- obs 24234 now H. perforatum, species_id 229, identified, manually_verified, human_corrected=1
**Files:** `data/foragingid.db`
**Pending:**
- Backlog cleanup: card 810 Hypericum humifusum and card 108 Sambucus canadensis now have 0 observations
- SAFETY: Hypericum perforatum (229) edibility edible, unverified, toxicity none - now on little foray walk; Melvin to decide (caution/photosensitivity like 810/381?)
- Anthriscus caucalis (138) hold: walk obs 17188 photo check (A. sylvestris / Chaerophyllum temulum?)

### 2026-10-15 10:33
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_103337.sqlite`

### 2026-10-15 10:26
**Re-ID Sambucus canadensis -> Sambucus nigra (obs 17807, 9392, 8345, 20881) via PATCH /api/observations/{id}/correct; snapshot db_20261015_102637**

**Fixed:**
- 4 obs now Sambucus nigra, species_id 107, identified, manually_verified, human_corrected=1; observation_edits rows 19516-19523; 0 Sambucus canadensis obs remain
**Files:** `data/foragingid.db`
**Pending:**
- Anthriscus caucalis (138): Melvin to choose toxicity (none/caution/toxic) - placeholder not filled, nothing written
- Species card 108 Sambucus canadensis now has 0 observations - add to junk-card cleanup (needs OK)
- saved_walks id 3 waypoint labels still say Sambucus canadensis (stored at save time)

### 2026-10-15 10:26
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_102637.sqlite`

### 2026-10-15 10:19
**Human edibility verification of 'little foray' walk species (Melvin-approved list); snapshot db_20261015_101900 first**

**Fixed:**
- Verified as-is (status unchanged, verified_by=human): 690, 185, 376, 9, 670, 201, 346, 273, 186, 189, 6, 369, 93, 107
- Status set + verified: 763 Atropa bella-donna unknown->toxic/deadly; 719 Senecio ovatus unknown->toxic/toxic; 764 Artemisia absinthium unknown->caution; 810 Hypericum humifusum unknown->caution (photosensitivity); 381 Hypericum tetrapterum edible->caution (photosensitivity); 762 Melampyrum pratense unknown->inedible
- 28 species_edibility_history rows written (changed_by=human); direct SQL, no drafts/enrichment triggered; all 20 rows re-queried by ID
**Files:** `data/foragingid.db`
**Pending:**
- Hold: 108 Sambucus canadensis - obs 17807 on walk (also 9392 Gresgen, 8345/20881 Sheffield) likely S. nigra, Melvin to re-ID
- Hold: 138 Anthriscus caucalis inedible+toxic contradiction - Melvin to decide
- Backlog: Erigeron annuus (273) family='Erigeron' should be Asteraceae
- Backlog: species_edibility_history was empty for all species before today (23 human-verified species had no audit rows)

### 2026-10-15 10:19
**Snapshot** — Manual snapshot
DB: `snapshots/db_20261015_101900.sqlite`

### 2026-10-15 10:08
**Daucus carota verification audit (read-only) + walk builder fixes a-d from Melvin's browser test; 2e duplicates already deleted**

**Built:**
- Walk save: in-flight guard (second click ignored while prompt/request open), 'Saved as <name>' status line + button '✓ Saved', warn if same route already saved/loaded (route signature) or same name already in saved list
- Walk header/summary/minimise bar show the saved or loaded walk's name while the route matches it; falls back to 'Walk Route (N stops)' after regroup/loop toggle/new selection or deletion
- Centroid clustering second pass: pins > R from their stop's final centre move to nearest stop within R or start a new stop; repeat until stable (cap 10)
**Fixed:**
- Duplicate summary header: #wbs-summary now phone-only (laptop shows walk-title header only)
- Centre drift: Gresgen ±0.02° box R=30 max 42.1->29.7 m, R=100 max 141.0->97.5 m; 'little foray' pins had no drift (max 26.6 m at R=30, unchanged)
**Files:** `frontend/index.html`
**Pending:**
- Melvin to verify walk fixes a-d live
- Daucus carota: edibility_verified=0, verified_by NULL, no species_edibility_history rows (table empty for ALL species). No UI path can verify an already-'edible' species: Edibility Review queue excludes edible; species-card dialog sends 'edible' status-only (verified untouched). Needs a decision/backend change (app/)
- saved_walks: only id 3 'little foray' remains (ids 2 and 4 deleted via UI DELETE in server_20261015_081452.log)
- Backend: GET /api/walk/saves stop_count counts obs_ids (39) not waypoints (20) for v2 walks

### 2026-10-15 10:02
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261015_100246.sqlite`

### 2026-10-15 10:02
**Session ended** — Session ended from Settings page

### 2026-10-15 09:51
**Walk builder Stage 2: stops by centroid clustering, stop-radius slider, ORS 50-waypoint cap, real ORS failure reasons with opt-in straight line, Google Maps export note. Frontend only (frontend/index.html).**

**Built:**
- _clusterStops: pin joins a stop only if within R of the stop CENTRE (centre recomputed as pins join); one stop = one waypoint with many species; notes stay separate
- Stop radius slider (10-100 m, default 30) in the route row; regroups the last drawn selection, ORS call debounced 600 ms; stale ORS responses ignored (_walkBuildSeq); disabled for loaded walks (fixed stops), shows saved radius
- Stop cap: >50 stops (49 when circular - return point) -> no ORS call, clear message + one-tap Increase radius (smallest 5 m step <=100 m that fits)
- ORS failures show the actual reason (rate limit / timeout / no key / no route / server / network) with Retry and an opt-in 'Draw straight line instead' (dashed, tooltip + status say straight line); distance labelled 'straight-line' when not from ORS
- Saved walks v2: waypoint per stop {type:'obs', lat, lng, obs_ids[], labels[]}; foragingid {version:2, circular, stop_radius_m}; loadSavedWalk reads v2, v1 (single obs_id) and untyped old walks
- Stop card lists every species at the stop; Stage 1 toxic guard applied per species
**Fixed:**
- Google Maps export: was dropping middle stops beyond 8 silently while keeping the last stop; now exports the first 10 points in order (start + 8 + end), closes the loop for circular walks when it fits, and shows 'exporting stops 1-10 of N'
**Files:** `frontend/index.html`
**Pending:**
- Live click-through by Melvin (not browser-verified by Claude per CLAUDE.md)
- Centroid drift: members can end up beyond R from the final centre (live Gresgen data: up to 42 m at R=30, 104 m at R=75) - optional refinement pass to reassign stragglers
- Proximity alerts and the summary export still read one representative species per stop (s.p) - multi-species stops show only the first there
- Dense Gresgen selections (e.g. 665 pins) exceed 50 stops even at 100 m - by design: message asks for a smaller area

### 2026-10-15 09:44
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20261015_094404.sqlite`

### 2026-10-15 09:44
**Session ended** — Session ended from Settings page

### 2026-10-15 08:12
**Identification fixes Stage A (safety-critical). Snapshot: db_20261015_080820.sqlite. Items 1+2 implemented; item 3 STOPPED (dependencies found). Dry-run on a scratch DB copy for obs 24077/24167/24221/24222; live rows untouched.**

**Built:**
- Disagreement promotion (scan.py): when PlantNet and iNat top names differ and iNat's location-ranked #1 is in PlantNet's top 5, it becomes the top/suggested ID with its OWN PlantNet score; never counts toward dual agreement/auto-approve (explicit _promoted_from guard in _dual_agree); always needs_review; logged with a [promoted: ...] note; candidate entry carries promoted_over
- iNat vision + combined (location-weighted) scores stored per candidate (species_candidates_json keys inat_vision_score / inat_combined_score; SpeciesCandidate.api_response_raw JSON)
- dual_source_agreement now written: 1 = top names agree, 0 = disagree or single source, NULL = no candidates (model comment corrected; historical values untouched)
**Fixed:**
- inaturalist.py: gating score = min(vision, combined) as documented (code used vision alone). Can only lower iNat scores -> fewer auto-approves, never more. Docstring + CLAUDE.md updated.
**Files:** `app/integrations/inaturalist.py`, `app/api/scan.py`, `app/models/observation.py`, `CLAUDE.md`
**Pending:**
- Item 3 (cards only on approval) NOT done - dependencies: trust.py accept-species and the dual-agree auto-approve path create no card; species_id linking for later-created cards relies on the init_db startup backfill; taxonomy OBS_STATE 'in_review' and the edibility review queue are built from cards; enrichment/safety info would no longer be ready at review time
- Dry-run: 24077 -> Verbascum thapsus suggested (below 30%, unidentified), 24167 -> Larix decidua suggested; 24221/24222 unchanged (iNat #1 not in PlantNet top 5) - needs the GBIF range flag
- Promoted IDs usually fall below min_identification_confidence (0.3) and land as below_threshold with species_suggested - no species assigned, no card created
- reidentify.py also uses inat_score: its displayed iNat scores drop the same way
- Cleanup of existing cards/obs (Aspalathus, Ambrosia, Larix occidentalis/lyallii, Verbascum boerhavii) awaits OK

### 2026-10-15 07:55
**Launcher: tee now ignores Ctrl+C so uvicorn shutdown output reaches the log**

**Fixed:**
- START_ForagingID.command: pipe to (trap  INT; exec tee -a "$LOG") - tee no longer exits on the same Ctrl+C; ends when uvicorn closes the pipe; window close (SIGHUP) still stops it. Swapped in via temp file + mv so the running launcher was unaffected. Isolated test: old pipeline lost the shutdown line, new one kept it.
**Files:** `START_ForagingID.command`
**Pending:**
- Takes effect on next launch; confirm the log ends with Application shutdown complete after Ctrl+C

### 2026-10-15 07:50
**Walk builder Stage 1: three save/load bugs + toxic guard (frontend only). Also: ngrok shutdown fix (sharing.stop_ngrok_subprocess + lifespan), done earlier with the server stopped.**

**Built:**
- Walk panel toxic guard: recipe snippets hidden when toxicity_severity is toxic/deadly (same rule as print_pdf.html:380), fail-closed when toxicity can't be read; badge shows the toxicity warning instead of any edibility label
- Saved walks keep route shape + circular flag in route_geojson (FeatureCollection + 'foragingid' foreign member {version, circular}) - no migration, no backend change
**Fixed:**
- promptSaveWalk: field-note stops no longer stored as observation ids (obs_ids excludes notes; waypoints {type:'note', note_id} / {type:'obs', obs_id})
- loadSavedWalk: reads old walks (label 'Note' + legacy obs_id read as note id); restores circular flag; draws saved geometry without re-calling ORS; never overwrites saved distance/duration; old walks without geometry still re-route for drawing only, loop closed when circular
- ngrok: app now stops its own ngrok subprocess on every graceful shutdown incl. --reload restarts (implemented, unverified live)
**Files:** `frontend/index.html`, `app/api/sharing.py`, `app/main.py`
**Pending:**
- Live check (Melvin): walk Stage 1 click-through + ngrok stop on Ctrl+C / reload
- Toxicity comes from /api/species/{name}/profile (1 extra request per species) - cleaner: add toxicity_severity to GET /api/culinary/{name} (backend, 1 line)
- Not in scope, still unguarded: culinary-notes hint (edible_parts/taste_notes) on toxic stop cards; exportWalkSummary; the walk-sheet species list (_wbsRenderLasso) badges
- Saved walk 1 'Ewden brook circular' predates the flag - loads one-way; re-save to store circular
- New walks: list 'N stops' counts observation stops only (backend stop_count = len(obs_ids)); notes no longer counted
- Launcher: tee exits on Ctrl+C so uvicorn shutdown lines are missing from the log - fix proposed, awaiting OK

### 2026-10-15 07:32
**Server process discipline + follow-up data work + read-only review of today's species cards. Snapshot: db_20261015_072953.sqlite.**

**Built:**
- START_ForagingID.command rewritten: uvicorn in the FOREGROUND (no '&'), output tee'd to logs/server_<ts>.log, port check instead of kill -9, cleanup trap (EXIT INT TERM HUP), --host 0.0.0.0, init_db pre-step dropped (lifespan runs init_db at main.py:132), ngrok not handled by the launcher (Settings -> Start sharing)
**Fixed:**
- Root cause of orphaned servers: bash makes '&' background commands in a script ignore SIGINT, so Ctrl+C killed the launcher but not uvicorn (re-parented to launchd)
- Re-enriched Alnus alnobetula (797), Melampyrum nemorosum (787), Salix aurita (795): culinary_info 767/768/769, 5 sources each, 1 pending medicinal_notes draft each; edibility unchanged (unknown, unverified)
- Obs 24065 retried (force_review=True): needs_review / below_threshold, Pinus sylvestris 10.2% < 30%, no species assigned
- Deleted 2 unreferenced orphan pipeline2 copies (7b0c5e25..._PXL_20260930_091034691.jpg, 7972b94d..._PXL_20261001_065044808.jpg)
**Files:** `START_ForagingID.command`
**Pending:**
- Orphan thumbnails for the 2 deleted copies still in data/thumbnails (awaiting OK)
- App does not stop its ngrok subprocess on server shutdown (lifespan) - only dies via process-group signal (Ctrl+C / window close); a --reload worker restart or kill -INT leaves the tunnel up
- observations.dual_source_agreement never populated (NULL on all 232 phone obs ingested 15 Oct)
- Implausible IDs awaiting review (all needs_review, none approved): Aspalathus retroflexa 24221, Ambrosia confertiflora 24222, Larix occidentalis 24167, Larix lyallii 24068/24166/24174, Verbascum boerhavii 24077/24188; Gentiana verna 24059/24149 (season)
- Species cards are created for below-review top candidates (>30%) - source of implausible cards
- Lock fix: watch the next P1 batch under the new launcher (no new files at 07:31)

### 2026-10-15 07:21
**SQLite write-lock contention fix (15 Oct 2026 'database is locked' storm during P1 ingest). Snapshots: db_20261015_064059.sqlite (taken while an orphaned server was still running — .backup is consistent), db_20261015_064330.sqlite (taken after it was stopped, before any edit). Verified live on the next P1 batch (90 files): 0 'database is locked', 0 tracebacks; all 14 new species cards enriched only after their batch / orphan_sweep finished, one at a time.**

**Built:**
- app/services/enrich_gate.py: in-memory ingest registry (ingest_active/ingest_done, 300s stall release), new-species enrichment queue + single worker, shared enrichment_slot Semaphore(1)
- Ingest priority: P1 _process_all, P1 _reprocess_ids, P2 sessions (upload / process-delta / retry-id / Job Queue folder-identify), P2 archive scan, reprocess-pending batch, orphan_sweep all register with enrich_gate; _upsert_species_card queues enrichment instead of create_task; _run_enrichment_task holds the shared slot and (trigger=auto) waits for idle ingest
**Fixed:**
- enrich_species: transaction A (sources + culinary_info) committed before fungi lookup / AI drafts; drafts generated with no write transaction open (no_autoflush); re_enrich invalidation moved after LLM calls with equivalent covered-status query - WHEN changed, not WHAT
- P1 _ingest_file: classify_plant_likelihood before the INSERT; it and generate_thumbnail via asyncio.to_thread; failed INSERT removes that attempt's pipeline2 copy + thumbnail (commit-guarded)
- database.py: lock wait 10s -> 30s; PRAGMA busy_timeout=30000 and synchronous=NORMAL on every connection via connect hook
**Files:** `app/services/enrich_gate.py (new)`, `app/services/enrichment.py`, `app/api/scan.py`, `app/api/syncthing.py`, `app/api/enrich.py`, `app/services/orphan_sweep.py`, `app/database.py`, `CHANGELOG.md (pending note)`
**Pending:**
- Enrichment queue is in-memory: after ANY restart, check the backfill panel for un-enriched cards
- Follow-up data work awaiting OK: re-enrich Alnus alnobetula, Melampyrum nemorosum, Salix aurita; retry obs 24065; remove 2 orphan pipeline2 copies (7b0c5e25..._PXL_20260930_091034691.jpg, 7972b94d..._PXL_20261001_065044808.jpg)
- Pre-existing, not changed: re_enrich invalidates a just-queued pending fungi edibility suggestion draft (behaviour preserved, flag for review)
- Not gated (out of scope): culinary.py enrichment_run batch runner; trigger_ai_drafts_for_species path; ITIS trigger task
- START_ForagingID.command backgrounds uvicorn with & - server survives closing the terminal (cause of today's orphaned server)
- Leaflet SRI fix (frontend/index.html, review.html, species.html) still awaiting browser confirmation

### 2026-08-02 08:02
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260802_080254.sqlite`

### 2026-08-02 08:02
**Session ended** — Session ended from Settings page

### 2026-07-29 09:06
**Phase 3e-1b — client consumes controls descriptor; capability lists moved to single home (process_controls.py)**

**Built:**
- process_controls.py is now the single home for all four control vocabularies: CANCELLABLE_TYPES and RESUME_ROUTES moved in from processes.py as module-level constants alongside _SESSION_PAUSE_TYPES/_QUEUE_CANCEL_TYPES
- Lazy import (_authoritative_sets) removed — the processes->background_processes->process_controls cycle is gone now that process_controls is a true leaf
- processes.py imports the two constants from process_controls; endpoints (/pause guard, /cancellable-types) and settings.html consumer unchanged
- job-status-widget.js renders per-row buttons straight from the server controls descriptor (one button per non-null key: resume/pause/end/dismiss), fail-closed to no buttons when controls is absent
- Client click handlers (__jswResume/__jswPause/__jswEnd/__jswDismiss) post it.controls.<key>.url verbatim
**Fixed:**
- Removed dead stalled branch in _queue_controls: queue rows surface stale running as interrupted (queue_api._row_to_dict), never stalled, so the stalled test was unreachable
- Deleted client-side capability machinery: SESSION_PAUSE_TYPES, QUEUE_CANCEL_TYPES, cancellableProcessTypes/resumeRoutes/pausableProcessTypes, _loadCancellableTypes fetch, the four *Target() functions, the session-id detail regex, and the 3e-1a parity shim plus its deferred-guard
- Dropped the now-unused detail field carried on process rows (session id parsed server-side)
**Files:** `app/services/process_controls.py`, `app/api/processes.py`, `frontend/static/js/job-status-widget.js`
**Pending:**
- LIVE VERIFICATION OWED (user, per CLAUDE.md): running auto_enrich shows Pause+End; paused shows Resume+End from descriptor URLs; one POST per click to the descriptor URL; no console error on a controls-less row; buttons appear on first poll (no async load-race delay)
- 3e-2 server-side serialization (separate session)
- 3e-3 UI consolidation: render restart, scan.html queue panel, review.html enrichment banner de-dup

### 2026-07-29 08:48
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260729_084855.sqlite`

### 2026-07-29 08:48
**Session ended** — Session ended from Settings page

### 2026-07-28 07:36
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260728_073659.sqlite`

### 2026-07-28 07:36
**Session ended** — Session ended from Settings page

### 2026-07-23 22:12
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260723_221256.sqlite`

### 2026-07-23 21:40
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260723_214021.sqlite`

### 2026-07-23 21:40
**Session ended** — Session ended from Settings page

### 2026-07-23 21:14
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260723_211406.sqlite`

### 2026-07-23 21:14
**Session ended** — Session ended from Settings page

### 2026-07-23 20:41
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260723_204119.sqlite`

### 2026-07-23 08:20
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260723_082009.sqlite`

### 2026-07-23 07:45
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260723_074531.sqlite`

### 2026-07-23 05:38
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260723_053847.sqlite`

### 2026-07-22 20:43
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260722_204314.sqlite`

### 2026-07-22 20:43
**Session ended** — Session ended from Settings page

### 2026-07-22 08:42
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260722_084247.sqlite`

### 2026-07-22 07:06
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260722_070612.sqlite`

### 2026-07-21 21:21
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260721_212105.sqlite`

### 2026-07-21 20:58
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260721_205825.sqlite`

### 2026-07-21 20:58
**Session ended** — Session ended from Settings page

### 2026-07-21 19:26
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260721_192653.sqlite`

### 2026-07-21 16:43
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260721_164318.sqlite`

### 2026-07-21 08:01
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260721_080125.sqlite`

### 2026-07-20 22:10
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260720_221051.sqlite`

### 2026-07-20 22:10
**Session ended** — Session ended from Settings page

### 2026-07-20 22:10
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260720_221009.sqlite`

### 2026-07-20 22:10
**Session ended** — Session ended from Settings page

### 2026-07-20 21:51
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260720_215128.sqlite`

### 2026-07-20 21:32
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260720_213251.sqlite`

### 2026-07-20 19:13
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260720_191317.sqlite`

### 2026-07-20 19:05
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260720_190529.sqlite`

### 2026-07-20 18:42
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260720_184211.sqlite`

### 2026-07-20 15:17
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260720_151717.sqlite`

### 2026-07-20 15:15
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260720_151504.sqlite`

### 2026-07-20 15:15
**Session ended** — Session ended from Settings page

### 2026-07-20 09:55
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260720_095533.sqlite`

### 2026-07-20 06:32
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260720_063250.sqlite`

### 2026-07-20 06:32
**Session ended** — Session ended from Settings page

### 2026-07-19 21:56
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260719_215647.sqlite`

### 2026-07-19 21:56
**Session ended** — Session ended from Settings page

### 2026-07-19 21:49
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_214921.sqlite`

### 2026-07-19 16:59
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260719_165927.sqlite`

### 2026-07-19 16:59
**Session ended** — Session ended from Settings page

### 2026-07-19 16:50
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_165039.sqlite`

### 2026-07-19 11:27
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_112749.sqlite`

### 2026-07-19 11:14
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_111420.sqlite`

### 2026-07-19 10:55
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_105503.sqlite`

### 2026-07-19 10:45
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_104558.sqlite`

### 2026-07-19 09:13
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_091303.sqlite`

### 2026-07-19 08:50
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260719_085020.sqlite`

### 2026-07-19 05:55
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260719_055536.sqlite`

### 2026-07-19 05:55
**Session ended** — Session ended from Settings page

### 2026-07-18 08:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260718_080919.sqlite`

### 2026-07-18 08:09
**Session ended** — Session ended from Settings page

### 2026-07-18 07:56
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260718_075603.sqlite`

### 2026-07-18 07:56
**Session ended** — Session ended from Settings page

### 2026-07-18 06:40
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260718_064023.sqlite`

### 2026-07-18 05:57
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260718_055724.sqlite`

### 2026-07-18 05:57
**Session ended** — Session ended from Settings page

### 2026-07-17 21:34
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_213411.sqlite`

### 2026-07-17 21:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260717_210939.sqlite`

### 2026-07-17 21:09
**Session ended** — Session ended from Settings page

### 2026-07-17 21:04
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260717_210447.sqlite`

### 2026-07-17 21:04
**Session ended** — Session ended from Settings page

### 2026-07-17 20:45
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_204557.sqlite`

### 2026-07-17 20:22
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_202238.sqlite`

### 2026-07-17 12:56
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260717_125657.sqlite`

### 2026-07-17 12:56
**Session ended** — Session ended from Settings page

### 2026-07-17 12:52
**Cleared the gate-clobbered prefilter_category on the 11. Restored to the prefilter own logged verdict (plant), recovered from syncthing_ingest logs — not guessed. Band-only: zero status/ident/category changes. Closes the kingdom-gate pass.**

**Pending:**
- SNAPSHOT db_20260717_125003.sqlite (commit 687a2db7) before the write
- DERIVED BY PREDICATE: exactly 11 — 21311, 21312, 21322, 21412, 21446, 21863, 21891, 21965, 21992, 22003, 22050
- ORIGINAL BAND RECOVERED, NOT INVENTED: every one of the 11 has its own syncthing_ingest log reading prefilter=plant conf=0.900, and the logged conf matches the row stored plant_detect_confidence exactly — which ties the log to the row. 11/11 recoverable, 0 guessed. Restored prefilter_category person_animal -> plant
- VERIFIED per row: all 11 band=plant, is_plant_likely=1, conf=0.9, needs_review, original AND thumbnail on disk
- 18180 (conf 0.117) and 19361 (conf 0.05) UNTOUCHED — still band=person_animal, plant_likely=0. They genuinely failed the prefilter; their band may be the prefilter own verdict. Separate question, left alone
- BAND-ONLY CONFIRMED vs snapshot: prefilter_category changed on exactly 11 rows. review_status changed on 0 rows. identification_status changed on 0 rows. obs_category changed on 0 rows. observations row count unchanged 13836, max id unchanged 22140
- AUDIT: 11 observation_edits rows, edited_by=system:kingdom_gate_band_repair — deliberately NOT human, since per CLAUDE.md changed_by=human is the human-lock marker and this is a machine correcting a machine false write. Plus 11 processing_logs entries recording the provenance of the restored value
- GUARD RAILS: Mammalia 68 rejected + 3 needs_review (unchanged). Keepers 141/141 pending with files, none touched. 21212/21215/21216 never_reject=1 thumbs intact. The 9 stalled 9/9 needs_review. 5 private DELETEs pending with files. deleted_hashes 12
- KINGDOM-GATE PASS CLOSED. Out of scope / separate decisions: 68 Mammalia, 5 Aves, 2 Animalia, 1 Chromista, 1 Reptilia, 1 Mollusca still rejected (all recoverable); identification.py:324 no-candidates gate still auto-rejects + deletes + ignores force_review (likely mechanism behind the 2,083)

### 2026-07-17 12:50
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_125003.sqlite`

### 2026-07-17 12:42
**Restored the 13 Insecta kingdom-gate rejections to needs_review. Files hash-verified from Syncthing source (11) and DIGIERA (2). Mammalia untouched. Exactly 13 rows changed.**

**Pending:**
- SNAPSHOT db_20260717_123904.sqlite (commit 9c4d65fd) before the write
- SPLIT CONFIRMED: 13 Insecta = 11 Syncthing-source + 2 DIGIERA. Every Syncthing-source kingdom-gate row is Insecta, as Melvin said
- RESTORED 13/13 files, sha256 verified per row, zero mismatches, thumbnails regenerated. Routed to needs_review + review_label=non_plant. No identification re-run, no approvals, no obs_category/prefilter/edibility changes
- VERIFIED per row: all 13 needs_review with original AND thumbnail on disk
- MAMMALIA UNTOUCHED: 0 rows changed by this pass. 71 distinct Mammalia rows — 68 rejected + 3 needs_review (20223/21178/21250, restored in the earlier pass, not this one)
- COUNT CORRECTION: my earlier audit reported Mammalia 73 / Insecta 13 — those were LOG ROW counts. Distinct observations: Mammalia 71 (obs 19447 has 3 duplicate gate logs), Insecta 13 (13 log rows = 13 distinct, so the Insecta figure was right). No data discrepancy; my expectation was wrong
- EXACTLY 13 rows changed DB-wide vs snapshot: 18180, 19361, 21311, 21312, 21322, 21412, 21446, 21863, 21891, 21965, 21992, 22003, 22050. Deltas: needs_review 51->64 (+13), rejected 11467->11454 (-13), observation_edits +13, processing_logs +13. observations row count unchanged 13836, max id unchanged 22140
- deleted_hashes UNTOUCHED at 12. None of the 13 was blacklisted. The 7 DELETE foreclosures hold
- GUARD RAILS: keepers 141/141 pending with files, none touched. 21212/21215/21216 never_reject=1 thumbs intact. The 9 stalled all still needs_review. 5 private DELETEs pending with files
- OPEN ITEM (not actioned, out of scope per no prefilter changes): all 13 carry prefilter_category=person_animal, written by the gate. 11 of 13 contradict it with is_plant_likely=1 conf=0.900 — the prefilter passed them as plant and the gate then relabelled the band. They will show a person_animal badge in review, which is not the same footing as any other card. 18180 (conf 0.117) and 19361 (conf 0.05) genuinely failed the prefilter, so a blanket revert would be wrong. Needs Melvins call
- REMAINING kingdom-gate rejections not in scope: 68 Mammalia, 5 Aves, 2 Animalia, 1 Chromista, 1 Reptilia, 1 Mollusca

### 2026-07-17 12:39
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_123904.sqlite`

### 2026-07-17 12:28
**iNat kingdom gate now routes to needs_review and never deletes; fixed on BOTH paths (scan.py + identification.py twin). 20223 restored from DIGIERA hash-verified, completing 4/4. Audit: 93 historical gate rejections, ALL recoverable, zero gone.**

**Fixed:**
- scan.py:1250 kingdom gate — review_status rejected->needs_review, review_label=non_plant, NO delete_observation_file(), _p2_tick files_rejected->files_review. prefilter_category no longer clobbered to person_animal (the prefilter passed these as plant conf 0.900; relabelling them a prefilter rejection was untrue and buried them in the wrong triage band). Note now names candidate+score and frames it as a signal, not a verdict
- identification.py:189 TWIN gate — same fix. It also called _delete_file(). Fixing one path and not the other would have left the destructive path live on half the traffic
- force_review honoured trivially and permanently on both: the branch has no reject path left, only outcome is needs_review
**Files:** `app/api/scan.py`, `app/services/identification.py`
**Pending:**
- SNAPSHOT db_20260717_122157.sqlite (commit 5e52dc6b)
- 20223 RESTORED from /Volumes/DIGIERA/Pictures/2023/IMG_20230725_113806.jpg, sha256 verified identical, thumbnail regenerated. 4/4 damaged rows now have files. ALL 9 needs_review with files+thumbs on disk. 0 orphans
- VERIFY 12/12 behavioural: non-plant top candidate -> needs_review with FILE STILL ON DISK; review_label=non_plant; prefilter_category NOT clobbered; note names candidate+score; force_review honoured; twin path same; normal ID unaffected (real APIs, Corylus 64.35%)
- AUDIT — 97 kingdom-gate rejections logged, 93 still rejected (4 are the ones restored today). Date range 2026-06-06 to 2026-07-17. Score distribution: min 5.1%, median 22.2%, max 93.3%. 45/97 rejected on <20% confidence, 29/97 on <10%
- AUDIT RECOVERABILITY: 82 recoverable from DIGIERA, 11 from Syncthing source, 0 still on disk, ZERO PERMANENTLY GONE. Nothing restored — Melvins call, separate decision
- AUDIT PATTERN: 73 Mammalia (mostly Canis familiaris / Homo sapiens — plausibly genuine dog/people photos, though 29 were <10% noise). 13 Insecta — ALL from Syncthing source and ALL plant-dwelling: gall wasps (Andricus foecundatrix = oak artichoke gall, Bassettia flavipes), leaf miners (Caloptilia negundella), aphids (Prociphilus fraxinifolii = ash aphid), viburnum beetle, AND Bombus frigidus 51.1% — a BUMBLEBEE, literally the fireweed/bumblebee case CHANGELOG already flagged. These 13 are high-suspicion false rejections: the model named the organism ON the plant instead of the plant
- SEPARATE FINDING, not fixed: identification.py:324 No candidates -> auto-reject ALSO deletes and ignores force_review. It fires on transport failure (if pn_error). scan.py equivalent routes to needs_review instead (P1 must never be auto-rejected on confidence). Asymmetry: P2 file_upload deletes, P1 syncthing does not. Same shape as the 2,083 rejected-on-transport-failure question
- INTEGRITY: all 43 tables EXACT MATCH to pre-write snapshot, max obs id 22140 unchanged. 4 test rows cleaned in FK order + files. Guard rails: keepers 141/141 pending with files, never_reject 3 thumbs intact, 5 private DELETEs pending with files, deleted_hashes 12

### 2026-07-17 12:21
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_122157.sqlite`

### 2026-07-17 12:16
**INCIDENT + FIX. Parts 1-3 implemented and working (prologue guard, durable failure recorder, orphan sweep). But clearing the 9 triggered the iNat kingdom gate, which auto-rejected 4 and unlinked their files. 3 of 4 recovered; 20223 needs DIGIERA remounted.**

**Built:**
- scan.py _mark_identify_failed() — single durable failure recorder, retries 3x on lock contention (the fault that most often lands there), never raises, message=str(exc) per the 16 July no-guessing contract
- scan.py _identify_scanned is now a thin wrapper around _identify_scanned_inner, catching from function entry onward. Covers the 104-line prologue AND the inner handler failing under the same contention. 6-line diff instead of re-indenting 93 lines of a 499-line live function
- syncthing.py _run_identification except now calls _mark_identify_failed — was in-memory counters only, lost on restart
- app/services/orphan_sweep.py — periodic sweep for stage=ingested with no identify log. Takes the same pipeline mutex as P1/archive via pipeline_try_acquire (non-blocking, skips if a scan holds it, so it can never be the concurrent writer that caused this). 15-min grace period is load-bearing: a row sits at ingested for the whole duration of its own identification, so no grace = double-identify. 10-min cadence, cap 20/cycle, force_review=True, logs every sweep. Wired into lifespan
**Files:** `app/api/scan.py`, `app/api/syncthing.py`, `app/services/orphan_sweep.py`, `app/main.py`
**Pending:**
- SNAPSHOT db_20260717_120523.sqlite (commit b0705273) before the write
- *** INCIDENT: 4 of the 9 auto-rejected -> delete_observation_file fired -> files unlinked. 20223 (dog 6.8%), 20560 (mite 48.4%), 21178 (cat 12.1%), 21250 (cow 9.4%) ***
- *** ROOT CAUSE OF INCIDENT — iNat KINGDOM GATE, scan.py:1250. If iNat top candidate is not plantae/fungi AND score >= 0.05, auto-reject + prefilter_category=person_animal + files unlinked. force_review does NOT veto it — only guards are manually_verified and human_corrected. The 15 July force_review fix covered auto-APPROVE only; auto-REJECT was never covered ***
- THE 5% THRESHOLD IS THE REAL DEFECT. Code comment claims at >=5% confidence the subject is definitively non-target. A 6.8% dog guess is noise, not a verdict. 20560 was rejected on Eriophyes tiliae 48.4% — a LIME GALL MITE that lives on lime leaves, i.e. the photo is almost certainly lime foliage with galls. Same class as CHANGELOG fireweed/bumblebee note but worse: that binned, this DELETES
- RECOVERY: 21178 + 21250 restored from /tmp/foragingid_undo (test script exited before their 30s timers fired). 20560 restored from the Syncthing read-only source dir, sha256 verified identical, thumbnail regenerated. 20223 STILL MISSING — no local copy; was verified present on DIGIERA earlier today; DIGIERA has since been UNMOUNTED. Remount and restore IMG_20230725_113806.jpg
- My first permanently-lost call was WRONG — DIGIERA had been unmounted, so find returned nothing. Corrected.
- ALL 9 now needs_review, 0 orphans remaining (predicate returns empty). 4 test rows 22141-22144 cleaned in FK order, proven gone
- GUARD RAILS INTACT: keepers 141, never_reject 3 (thumbnails on disk), deleted_hashes 12, 5 private DELETEs pending with files
- Behavioural verify 10/12. The 2 failures were NOT the new code — they are the kingdom-gate bug, caught by the test exactly as intended
- NOT FIXED, needs Melvin decision: kingdom gate ignores force_review; 5% threshold; gate auto-deletes files

### 2026-07-17 12:05
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_120523.sqlite`

### 2026-07-17 09:23
**Read-only diagnostic of the 9 stalled pending_identification rows. Root cause: _identify_scanned outer try starts at line 1042 but the function starts at 938 — a 104-line unprotected prologue containing two DB sessions. Exceptions there escape silently. Ceiling is exactly 9.**

**Pending:**
- ID LIST CORRECTION: Melvins list had 20185 and 20623 — both are rejected/not_plant (part of the 1,113 just rejected). The real stalled rows are 20105 and 20223. Correct 9: 20105, 20223, 20560, 20561, 20562, 21178, 21248, 21250, 21251
- ROOT CAUSE: scan.py _identify_scanned spans 938-1437 but its outer try opens at 1042. Lines 938-1041 are UNPROTECTED and contain two AsyncSessionLocal() blocks (977 pause check, 988 category routing). Any exception there escapes the handler at 1425 that would otherwise set failed_identification + write an identify log. Row stays at ingested/pending_identification with zero trace
- P1 AMPLIFIER: syncthing.py _run_identification except block (777-782) catches, increments in-memory _state and scan_sessions.files_failed, then writes NOTHING to the row and NOTHING to processing_logs — not even a log.error. The only durable trace is an integer files_failed on the session row
- P2 PATH: scan.py:538 background_tasks.add_task(_identify_scanned, obs_id, source). An exception in the unprotected prologue propagates to Starlette, app log only, row orphaned. NOT P1-only — 3 of 9 are file_upload, 6 syncthing
- CEILING IS EXACTLY 9. Query: stage=ingested AND no identify log = 9 rows, all pending/pending_identification/band=plant. Date range 2026-06-07 05:46:50 to 2026-06-14 05:26:46. No hidden population
- NOT an interrupted run: stalled rows are INTERLEAVED with successes (21248 stalled, 21249 approved, 21250/21251 stalled). Neighbours identified fine. Individual per-row failures
- CORROBORATION (not proof): database is locked errors occurred 11x on 2026-06-07 and 5x on 2026-06-14 — exactly the two stall dates (67 total, 2026-05-27 to 2026-06-27). Each stall moment had 2-4 rows created in the SAME SECOND = concurrent writers. Consistent with SQLite lock contention throwing in the unprotected prologue. Cannot be proven — the diagnosis was discarded by design and June app logs no longer exist (logs/ starts 2026-06-24)
- NO RETRY SWEEP: nothing in main.py lifespan sweeps stage=ingested or pending_identification. reprocess-pending is manual and filters on file_path substring + review_status. Stalled rows are orphaned permanently
- NOT SURFACED: stats endpoint breaks down by review_status only, no identification_status. review.html had no pending_identification branch until my fix today — these rendered as BLANK CARDS. They were invisible until the queue count forced a look

### 2026-07-17 09:11
**DESTRUCTIVE: rejected 1,113 triaged non-keeper not_plant rows through the bulk reject path. Scope corrected from 1,122 to 1,113 — the 9 pending_identification rows were never triaged and 7 of them are not on DIGIERA.**

**Pending:**
- SNAPSHOT db_20260717_090803.sqlite (commit 1a3d24f2) before the write. Earlier db_20260717_090137 covers the stop-and-report pass
- SCOPE CORRECTED: Melvin approved 1,113 not 1,122. The 9 pending_identification rows (band=plant, is_plant_likely=1, conf=0.9, ZERO identify logs) were never on any contact sheet — the 25 sheets covered exactly the 1,262 not_plant rows per band; no plant band sheet exists. 7 of the 9 are NOT on DIGIERA (six PXL_2026 phone photos post-date the DIGIERA consolidation) so rejecting them would have been permanent
- DIGIERA recoverability verified before writing: 40/40 sampled not_plant reject rows found on DIGIERA (100%). The 1,113 are recoverable
- EXECUTED: 8 batches of 150 via POST /api/bulk/review on the live server (so delete_observation_file 30s hard-delete fires in the server event loop; a standalone script would exit first and orphan files in /tmp). 1,113/1,113 in 22.8s. Undo dir drained to 0 in 20s
- VERIFIED: 1,113/1,113 rejected, 0 originals and 0 thumbnails left on disk, file_hash retained on all 1,113 (dedupe still blocks re-ingest). ALL 141 keepers intact — triage_keep=1, still pending, originals on disk, ZERO touched. 21212/21215/21216 thumbnails intact on disk (8328b/1275b/13209b), never_reject=1. 5 private DELETEs untouched. The 9 pending_identification untouched, files on disk
- INTEGRITY vs pre-write snapshot: observations row count UNCHANGED 13836 (reject keeps rows), max id 22140 unchanged. Only deltas: observation_edits +1113 (audit trail), background_processes +8 (the batches). deleted_hashes still 12 — NO blacklisting this pass, as instructed
- pending 1271 -> 158 (-1113). rejected 10354 -> 11467 (+1113). approved and manually_verified UNCHANGED
- Pending queue now 158 = 141 keepers + 3 never_reject + 5 private DELETEs + 9 pending_identification
- NEXT (separate passes): the 7 DELETEs with blacklist (13623, 13368, 20066, 20053, 20022, 19436, 19437); the 9 pending_identification need Request ID run, not rejection; the 141 keepers go to review via override-prefilter

### 2026-07-17 09:08
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_090803.sqlite`

### 2026-07-17 09:01
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_090137.sqlite`

### 2026-07-17 08:30
**Deleted-hash ingest gate: was P1-only, now enforced on all 5 ingest paths via single shared guard (services/ingest_guard.py). Verified behaviourally on every path: 14/14 assertions. Test rows cleaned in FK order, DB exact-match to pre-test snapshot.**

**Built:**
- app/services/ingest_guard.py — blacklisted_skip(session, hash, source, path). Single implementation of the deleted-hash rule. Uses caller session for the indexed lookup; writes the skip log in its OWN session and commits, because the 5 call sites have incompatible commit conventions and a log added to the caller session would be silently dropped on exactly the paths that matter
- ingestion.py scan_folder now returns blacklisted count separately — was being miscounted as failed by the else branch
**Fixed:**
- RECON CORRECTED THE PREMISE: gap was not P1-vs-P2. FIVE ingest paths exist; only ONE (p1_syncthing) had the check. Unprotected: p2_scan_image, p2_upload, folder_scan (ingestion.py), p2_archive_scan (_run_archive_scan = the DIGIERA rescan, the exact event the blacklist exists to prevent)
- Wired gate into all 5 at the point where hash is known and before any row write. syncthing.py inline check REPLACED by the shared guard — one implementation, five call sites
- DRIFT not deliberate: reflog walk over 21 distinct versions — check has NEVER existed on scan.py/upload.py/ingestion.py in any recoverable commit. Same birth-defect shape as review.html missing else and _dual_agree bypass
**Files:** `app/services/ingest_guard.py`, `app/api/scan.py`, `app/api/upload.py`, `app/services/ingestion.py`, `app/api/syncthing.py`
**Pending:**
- SNAPSHOT db_20260717_082013.sqlite (commit a198957b) before any write
- BEHAVIOURAL VERIFY 14/14 on all 5 real entry points: blacklisted -> 0 rows + skip logged; clean -> row created. p1_syncthing still returns duplicate (counting unchanged); folder_scan returns new blacklisted status
- CLEANUP: 5 test observations (22126-22130) + children deleted in FK order; 1 orphan ingest/success log with observation_id=None initially missed by the FK sweep, found by id-range diff and removed. FINAL: all 43 tables exact-match to pre-test snapshot; max obs id 22125 unchanged
- NO true chokepoint exists — the 5 paths share no common row-writing function. Building one = restructuring ingest, out of scope, NOT done. A BEFORE INSERT trigger was considered and rejected (opaque exception instead of clean logged skip)
- PERMANENCE: deleted_hashes has no removal path. Blacklisting is a PERMANENT foreclosure per hash — that photo can never be ingested again by any path, from any source. The DELETE decision is final. Not adding a removal path (per instruction)
- Lookup scales: EXPLAIN QUERY PLAN confirms SEARCH USING INDEX ix_deleted_hashes_file_hash (UNIQUE). O(log n) at 7, 1130, or 10354
- syncthing.py:157 bulk path (loads all hashes into a set) left as-is — it is a whats-new prefilter, not a row-write gate; the per-file gate at :610 is the actual guarantee
- NEXT (separate passes): reject 1,122; DELETE 7 with blacklist

### 2026-07-17 08:20
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_082013.sqlite`

### 2026-07-17 08:16
**Survivors-only contact sheets built for the 141 keepers (3 sheets). Blacklist recon: blanket blacklist dropped — reject cannot re-ingest. Passport pages 20053/20022 confirmed visually; 19436/19437 found as same-shoot neighbours, added to DELETE set.**

**Built:**
- scripts/make_survivor_sheets.py — reimplementation of the 15 July sheet generator (original was never in the repo). Conventions matched to no_plant_signal_sheet_14.jpg: 2488x1360, 10x6=60/sheet, photo_taken_at asc NULLs last, header band/sheet-no/count/id-range/order, per-photo #id + date
- 3 survivors sheets at ~/Documents/ForagingID/triage_survivors/ — distinct path, original 25 whole-queue sheets untouched (timestamps still 15 Jul 05:26)
**Files:** `scripts/make_survivor_sheets.py`
**Pending:**
- DECISION 1: blanket hash-blacklist DROPPED. Premise was false — reject retains the observations row and file_hash, and scan.py:1783 dedupes on Observation.file_hash, so rejected rows classify as already not new. All 10,354 existing rejections are un-blacklisted and none have re-ingested in 7 weeks. Blacklist matters only for DELETE (row removed)
- GAP (unfixed, reported): P2 — scan.py/upload.py/ingest.py — NEVER checks deleted_hashes. Only P1 syncthing.py:157 and :606 do. The DIGIERA rescan is P2, so a DELETED photo would re-ingest today. Affects the 7 DELETEs, not the rejects
  - **CORRECTION (20 Jul 2026): CLOSED — this gap no longer exists.** The check was extracted into `app/services/ingest_guard.py::blacklisted_skip()` — one implementation, five call sites. Its docstring records the history: *"Until 17 July that guarantee was fictional on four of five ingest paths."* Guarded P2 paths, each **before** the dup check and before any row is written: `scan.py:273` (`p2_scan_image` — the browser scan/upload), `scan.py:2531` (`p2_archive_scan` — the DIGIERA rescan, named in-code as the exact event the blacklist exists to prevent), `ingestion.py:136` (`folder_scan`). There is no `upload.py`; `ingest.py` creates no rows — `_run_scan` delegates to `scan_folder` → `_ingest_one_no_commit`, inheriting the guard. P1 unchanged, now at `syncthing.py:798` + `:211` (the `:157`/`:606` line refs above are stale post-refactor). Proven 20 Jul: 4/4 paths return the skip verdict against a blacklisted hash, 4/4 pass a non-blacklisted hash (negative control), and the real `folder_scan` call site returns `(None, "blacklisted")` creating no row. Run against a throwaway DB copy; live DB sha256 unchanged.
- GAP (unfixed, reported): deleted_hashes is irreversible — no code path removes a row. Manual DELETE FROM only
  - **CORRECTION (20 Jul 2026): half of this still stands, half was wrong.** STILL TRUE: no code path *removes* a row — that is deliberate, not a gap (see `ingest_guard.py` PERMANENCE: blacklisting is a permanent foreclosure, so a DELETE decision must be taken as final). NOW WRONG: population is **not** manual-only. `observations.py:886-896` (`DELETE /{observation_id}`) writes the `DeletedHash` row automatically on hard delete, atomic with row removal — the insert, `db.delete(obs)` (:929) and the single `db.commit()` (:937) are one transaction. This is the **only** hard-delete path in the app (one hit for `db.delete(obs)`/`sql_delete(Observation)` app-wide); the other `delete_observation_file` call sites are reject/prefilter paths that keep the row, so the dup check covers those and they are correctly not blacklisted. Corroboration: `deleted_hashes` is now 15 rows, not the 12 recorded elsewhere in this log.
- DECISION 2: DELETE-with-blacklist set now 7 — 13623, 13368, 20066, 20053, 20022 (pending) + 19436, 19437 (already rejected). 20053/20022 visually confirmed as UK passport photo page on no_plant_signal_sheet_14.jpg. 19436 shares 20053 exact capture second (2024-04-19 10:35:48), 19437 +5min
- REJECT COUNT REVISED: 1,122 = 1,271 − 141 keepers − 3 never_reject − 5 pending private DELETEs. Not 1,124, not ~950
- DECISION 3: 48 screenshots in reject set NOT reviewed — Melvins call
- Sheet ranges: 01 ids 11544–20656 (60) | 02 ids 11132–21161 (60) | 03 ids 16123–22043 (21)
- NEXT: Melvin confirms keep set against the 3 survivors sheets, then reject 1,122 + DELETE 7
- Filename keyword search for documents is worthless — all filenames are hash-prefixed device names. Timestamp clustering is what found 19436/19437

### 2026-07-17 06:58
**Marked the 141 keepers from Melvin 15 July triage. Migration 0050 adds triage_keep/triage_keep_at/never_reject. 141 rows marked triage_keep=1; 21212/21215/21216 marked never_reject=1 with enforcement in delete_observation_file(). Marks only — no status/category/file changes.**

**Built:**
- Migration 0050_add_triage_keep — triage_keep BOOLEAN nullable (3-state NULL/1/0), triage_keep_at DATETIME, never_reject BOOLEAN. All additive, all nullable
- never_reject enforced inside delete_observation_file() — hard veto at the destructive call site, covering all 7 reject callers. Behaviourally tested: protected file survives, unprotected still moves to undo dir
**Files:** `migrations/versions/0050_add_triage_keep.py`, `app/models/observation.py`, `app/services/file_cleanup.py`
**Pending:**
- SNAPSHOT db_20260717_065439.sqlite (commit c044ee3e) taken before any write
- 141 keepers marked triage_keep=1, all re-SELECTed by ID individually: all triage_keep=1, triage_keep_at set, review_status=pending, identification_status=not_plant. Zero failures
- Resolution method VALIDATED against the artifact: my derived sheet-14 offset-780 slice matched Melvins sheet-read exactly including the non-monotonic run 20509,20512,20510,20511. Sheet size 60 confirmed
- Band spread: 125 no_plant_signal + 8 sky_blue + 8 person_animal = 141. Zero dupes. All 141 existed, non-rejected, not_plant, correct band
- Non-keepers: 1121 = 1262-141, all still pending, all files intact except 21212/21215/21216 (thumbnail-only, known, now never_reject protected)
- 13623/13368/20066 untouched: triage_keep NULL, never_reject NULL, still pending/not_plant. Require DELETE + hash blacklist — separate pass, not done
- ZERO rows rejected, deleted, approved, or unlinked. undo dir empty. Status counts unchanged: rejected 10354, approved 2062, manually_verified 105, pending 1271, needs_review 28
- NEXT: survivors-only contact sheets -> Melvin confirms -> then rejection. Keepers to review via override-prefilter, separate pass

### 2026-07-17 06:54
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260717_065439.sqlite`

### 2026-07-17 06:43
**PlantNet transient write-timeout: (5,25) timeout tuple + bounded retry (3 attempts, 0.5s/1.5s backoff), transport-only. Verified 22099 live: dual agreement 80.39/87.83 Circaea lutetiana. Plus read-only impact assessment of 7 weeks of transport failures.**

**Built:**
- plantnet.py bounded retry on socket stalls only — never on HTTP status (429/4xx/5xx answered = no retry, verified by unit check: 1 post call)
- PlantNetResult.attempts + PlantNetError.attempts — retried successes/failures measurable
- processing_logs retry line in identification.py and scan.py — logs only when attempts>1
**Fixed:**
- plantnet.py:33 REQUEST_TIMEOUT_S=8 scalar -> REQUEST_TIMEOUT=(5,25) tuple. connect=5 keeps fail-fast; read=25 ~5x observed worst success (5.02s)
- Root mechanism: requests timeout is per-socket-op, NOT total. 8s never meant the upload may take 8s
**Files:** `app/integrations/plantnet.py`, `app/services/identification.py`, `app/api/scan.py`
**Pending:**
- VERIFIED 22099: PlantNet 80.39% + iNat 87.83% Circaea lutetiana, inat_state=ok, zero warnings, plantnet_failed=False. Token refresh confirmed working
- 22099 did NOT auto-approve — still needs_review/below_threshold. retry-identify is read-only by contract (never auto-approves). Auto-approve only runs on the P1 scan path at ingest. Melvins call whether to confirm manually or re-ingest
- IMPACT (read-only): 3,239 observations had >=1 PlantNet transport failure. 828 identified iNat-ONLY (PlantNet silently dropped out of _dual_agree). dual_source_agreement set on ZERO of the 3,239 — no row was ever auto-approved on a degraded dual-source check
- IMPACT: 2,083 REJECTED rows had zero candidates AND a PlantNet transport failure — rejected on incomplete evidence. Files unlinked. Recoverable only from DIGIERA/phone
- PREFILTER CLEAN: 0 not_plant rows had a PlantNet transport failure. prefilter.py never calls PlantNet (runs before it, local classifier only). not_plant decisions are NOT contaminated
- 141-KEEPER BATCH CLEAN: 0 pending-queue rows have a PlantNet transport failure. The batch does not need this question asked of it
- Backlog (parked): httpx swap for plantnet.py — fault is not the library, retry addresses it

### 2026-07-16 19:28
**Identification failure messaging + iNat timeout. reidentify.py now reports recorded transport state instead of guessing; PlantNetError preserved; below_threshold card copy corrected to distinguish transport failure from genuine below-threshold; iNat vision timeout split per-phase.**

**Built:**
- _inat_warning() / _plantnet_warning() in reidentify.py — single mapping from recorded state to text; never infers cause from an empty list
- retry-identify response now returns structured inat_state + plantnet_failed alongside prose warnings
**Fixed:**
- reidentify.py x3 sites (163/175, 300/310, 507/516): bare except Exception -> return None replaced with except PlantNetError as exc capture, preserving is_connection_error + status_code
- reidentify.py:235/243, 432/436, 582/591: guess-disjunction warnings removed. grep confirms zero remaining instances of API error or rate limit / API error or expired token
- review.html below_threshold copy: now keys off candidates.length — candidates present vs none on record. Prior copy (mine, earlier today) claimed threshold filtering for rows that had candidates=[] from transport failure
- inaturalist.py: score_image now uses httpx.Timeout(connect=5, write=30, read=20, pool=5). TIMEOUT_S=8 retained for small JSON GETs only
**Files:** `app/api/reidentify.py`, `app/integrations/inaturalist.py`, `frontend/review.html`
**Pending:**
- iNAT TOKEN NOW GENUINELY EXPIRED — exp claim was 2026-07-16T07:09:35Z, elapsed ~10h ago. Refresh at inaturalist.org/users/api_token. Verified live: new code reports token expired or invalid (HTTP 401) correctly; old code would have said API error or expired token as a guess
- PlantNet healthy throughout: #22083 retry returns 6 candidates, top Verbascum chaixii 79.16%, plantnet_failed=False, no PlantNet warning emitted. Old code would have blamed PlantNet for a rate limit it never hit
- RECON RESULT: guess-from-[] defect was contained to reidentify.py. identification.py:150/168 is the correct reference impl (catches PlantNetError, reads is_connection_error, uses raise_on_connection_error=True). scan.py:1079 already calls last_inat_status(). sharing.py:292 exposes it at /api/me. No other surface affected — no broad fix needed
- Melvin to verify live in browser: below_threshold cards now render an honest species block; review.html changes are unverified by Code per project rule

### 2026-07-15 12:24
**Read-only diagnostic of identification API failures on #22083/#22099. Root cause: transient network failure on the local machine, not auth/quota/no-match. Both APIs verified healthy now; both photos identify at ~80%.**

**Pending:**
- KILLED: iNat expired-token claim — token valid until 2026-07-16T07:09:35Z (21.95h left), live calls 6/6 ok
- ROOT CAUSE: transient local network loss. Both providers last succeeded together at #22120 07:11:36; both failed 07:21:41 with DNS [Errno 8]. Shared uplink = not independent failures
- #22083 retry now -> PlantNet 79.16% Verbascum chaixii; #22099 -> PlantNet 80.39% + iNat 87.83% Circaea lutetiana (dual agreement, would auto-approve)
- BUG: reidentify.py:511-512 swallows PlantNetError -> None, discarding is_connection_error + message
- BUG: reidentify.py:582/591 warnings guess (API error or rate limit / expired token) while last_inat_status() already holds the true state (ok/ok_empty/token_expired/rate_limited/unreachable/file_error). Already imported in scan.py:1079 and exposed at /api/me; reidentify never calls it
- FRAGILITY: iNat TIMEOUT_S=8 vs measured healthy latency 3.62-8.78s — trial exceeded the timeout on a working network
- Upload measured 2.29 Mbit/s with ngrok tunnel active — thin margin for 3.5-4MB uploads

### 2026-07-15 11:04
**Fixed silent blank species block in review cards: identification_status chain had no terminal else, so below_threshold/failed_identification/pending_identification rendered nothing (3,850 cards). Also stopped P7 fabricating a 0.0% score for names with no backing candidate (10 rows).**

**Built:**
- Final-catch species block branch in _makeCardHtml — states pipeline outcome per identification_status, neutral styling, no edibility/safety signal
**Fixed:**
- below_threshold (5,077 rows) / failed_identification (16) / pending_identification (9) no longer render a blank species area
- P7 suggestion block no longer fabricates 0.0% + conf-low red when species_suggested has no matching candidate — score omitted, labelled unverified (10 rows incl. 22087 salsify, 22093 wood fern)
**Files:** `frontend/review.html`
**Pending:**
- STILL OPEN: edits-dont-sustain symptom — NOT caused by missing edit target (corr-wrap always rendered; root cause unfound)
- STILL OPEN: strikethrough on 22087 — line-through exists nowhere in frontend/ or git history; needs screenshot
- review.html chain has a branch for pending_connection (0 rows, never existed)
- Look up button silently persists typed text to species_suggested via fire-and-forget PATCH /suggest — design question
- 18669/18706/19490: below_threshold WITH species_primary set (all rejected)

### 2026-07-15 09:25
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260715_092525.sqlite`

### 2026-07-15 09:25
**Session ended** — Session ended from Settings page

### 2026-07-15 06:38
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260715_063835.sqlite`

### 2026-07-15 04:38
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260715_043815.sqlite`

### 2026-07-15 04:32
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260715_043230.sqlite`

### 2026-07-15 04:32
**Session ended** — Session ended from Settings page

### 2026-07-14 23:38
**Real date bands for Recently added; fix stale venv path in CLAUDE.md**

**Built:**
- ObservationOut.created_at added (from_attributes, additive)
- sightings.html added_desc now bands by created_at via extracted shared bandForDate() helper (Today/Yesterday/day/month), Date unknown fallback
**Fixed:**
- CLAUDE.md Project Overview venv path corrected venv/ -> ~/foragingid-venv (both Venv row and Run command)
**Files:** `app/api/observations.py`, `frontend/sightings.html`, `CLAUDE.md`

### 2026-07-14 22:39
**Build read-only Sightings browse gallery (frontend only)**

**Built:**
- frontend/sightings.html: date-banded CSS-columns masonry gallery over GET /api/observations; sort (newest/oldest/recently-added), single-select status chips (All/Confirmed/Pending review), geotagged toggle, debounced name search; infinite scroll (limit=100, offset paging); per-thumb confirmed/pending-review badge from review_status only (no edibility); shared lightbox with GPS-pin map deep-link and species-card link
- Route /sightings in main.py
- Sightings nav entry in site-header.js NAV_LINKS (propagates to all pages)
**Files:** `frontend/sightings.html`, `app/main.py`, `frontend/static/js/site-header.js`
**Pending:**
- added_desc bands by ingest order under a single Recently added header — true created_at date-bands blocked: ObservationOut exposes no created_at (would need 1-line backend field)
- Melvin to visually verify masonry/sticky bands/lightbox zoom/pin-jump in his browser

### 2026-07-14 22:04
**Add free-text name search param q to GET /api/observations**

**Built:**
- q param: case-insensitive substring name search across species_primary, species_suggested, Species.itis_accepted_name, Species.common_names via ilike; composes (AND) with existing filters; blank/whitespace treated as absent
**Files:** `app/api/observations.py`
**Pending:**
- Sightings page (not started)

### 2026-07-14 16:39
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260714_163940.sqlite`

### 2026-07-14 16:39
**Session ended** — Session ended from Settings page

### 2026-07-14 16:34
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260714_163401.sqlite`

### 2026-07-14 10:40
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260714_104045.sqlite`

### 2026-07-14 07:16
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260714_071632.sqlite`

### 2026-07-14 06:30
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260714_063003.sqlite`

### 2026-07-13 22:36
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260713_223620.sqlite`

### 2026-07-13 22:36
**Session ended** — Session ended from Settings page

### 2026-07-13 21:12
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260713_211208.sqlite`

### 2026-07-13 21:12
**Session ended** — Session ended from Settings page

### 2026-07-12 16:46
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260712_164618.sqlite`

### 2026-07-12 16:46
**Session ended** — Session ended from Settings page

### 2026-07-12 16:41
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260712_164106.sqlite`

### 2026-07-12 16:41
**Session ended** — Session ended from Settings page

### 2026-07-12 16:32
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260712_163248.sqlite`

### 2026-07-12 16:32
**Session ended** — Session ended from Settings page

### 2026-07-12 06:42
**Snapshot** — End of session — Data-integrity + docs session (no code/DB schema changes). (1) Cleared FK orphans for deleted species 244: removed 24 enrichment_sources + 5 species_ai_drafts rows, snapshot-before-write, read-back verified, no collateral. (2) Appended Data Model & Safety Doctrine section to CLAUDE.md and git rm'd ANTIGRAVITY.md (staged).
DB: `snapshots/db_20260712_064208.sqlite`

### 2026-07-12 06:42
**Session ended** — Data-integrity + docs session (no code/DB schema changes). (1) Cleared FK orphans for deleted species 244: removed 24 enrichment_sources + 5 species_ai_drafts rows, snapshot-before-write, read-back verified, no collateral. (2) Appended Data Model & Safety Doctrine section to CLAUDE.md and git rm'd ANTIGRAVITY.md (staged).

### 2026-07-11 14:35
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260711_143540.sqlite`

### 2026-07-11 14:35
**Session ended** — Session ended from Settings page

### 2026-07-10 12:45
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260710_124543.sqlite`

### 2026-07-10 12:45
**Session ended** — Session ended from Settings page

### 2026-07-09 21:35
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260709_213514.sqlite`

### 2026-07-09 21:21
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260709_212135.sqlite`

### 2026-07-09 21:05
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260709_210551.sqlite`

### 2026-07-09 21:02
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260709_210257.sqlite`

### 2026-07-08 21:43
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260708_214330.sqlite`

### 2026-07-08 21:43
**Session ended** — Session ended from Settings page

### 2026-07-08 21:43
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260708_214307.sqlite`

### 2026-07-08 21:43
**Session ended** — Session ended from Settings page

### 2026-07-08 19:24
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260708_192449.sqlite`

### 2026-07-08 19:24
**Session ended** — Session ended from Settings page

### 2026-07-08 11:49
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260708_114945.sqlite`

### 2026-07-08 11:49
**Session ended** — Session ended from Settings page

### 2026-07-08 09:41
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260708_094155.sqlite`

### 2026-07-08 09:41
**Session ended** — Session ended from Settings page

### 2026-07-08 06:42
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260708_064238.sqlite`

### 2026-07-08 06:42
**Session ended** — Session ended from Settings page

### 2026-07-07 11:55
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260707_115511.sqlite`

### 2026-07-07 11:55
**Session ended** — Session ended from Settings page

### 2026-07-07 08:57
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260707_085719.sqlite`

### 2026-07-07 08:57
**Session ended** — Session ended from Settings page

### 2026-07-07 03:28
**Snapshot** — End of session — Built the taxonomic data layer (Unit A) end to end: additive migration 0045 (phylum/class_/order_ + gbif_match_type/confidence, reusing gbif_usage_key), a new GBIF backbone client with an EXACT-only non-clobbering write-gate, a 644-species backfill (501 clean EXACT / 130 conflict-withheld / 13 parked, 0 errors), and a metadata-only enrichment hook in _enrich_new_species_card() — all verified walled off from identification, confidence, routing, and edibility. Backfill surfaced a batch of wrong-organism card desyncs (evidence for audit #3b) and several sci-name typos, all parked for manual review, none auto-resolved.
DB: `snapshots/db_20260707_032827.sqlite`

### 2026-07-07 03:28
**Session ended** — Built the taxonomic data layer (Unit A) end to end: additive migration 0045 (phylum/class_/order_ + gbif_match_type/confidence, reusing gbif_usage_key), a new GBIF backbone client with an EXACT-only non-clobbering write-gate, a 644-species backfill (501 clean EXACT / 130 conflict-withheld / 13 parked, 0 errors), and a metadata-only enrichment hook in _enrich_new_species_card() — all verified walled off from identification, confidence, routing, and edibility. Backfill surfaced a batch of wrong-organism card desyncs (evidence for audit #3b) and several sci-name typos, all parked for manual review, none auto-resolved.

### 2026-07-07 03:27
**Taxonomic data layer (Unit A) — full GBIF lineage per species, backfilled + hooked into new-species enrichment. Metadata-only, walled off from identification/confidence/routing/edibility.**

**Built:**
- Migration 0045: additive rank + GBIF match columns on species (phylum, class_, order_, gbif_match_type, gbif_match_confidence); reused existing gbif_usage_key instead of adding redundant gbif_taxon_key
- app/integrations/gbif.py: GBIF backbone client (name /species/match + /species/{key}), GBIFMatch dataclass, apply_gbif_lineage() EXACT-only write-gate with non-clobber-of-human-values + coherent EXACT_CONFLICT withholding, enrich_species_taxonomy() resolve-by-key-else-name helper
- Step 4 pipeline hook in _enrich_new_species_card(): own session, own error isolation, guarded on gbif_match_type IS NULL, fully outside identification/routing/edibility
**Fixed:**
- GBIF backfill surfaced 130 EXACT-conflicts: many family-column-holds-genus placeholders plus a batch of genuine wrong-organism card desyncs (evidence for audit #3b; confirms species 412 + 625). None auto-resolved — parked for manual review.
**Files:** `app/models/species.py`, `migrations/versions/0045_add_species_taxonomy_lineage.py`, `app/integrations/gbif.py`, `app/api/scan.py`
**Pending:**
- Manual review of 130 EXACT_CONFLICT list (esp. wrong-organism desyncs) — overlaps audit #3b
- Manual review of 13 FUZZY/HIGHERRANK/NONE incl. scientific_name typos (287 Sambuca nigra, 288 Valeriana officianalis, 685 norway spruce)
- Unit B (taxonomic graph visualisation) — still parked until FUZZY list eyeballed

### 2026-07-06 17:45
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260706_174529.sqlite`

### 2026-07-06 17:29
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260706_172916.sqlite`

### 2026-07-06 17:29
**Session ended** — Session ended from Settings page

### 2026-07-06 12:18
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260706_121841.sqlite`

### 2026-07-06 12:18
**Session ended** — Session ended from Settings page

### 2026-07-06 12:13
**Snapshot** — Pre-write: fix Second Opinion apostrophe-escape bug in onclick (review.html:2132)
DB: `snapshots/db_20260706_121352.sqlite`

### 2026-07-06 12:06
**Snapshot** — End of session — Test: confirm End Session runs cleanly after removing Obsidian vault sync
DB: `snapshots/db_20260706_120629.sqlite`

### 2026-07-06 12:06
**Session ended** — Test: confirm End Session runs cleanly after removing Obsidian vault sync

### 2026-07-06 12:02
**Snapshot** — Pre-write: remove Obsidian vault sync integration (Current State.md/Decisions Log.md)
DB: `snapshots/db_20260706_120246.sqlite`

### 2026-07-06 10:34
**Snapshot** — Pre-write: change encounter export destination from Obsidian vault to local exports/
DB: `snapshots/db_20260706_103431.sqlite`

### 2026-07-06 10:16
**Snapshot** — Pre-write: remove GDrive integration (superseded by External Backup)
DB: `snapshots/db_20260706_101623.sqlite`

### 2026-07-06 09:28
**Snapshot** — Pre-write: gitignore cleanup + untrack bak/backup DBs and confirmed_plants photos
DB: `snapshots/db_20260706_092810.sqlite`

### 2026-07-06 07:36
**Snapshot** — Pre-write: Hypericum ID accuracy note (id_notes)
DB: `snapshots/db_20260706_073634.sqlite`

### 2026-07-06 07:06
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260706_070642.sqlite`

### 2026-07-06 07:06
**Session ended** — Session ended from Settings page

### 2026-07-05 20:35
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260705_203505.sqlite`

### 2026-07-05 20:35
**Session ended** — Session ended from Settings page

### 2026-07-05 20:22
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260705_202232.sqlite`

### 2026-07-05 20:12
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260705_201237.sqlite`

### 2026-07-05 16:23
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260705_162315.sqlite`

### 2026-07-05 12:25
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260705_122501.sqlite`

### 2026-07-05 12:25
**Session ended** — Session ended from Settings page

### 2026-07-04 18:41
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260704_184141.sqlite`

### 2026-07-04 18:41
**Session ended** — Session ended from Settings page

### 2026-07-04 18:38
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260704_183845.sqlite`

### 2026-07-04 13:56
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260704_135615.sqlite`

### 2026-07-04 13:56
**Session ended** — Session ended from Settings page

### 2026-07-04 06:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260704_060908.sqlite`

### 2026-07-04 06:09
**Session ended** — Session ended from Settings page

### 2026-07-04 06:00
**Map Redesign P3-count: species-in-view count + map-page cosmetics**

**Built:**
- Species-in-view count added to the counts pill ("n sightings · m species") — computed entirely client-side by collecting distinct species_primary inside the existing _passesFilters loop in renderMarkers(), so it's guaranteed to describe the identical filtered in-view set as the sightings count. No backend endpoint was needed or added — client already had species identity per feature.
- Legend chip moved from bottom-right to bottom-left; legend panel's own position adjusted (bottom:126px) to sit above its new chip location
- Leaflet attribution control font-size reduced (0.62rem) and padding tightened — all text/links kept intact
- Fixed chip/sidebar overlap: search-chip, settings-chip, and legend-chip now hide while the pin-detail/discover sidebar (#rp-pane) is open, instead of the previous approach (not present before this task) of shifting them left — a shift large enough to clear the 300px sidebar collides with the opposite-corner nav-chip/legend-chip on narrow viewports
**Fixed:**
- During Step 2c work, an initial shift-based fix (right:322px when sidebar open) was found to overshoot on 390px viewports, pushing the search/settings chips into the nav-chip and legend-chip on the opposite side — replaced with a hide-while-open approach that works at any width
- This same investigation surfaced a pre-existing (P1/P2-era) near-collision between the Leaflet locate control (which already shifted left when the sidebar opens) and the new bottom-left legend chip — resolved as a side effect of hiding the legend chip while the sidebar is open
**Files:** `frontend/index.html`
**Pending:**
- No endpoint was added (client-side computation was sufficient) — confirming for the record per the prompt's instruction to note this either way

### 2026-07-03 22:23
**Map Redesign P2: Discovery merge (Near me + Find) + config-panel section reorder**

**Built:**
- Unified #discover-view opened by the top-right search chip: existing species/place search field (moved from the chip, unchanged internals) + Near me radius-filter toggle (reuses existing 200/500/1000m radius logic and distance ranking) + Find's In season/Recipes/Medicinal modes, sharing one #discover-results list
- Near me toggle ON hides the Find mode row and shows radius chips + GPS-nearby results; toggle OFF restores whichever Find mode was active — single shared results container either way
- Result-tap behaviour changed (per explicit decision) from navigating to /species?s=... to filtering the map to that species and fitting bounds to its pins, modelled on the existing top-chip species-select pattern (_selectSearchItem) — new _discoverShowSpecies() helper, reused across in-season/recipes/medicinal/near-me cards
- Removed the DISCOVER config-panel section, the old standalone #nearme-view/#find-view panels, the 'Near me now' Find mode (folded into the Near me toggle), and the now-orphaned _findNearbyInSeason()
- Config panel section order changed to VIEW / BASE LAYER / OVERLAYS / TOOLS / FILTERS (TOOLS moved above FILTERS, below the In-season-now control)
**Fixed:**
- Found and fixed a pre-existing latent bug (not introduced by this task, but reliably triggered by the new result-tap fitBounds calls): _recalcHeatMax() crashed on any zoomend while the heatmap layer wasn't on the map (heatLayer._canvas null in Pins/Clusters view) — added a guard so it no-ops when the heat layer isn't active
- Fixed 3 leftover direct references to the deleted #nearme-view element (in showFilterView/showDetailView/_showWalkDetail) that would have thrown after the merge — retargeted to #discover-view
- Cleared stale 'Location unavailable' sub-header text when toggling Near me off back to Find mode
**Files:** `frontend/index.html`
**Pending:**
- P3: behaviour pass (Clusters merge into Pins, species-in-view count for the counts pill) — not started, out of scope for P2
- Pre-existing minor cosmetic overlap between the settings/legend chips and the open sidebar on narrow viewports (~390px) — predates P2, not touched

### 2026-07-03 21:19
**Map P1.1: chrome polish (leaf glyph, larger gear, legend consolidation)**

**Built:**
- Nav-drawer chip now uses the same dandelion-icon.svg as the site header (inverted white), replacing the placeholder inline SVG
- Settings chip gear enlarged via font-size (22.4px, up from ~13px inherited default); chip size/position unchanged
- New bottom-right legend chip (list/key icon) between the settings chip and locate-me, opens the same schutz-legend panel via toggleLegendPanel()/closeLegendPanel()
- Pin legend (Plant confirmed/pending/Fungi/Landscape) moved from the config sheet's LEGEND section into #schutz-legend, combined with the existing Schutzgebiete rows under one panel with a divider
- Added a close (X) button to #schutz-legend; existing auto-show-on-overlay-toggle behaviour in toggleSchutzOverlay() left unchanged
**Files:** `frontend/index.html`

### 2026-07-03 18:36
**Map Redesign P1: Shell (full-bleed, drawer, config sheet)**

**Built:**
- Design tokens (frontend/static/css/tokens.css) + DESIGN.md, linked map-page-only
- Full-bleed map shell: removed site header + stats strip from /map
- Left nav drawer (map-page-only fragment, seam commented for future site-wide adoption) with Review badge reusing existing pending+flagged count source
- Standing controls: locate-me moved to bottom-right, zoom hidden on touch via @media(pointer:fine), search chip (top-right) expanding to the existing unchanged search input
- Config sheet: bottom sheet <1024px / right panel >=1024px with VIEW (Pins/Clusters/Heatmap segmented + inline heatmap sliders), BASE LAYER (all 7 layers + star), OVERLAYS (Schutzgebiete chips + In Season toggle, mirrored with Filters per Melvin's decision), FILTERS (existing content, no-gps banner removed), DISCOVER (Near me/Find), TOOLS (Drop a note/Build a walk), LEGEND
- Counts pill (top-center, Pins/Clusters only, hidden in Heatmap) wired to existing in-view sightings count; species-in-view marked TODO(P3) since not computed client-side today
- Deleted no-GPS manual-geotagging feature entirely per Melvin's explicit confirmation (was real functionality, not just a banner — loadNoGPSObs/saveNoGPS/useMapCentre/_renderNoGPSList + ~50 lines CSS + API call site all removed)
**Fixed:**
- Two duplicate-ID/positioning collisions found during Step 8 verification and fixed: search chip was overlapping the Leaflet zoom control; config-sheet gear chip was overlapping the locate-me button
- In-season checkbox desync: clearAllFilters() reset the Filters checkbox but not the mirrored Overlays checkbox — fixed
- Drop-a-note crosshair and Build-a-walk bottom sheet could previously be obscured by/collide with the new config sheet on mobile — both flows now explicitly close the config sheet on entry
- loadHeat()/renderMarkers()/_loadReviewCount() retargeted from deleted #stats-bar spans to the new counts pill and nav drawer badge
**Files:** `frontend/index.html`, `frontend/static/css/tokens.css`, `DESIGN.md`
**Pending:**
- P2: discovery merge (Near me + Find unification) — not started, explicitly out of scope for P1
- P3: behaviour pass — Clusters merge into Pins, species-in-view count for the pill, zoom pointer:fine verified by code reading only (test env couldn't emulate coarse pointer)
- Checkpoint commit not yet made — awaiting Melvin's go-ahead per protocol (Step 8 passed clean)

### 2026-07-03 16:04
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260703_160413.sqlite`

### 2026-07-03 16:04
**Session ended** — Session ended from Settings page

### 2026-07-03 11:53
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260703_115335.sqlite`

### 2026-07-03 07:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260703_074747.sqlite`

### 2026-07-03 07:47
**Session ended** — Session ended from Settings page

### 2026-07-03 06:41
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260703_064124.sqlite`

### 2026-07-03 06:41
**Session ended** — Session ended from Settings page

### 2026-07-03 06:25
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260703_062527.sqlite`

### 2026-07-03 06:25
**Session ended** — Session ended from Settings page

### 2026-07-03 06:17
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260703_061750.sqlite`

### 2026-07-03 05:59
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260703_055904.sqlite`

### 2026-07-03 05:24
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260703_052433.sqlite`

### 2026-07-02 21:25
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260702_212558.sqlite`

### 2026-07-02 21:25
**Session ended** — Session ended from Settings page

### 2026-07-02 18:05
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260702_180518.sqlite`

### 2026-07-02 16:33
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260702_163342.sqlite`

### 2026-07-02 10:36
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260702_103606.sqlite`

### 2026-07-02 10:36
**Session ended** — Session ended from Settings page

### 2026-07-02 07:58
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260702_075804.sqlite`

### 2026-07-02 07:41
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260702_074107.sqlite`

### 2026-07-02 07:41
**Session ended** — Session ended from Settings page

### 2026-07-02 06:38
**Ingested medicinal_folklore batch D (50 species + Centaurium erythraea, Opus-authored), applied 4 toxic edibility_status changes + 1 upgrade to edible per curator directive**

**Pending:**
- Oxalis grandis (691) deliberately excluded - PFAF page has no species-specific content
- Medicinal_folklore backfill pool now exhausted under standing eligibility criteria
- Betonica officinalis (625) primary_source_url under synonym Stachys officinalis - data drift, same pattern as Reynoutria/Fallopia, not fixed
- Google Drive snapshot backup still failing on unicode em-dash ascii encoding error

### 2026-07-02 06:32
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260702_063214.sqlite`

### 2026-07-02 06:16
**Amended and approved the two held medicinal_folklore drafts (Cytisus scoparius 518, Dryopteris crassirhizoma 477) with explicit not-for-eating caution added**

**Pending:**
- Batch D (50 species) still awaiting synthesis/ingest
- 2 species remain queued after batch D for a final batch E
- Reynoutria japonica (419) culinary_info.primary_source_url still stale (Fallopia japonica synonym)
- Google Drive snapshot backup still failing on unicode em-dash ascii encoding error

### 2026-07-02 06:13
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260702_061336.sqlite`

### 2026-07-02 06:10
**Ingested medicinal_folklore batch C (50 species, Opus-authored), changed Arnica montana edibility_status to toxic per curator directive, held 2 species on caution-text gap**

**Pending:**
- Cytisus scoparius (518) and Dryopteris crassirhizoma (477) draft rows inserted but NOT approved - missing explicit not-to-eat caution clause, awaiting Melvin decision to revise text or approve as-is
- Reynoutria japonica (419) culinary_info.primary_source_url still points to stale Fallopia japonica synonym URL - data drift, needs a sync pass
- 52 species from batch C export still queued for a future batch D
- Google Drive snapshot backup still failing on unicode em-dash ascii encoding error

### 2026-07-02 06:05
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260702_060459.sqlite`

### 2026-07-02 05:58
**Ingested and approved medicinal_folklore batch B_v2 (49 species, Opus-authored) with PFAF provenance**

**Pending:**
- Batch C (52 remaining eligible species from batch C export) still awaiting synthesis/ingest
- Google Drive snapshot backup failing on unicode em-dash encoding (ascii codec error) - separate from documented token refresh issue

### 2026-07-02 05:52
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260702_055254.sqlite`

### 2026-07-01 21:10
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260701_211033.sqlite`

### 2026-07-01 21:10
**Session ended** — Session ended from Settings page

### 2026-07-01 20:43
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_204327.sqlite`

### 2026-07-01 17:29
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_172902.sqlite`

### 2026-07-01 15:36
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_153633.sqlite`

### 2026-07-01 15:16
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_151604.sqlite`

### 2026-07-01 14:42
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_144218.sqlite`

### 2026-07-01 12:12
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_121247.sqlite`

### 2026-07-01 12:12
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260701_121203.sqlite`

### 2026-07-01 12:12
**Session ended** — Session ended from Settings page

### 2026-07-01 09:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260701_090927.sqlite`

### 2026-07-01 09:09
**Session ended** — Session ended from Settings page

### 2026-07-01 07:53
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260701_075334.sqlite`

### 2026-07-01 07:53
**Session ended** — Session ended from Settings page

### 2026-07-01 07:44
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_074410.sqlite`

### 2026-07-01 06:57
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_065747.sqlite`

### 2026-07-01 06:18
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260701_061848.sqlite`

### 2026-06-30 12:29
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260630_122904.sqlite`

### 2026-06-30 12:29
**Session ended** — Session ended from Settings page

### 2026-06-30 12:23
**Melvin manual review of 3 toxic-signal holds + 1 pre-vetted species**

**Fixed:**
- Prunus cerasus: caution/verified/human — false positive toxic hold (genus HCN hedge, fruit is edible sour cherry)
- Cornus sanguinea: caution/verified/human — false positive (regex matched denial in hazard text)
- Veronica beccabunga: edible/verified/human — Melvin confirmed 2-source pre-vetted match
**Files:** `data/foragingid.db`
**Pending:**
- 6 remaining toxic holds still unresolved (Anthriscus sylvestris, Echium vulgare, Galeopsis tetrahit, Lotus corniculatus, Polygala vulgaris, Symphytum officinale, Thalictrum aquilegiifolium)
- 4 Ranunculus species toxic writes (human directive)
- 213 unresolved queue species (insufficient source coverage)
- Standing ingest-time protocol

### 2026-06-30 08:48
**Consolidated tiered multi-source agreement pass against 257-species Edibility Review queue**

**Built:**
- Tier A PFAF+edibleplantdb agreement logic written and executed
- 34 species resolved to caution (verified=1, multi-source-tier-a)
- 9 toxic-signal holds identified and documented for manual review
- 1 pre-vetted 2-source species (Veronica beccabunga)
- culinary_info_history logging for all writes
**Fixed:**
- Fixed culinary_info_history schema mismatch (species_id → culinary_info_id FK)
**Files:** `data/source_lookups/edibleplantdb_extract.md (read only)`, `data/foraging_source_lookups.md (read only)`, `data/foragingid.db (34 species edibility_status writes + history log entries)`
**Pending:**
- 9 toxic-signal holds need manual review (Anthriscus sylvestris, Cornus sanguinea, Echium vulgare, Galeopsis tetrahit, Lotus corniculatus, Polygala vulgaris, Prunus cerasus, Symphytum officinale, Thalictrum aquilegiifolium)
- 213 species remain unresolved (insufficient source coverage)
- Veronica beccabunga: 2-source pre-vetted, quick-confirm candidate
- 4 Ranunculus species toxic writes (human directive, unchanged)
- Standing ingest-time protocol (not yet built)

### 2026-06-30 08:44
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260630_084416.sqlite`

### 2026-06-30 08:33
**Bulk extract edibleplantdb data for all 635 ForagingID species via local kiwix-serve**

**Built:**
- data/source_lookups/edibleplantdb_extract.md created with 635 species, 341 matches (168 edible, 134 caution, 39 toxic, 294 no-match)
**Fixed:**
- Fixed 7 species with alternate page format (no Edible parts: label) by parsing What to Eat section directly
**Files:** `data/source_lookups/edibleplantdb_extract.md`
**Pending:**
- Phase 2 of edibility task: consolidated tiered agreement pass against 168-species review queue using PFAF + edibleplantdb tiers
- 4 Ranunculus species toxic writes (human directive)
- Standing ingest-time protocol (auto-check new species)

### 2026-06-30 08:26
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260630_082611.sqlite`

### 2026-06-30 08:26
**Session ended** — Session ended from Settings page

### 2026-06-30 07:29
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260630_072931.sqlite`

### 2026-06-30 07:29
**Session ended** — Session ended from Settings page

### 2026-06-30 06:22
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260630_062228.sqlite`

### 2026-06-30 05:52
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260630_055224.sqlite`

### 2026-06-30 05:45
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260630_054546.sqlite`

### 2026-06-29 21:40
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260629_214028.sqlite`

### 2026-06-29 20:00
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260629_200017.sqlite`

### 2026-06-29 10:00
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260629_100038.sqlite`

### 2026-06-29 09:38
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260629_093835.sqlite`

### 2026-06-29 09:38
**Session ended** — Session ended from Settings page

### 2026-06-29 09:35
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260629_093558.sqlite`

### 2026-06-29 09:35
**Session ended** — Session ended from Settings page

### 2026-06-29 06:48
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260629_064823.sqlite`

### 2026-06-29 06:48
**Session ended** — Session ended from Settings page

### 2026-06-28 18:29
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260628_182905.sqlite`

### 2026-06-28 18:29
**Session ended** — Session ended from Settings page

### 2026-06-28 18:20
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260628_182009.sqlite`

### 2026-06-28 18:20
**Session ended** — Session ended from Settings page

### 2026-06-28 16:48
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260628_164831.sqlite`

### 2026-06-28 16:48
**Session ended** — Session ended from Settings page

### 2026-06-28 15:07
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260628_150733.sqlite`

### 2026-06-28 15:07
**Session ended** — Session ended from Settings page

### 2026-06-25 13:40
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260625_134008.sqlite`

### 2026-06-25 13:40
**Session ended** — Session ended from Settings page

### 2026-06-24 21:37
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260624_213713.sqlite`

### 2026-06-24 21:37
**Session ended** — Session ended from Settings page

### 2026-06-24 16:10
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260624_161026.sqlite`

### 2026-06-24 16:10
**Session ended** — Session ended from Settings page

### 2026-06-24 16:02
**Seasons Prompt 3: phenology band, zoom, booklet selection, encounter stubs**

**Built:**
- Phenology band beneath photo band with coloured stage bars (leaf/flower/fruit) and density markers for no-phenology species
- Vertical cursor line tracking scroll date across phenology band
- Bidirectional cross-highlight between phenology rows and photo band thumbnails
- Zoom overlay via double-tap/tap-hold showing encounter photos per species in fortnight window
- Booklet selection: long-press to toggle My Season membership via personal-list API
- Species card modal with add/remove My Season button
- Encounters-without-photos text-card stubs in zoom view
- Extended /at API with sighting_doys and encounters data
**Files:** `app/api/timeline.py`, `frontend/seasons.html`
**Pending:**
- Encounters inter-tab nav verification
- Seasons edibility y-weighting eyeball check
- Seasons lens modes (future)
- Seasons nav guest/admin tier split

### 2026-06-24 15:45
**Fixed broken record/save on /encounters - extracted inline script to external JS file**

**Fixed:**
- Root cause: em-dashes (U+2014) and curly quotes (U+2018/U+2019) in JS comments inside the inline <script> block caused a SyntaxError that silently killed the entire IIFE before record/save handlers could bind
- Fix: extracted the 75KB inline script to frontend/static/js/encounters-main.js, replaced non-ASCII comment characters (em-dashes, curly quotes, arrows, ellipses) with ASCII equivalents
- encounters.html now references the external script via <script src=/static/js/encounters-main.js>
- All functions (switchTab, recToggle, recSave, etc.) now load and execute correctly
**Files:** `frontend/encounters.html`, `frontend/static/js/encounters-main.js`

### 2026-06-24 15:42
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260624_154224.sqlite`

### 2026-06-24 15:42
**Session ended** — Session ended from Settings page

### 2026-06-24 11:51
**Seasons UI fixes: nav across all pages, 2D Poisson scatter, temporal focus effect**

**Built:**
- Seasons nav link added to all 9 pages (index, species, review, encounters, scan, settings, lists, about, upload)
- 2D Poisson disk placement with bounded horizontal jitter (X_JITTER=0.12) — species scatter as organic cloud, not column
- Temporal focus effect: blur/scale/opacity falloff computed from species peak_doy vs scroll-centre day, not pixel distance
- Layout race fix: dimensions computed after API fetch round-trip with window fallback
- Window resize handler repositions species
**Fixed:**
- Nav: Seasons link was only on seasons.html — now on all pages in correct order
- Placement: co-peaking species no longer stack vertically — proper 2D scatter
- Focus: decoupled from pixel position — temporally near species are sharp regardless of jitter position
**Files:** `app/api/timeline.py`, `frontend/seasons.html`, `frontend/index.html`, `frontend/species.html`, `frontend/review.html`, `frontend/encounters.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/lists.html`, `frontend/about.html`, `frontend/upload.html`

### 2026-06-24 10:43
**Timeline photo band frontend — scrolling band view at /seasons**

**Built:**
- New route /seasons serving frontend/seasons.html
- Horizontal scroll band with CSS scroll-snap, 36 stops across the year (~10 days each)
- Opens at today day-of-year (June), past scrolls left, future scrolls right
- Species at fixed (x,y) positions from /api/timeline/positions — never reposition on scroll
- Fade in/out as scroll crosses visible_from/visible_to boundaries
- Thumbnails from /api/timeline/at, lazy-loaded and cached per 10-day quantised window
- Focus effect: horizontal blur+scale falloff from centre; vertical opacity gradient (centre full, edges ~60%)
- All scroll-driven transforms throttled with requestAnimationFrame
- Month bar at bottom with tap-to-jump; active month highlighted
- Minimal nav bar with links to Species, Encounters, Seasons
**Files:** `app/main.py`, `frontend/seasons.html`
**Pending:**
- Prompt 3: phenology arcs, zoom, selection/tap interaction

### 2026-06-24 08:07
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260624_080734.sqlite`

### 2026-06-24 08:07
**Session ended** — Session ended from Settings page

### 2026-06-24 08:02
**Timeline data layer: compound index, positions endpoint with Poisson placement + lens system, content-at endpoint**

**Built:**
- Migration 0043: compound index (species_id, photo_taken_at) on observations — nearest-date queries now use index
- GET /api/timeline/positions?lens=edibility — 471 species with deterministic (x,y) placement, sighting-derived visibility windows
- Poisson-disk placement: seeded from species_id + year constant, byte-identical across sessions/devices
- Lens registry: pluggable scoring system — edibility lens implemented, structure for favourites/in-flower-now/etc.
- Sighting density analysis: 10-day bins, peak=mode (not mean), visible_from/to from 20% of peak threshold
- GET /api/timeline/at?day=N&lens=edibility — top 10 visible species with nearest-day thumbnail + phenology arcs
- Phenology parsing: flower/fruit/leaf_months comma-separated ints → structured arcs
- photo_taken_at with created_at fallback for all date queries
**Files:** `app/api/timeline.py`, `app/main.py`, `migrations/versions/0043_add_species_photo_taken_index.py`
**Pending:**
- Frontend timeline UI
- NOTE: species_primary index=True in model but missing in DB — model/DB drift, not fixed

### 2026-06-24 07:58
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260624_075828.sqlite`

### 2026-06-24 04:01
**A4 — Encounters browse tab: reverse-chron, grouped by walk, confirm + photo chips**

**Built:**
- Browse tab (📋 Encounters) — reverse-chron encounter cards grouped by walk/session
- Walk grouping: 90-min gap between encounters starts a new walk group (temporal inference, no formal walk model)
- Each card: thumbnail (bound photo) or dotted photo-pending placeholder, species, time, note/transcript
- Facet-suggestion chips: reuses existing resolveSuggestion() machinery — confirm/dismiss inline
- Photo-candidate strip: lazy-loaded proximity candidates with distance + timestamp, tap to bind
- Widen control: doubles radius/window to find more candidates
- Manual bind: native OS file picker as escape hatch — uploads via P2, binds via POST /bind-photo
- Per-walk status line: quiet count of encounters with unconfirmed notes or pending photos
- GET /api/encounters now returns photos array with thumbnails and binding methods
- GET /api/encounters/{id}/photo-candidates — proximity candidates with configurable radius/window
- POST /api/encounters/{id}/bind-photo — manual or proximity binding
**Files:** `app/api/encounters.py`, `frontend/encounters.html`

### 2026-06-23 21:16
**A3 — Resolvers: filename (deterministic) + proximity-and-time (fallback), hooked into P1/P2 ingest**

**Built:**
- Filename resolver: auto-binds observation to encounter by expected_filename match (±24h window, normalised stems)
- Syncthing (N) suffix normalisation: strips " (1)" etc. before comparing — covers 0.5% drift in recent P1 data
- Pixel Motion Photo .MP.jpg normalisation: treats .MP.jpg and .jpg as same stem
- own_named vs filename binding_method: encounter_ prefix triggers own_named for audit trail
- Proximity+time resolver: finds candidates within 20m AND 5min — surfaces for ratification, never auto-binds
- Fire-and-forget hooks in P1 (_process_one after identification) and P2 (background_tasks after commit)
- POST /api/encounters/backfill-photo-bindings — runs both resolvers retroactively over all GPS-tagged observations
- All resolver errors logged, never fatal — ingest timing and success unaffected
**Files:** `app/services/photo_binding.py`, `app/api/syncthing.py`, `app/api/scan.py`, `app/api/encounters.py`
**Pending:**
- A4 — Proximity candidate ratification UI

### 2026-06-23 20:42
**A2 — Record tab: capture (online own-name / offline JSON+filename), offline-first**

**Built:**
- Record tab added as landing tab on Encounters page — minimal flow: mic + photo + note + save
- Audio recording with MediaRecorder — direct upload via POST /api/encounters (same as existing pattern)
- Photo online path: capture → rename encounter_[UUID].ext → upload via P2 → bind via encounter_photos
- Photo offline path: gallery pick → read file.name only → store as expected_filename → discard File (no binary in queue)
- All saves capture precise timestamp + live GPS fix via GPS.getOnce({maxAge:0})
- Text/photo-only saves use EncounterQueue outbox (client_uuid idempotency, offline-first)
- Backend accepts expected_filename and photo_observation_ids on POST /api/encounters
- expected_filename returned in encounter response dict
**Files:** `app/api/encounters.py`, `frontend/encounters.html`
**Pending:**
- A3 — P1 filename binding resolver on arrival
- Preview browser cannot execute inline scripts with Unicode box-drawing chars — not an app bug, works in real browsers

### 2026-06-23 20:15
**A1 — Encounter model: expected_filename column for photo binding**

**Built:**
- encounters.expected_filename nullable Text column — stores camera filename for p1 binding on arrival
- binding_method values updated: own_named / filename / proximity / manual
- Alembic migration 0042 — additive only, existing 13 encounters untouched
**Files:** `app/models/encounter.py`, `migrations/versions/0042_add_expected_filename_to_encounters.py`
**Pending:**
- Photo binding resolver
- Encounter recorder UI with photo capture

### 2026-06-23 06:13
**Encounter model: encounter_photos join table migration (photo binding + facet readiness)**

**Built:**
- encounter_photos many-to-many join table (encounter_id, observation_id, binding_method, binding_detail, created_at)
- EncounterPhoto SQLAlchemy model with relationships to Encounter and Observation
- Unique constraint on (encounter_id, observation_id) prevents duplicate bindings
- binding_method field records how binding was made: proximity / filename / manual
- Alembic migration 0041 — additive only, existing encounters untouched
**Files:** `app/models/encounter.py`, `migrations/versions/0041_encounter_photos_join_table.py`
**Pending:**
- Photo binding resolver (proximity + filename match)
- Structured habitat columns deferred to v2

### 2026-06-23 06:12
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260623_061238.sqlite`

### 2026-06-22 15:17
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260622_151747.sqlite`

### 2026-06-22 15:17
**Session ended** — Session ended from Settings page

### 2026-06-22 15:07
**AI draft review/approve on species card + search box in review queue**

**Built:**
- Pending AI Drafts section on species card — approve, edit+approve, reject, regenerate controls (reuses existing backend endpoints)
- Profile endpoint expanded to return full pending_drafts objects (id, field_name, draft_text, model, generated_at)
- 409 human-lock guard surfaces inline error message on species card (not silent failure)
- Section suppressed for toxic/inedible species (mirrors enrichment edibility gate)
- Search box in AI Draft Review tab — filters cards live by species name, clear button resets
- Write-verification: approved draft confirmed by re-querying profile endpoint
**Files:** `app/api/culinary.py`, `frontend/species.html`, `frontend/review.html`

### 2026-06-22 12:36
**Common name edit affordance on species card profile header**

**Built:**
- PATCH /api/species/{name}/common-names endpoint — saves preferred_common_name, common_names (EN), common_names_de (DE) with human-lock history row
- common_names_human_locked boolean in species profile endpoint response
- Inline edit panel in species profile header with pencil button, preferred name input, EN/DE textareas, save/cancel
- Human-locked badge (purple pill) shown after save — same pattern as taste notes
**Fixed:**
- Fixed lock badge display bug — both taste notes and common names badges now use display:inline instead of empty string (CSS default was display:none)
**Files:** `app/api/culinary.py`, `frontend/species.html`, `requirements.txt`, `app/services/enrichment.py`, `app/api/chat.py`

### 2026-06-22 10:14
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260622_101427.sqlite`

### 2026-06-22 10:14
**Session ended** — Session ended from Settings page

### 2026-06-22 09:30
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260622_093004.sqlite`

### 2026-06-22 09:30
**Session ended** — Session ended from Settings page

### 2026-06-22 04:29
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260622_042909.sqlite`

### 2026-06-22 04:29
**Session ended** — Session ended from Settings page

### 2026-06-21 15:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260621_154726.sqlite`

### 2026-06-21 15:47
**Session ended** — Session ended from Settings page

### 2026-06-21 11:11
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260621_111135.sqlite`

### 2026-06-21 11:11
**Session ended** — Session ended from Settings page

### 2026-06-21 11:06
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260621_110636.sqlite`

### 2026-06-21 11:06
**Session ended** — Session ended from Settings page

### 2026-06-21 09:43
**Snapshot** — End of session — Fixed isToxic crash, suppressed culinary for toxic species (safety), wired 5 bulk actions into background_processes with global banner widget, cleaned 12.6GB snapshots from git, relocated snapshot storage with retention policy, cleaned orphaned files (63MB).
DB: `snapshots/db_20260621_094315.sqlite`

### 2026-06-21 09:43
**Session ended** — Fixed isToxic crash, suppressed culinary for toxic species (safety), wired 5 bulk actions into background_processes with global banner widget, cleaned 12.6GB snapshots from git, relocated snapshot storage with retention policy, cleaned orphaned files (63MB).

### 2026-06-21 05:55
**Snapshot** — Verify new SNAPSHOTS_DIR
DB: `snapshots/db_20260621_055547.sqlite`

### 2026-06-21 05:54
**Snapshot** — Test snapshot — verify new SNAPSHOTS_DIR
DB: `snapshots/db_20260621_055405.sqlite`

### 2026-06-20 22:16
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260620_221633.sqlite`

### 2026-06-20 22:16
**Session ended** — Session ended from Settings page

### 2026-06-20 21:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260620_214727.sqlite`

### 2026-06-20 21:47
**Session ended** — Session ended from Settings page

### 2026-06-20 20:27
**Diagnostic: DB divergence between DIGIERA and ~/ForagingID — confirmed identical for production data**

**Fixed:**
- file_cleanup.py: thumbnail_path resolved via _PROJECT_ROOT from __file__, not Path.cwd()
- observations.py reject-undo: same fix for thumbnail restore path
- Cleaned orphaned undo file for obs 21216
**Files:** `app/services/file_cleanup.py`, `app/api/observations.py`
**Pending:**
- Merge this session code changes from DIGIERA back to ~/ForagingID
- Revert test-observation rejections in both DBs (21212-21216 in DIGIERA, 21214 in HOME)

### 2026-06-20 20:11
**Fixed path resolution (cwd→__file__), confirmed thumbnail_path safety, cleaned undo dir, audited prior test validity**

**Fixed:**
- file_cleanup.py: thumbnail_path resolved via _PROJECT_ROOT (from __file__) instead of Path.cwd()
- observations.py reject-undo: same fix for thumbnail restore path
- Cleaned orphaned undo file from obs 21216 (first test, pre-reload server)
**Files:** `app/services/file_cleanup.py`, `app/api/observations.py`

### 2026-06-20 19:49
**Added thumbnail cleanup to both Reject and Delete paths, fixed multi-file hard-delete bug**

**Built:**
- thumbnail_path cleanup in delete_observation_file() — resolves relative path, moves to undo dir
- thumbnail_path cleanup in DELETE endpoint — immediate unlink
- thumbnail_path restore in reject-undo — new label branch
**Fixed:**
- Fixed multi-file hard-delete: single task now handles all files (was cancelling earlier tasks, only last file survived)
**Files:** `app/services/file_cleanup.py`, `app/api/observations.py`
**Pending:**
- Existing ~24k orphaned thumbnails — separate diagnostic/cleanup task

### 2026-06-20 19:38
**Closed confirmed_copy_path gap, merged reject-photo into Reject, fixed undo to restore both files**

**Fixed:**
- Added /photos/confirmed_plants/ to delete_observation_file allowlist
- Map confirmRemovePhoto() now calls PATCH review?status=rejected instead of POST reject-photo
- Removed dead reject-photo route from observations.py
- Fixed reject-undo to restore ALL files (file_path + confirmed_copy_path) not just the first match
**Files:** `app/services/file_cleanup.py`, `app/api/observations.py`, `frontend/index.html`
**Pending:**
- Thumbnail cleanup (data/thumbnails/) — standing leak in both Reject and Delete, backlog item
- 21 existing rejected observations with orphaned confirmed copies — retroactive cleanup if wanted

### 2026-06-20 17:04
**Verified delete-on-reject: fixed all 10 call sites to delete AFTER commit, confirmed asyncio task retention, live API tests pass**

**Fixed:**
- All 10 reject paths now call delete_observation_file() after DB commit/flush, not before
- Paths G/H use await session.flush() before delete (service-layer functions that return before caller commits)
- Bulk paths C/D/I/J collect rejected obs and delete after commit loop
- file_cleanup.py logging switched to print() for server log visibility
**Files:** `app/services/file_cleanup.py`, `app/api/observations.py`, `app/api/audit.py`, `app/api/identify.py`, `app/api/upload.py`, `app/api/scan.py`, `app/services/identification.py`, `app/services/prefilter.py`
**Pending:**
- Existing 10,364 rejected observations not yet cleaned — separate backfill task

### 2026-06-18 14:53
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260618_145323.sqlite`

### 2026-06-18 14:53
**Session ended** — Session ended from Settings page

### 2026-06-17 20:51
**Botanical PDF layout fix — text overflowing into corner border area**

**Fixed:**
- print_pdf.html: added padding: 170px to .content for botanical style — matches herbalist 170px horizontal baseline, applied to all four sides to clear 160px corner images (42mm) from all corners; @page normal margin 10mm/8mm + 170px content padding = 53mm left/right and 55mm top/bottom clearance
**Files:** `app/templates/print_pdf.html`
**Pending:**
- Item 4 synonym layer
- Print layout fix — visual verify of botanical PDF needed
- Review queue backlog

### 2026-06-17 19:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260617_190957.sqlite`

### 2026-06-17 19:09
**Session ended** — Session ended from Settings page

### 2026-06-17 19:04
**Apiaceae look_alike_warnings data pass — 16 species, append-safe**

**Fixed:**
- look_alike_warnings written to culinary_info for 16 Apiaceae species (5 groups); 16 culinary_info_history rows inserted with changed_by=human; Conium maculatum skipped as instructed; DB snapshot taken before writes at snapshots/db_20260617_190228.sqlite
**Pending:**
- Item 2 merge diagnostic fix (server restart needed)
- Item 4 synonym layer
- Print layout fix
- Review queue backlog

### 2026-06-17 19:02
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260617_190228.sqlite`

### 2026-06-17 11:57
**WeasyPrint lazy-import fix + CLAUDE.md server command check**

**Fixed:**
- lists_pdf.py: removed module-level WeasyPrint try/except import (lines 17-27 removed); WEASYPRINT_AVAILABLE flag removed
- lists_pdf.py: removed if-not-WEASYPRINT_AVAILABLE 503 guard from generate_pdf
- lists_pdf.py: added lazy import (from weasyprint import HTML as WeasyprintHTML) inside generate_pdf, just before write_pdf() call, with broad Exception catch returning 503
- CLAUDE.md: --reload --reload-dir app flags already present on line 64 — no change needed
**Files:** `app/api/lists_pdf.py`
**Pending:**
- SERVER RESTART REQUIRED: server still running old code (no --reload). Restart with: uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
- Apiaceae one-liner data pass (all 17, append-safe, changed_by=human)
- Item 4 synonym layer

### 2026-06-17 11:48
**4 cleanup tasks: Artemisia vulgaris name fix, 3 tombstone hard-deletes, 3 sibiricum AI draft invalidations, server reload confirmation**

**Fixed:**
- Artemisia vulgaris: preferred_common_name set to Mugwort, common_names corrected from [Japanese mugwort, Korean Mugwort] to [Mugwort], audit row written to CI 29 changed_by=human
- Hard-deleted 3 merge tombstone species rows: Artemisia verlotiorum (72), Ulmus uyematsui (357), Ulmus laevis (627) — all confirmed zero obs/CI/encounters before delete
- Invalidated 3 sibiricum-origin AI drafts on sphondylium (ids 1862/1863/1864): taste_notes, medicinal_notes, recipe — content was sibiricum-specific text
**Pending:**
- SERVER RESTART REQUIRED: server running without --reload, updated merge function CI reparent+delete code not live. Restart with: uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
- Apiaceae one-liner data pass (all 17, append-safe, changed_by=human)
- Item 2 WeasyPrint lazy-import fix
- Item 4 synonym layer

### 2026-06-17 11:47
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260617_114706.sqlite`

### 2026-06-17 11:29
**Part 2: 4 species delete/merge operations complete**

**Fixed:**
- Ulmus laciniata (619): obs 21364 nulled+unidentified, CI+sources+drafts deleted, species hard-deleted
- Artemisia verlotiorum (72) merged into Artemisia vulgaris (98): 1 obs, 44 sources, 3 drafts, CI reparented; verlotiorum CI history (5 rows) manually reparented to vulgaris CI 29
- Ulmus uyematsui (357) merged into Ulmus x hollandica (547): 2 obs, 8 sources, 2 drafts, CI reparented
- Ulmus laevis (627) merged into Ulmus glabra (23): 1 obs by name, 5 sources, 1 draft, CI reparented
- CI orphan cleanup: CI rows 47/309/584 deleted after manual history reparent (server had not reloaded before merges ran)
**Pending:**
- Apiaceae one-liner data pass (all 17, append-safe, changed_by=human)
- Item 2 WeasyPrint lazy-import fix
- Item 3 merge diagnostic - server reload race condition: CI reparent code ran old path for all 3 merges; fixed manually. Should verify server picks up new code on next restart.
- Sphondylium has 4 pending AI drafts including redundant ones from sibiricum reparent (ids 1862/1863/1864) - may want to invalidate

### 2026-06-17 11:21
**Merge function extension (culinary_info_history + species_resources) + Heracleum sibiricum cleanup**

**Built:**
- merge_species: added culinary_info_history reparenting in CI else-branch before db.delete(source_ci)
- merge_species: added species_resources step 13 (string-keyed dedupe + reparent by species_name)
- merge_species docstring updated to 14 top-level tables
**Fixed:**
- Heracleum sibiricum (id=537): obs 19786 species_primary fixed to Heracleum sphondylium
- Heracleum sibiricum: 9 enrichment_sources reparented to sphondylium (id=144)
- Heracleum sibiricum: 3 AI drafts reparented to sphondylium (id=144)
- Heracleum sibiricum: CI row 489 deleted (edible_parts already on sphondylium)
- Heracleum sibiricum: species row hard-deleted
**Files:** `app/api/culinary.py`
**Pending:**
- Ulmus laciniata clean delete + obs 19786 nulled
- Artemisia verlotiorum -> Artemisia vulgaris merge
- Ulmus uyematsui -> Ulmus x hollandica merge
- Ulmus laevis -> Ulmus glabra merge
- Sphondylium now has 4 pending AI drafts (2x medicinal_notes, 1x taste_notes, 1x recipe) — redundant pending drafts from sibiricum reparenting may need invalidating

### 2026-06-17 11:12
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260617_111235.sqlite`

### 2026-06-17 10:46
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260617_104629.sqlite`

### 2026-06-17 10:46
**Session ended** — Session ended from Settings page

### 2026-06-17 10:36
**Tasks 1-4: Veratrum album safety data, Helleborus foetidus prep_warnings, PendingRollbackError fix on bulk-approve enrichment, GitHub popup removed from review.html**

**Fixed:**
- Veratrum album: edibility_status=toxic, toxicity_severity=deadly, preparation_warnings written, history rows locked changed_by=human
- Helleborus foetidus: preparation_warnings written, history row locked changed_by=human
- enrichment.py trigger_ai_drafts_for_species: commit now inside db_write_lock(), OperationalError database-is-locked now calls session.rollback() to prevent PendingRollbackError cascade
- review.html: git-banner script removed, _editsMade flag and all assignments removed, nav/beforeunload showGitBanner listeners removed
**Files:** `app/services/enrichment.py`, `frontend/review.html`
**Pending:**
- Apiaceae one-liner data pass (all 17, append-safe, changed_by=human lock)
- Item 2 WeasyPrint lazy-import fix
- Item 3 merge diagnostic fix
- Item 4 synonym layer

### 2026-06-17 10:24
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260617_102457.sqlite`

### 2026-06-17 10:12
**Write look_alike_warnings for Aconitum napellus and Artemisia vulgaris — authored text, verbatim, human-locked**

**Pending:**
- Apiaceae one-liner data pass (all 17, append-safe, changed_by=human lock)
- Item 2 WeasyPrint lazy-import fix
- Item 3 merge diagnostic fix
- Item 4 synonym layer

### 2026-06-17 10:08
**Prompt 4 of 4: Verify pass — all safety-render consolidation targets confirmed**

### 2026-06-17 06:33
**Prompt 3 of 4: Add severity-coloured safety box to recipe_booklet layout**

**Built:**
- toxicity_severity added to _flatten_species dict in lists_pdf.py
- rb-safety-deadly CSS: dark red background (#7f1d1d), red border-left (#ef4444), white text, WeasyPrint-safe
- rb-safety-toxic CSS: dark amber background (#78350f), amber border-left (#f59e0b), yellow text, WeasyPrint-safe
- rb-safety-h CSS: bold uppercase heading shared by both severity boxes
- recipe_booklet Jinja block: deadly -> skull + NOT SAFE DEADLY + prep_warnings (or default text) + look_alike
- recipe_booklet Jinja block: toxic -> NOT SAFE + prep_warnings (or default text) + look_alike if present
- none severity: safety block omitted entirely (silence is correct for print)
- Default text for empty prep_warnings: appreciation text as specified
**Files:** `app/api/lists_pdf.py`, `app/templates/print_pdf.html`
**Pending:**
- Server restart required for lists_pdf.py change to be live (server runs without --reload)
- Prompt 4 of 4: verify pass (eyeball all four deadly cards + Helleborus + plain toxic + edible)

### 2026-06-17 06:16
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260617_061632.sqlite`

### 2026-06-17 06:16
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260617_061606.sqlite`

### 2026-06-17 06:16
**Session ended** — Session ended from Settings page

### 2026-06-16 20:05
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260616_200539.sqlite`

### 2026-06-16 20:05
**Session ended** — Session ended from Settings page

### 2026-06-16 05:35
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260616_053528.sqlite`

### 2026-06-16 05:35
**Session ended** — Session ended from Settings page

### 2026-06-16 05:29
**Fix Resume button for ai_draft_backfill + fix outstanding count inflation**

**Fixed:**
- _jqResumeJob in scan.html: added ai_draft_backfill special-case before generic /api/queue/{id}/resume call — cancel stuck job, dismiss, POST /api/drafts/backfill (resumes from in-memory resume_from), reload list, return. Identical to existing _jqRerunJob pattern.
- _OUTSTANDING_SQL in culinary.py: added AND EXISTS filter on culinary_info requiring at least one of edible_parts, traditional_uses, or medicinal_folklore to be non-NULL — excludes the 93 no-context species that were permanently inflating the outstanding count.
**Files:** `frontend/scan.html`, `app/api/culinary.py`

### 2026-06-16 05:26
**Taste notes human edit affordance — edit toggle, voice recorder, Whisper transcription, human-lock history row, lock indicator**

**Built:**
- Edit toggle (pencil button, data-guest-hide) on taste notes section heading
- Inline edit panel with textarea pre-filled from current taste_notes value
- Voice recorder widget (same dandelion waveform as Foraging Notes) inside edit panel
- Transcribe button: sends audio to POST /api/culinary/transcribe-audio, populates textarea with Whisper transcript
- Save button: PATCH /api/culinary/{species_name}/taste-notes — server hardcodes changed_by=human, never from client
- Server writes CulinaryInfoHistory row with changed_by=human on every save (the retroactive lock)
- species_profile endpoint now queries taste_notes history and returns taste_notes_human_locked boolean
- Lock badge (purple pill, 🔒 Human-locked) shown in heading when taste_notes_human_locked=true
- Cancel button collapses edit panel and recorder cleanly
- POST /api/culinary/transcribe-audio: temp file, Whisper, delete temp, return transcript — no DB writes, no encounter created
- TasteNotesEdit Pydantic model (value-only, no changed_by field — prevents client from sending changed_by)
**Files:** `app/api/culinary.py`, `frontend/species.html`

### 2026-06-16 05:07
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260616_050739.sqlite`

### 2026-06-16 05:05
**Diagnose + fix unresponsive My Season / Reading note tabs on mobile**

**Fixed:**
- _buildCaptureHTML canvas: added style=display:none — 640px canvas was visible on page load, making document.scrollWidth ~674px and triggering iOS scroll-vs-click disambiguation that swallowed tab taps
- .tab-bar CSS: added overflow-x:auto — prevents any remaining button overflow from widening the document
- .tab-btn CSS: added touch-action:manipulation and flex-shrink:0 — bypasses iOS disambiguation delay, stops buttons shrinking below their text width
**Files:** `frontend/encounters.html`

### 2026-06-16 04:45
**Prompt 2/2: lookup normalization — orphan delete, collapse_autonym helper, rewire 8 name→species sites to name_key, migration NOT NULL + UNIQUE**

**Built:**
- collapse_autonym(name) in app/services/taxonomy.py — collapses trailing autonym tokens (Larix decidua decidua → Larix decidua), case-preserving
- 4 collapse_autonym tests added to tests/test_taxonomy.py (17/17 pass)
- Migration 0038_name_key_not_null_unique — backfills 1 NULL name_key, makes NOT NULL, drops non-unique ix, adds UNIQUE index uq_species_name_key
**Fixed:**
- Deleted orphan culinary_info id=197 (species_id=244, deleted species; content-free PFAF junk). Orphan count = 0.
- scan.py kingdom/fungi gate (~967): scientific_name == → name_key == normalize_taxon_key(species_primary)
- scan.py _upsert_species_card lookup (~1364): scientific_name == → name_key == normalize_taxon_key(scientific_name)
- scan.py _upsert_species_card CREATE (~1382): now stores scientific_name=collapse_autonym(name), name_key=normalize_taxon_key(collapsed)
- scan.py _enrich_new_species_card lookup (~1436): scientific_name == → name_key == normalize_taxon_key(scientific_name)
- enrichment.py _get_or_create_species lookup (~547): scientific_name == → name_key == normalize_taxon_key; CREATE sets name_key + collapse_autonym
- enrichment.py _backfill_taxonomy_from_observations (~585): .lower() comparison → normalize_taxon_key(candidate) == sp.name_key
- enrichment.py trigger_ai_drafts_for_species lookup + CREATE (~1808-1812): rewired to name_key, CREATE sets name_key + collapse_autonym
- identification.py fungi-routing lookup (~123): scientific_name == → name_key == normalize_taxon_key(species_primary)
- reidentify.py confirm-species (~697): new_species = collapse_autonym(body.scientific_name.strip())
**Files:** `app/services/taxonomy.py`, `tests/test_taxonomy.py`, `app/api/scan.py`, `app/services/enrichment.py`, `app/services/identification.py`, `app/api/reidentify.py`, `app/models/species.py`, `migrations/versions/0038_name_key_not_null_unique.py`

### 2026-06-16 04:40
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260616_044040.sqlite`

### 2026-06-16 04:32
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260616_043253.sqlite`

### 2026-06-16 04:32
**Session ended** — Session ended from Settings page

### 2026-06-15 22:18
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260615_221835.sqlite`

### 2026-06-15 22:18
**Session ended** — Session ended from Settings page

### 2026-06-15 22:08
**Add app-level write lock to serialise background job commits vs user write endpoints**

**Built:**
- app/services/write_lock.py: db_write_lock() blocking async context manager
- trust.py:accept_species — commit wrapped
- observations.py:correct_species — commit wrapped
- reidentify.py:confirm_species — commit wrapped
- culinary.py:_run_draft_backfill_task — per-species commit + _jq_set_progress + _jq_finish wrapped
- culinary.py:_run_id_notes_backfill_task — _write_id_notes + _jq_set_progress + _jq_finish wrapped
**Fixed:**
- Eliminated up-to-10s SQLite busy-wait hang on user writes during running backfill jobs
**Files:** `app/services/write_lock.py`, `app/api/trust.py`, `app/api/observations.py`, `app/api/reidentify.py`, `app/api/culinary.py`

### 2026-06-15 17:36
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260615_173643.sqlite`

### 2026-06-15 17:15
**Lookup normalization groundwork — normalize_taxon_key, unit tests, migration 0037, backfill, collision report**

**Built:**
- app/services/taxonomy.py: normalize_taxon_key() pure function
- tests/test_taxonomy.py: 13-case unit test suite
- migration 0037_add_species_name_key: species.name_key VARCHAR nullable, non-unique index
- Species model updated with name_key mapped column
- Backfill: 559/559 rows populated in one transaction
**Files:** `app/services/taxonomy.py`, `tests/test_taxonomy.py`, `migrations/versions/0037_add_species_name_key.py`, `app/models/species.py`
**Pending:**
- Prompt 2: rewire _upsert_species_card and _get_or_create_species to use name_key for matching (depends on collision report review)

### 2026-06-15 16:40
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260615_164025.sqlite`

### 2026-06-15 16:40
**Session ended** — Session ended from Settings page

### 2026-06-15 13:00
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260615_130047.sqlite`

### 2026-06-15 13:00
**Session ended** — Session ended from Settings page

### 2026-06-15 11:48
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260615_114843.sqlite`

### 2026-06-15 11:48
**Session ended** — Session ended from Settings page

### 2026-06-15 08:48
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260615_084851.sqlite`

### 2026-06-15 08:48
**Session ended** — Session ended from Settings page

### 2026-06-15 08:13
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260615_081328.sqlite`

### 2026-06-15 08:13
**Session ended** — Session ended from Settings page

### 2026-06-15 05:36
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260615_053618.sqlite`

### 2026-06-15 05:36
**Session ended** — Session ended from Settings page

### 2026-06-15 05:08
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260615_050805.sqlite`

### 2026-06-14 21:03
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260614_210335.sqlite`

### 2026-06-14 21:03
**Session ended** — Session ended from Settings page

### 2026-06-14 20:58
**Toxic/inedible recipe remediation + goat's beard safety caveat (Prompt 1)**

**Fixed:**
- Prompt B hybrid path gap: enrichment.py _maybe_generate_ai_drafts and _section_ai_draft hybrid blocks now pass preparation_warnings to _build_context and use _build_safety_caveat instead of manual edibility_conditions append. Also gates taste_notes/recipe on generate_culinary flag in _maybe_generate_ai_drafts hybrid path.
- Part A — Aruncus dioicus: preparation_warnings set (327 chars, PFAF + Fontanari 2016 cyanogenic prunasin warning). Recipe and taste_notes regenerated via _section_ai_draft; new pending drafts (2182/2183, hybrid/deepseek) now open with safety caveat verbatim.
- Part B — Carex caryophyllea, Dactylorhiza majalis, Larix kaempferi: live recipe nulled in culinary_info (audit trail via culinary_info_history). Approved draft rows (477, 479, 588, 228) invalidated.
- Part C — Chaerophyllum hirsutum: approved recipe drafts (195 claude-haiku, 1653 data_trust_clear) and taste_notes draft (193) invalidated; live fields confirmed NULL. Hieracium maculatum: approved taste_notes draft (480) invalidated; live field confirmed NULL.
**Files:** `app/services/enrichment.py`
**Pending:**
- Aruncus dioicus: new caveat-bearing pending drafts (2182/2183) need curator approval to go live
- 7 caution species with live recipe but empty preparation_warnings (Prompt B data gap) — curator review needed
- Hybrid path Gap 1 (_maybe_generate_ai_drafts): generate_culinary gate added in this session for fields_needed filter, but no test against unconfirmed-edibility species triggered yet
- Token expiry UX, text-only encounter GPS, ngrok outbox validation (outstanding from prior sessions)

### 2026-06-14 20:51
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260614_205109.sqlite`

### 2026-06-14 17:25
**Diagnose and fix: backfill jobs not appearing in Job Queue UI**

**Fixed:**
- _generate_drafts_for_species (culinary.py:1881): unconditional `if not anthropic_api_key: return` was blocking all species regardless of enrichment_backend setting. With hybrid/DeepSeek backend and no Anthropic key, every species was blocked in ~5ms, completing the job in 0.4s with 0 drafts. Fixed by making the check backend-conditional: only blocks when backend==anthropic AND key absent. Mirrors the correct pattern in _maybe_generate_ai_drafts.
**Files:** `app/api/culinary.py`
**Pending:**
- 78 outstanding medicinal_notes species have zero source context — _ensure_medicinal_default not called by backfill path (separate design gap, not the API-key bug)
- Token expiry UX: explicit expired-token chip state in encounter-queue.js
- Text-only encounter location capture: fire GPS in saveEncounter for text path
- ngrok outbox body-validation before delete
- iNaturalist token refresh
- Takeout batch rescan

### 2026-06-14 17:14
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260614_171401.sqlite`

### 2026-06-14 17:01
**Tier 4 — foraging session model + GPS location suggestions**

**Built:**
- Migration 0034: recorded_walk_id FK on foraging_sessions
- ForagingSession model updated with recorded_walk_id
- PATCH /api/workshop/sessions/{id} — update session (link/unlink recorded walk)
- GET /api/workshop/sessions/{id}/location-suggestions — timestamp-match encounters against GPS track
- workshops.html: sessions table new Walk column + Link walk button
- workshops.html: Link Walk modal — select from recorded walks list
- workshops.html: Location Suggestions modal — per-encounter accept/skip + accept-all
- Backdrop-click-to-close on both modals
- model_fields_set sentinel for null unlink handling
**Files:** `migrations/versions/0034_add_recorded_walk_to_foraging_sessions.py`, `app/models/foray_session.py`, `app/api/workshop_tokens.py`, `frontend/workshops.html`
**Pending:**
- Token expiry UX (finding 3): explicit expired-token chip state in encounter-queue.js
- Text-only encounter location capture (finding 1): fire GPS in saveEncounter for text path
- ngrok outbox body-validation before delete (finding 2)
- Disk + reloader stability investigation
- iNaturalist token refresh
- Takeout batch rescan

### 2026-06-14 16:55
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260614_165547.sqlite`

### 2026-06-14 16:50
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260614_165010.sqlite`

### 2026-06-14 16:50
**Session ended** — Session ended from Settings page

### 2026-06-13 21:43
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260613_214341.sqlite`

### 2026-06-13 21:43
**Session ended** — Session ended from Settings page

### 2026-06-13 21:28
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260613_212826.sqlite`

### 2026-06-13 21:28
**Session ended** — Session ended from Settings page

### 2026-06-13 20:21
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260613_202135.sqlite`

### 2026-06-13 20:21
**Session ended** — Session ended from Settings page

### 2026-06-13 18:23
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260613_182348.sqlite`

### 2026-06-13 18:23
**Session ended** — Session ended from Settings page

### 2026-06-13 16:07
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260613_160708.sqlite`

### 2026-06-13 16:07
**Session ended** — Session ended from Settings page

### 2026-06-13 11:31
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260613_113141.sqlite`

### 2026-06-13 11:31
**Session ended** — Session ended from Settings page

### 2026-06-12 18:01
**Phase 13.1 — guest token layer, encounter scoping, curator-only write guards**

**Built:**
- Migration 0031: workshop_participants + guest_tokens tables; tombstone id=1 reserves curator slot
- WorkshopParticipant and GuestToken SQLAlchemy models added to app/models/workshop.py
- app/api/identity.py: Identity dataclass + get_identity() FastAPI dependency (token/ngrok/localhost resolution)
- POST /api/encounters: anonymous guest → 403; participant token sets user_id + workshop_session_id
- GET /api/encounters: anonymous guest → []; participant token scopes to own user_id; curator sees all
- PATCH /api/species/.../foraging-notes: explicit curator-only guard (identity.is_guest → 403)
- POST /api/notes/: explicit curator-only guard (identity.is_guest → 403)
- app/api/workshop_tokens.py: POST/GET /api/workshop/participants + /tokens (curator-only mint/list)
**Files:** `migrations/versions/0031_add_workshop_participant_tokens.py`, `app/models/workshop.py`, `app/api/identity.py`, `app/api/encounters.py`, `app/api/culinary.py`, `app/api/notes.py`, `app/api/workshop_tokens.py`, `app/main.py`
**Pending:**
- Phase 13.2: Workshops UI
- Takeout batch: rescan → process delta (operational)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh
- iNaturalist token refresh

### 2026-06-12 17:14
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260612_171455.sqlite`

### 2026-06-12 17:14
**Session ended** — Session ended from Settings page

### 2026-06-12 17:14
**Add ESCOP and Commission E as reference-only entries in data_sources registry**

**Built:**
- data_sources id=471: ESCOP Monographs — reference-only, folklore/medicinal synthesis, paywalled, never scraped
- data_sources id=472: Commission E Monographs — reference-only, folklore/medicinal synthesis, print compendium, never scraped
**Files:** `data/foragingid.db (data_sources: 2 rows inserted)`
**Pending:**
- Synonym candidates (35) — manual review
- Takeout batch rescan → process delta (operational)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh
- iNaturalist token refresh

### 2026-06-12 11:39
**EMA clinical tags adapter + dry run — deterministic mapping from EMA herbal monograph JSON to medicinal_clinical tags**

**Built:**
- app/adapters/ package (new directory + __init__.py)
- app/adapters/ema_clinical.py: _load_finalised_monographs, _extract_binomials (no-space-before-authority fix), _part_for (semicolon-safe organ detection), _chip_for, build_chip_plan, _is_human_locked, dry_run, commit
- SYNONYMS map pre-seeded with Matricaria recutita → Matricaria chamomilla
- Write rules: empty-field-only + human-lock guard + ema provenance in history
- Dry run: 28 species would receive chips, 0 skipped-populated, 0 human-locked, 35 synonym candidates held for manual review
**Fixed:**
- Combination-product organ detection bug fixed: _part_for splits on [\s;,]+ not whitespace-only, so Hyperici herba;Cimicifugae rhizoma correctly yields Aerial parts (herba) not Rhizome (rhizoma)
**Files:** `app/adapters/__init__.py`, `app/adapters/ema_clinical.py`
**Pending:**
- Review dry-run output and approve synonym candidates for addition to SYNONYMS map
- Run commit step (separate prompt after review)
- Source file note: EMA JSON lives at docs/ not data/ — prompt referenced data/ema_herbal_medicines_en.json
- Takeout batch rescan → process delta (operational)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh
- iNaturalist token refresh

### 2026-06-12 07:29
**Lock gate fixes: block AI draft generation + approval for human-locked fields**

**Fixed:**
- Fix 1 (enrichment.py:1319): _maybe_generate_ai_drafts now queries CulinaryInfoHistory for changed_by=human before building fields_needed; human-locked fields are filtered out with DEBUG log
- Fix 2 (culinary.py:1715): approve-draft endpoint checks CulinaryInfoHistory for changed_by=human before setattr; raises HTTP 409 if locked
**Files:** `app/services/enrichment.py`, `app/api/culinary.py`
**Pending:**
- Medicinal backfill run (now safe — human lock gates in place)
- Takeout batch: rescan → process delta (operational)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh
- iNaturalist token refresh

### 2026-06-12 07:13
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260612_071320.sqlite`

### 2026-06-12 07:13
**Session ended** — Session ended from Settings page

### 2026-06-12 07:08
**Rename folklore heading + add standing disclaimers to medicinal sections**

**Built:**
- Renamed medicinal_notes label from Herbalism Notes to Folklore & Historical Uses (species card + booklet)
- Removed generic static .medicinal-disclaimer from #sec-medicinal HTML — replaced by conditional per-section disclaimers
- Added .medic-section-disclaimer CSS class (small, muted, italic) for species card disclaimers
- Clinical disclaimer rendered below clinical tags only when clinical section is shown
- Folklore disclaimer rendered below folklore/notes content only when that section is shown
- Booklet: same disclaimers using .entry-note class, conditioned on each block being rendered; code comment records plain-language provenance
**Files:** `frontend/species.html`, `app/templates/print_pdf.html`
**Pending:**
- Takeout batch: rescan → process delta (operational)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh
- iNaturalist token refresh

### 2026-06-12 06:58
**Split medicinal_notes into FOLKLORE and CLINICAL fields**

**Built:**
- Alembic migration 0030: additive medicinal_clinical TEXT column on culinary_info
- Model: medicinal_clinical mapped column on CulinaryInfo
- API: medicinal_clinical in profile response and PATCH allowed_fields
- lists_pdf.py: medicinal_clinical_tags parsed and passed to booklet template
- print_pdf.html: Clinical/Evidence-based block (tag list) before Medicinal preparations block
- species.html: CSS for .clinical-tag/.clinical-tags; clinical tags rendered first in medicinal section, folklore and AI notes below
**Files:** `migrations/versions/0030_add_medicinal_clinical_to_culinary_info.py`, `app/models/culinary.py`, `app/api/culinary.py`, `app/api/lists_pdf.py`, `app/templates/print_pdf.html`, `frontend/species.html`
**Pending:**
- Takeout batch: rescan → process delta (operational)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh
- iNaturalist token refresh

### 2026-06-12 06:03
**Three startup performance fixes: rescue UPDATE gate, defer enrichment import, defer PIL imports**

**Fixed:**
- FIX 1 (database.py): rescue UPDATE now gated behind LIMIT 1 probe — full-table scan skipped on every boot once the fix has been applied (0 rows currently match)
- FIX 2 (enrich.py): moved run_enrichment_batch import from module top level into _run_enrichment_task() — defers bs4/enrichment chain until first enrichment run, not at boot
- FIX 3 (prefilter.py, thumbnail.py): moved PIL/Pillow imports from module top level into the functions that use them — PIL now loads on first image processed, not at import time
**Files:** `app/database.py`, `app/api/enrich.py`, `app/services/prefilter.py`, `app/utils/thumbnail.py`
**Pending:**
- Takeout batch rescan → process delta
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh

### 2026-06-12 05:41
**Fix file_path root for 551 P1 PhoneForaging observations**

**Fixed:**
- 551 P1 observations: file_path updated from /Users/melvinjarman/Documents/PhoneForaging/ to /Users/melvinjarman/Local(unsynced)/PhoneForaging/ — all 551 files confirmed present at new path before update
**Files:** `data/foragingid.db`
**Pending:**
- Takeout batch rescan → process delta
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh

### 2026-06-12 05:41
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260612_054106.sqlite`

### 2026-06-12 05:34
**Fix _ARCHIVE_ROOT_DEFAULT path — remove /Downloads segment**

**Fixed:**
- _ARCHIVE_ROOT_DEFAULT corrected from /Volumes/DIGIERA/Downloads/Pictures to /Volumes/DIGIERA/Pictures
**Files:** `app/api/scan.py`
**Pending:**
- Takeout batch rescan → process delta
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh

### 2026-06-11 22:10
**Add server-side archive scan: POST /api/scan/scan-archive + SSE + Scan archive UI in File Upload panel**

**Built:**
- _ARCHIVE_ROOT_DEFAULT and _archive_queues added to scan.py in-memory state
- POST /api/scan/scan-archive: validates DIGIERA mount, discovers year folders, dry_run probe mode, starts _run_archive_scan background task
- GET /api/scan/archive-progress/{job_id}: SSE stream for archive job (folder_start, file, folder_done, done, error events)
- _run_archive_scan(): sequential year-folder processing — hash, duplicate-check, prefilter, copy to pipeline2/, create Observation, await _identify_scanned()
- Scan archive section added to File Upload panel in scan.html: volume probe on open, year chips, Scan Archive button, per-folder progress bar, summary rows, grand total
**Files:** `app/api/scan.py`, `frontend/scan.html`
**Pending:**
- Takeout batch rescan → process delta (operational task)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh

### 2026-06-11 21:54
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260611_215412.sqlite`

### 2026-06-11 21:54
**Session ended** — Session ended from Settings page

### 2026-06-11 21:48
**BUILD 1: Wire synthesis sources into AI draft generation; BUILD 2: Synthesis sources management UI in Settings**

**Built:**
- SYNTHESIS_SOURCES updated with 5 new domains (healthyhildegard.com, eatweeds.co.uk, gallowaywildfoods.com, wildmanstevebrill.com, botanical.com)
- fetch_synthesis_context() added to culinary_links.py — searches, fetches, and cleans body text for one synthesis domain
- claude_draft.py: synthesis_context param added to generate_ai_drafts(), _build_context(), _context_to_text()
- _MEDICINAL_SYSTEM_PROMPT updated with synthesis-only non-reproduction clause
- enrichment.py _maybe_generate_ai_drafts(): thin-source gate, parallel synthesis fetch from all SYNTHESIS_SOURCES, passed to anthropic + hybrid backends
- GET/POST/DELETE /api/settings/synthesis-sources endpoints added to settings.py
- Synthesis Sources section added to Settings page UI with list, add form, remove buttons, loaded on init
**Files:** `app/integrations/culinary_links.py`, `app/integrations/claude_draft.py`, `app/services/enrichment.py`, `app/api/settings.py`, `frontend/settings.html`
**Pending:**
- Takeout batch rescan → process delta (operational task)
- Roadmap update to v20
- Fix 5 total/geotagged count
- Google Drive token refresh

### 2026-06-11 19:08
**Add curated medicinal note to Alchemilla vulgaris + greenguild.co.uk source classification**

**Built:**
- Curated 2865-char medicinal_notes entry for Alchemilla vulgaris written directly to culinary_info
- CulinaryInfoHistory row (id=410) with changed_by=human for medicinal_notes — permanent human-edit marker
- SpeciesAIDraft row (id=2105) with status=approved, model=human for medicinal_notes — blocks future AI draft generation
- RAW_CONTENT_BLOCKLIST frozenset added to culinary_links.py with greenguild.co.uk
- SYNTHESIS_SOURCES list added to culinary_links.py with greenguild.co.uk as first entry
- Blocklist guard added in _fetch_search() — refuses to fetch any domain in RAW_CONTENT_BLOCKLIST
- Module docstring updated with clear distinction between raw-scrape-blocked and synthesis-reference sources
- TODO comment in code for hooking synthesis sources into claude_draft.py
**Files:** `app/integrations/culinary_links.py`
**Pending:**
- Takeout batch: rescan → process delta (operational)
- Roadmap update to v20
- Fix 5 total/geotagged count — confirm correct thresholds with Melvin
- Google Drive token refresh
- Hook SYNTHESIS_SOURCES into claude_draft.py so greenguild.co.uk is actually read at generation time (when ready)

### 2026-06-11 19:05
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260611_190534.sqlite`

### 2026-06-11 18:23
**Add Seasonal Returns section to booklet output**

**Built:**
- Seasonal returns dropdown (1/5/10/15/20/Foray only, default 10) in Step 2 toolbar on lists.html
- _fetchAndCacheSr() fetches /api/notifications/seasonal-returns?all=true, applies foray filter or numeric cap, caches to localStorage
- _seasonalReturnsHtml() renders section block — omits if empty
- renderPreview() in lists.html injects SR block between cover and species entries
- init() restores dropdown from localStorage, seeds from cache, fetches fresh in background
- print.html reads foragingid_sr_data from localStorage, injects SR block into preview and popup window
- downloadPdf() passes seasonal_returns array in PDF request payload
- lists_pdf.py: seasonal_returns field added to PdfRequest; dates formatted with Python 3.9-safe fromisoformat
- print_pdf.html: SR CSS and HTML section between cover and species-grid; page-break-after for non-field_guide layouts; field_guide uses 2-column sr-grid
**Files:** `frontend/lists.html`, `frontend/print.html`, `app/api/lists_pdf.py`, `app/templates/print_pdf.html`
**Pending:**
- Takeout batch: rescan → process delta (operational, not a code task)
- Roadmap update to v20
- Fix 5 total/geotagged count — confirm correct thresholds with Melvin
- Google Drive token refresh

### 2026-06-11 12:40
**Session B — Review UI fixes: confirmed common name display already in place, confirmed button rename already done, fixed enrichBulkSave gap where species with no field edits never got edibility_verified=True**

**Built:**
- POST /api/culinary/{name}/mark-verified endpoint
- enrichBulkSave: calls mark-verified for all selected species so they always leave the review queue
**Fixed:**
- enrichBulkSave gap: selecting a species with no field edits and clicking Approve selected now sets edibility_verified=True
**Files:** `app/api/culinary.py`, `frontend/review.html`

### 2026-06-11 12:30
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260611_123022.sqlite`

### 2026-06-11 12:30
**Session ended** — Session ended from Settings page

### 2026-06-11 11:20
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260611_112051.sqlite`

### 2026-06-11 08:53
**Audit remediation: removed AI edibility path; fixed backfill lock, domain-scoping, context, counts, provenance, Run-all**

**Built:**
- Run-all orchestrator: one POST /api/drafts/backfill?field=all runs id_notes then a combined draft job sequentially as separate job_queue rows (M15)
- Per-domain scoping threaded through _collect_backfill_targets / _generate_drafts_for_species / _maybe_generate_ai_drafts(only_field) (I6)
- id_notes backfill builds real context via _build_context/_context_to_text (I7), LEFT JOIN + upsert culinary_info (I9), AI provenance recorded (M12)
- backfill-counts Outstanding equals exact target predicate, verified to match _collect_backfill_targets 91/93/81 (I8)
- Self-contained _showToast in scan.html (I10)
**Fixed:**
- C1: _draft_backfill_job released in finally of leaf tasks; orchestrator holds/releases across sequence — backfill no longer single-use
- I8: rejected drafts now outstanding and re-processable (backfill passes reprocess_rejected=True; enrichment unchanged)
- Removed AI edibility_status path entirely per design decision (C2/C3/C4 moot)
- M13: removed dead _BACKFILL_DOMAIN_LABELS/_BACKFILL_JOB_TYPES, draftsRunBackfill shim, dead edibility job handler, unused _context_to_text import
**Files:** `app/integrations/deepseek_draft.py`, `app/services/enrichment.py`, `app/api/culinary.py`, `frontend/scan.html`
**Pending:**
- Run a real backfill end-to-end (needs DeepSeek key)
- Browser screenshot of Backfill panel (preview tooling cannot drive the externally-managed uvicorn server)

### 2026-06-11 07:03
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260611_070349.sqlite`

### 2026-06-11 07:03
**Session ended** — Session ended from Settings page

### 2026-06-11 06:26
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260611_062658.sqlite`

### 2026-06-11 06:26
**Session ended** — Session ended from Settings page

### 2026-06-09 06:46
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260609_064655.sqlite`

### 2026-06-09 06:46
**Session ended** — Session ended from Settings page

### 2026-06-09 04:00
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260609_040024.sqlite`

### 2026-06-09 02:15
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260609_021510.sqlite`

### 2026-06-09 02:15
**Session ended** — Session ended from Settings page

### 2026-06-08 20:24
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260608_202400.sqlite`

### 2026-06-08 20:24
**Session ended** — Session ended from Settings page

### 2026-06-08 20:17
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260608_201750.sqlite`

### 2026-06-08 20:17
**Session ended** — Session ended from Settings page

### 2026-06-08 19:53
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260608_195344.sqlite`

### 2026-06-08 19:53
**Session ended** — Session ended from Settings page

### 2026-06-08 12:55
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260608_125528.sqlite`

### 2026-06-08 12:55
**Session ended** — Session ended from Settings page

### 2026-06-08 12:14
**GPX file import for recorded walks list**

**Built:**
- 📥 GPX button in wbs-recorded-walks-header (stopPropagation so it does not toggle the section)
- Hidden <input type=file accept=.gpx> cleared after each pick so the same file can be re-imported
- _gpxImportPick() programmatically clicks the file input
- _gpxImportFile(): reads file text, DOMParser parses GPX XML, checks parsererror element, extracts <trkpt> lat/lon/ele/time, skips bad points with console.warn, derives started_at/ended_at/duration_s from timestamps, POSTs to /api/recorded-walks (server computes distance_m), on success opens recorded-walks section + reloads list + calls _openRecordedWalk to show on map
- Graceful error handling: file read failure, XML parse error, no trkpts, HTTP error from server — all show alert() with specific message
**Files:** `frontend/index.html`

### 2026-06-08 12:04
**Live recording trace: green solid polyline matching saved-trace style**

**Fixed:**
- _startRecording polyline init: color #c0392b → #2d5016, weight 3 → 3.5, opacity 0.75 → 0.85, removed dashArray:null. No other changes — append-on-state-change architecture was already correct.
**Files:** `frontend/index.html`

### 2026-06-08 12:02
**Simplify _drawRecordedTrace — raw GPS points, green solid line, no ORS**

**Fixed:**
- Removed _tryOrsTrace async function entirely
- _drawRecordedTrace now draws raw GPS track points as solid green polyline (color:#2d5016, weight:3.5, opacity:0.85) — no ORS call, no road-snapping
**Files:** `frontend/index.html`

### 2026-06-08 11:54
**Fix saved walk trace rendering — red raw GPS segments → green ORS/fallback polyline**

**Fixed:**
- _drawRecordedTrace was drawing raw GPS track points as a red (#c0392b) polyline — the live recording colour — with no ORS call and no green fallback
- Fixed: now draws green solid fallback (color:#2d5016, weight:3.5, opacity:0.85) immediately so fitBounds works, then calls new async _tryOrsTrace to upgrade to road-following ORS polyline
- _tryOrsTrace subsamples GPS points to ≤50 waypoints (step = ceil(n/50)), POSTs to /api/walk/ors-route, swaps _recTraceLayer on success; silently keeps green fallback on any error or fallback:true response
**Files:** `frontend/index.html`

### 2026-06-08 09:54
**Fix 1: resume after pause broken; Fix 2: resume after server restart broken**

**Fixed:**
- Fix 1: race guard in _jqRunIdentify — if Pause clicked while progress_total PATCH was in flight, _jqIdentifyDone was null so _pauseIdentify could not reject it; promise hung forever with _jqRunning=true; now throws __paused__ immediately after the PATCH returns if _jqPauseSignal/CancelSignal is set
- Fix 1: _jqResumeJob now explicitly clears _jqPauseSignal/_jqCancelSignal and re-arms _jqOpenSse before calling _jqTick
- Fix 2: Resume button for paused identify jobs is now always enabled (hasMem always true for identify); previously disabled when _p2FolderState=null after page reload
- Fix 2: _jqResumeJob synthesises _p2FolderState from _p2Sessions when missing — finds matching paused/running session, fetches retryable obs from new GET /api/scan/sessions/{id}/retryable-obs endpoint
- Fix 2: new GET /api/scan/sessions/{session_id}/retryable-obs backend endpoint returns failed_identification and pending_identification obs for a session
**Files:** `frontend/scan.html`, `app/api/scan.py`

### 2026-06-08 00:12
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260608_001258.sqlite`

### 2026-06-08 00:12
**Session ended** — Session ended from Settings page

### 2026-06-08 00:00
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260608_000005.sqlite`

### 2026-06-08 00:00
**Session ended** — Session ended from Settings page

### 2026-06-07 23:39
**Fix P2 batch table folder selection and empty-state cell destruction bugs**

**Fixed:**
- available-folders race: handler now skips _updateFolderDropdown if _p2AutoSelectDone is false, preventing it from locking the initial selection to the first alphabetical year folder before sessions load
- Empty-state cell destruction: _renderBatchTableForFolder now restores original <td id=bt-*> cells before writing values if the empty-state branch previously replaced them via tbody.innerHTML
**Files:** `frontend/scan.html`

### 2026-06-07 16:40
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260607_164049.sqlite`

### 2026-06-07 16:40
**Session ended** — Session ended from Settings page

### 2026-06-07 15:58
**Fix walk drawer: drag-from-handle and default open height**

**Fixed:**
- Fix 1 — Drag: replaced onclick-only handle with pointerdown/pointermove/pointerup drag handler. Sheet follows pointer freely; releases at drop position via inline transform. Tap (< 5px movement) still calls _wbsToggle. pointercancel snaps back to CSS-class position. _closeWalkSheet and _wbsToggle clear inline style so class-based transitions take over again.
- Fix 2 — Default height (phone): removed display:none !important from #wbs-empty-state phone rule so JS can show it. Added @media (max-width: 700px) rule: wbs-active:not(.wbs-route-active) opens to calc(100% - 275px) to show all three entry cards. _enterWalkMode now calls _wbsShowEmptyState(). Laptop: bump from 172px to 195px for quickbar breathing room.
**Files:** `frontend/index.html`

### 2026-06-07 15:33
**Scan page colour pass — legibility tweaks for dark UI**

**Fixed:**
- Pipeline title h2 text: dark green/purple on dark card → light green/lilac
- Pipeline tag upload: light purple bg → dark purple bg
- Pipeline desc: #666 on dark → #9aaa88, border lightened to dark
- Status chip hover/open: flash-to-white → dark green hover
- chip-val/chip-label, ss-val/ss-label: dark-on-dark → readable bright variants
- session-stats border, ss-chip border: light #e0e8d0 → dark #4a5e5a
- lifetime-breakdown: light #fbfdf7 bg → dark #2f3d3a; all text inside brightened
- new-files-box all variants: light callout bgs → dark themed equivalents
- dir-badge exists/missing: light bg → dark themed
- btn-pause, btn-wakelock: light #f1f5f9 → dark #2a3c3a
- btn-process-delta: light blue #eff6ff → dark #1a2a3a
- watch-dir-path: dark green #2d5016 on dark → #a8d890
- btn-view-all hover: light #e4edce → dark #3d524e
- source-label, status-line: #555 on dark → #9aaa88
- mc-title, mc-val, mc-desc: dark on dark → readable
- btn-recheck: white bg → dark #2f3d3a
- enrich-progress-wrap: light bg → dark #2f3d3a; enrich-log text brightened
- scan-tab-nav: white bg → #2a3330 (major: always-visible sticky bar)
- scan-tab-btn: #666 → #7a9e88; hover/active → #b8d48a
- sessions-modal header border and title: lightened
- sessions-table td: #333 on dark modal → #d8e4d8
- p2-narration.frozen: light #f4f4f4 bg → dark #2f3d3a
- min-conf-wrap border-top: light → dark
**Files:** `frontend/scan.html`
**Pending:**
- Trust tab cards (white background on dark tab pane — flagged, not in scope of this pass)

### 2026-06-07 15:25
**Restore caffeinate (Keep Mac Awake) as standalone feature in job queue panel**

**Built:**
- Toggle button in job queue panel header: coffee Keep Mac awake / Keeping awake
- Auto-activates when identify job starts running (_jqTick), auto-releases on finish/pause/cancel
- Manual toggle sets _caffManual flag — auto-release skipped if manually enabled
- Backend caffeinate flags updated from -i to -dimsu
**Files:** `frontend/scan.html`, `app/api/scan.py`
**Pending:**
- Scan page colour tweaks
- P1 session display fix (6+6 split)
- Pause/resume reliability on identify
- Stale path cleanup in Syncthing dropdown

### 2026-06-07 15:14
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260607_151433.sqlite`

### 2026-06-07 15:14
**Session ended** — Session ended from Settings page

### 2026-06-07 15:01
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260607_150155.sqlite`

### 2026-06-07 15:01
**Session ended** — Session ended from Settings page

### 2026-06-07 11:20
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260607_112044.sqlite`

### 2026-06-07 11:20
**Session ended** — Session ended from Settings page

### 2026-06-07 11:13
**Fix pause/cancel signals and dismiss persistence in job queue**

**Fixed:**
- Fix 1a: _pauseIdentify now uses _p2FolderState.sessionId directly instead of relying on stale _p2SelectedSession
- Fix 1b: Added _jqCancelSignal flag; _runProcessPass checks _jqPauseSignal||_jqCancelSignal before each file upload to stop loop immediately
- Fix 1c: _jqPauseJob for identify jobs now sets _jqPauseSignal=true before calling _pauseIdentify, stopping orphaned _runProcessPass loop
- Fix 1d: _jqCancelJob detects running identify/filter jobs and sets signals + calls _pauseIdentify before cancelling queue record
- Fix 2: queue_api.py _set_terminal now allows failed->cancelled transition (removed failed from 409 guard), so Dismiss can permanently transition failed jobs out of the always-shown list
**Files:** `frontend/scan.html`, `app/api/queue_api.py`

### 2026-06-07 07:31
**Task 1: Fix folder dropdown (wrong folder, collapses while running). Task 2: Job queue panel between P1 and P2 sections, replacing Keep Mac awake block.**

**Built:**
- Job queue panel between P1 and P2 sections with SSE live updates
- DB-backed job_queue table (migration 0028) — persists across server restarts
- POST /api/queue/enqueue, GET /api/queue/list, GET /api/queue/sse, PATCH /api/queue/{id}, cancel/pause/resume/move-to-top endpoints
- Queue runner in JS: one job at a time, SSE progress hook for identify jobs
- Filter/Identify/Enrich buttons now enqueue jobs instead of running directly
- Pause/Resume/Cancel/Move-to-top controls on each queue panel job
- Removed Keep Mac awake / caffeinate block and wakelock button
**Fixed:**
- Dropdown auto-select now correctly finds running > queued > paused > most-recent session (was only running/queued, missed paused and first-load fallback)
- onFolderSelectChange no longer opens showDirectoryPicker — just updates batch table for selected folder
**Files:** `migrations/versions/0028_add_job_queue.py`, `app/api/queue_api.py`, `app/main.py`, `frontend/scan.html`

### 2026-06-07 07:00
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260607_070006.sqlite`

### 2026-06-07 07:00
**Session ended** — Session ended from Settings page

### 2026-06-07 06:43
**Scan P2 redesign: staged pipeline (Filter/Identify/Enrich) + dropdown fix + iNat badge move**

**Built:**
- Folder dropdown: selecting triggers showDirectoryPicker() → auto-lists files instantly (no hash yet)
- Folder button (drop zone) also triggers listing via _processFolder → _p2ListFolder
- Dropdown shows all unique folders with run counts e.g. 2025 (3 runs)
- Stage machine: idle → listing → listed → filtering → filtered → identifying → identified → enriching
- Filter button: appears after listing; hashes all files with live progress Filtering... N/M; becomes ⏸ Pause while running
- Identify button: appears after filter when new+retryable>0; shows count; becomes ⏸ Pause while running
- Enrich button: appears after identify completes
- SSE done handler sets stage to identified (or filtered on pause)
- Page-load stage restore: if session is running on load, stage set to identifying
- Removed Rescan button — folder picker + listing is now the flow
- Removed iNat token badge from Scan page P2 header (Settings API Dashboard already has it)
**Fixed:**
- Dropdown now shows all folders (with run counts) not just most recent unique
- Removed dead btn-pause / btn-process P2 references
- Dead onProcessDeltaClick and onResumeClick left as unreachable code (harmless)
**Files:** `frontend/scan.html`

### 2026-06-07 06:15
**Scan page P2 section redesign: folder dropdown + batch table + consolidated buttons**

**Built:**
- Folder dropdown replacing session selector — groups sessions by source_path basename, defaults to most recently added
- Batch table with 6 cumulative columns (Received/Non-image/Already done/New/Retryable/Failed) and 3 live columns (Approved/In review/Rejected)
- Green flash on live column value increases
- Status line below table showing current run state
- Rescan button — opens folder picker + hash+classify (replaces folder-button flow)
- Process button — replaces Process delta + Reprocess pending, hidden when New+Retryable=0
- Pause button — visible only while session is running
- SSE handler updates status line live during processing
- Global summary bar (6 chips) verified correct against DB: total_seen=11218, auto_approved=514, manually_approved=39, in_review=130, pending=285, rejected=10249
**Fixed:**
- Removed btn-reprocess-pending and btn-process-delta DOM references
- Removed btn-resume DOM reference (resume via Rescan+Process flow instead)
- Fixed _processFolder to hide btn-process not btn-process-delta
**Files:** `frontend/scan.html`

### 2026-06-07 00:18
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260607_001848.sqlite`

### 2026-06-07 00:18
**Session ended** — Session ended from Settings page

### 2026-06-07 00:02
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260607_000213.sqlite`

### 2026-06-07 00:02
**Session ended** — Session ended from Settings page

### 2026-06-06 23:57
**Four fixes: Load saved expansion, Record live laptop msg, default layer, saved walk trace**

**Fixed:**
- Fix 1 (Load saved, laptop): _wbsLoadSaved now hides route controls (walk-tabs, walk-tab-stops, walk-tab-stats, wbs-bottom-actions, walk-ors-note, walk-sync-btn, wbs-empty-state) before opening sheet so saved/recorded walks sections are immediately visible without scrolling
- Fix 2 (Record live, laptop): _wbsStartRecording checks !isMobile(); on laptop opens sheet and shows #wbs-laptop-record-msg with message instead of calling _wrecToggle/GPS; mobile path unchanged
- Fix 3 (default layer, phone+laptop): one-time localStorage version bump (foragingid_layer_version=3) clears stale foragingid_default_layer so Outdoors becomes default again when Thunderforest key loads
- Fix 4 (saved walk trace, laptop): loadSavedWalk now tries ORS endpoint for a road-following polyline; if ORS unavailable, fallback is a solid green line (weight:3.5, opacity:0.85) matching ORS style instead of thin dashed; added map.fitBounds so route is visible on load
**Files:** `frontend/index.html`

### 2026-06-06 23:49
**Laptop walk mode: quickbar buttons above bottom-sheet handle**

**Built:**
- #wbs-quickbar HTML: 3 compact buttons (Create from map / Record live / Load saved) placed before #wbs-handle
- CSS: quickbar hidden by default; laptop media query shows it when wbs-active + not wbs-route-active + not wbs-open; peek height overridden to 172px (128px quickbar + 44px handle)
- wbs-route-active class: added by renderWalkPanel and _wbsStartRecording; cleared by _closeWalkSheet; hides quickbar and reverts to normal 44px peek
- _wbsStartLasso: simplified to just _enterLassoSelect() — quickbar stays visible, lasso draws over map
- _wbsStartRecording: adds wbs-route-active, opens sheet to show live stats, calls _wrecToggle
- _wbsLoadSaved: opens sheet (wbs-open) without wbs-route-active so user can load a walk from collapsibles
- _enterWalkMode: removed laptop auto-open and _wbsShowEmptyState — quickbar now handles the no-route entry state via CSS
**Files:** `frontend/index.html`
**Pending:**
- Verify in browser: quickbar appears above handle on laptop walk mode entry

### 2026-06-06 23:34
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_233435.sqlite`

### 2026-06-06 23:34
**Session ended** — Session ended from Settings page

### 2026-06-06 23:34
**Laptop walk panel: replace right panel with slide-up bottom sheet**

**Built:**
- Desktop @media block for #walk-bottom-sheet replaced: was fixed right panel (width:320px, right:0), now just max-height:68vh + scrollable stops — uses same slide-up transform mechanic as phone
- _enterWalkMode: on laptop adds wbs-open immediately so sheet slides fully open; shows empty state if no route
- renderWalkPanel: on laptop ensures wbs-open is added so route content is immediately visible
- _buildWalkRoute: opens sheet on both phone and laptop before renderWalkPanel fires
- _wbsStartLasso: fixed to remove wbs-open (collapse sheet) instead of removing wbs-active (which hid the sheet entirely)
- Stale comments updated: HTML comment, two JS comments referencing right panel
**Files:** `frontend/index.html`
**Pending:**
- Confirm in browser: walk mode on laptop slides sheet up from bottom with 3 entry cards
- Confirm route renders and sheet opens after lasso select or saved walk load

### 2026-06-06 23:19
**Walk bottom sheet: 5-task fix (recorded walks click, empty state, lasso ghost, popup cleanup)**

**Built:**
- Task 1: _openRecordedWalk now calls fitBounds to render route on map; removed _showWalkDetail call on desktop
- Task 2: Walk bottom sheet verified complete on laptop (wbs-active shows right panel)
- Task 3: #wbs-empty-state with 3 entry cards (Create from map, Record live, Load saved); shown on laptop when walk mode opens with no route; hidden when route loads
- Task 4: Lasso _lassoKeyDown (Escape) and _lassoDocClick (click outside map) handlers added/removed in _enterLassoSelect/_exitLassoSelect
- Task 5: Confirmed #walk-view fully removed; all bottom sheet functions verified present
**Fixed:**
- Removed _showWalkDetail call on desktop in _openRecordedWalk — was opening hidden sidebar behind walk bottom sheet
- Added map.fitBounds() after _drawRecordedTrace so route is always visible on click
- Added _wbsShowEmptyState/_wbsHideEmptyState/_wbsRestoreRouteContent helpers
- Added id=wbs-bottom-actions to bottom action buttons div for show/hide control
- Lasso ghost box: added document-level Escape key and click-outside handlers
**Files:** `frontend/index.html`
**Pending:**
- Confirm recorded walks render on map (phone + laptop) in browser
- Empty state appears on laptop Walk mode entry

### 2026-06-06 23:05
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_230520.sqlite`

### 2026-06-06 23:05
**Session ended** — Session ended from Settings page

### 2026-06-06 23:01
**Walk panel migration: fix recorded walk click, migrate walk-view to bottom sheet right panel, lasso fixes**

**Built:**
- Task 1: Fixed recorded walk onclick (JSON.stringify double-quote bug broke attribute; name arg removed)
- Task 1: _openRecordedWalk on mobile closes sheet after drawing route instead of opening sidebar detail
- Task 2+4: #walk-bottom-sheet now serves as fixed right panel on laptop (320px, right:0, below nav)
- Task 2+4: Migrated all walk-view content into #wbs-body — tabs, route stops, stats, buttons, saved/recorded lists
- Task 5: #walk-view removed from HTML and CSS; all classList.add/remove walk-view references cleaned up
- Task 3: Lasso hint overlay shown when lasso active on laptop (Draw an area to select species pins)
- Task 3: Ghost lasso rect fixed — _hideLassoRect() called first in _exitLassoSelect so rect always clears on dismiss
**Fixed:**
- loadSavedWalksList and loadRecordedWalksList now target single wbs-* elements only
- toggleSavedWalksList / toggleRecordedWalksList delegate to _wbsToggle* wrappers
- renderWalkPanel guards getElementById(walk-title) with if() in case element missing; shows wbs-header-block on desktop
- _walkSyncPending stale recorded-walks-list update removed
**Files:** `frontend/index.html`
**Pending:**
- Confirm recorded walks render on map on both phone and laptop
- Session tab on /lists
- Elevation lookup warnings expected (no outbound internet)

### 2026-06-06 22:36
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_223632.sqlite`

### 2026-06-06 22:36
**Session ended** — Session ended from Settings page

### 2026-06-06 22:04
**Five changes: rename Lists→Booklets, restructure toolbars, remove Install App**

**Fixed:**
- Renamed Lists→Booklets: page title, h2, nav active link in lists.html
- Renamed Lists→Booklets: nav links in about, encounters, index, my-season, review, scan, settings, species
- lists.html toolbar: 3 steps — Step 1 Format unchanged, Step 2 Content (Cover first, then 8 toggles), Step 3 Print Preview (Session+Clear+Print page)
- lists.html: removed Step 3 Design block (Botanical/Herbalist/Goethean) from toolbar entirely
- lists.html cover panel: removed print-style toggle (Botanical/Herbalist/Goethean) from inside cover panel
- print.html toolbar: added Step 4 Design (Botanical/Herbalist/Goethean) with step-label, added Step 5 label for Download PDF
- print.html: removed print-btn (openPrintWindow), back-btn text updated to Booklets, empty-state link updated
- pwa.js: removed Install App button (beforeinstallprompt handler + makeInstallButton), kept service worker registration
- PDF confirmed: botanical 1.1M, herbalist 1.0M, goethean 1.2M all HTTP 200
**Files:** `frontend/lists.html`, `frontend/print.html`, `frontend/about.html`, `frontend/encounters.html`, `frontend/index.html`, `frontend/my-season.html`, `frontend/review.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/species.html`, `frontend/static/js/pwa.js`

### 2026-06-06 21:51
**Fix PDF border rendering for all three print styles**

**Fixed:**
- setPrintStyle() in print.html now syncs window._pdfData.style so PDF style matches toolbar selection
- WeasyPrint base_url set to frontend/ dir so static image paths resolve correctly
- Botanical PDF: added 4 corner PNG images (corner flowing light/bold) via position:fixed, kept thin border line
- Herbalist PDF: added left/right side strip divs with serrated-leaves PNG background, increased content padding to 170px
- Added server-side logging: style, layout, margins, species count, template markers, base_url
**Files:** `app/api/lists_pdf.py`, `app/templates/print_pdf.html`, `frontend/print.html`

### 2026-06-06 21:08
**Move 4-step toolbar from print.html to lists.html bottom toolbar**

**Built:**
- lists.html: 4-step-group toolbar (Format/Content/Design/Print) at bottom of page
- lists.html: tb-style-toggle in Step 3 synced via syncToolbar and setPrintStyle
- lists.html: step-group CSS with dark green theme, .tb-btn / .tb-btn-action / .tb-btn-danger
- lists.html: cover panel and session panel bottom offset bumped to 80px
**Fixed:**
- print.html: restored simple single-row toolbar (CSS + HTML)
- print.html: removed module-level state (_layout, _ct, _names etc) and syncToolbar/setLayout/toggleCt/rerender
- print.html: restored local-variable main(), keeps window._pdfData for downloadPdf
- print.html: downloadPdf uses structured payload (no margins-select, defaults to normal)
- lists.html: removed stale #session-tab-btn duplicate CSS block
**Files:** `frontend/print.html`, `frontend/lists.html`, `frontend/static/sw.js`

### 2026-06-06 20:44
**Snapshot** — End of session — Toolbar redesign (print.html): two-row layout with four labelled step groups; layout toggle and content toggle buttons added; setLayout/toggleCt/rerender/syncToolbar functions added; module-level state hoisted. Workshop image-forward: ws-banner-photo full-width at top, safety section toggle-gated. Step 4 buttons clearly visible (white/green action style). lists.html: PRELOADER_DEFAULTS removed from setLayout — toggles now independent of layout selection. PDF endpoint tested: all 3 layout x style combinations return valid PDFs.
DB: `snapshots/db_20260606_204436.sqlite`

### 2026-06-06 20:44
**Session ended** — Toolbar redesign (print.html): two-row layout with four labelled step groups; layout toggle and content toggle buttons added; setLayout/toggleCt/rerender/syncToolbar functions added; module-level state hoisted. Workshop image-forward: ws-banner-photo full-width at top, safety section toggle-gated. Step 4 buttons clearly visible (white/green action style). lists.html: PRELOADER_DEFAULTS removed from setLayout — toggles now independent of layout selection. PDF endpoint tested: all 3 layout x style combinations return valid PDFs.

### 2026-06-06 20:22
**Snapshot** — End of session — Tightened Goethean PDF layout: injected page_margin/goe_width/goe_pad variables into print_pdf.html template via surgical Python string replacement (base64 data untouched). Added margins param (narrow/normal/wide) to PdfRequest model and _MARGIN_MAP in lists_pdf.py. Added Margins dropdown to print.html toolbar; downloadPdf() reads selected value and includes it in POST payload. Image crop was a no-op (both PNGs are 512x1024 full-bleed). All three margin variants tested and confirmed returning valid PDFs.
DB: `snapshots/db_20260606_202245.sqlite`

### 2026-06-06 20:22
**Session ended** — Tightened Goethean PDF layout: injected page_margin/goe_width/goe_pad variables into print_pdf.html template via surgical Python string replacement (base64 data untouched). Added margins param (narrow/normal/wide) to PdfRequest model and _MARGIN_MAP in lists_pdf.py. Added Margins dropdown to print.html toolbar; downloadPdf() reads selected value and includes it in POST payload. Image crop was a no-op (both PNGs are 512x1024 full-bleed). All three margin variants tested and confirmed returning valid PDFs.

### 2026-06-06 19:23
**Snapshot** — End of session — Built server-side Jinja2 template app/templates/print_pdf.html with all three print styles (botanical SVG border rule, herbalist warm background, goethean with base64-embedded oak leaf PNGs). Updated app/api/lists_pdf.py to accept structured PdfRequest (species list + profiles + style/layout/toggles/cover), render via Jinja2, pass to WeasyPrint. Updated print.html downloadPdf() to POST window._pdfData as structured JSON. All three styles return valid PDFs confirmed via curl.
DB: `snapshots/db_20260606_192355.sqlite`

### 2026-06-06 19:23
**Session ended** — Built server-side Jinja2 template app/templates/print_pdf.html with all three print styles (botanical SVG border rule, herbalist warm background, goethean with base64-embedded oak leaf PNGs). Updated app/api/lists_pdf.py to accept structured PdfRequest (species list + profiles + style/layout/toggles/cover), render via Jinja2, pass to WeasyPrint. Updated print.html downloadPdf() to POST window._pdfData as structured JSON. All three styles return valid PDFs confirmed via curl.

### 2026-06-06 19:06
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_190635.sqlite`

### 2026-06-06 19:06
**Session ended** — Session ended from Settings page

### 2026-06-06 19:02
**Snapshot** — End of session — Installed WeasyPrint 66.0. Added POST /api/lists/pdf endpoint (app/api/lists_pdf.py) with DYLD_LIBRARY_PATH fix for M1, graceful import guard, and FileResponse returning PDF. Wired router into main.py. Added Download PDF button and inline error span to print.html toolbar. Added weasyprint==66.0 to requirements.txt.
DB: `snapshots/db_20260606_190244.sqlite`

### 2026-06-06 19:02
**Session ended** — Installed WeasyPrint 66.0. Added POST /api/lists/pdf endpoint (app/api/lists_pdf.py) with DYLD_LIBRARY_PATH fix for M1, graceful import guard, and FileResponse returning PDF. Wired router into main.py. Added Download PDF button and inline error span to print.html toolbar. Added weasyprint==66.0 to requirements.txt.

### 2026-06-06 18:48
**Investigated back button on print.html — concluded button and /lists route are both correct; issue was server crash not a code bug**

### 2026-06-06 18:19
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_181930.sqlite`

### 2026-06-06 18:19
**Session ended** — Session ended from Settings page

### 2026-06-06 16:42
**Scan page display fix — SSE re-attach on reload, poll acceleration, SW cache bump**

**Fixed:**
- Fix 1: loadP2Sessions() init now re-attaches SSE via _p2OpenSse() if a running session is found on page load
- Fix 2: loadP2Sessions() init escalates poll to _P2_POLL_ACTIVE_MS (4s) if running session found, not stuck at 15s idle
- Fix 3: SW cache version bumped foragingid-v4 → foragingid-v5 to bust old cached scan.html
**Files:** `frontend/scan.html`, `frontend/static/sw.js`

### 2026-06-06 15:37
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_153706.sqlite`

### 2026-06-06 15:37
**Session ended** — Session ended from Settings page

### 2026-06-06 14:49
**Edibility status + safety warnings backfill**

**Fixed:**
- No Alembic migration needed — caution/toxic already valid in VARCHAR(30) column
- Symphytum officinale edibility_status: edible → caution
- Rumex obtusifolius edibility_status: caution → edible
- Comfrey preparation_warnings: pyrrolizidine alkaloid warning written
- Comfrey look_alike_warnings: Foxglove confusion text written
- renderList: caution badge added (⚠ caution amber); toxic/inedible split to ✗ labels
- Profile pills: human-readable labels with ✓/⚠/✗ prefixes instead of raw DB value
- Safety section: preparation_warnings now rendered first (before look_alike_warnings)
- Lasso bottom sheet: human-readable edibility labels with ✓/⚠/✗ prefixes
**Files:** `frontend/species.html`, `frontend/index.html`

### 2026-06-06 14:37
**Walk Mode Bottom Sheet — consolidate walk popup into bottom sheet**

**Built:**
- wbs-summary section: stops count, distance, duration — shown when route active
- wbs-upload section: upload pending walks button, driven by _walkUpdateSyncBtn()
- wbs-lasso section: lasso-selected species list with name/common/edibility/profile link
- _wbsUpdateSummary() function — updates walk summary in bottom sheet
- _wbsRenderLasso() function — renders species list from ForagingList into wbs-lasso
- showWalkRoute() mobile path: opens bottom sheet instead of sidebar walk-view
- Google Maps button hidden on < 1024px via media query
**Fixed:**
- _exitWalkMode() resets wbs-summary, wbs-lasso, wbs-upload on teardown
- _walkSyncPending() disables wbs-sync-btn during upload
**Files:** `frontend/index.html`

### 2026-06-06 14:22
**Walk Mode Map Fix — 4 bugs in GPS walk recording**

**Fixed:**
- Bug 1: _detachWalkDraw() called at start of _startRecording() to re-enable map drag
- Bug 2: WalkRecorder.isRecording() guard added to map.on(click) handler
- Bug 3: WalkRecorder no longer owns GPS watch — uses GPS.getLast() in _tick(), GPS.getOnce() to seed on start
- Bug 4: map.invalidateSize() called after walk-rec-hud gains .active class
**Files:** `frontend/index.html`, `frontend/static/js/walk-record.js`

### 2026-06-06 12:54
**Fix 1 investigated (no code gap found), Fix 2 — remove German names from species list tiles**

**Fixed:**
- Fix 1: Investigated list endpoint vs profile endpoint common name fields — both use _parse_json_list(sp.common_names) and sp.preferred_common_name from the same DB row. No code gap. 20 species have no common names in DB (data gap, not code). No change needed.
- Fix 2: Removed common-de div from renderList tile template (line 1411). Profile view DE names via renderProfile untouched. DE toggle button still works for profile view.
**Files:** `frontend/species.html`

### 2026-06-06 12:39
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_123909.sqlite`

### 2026-06-06 12:39
**Session ended** — Session ended from Settings page

### 2026-06-06 12:31
**Darken safety record box and edibility badges in species.html**

**Fixed:**
- .safety-clear #f0fdf4/#14532d → #1e3028/#7ac8a0
- .safety-warn #fff4f4/#7b0000 → #2e1a1a/#e08080
- .edibility-edible/caution/inedible/unknown — all light backgrounds darkened
- .edib-cond-chip #f0fdf4 → #1e3028; .has-unsafe #fef2f2 → #2e1a1a
- JS inline obs-badges for edible/conditional — darkened to match
**Files:** `frontend/species.html`

### 2026-06-06 12:27
**Species profile view dark theming + input box darkening across all pages**

**Fixed:**
- species.html profile view: .section white → #283830, section h3 #2d5016 → #8ab87a, field values #333 → #c8d8c0
- species.html: profile header .sci/#2d5016 → #8ab87a, .common #555 → #c8d8c0, .back-link sage
- species.html: #prof-rename-form dark bg, inputs dark, buttons sage-themed
- species.html: ai-field-block, recipe-block, id-notes-block, field-recipe-card, recipe-bank-card all darkened
- species.html: recipe-season-tab, de-toggle, prof-send-review-btn, chat-send-btn, prof-edit-save-bar #2d5016 → #3a5c2a
- species.html: culinary links #2d5016 → #8ab87a
- species.html: #species-search, #chat-input, .fn-notes, .resources-add-form inputs, .fn-name-input → background #2f3d3a
- review.html: #ingest-form input → background #2f3d3a
- index.html: #map-search-input #fafcf7 → #2f3d3a
- scan.html: .trust-filter-bar select, .trust-tool-row select white → #2f3d3a
**Files:** `frontend/species.html`, `frontend/review.html`, `frontend/index.html`, `frontend/scan.html`

### 2026-06-06 12:21
**Heading/subtitle colour pass + badge/chip/card-title consistency across all frontend pages**

**Fixed:**
- species.html: #list-view h2 #2d5016 → #8ab87a; .subtitle #666 → #7a9a7a
- about.html: .about-section h2 #2d5016 → #8ab87a
- settings.html: .page-title h2 #2d5016 → #8ab87a; .page-subtitle #666 → #7a9a7a
- upload.html: h2 #2d5016 → #8ab87a; .subtitle #666 → #7a9a7a
- lists.html: #list-page h2 #2d5016 → #8ab87a
- encounters.html: h2 #c8e6a0 → #8ab87a; .subtitle #999 → #7a9a7a; .enc-species #c8e6a0 → #a8c88a (card title)
- my-season.html: h2 #c8e6a0 → #8ab87a; .subtitle #999 → #7a9a7a
- index.html: .nearme-name #2d5016 → #a8c88a; .find-name #2d5016 → #a8c88a (card title equivalents)
**Files:** `frontend/species.html`, `frontend/about.html`, `frontend/settings.html`, `frontend/upload.html`, `frontend/lists.html`, `frontend/encounters.html`, `frontend/my-season.html`, `frontend/index.html`

### 2026-06-06 12:08
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_120815.sqlite`

### 2026-06-06 12:08
**Session ended** — Session ended from Settings page

### 2026-06-06 11:38
**Foreground colour pass — body color #d8e4d8 across app pages, landing.html text colours updated for dark bg**

**Fixed:**
- body color: #222 → #d8e4d8 on about, review, scan, settings, species, upload, lists
- landing.html body color #1a2e0a → #d8e4d8
- landing.html .logo #2d5016 → #a8d890
- landing.html .tagline #3a4a2a → #b8ccb8
- landing.html .footer #6b7a55 → #7a9e80
- landing.html #learn .back and h1 #2d5016 → #a8d890
- landing.html .prose p and .btn-ghost left unchanged (self-contained bg)
**Files:** `frontend/about.html`, `frontend/review.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/species.html`, `frontend/upload.html`, `frontend/lists.html`, `frontend/landing.html`
**Pending:**
- Run fungi edibility backfill: curl -X POST http://localhost:8000/api/culinary/backfill-fungi-edibility

### 2026-06-06 11:36
**Global background colour pass — #2a3330 app-wide, #1e2b28 lists page**

**Built:**
- Background colour unified across all app pages to #2a3330
- Lists page set to #1e2b28 (one shade darker)
- encounters.html and my-season.html aligned from #1a1a1a to #2a3330 (text already light)
**Files:** `frontend/about.html`, `frontend/encounters.html`, `frontend/index.html`, `frontend/landing.html`, `frontend/lists.html`, `frontend/my-season.html`, `frontend/review.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/species.html`, `frontend/upload.html`
**Pending:**
- Foreground colour pass (see contrast flags below) — awaiting confirmation
- Run fungi edibility backfill

### 2026-06-06 11:32
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_113210.sqlite`

### 2026-06-06 11:32
**Session ended** — Session ended from Settings page

### 2026-06-06 11:28
**Phase 12 follow-up: Encounter tag extraction — rename Extract to Tag + surface suggestions inline**

**Built:**
- Part 1: Renamed Extract to Tag — button labels (Tag / Re-tag), in-progress text (Tagging), error text (Tagging failed). Endpoint, CSS class, onclick handler unchanged.
- Part 2: _renderSuggestions now skips confirmed non-recipe items; _renderRecipeSuggestion returns empty string when confirmed; panel wrapper hidden when all items are resolved.
**Files:** `frontend/encounters.html`

### 2026-06-06 11:12
**Phase 12 follow-up: Species card edibility lock + send-for-review + source notes + backfill endpoint**

**Built:**
- Parts 1-3 confirmed already built in previous session (CHANGELOG 11:09 entry)
- Part 4: POST /api/culinary/backfill-fungi-edibility — queries all fungi species (kingdom ilike fungi OR obs_category=fungi) where edibility not set and not verified; runs _maybe_enrich_fungi_edibility per species in short-lived sessions; bp_start/bp_progress/bp_finish for background_processes tracking; double-check guards at runtime; returns written/queued_review/failed/skipped summary; defined before {species_name:path} catch-all (route idx=1, first catch-all idx=4)
**Files:** `app/api/culinary.py`

### 2026-06-06 11:09
**Phase 12 follow-up: Species card edibility lock + flag-for-review + source notes display**

**Built:**
- Part 1: toggleEditMode() in species.html — _EDIBILITY_LOCKED set guards edibility_status and edibility_verified from ever becoming textareas; skip guard fires before any DOM manipulation
- Part 2: flagEdibilityForReview() function + prof-edibility-flag container rendered in renderProfile(); button shown when edibility_status exists AND NOT (edibility_verified=True AND edibility_human_verified=True); posts to /api/culinary/{name}/request-review with edibility field note
- Part 3: prof-fungi-notes container rendered in renderProfile(); only shown for kingdom=fungi AND fungi_edibility_notes present; plain text Source notes: label, no markdown rendering
- DB migration 0027: added nullable notes TEXT column to culinary_info_history
- CulinaryInfoHistory model: notes field added
- enrichment.py _maybe_enrich_fungi_edibility: history row now includes FAO notes + MO status + confidence in notes column
- culinary.py species_profile endpoint: added edibility_human_verified (bool from history) and fungi_edibility_notes (str from fao+mo history row notes) to response
**Files:** `frontend/species.html`, `app/api/culinary.py`, `app/models/species.py`, `app/services/enrichment.py`, `migrations/versions/0027_add_notes_to_culinary_info_history.py`

### 2026-06-06 10:58
**Phase 12 Prompt 1: Fungi edibility second source integration — FAO scrape + Mushroom Observer lookup**

**Built:**
- Part 1: app/integrations/fao_fungi.py — fetch_fao_edibility() async scraper for wildusefulfungi.org; 10s timeout, 2s crawl delay, graceful None on failure; extracts edibility verdict only; toxic checked before edible in _classify_text()
- Part 2: app/integrations/mushroom_observer.py extended — fetch_mo_edibility() keyword-map inference from MO description; reuses search_by_name(); confidence=0.4; toxic signals checked before edible; never raises
- Part 3: app/services/fungi_edibility.py — resolve_fungi_edibility() two-source agreement service; asyncio.gather concurrent fetch; FAO base=0.6, MO corroboration +0.3, MO conflict -0.3, single source capped at 0.5; final safety invariant: requires_review → edibility_verified=False unconditionally
- Part 4: enrichment.py — _maybe_enrich_fungi_edibility() wired into enrich_species() after PFAF/Wikidata; guards: is_fungi check (kingdom or obs_category), edibility not already set, not edibility_verified, no human history on edibility_status; writes edibility on verified result; queues SpeciesAIDraft on requires_review; both fail → no change, no exception
- Part 5: database.py init_db() — INSERT OR IGNORE for Mushroom Observer in data_sources (was absent from registry); FAO Wild Edible Fungi confirmed as ID 36 (not 35 as prompt stated)
**Fixed:**
- Corrected data_sources ID: FAO Wild Edible Fungi is ID 36 not 35; MO was absent from registry — added via idempotent init_db INSERT
**Files:** `app/integrations/fao_fungi.py`, `app/integrations/mushroom_observer.py`, `app/services/fungi_edibility.py`, `app/services/enrichment.py`, `app/database.py`

### 2026-06-06 10:42
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_104247.sqlite`

### 2026-06-06 10:42
**Session ended** — Session ended from Settings page

### 2026-06-06 10:22
**Offline Walk Save: GPX Export + IndexedDB Queue + Sync**

**Built:**
- Layer 1: GPX 1.1 download on save modal confirm — triggered before server POST, works offline
- Layer 2: IndexedDB (foragingid_walks store) write on confirm — status=pending immediately, upgraded to synced on server success; failure shows Saved locally toast and closes modal
- Layer 3: Sync button below Recorded Walks list — visible only when pending>0, uploads each pending walk with audio, per-walk inline status, duplicate guard by name+started_at
**Files:** `frontend/index.html`

### 2026-06-06 10:07
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_100757.sqlite`

### 2026-06-06 10:07
**Session ended** — Session ended from Settings page

### 2026-06-06 07:17
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260606_071732.sqlite`

### 2026-06-06 07:17
**Session ended** — Session ended from Settings page

### 2026-06-05 23:56
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_235612.sqlite`

### 2026-06-05 23:56
**Session ended** — Session ended from Settings page

### 2026-06-05 23:44
**Prompt J — Wire encounter export into End Session flow**

**Built:**
- dev.py: extracted _export_encounters_to_obsidian(since=None) shared async function — queries encounters with optional date cutoff, writes per-encounter markdown notes to ~/Documents/Obsidian/ForagingID/foraging/, append-only
- dev.py: one-time POST /api/dev/export-encounters-to-obsidian now delegates to _export_encounters_to_obsidian(since=None)
- dev.py end_session step 7: calls _export_encounters_to_obsidian(since=last_snapshot_dt) — uses git log --skip=1 to find the previous snapshot timestamp as the since cutoff; falls back to None (all) if no prior snapshot; wrapped in try/except so failures never block end-session; result included in response as encounter_export
**Files:** `app/api/dev.py`

### 2026-06-05 23:44
**Snapshot** — End of session — Prompt J test run
DB: `snapshots/db_20260605_234422.sqlite`

### 2026-06-05 23:44
**Session ended** — Prompt J test run

### 2026-06-05 23:32
**Prompt I — Encounter export to Obsidian (test run)**

**Built:**
- app/api/dev.py: POST /api/dev/export-encounters-to-obsidian — queries all encounters with species join, builds dated markdown notes, writes to ~/Documents/Obsidian/ForagingID/foraging/; append-only (skips existing files); deduplicates same-date same-species via encounter id suffix
**Files:** `app/api/dev.py`
**Pending:**
- Wire into End Session permanently (next prompt)

### 2026-06-05 23:15
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_231519.sqlite`

### 2026-06-05 23:15
**Session ended** — Session ended from Settings page

### 2026-06-05 23:13
**Fix 5 — DB lock: background enrichment batch holding session open across full loop**

**Fixed:**
- enrichment.py run_enrichment_batch: removed session parameter (now Optional, ignored); initial species-name query uses its own short-lived AsyncSessionLocal context; per-species loop opens a fresh AsyncSessionLocal per item and commits+closes before the next iteration — no write-lock held across the batch
- culinary.py _run_enrichment_job: removed the outer async with AsyncSessionLocal() that wrapped the entire run_enrichment_batch call; draft_count query now uses its own short-lived session
- itis.py _run_backfill: confirmed already correct — short-lived sessions per item, not held across loop
**Files:** `app/services/enrichment.py`, `app/api/culinary.py`

### 2026-06-05 23:06
**Prompt H — Voice library wired into enrichment and chat prompt builders**

**Built:**
- enrichment.py _section_ai_draft: loads load_voice_context(recipe) for taste/recipe fields, load_voice_context() for medicinal; passes voice_context= into _draft_kwargs
- chat.py: loads load_voice_context() and prepends to system_prompt with blank-line separator; graceful fallback if loader raises
- claude_draft.py: voice_context param added to generate_ai_drafts and all three _generate_* helpers; prepended to system string at call time
- ollama_draft.py: same voice_context threading through generate_ollama_drafts and all three _generate_* helpers
**Files:** `app/services/enrichment.py`, `app/api/chat.py`, `app/integrations/claude_draft.py`, `app/integrations/ollama_draft.py`

### 2026-06-05 22:35
**Prompt G — Voice library: folder, seed file, and loader service**

**Built:**
- voice_library/ folder created at project root
- voice_library/melvin_voice.md — seed file with ## Values and ## Recipe examples sections (3 placeholder recipes: elder rob jelly, cleavers spring tonic, nettle soup)
- app/services/voice_library.py — loader: _parse_file, _extract_sections, load_voice_context(context) — Python 3.9 compatible (Optional[str] instead of str|None)
**Files:** `voice_library/melvin_voice.md`, `app/services/voice_library.py`
**Pending:**
- Prompt H: wire load_voice_context into enrichment and chat prompt builders

### 2026-06-05 22:28
**Four fixes: raw_data AttributeError, Wake Lock button, ITIS backfill, lasso null-coordinate guard**

**Fixed:**
- Fix 1: enrichment.py _section_ai_draft — replaced row.raw_data with row.raw_response_json (correct EnrichmentSource column name), confirmed clean on Ulmus uyematsui POST /api/culinary/.../enrich?section=taste
- Fix 2: scan.html _initWakeLock — changed btn.style.display = empty-string to inline-block so Wake Lock button becomes visible when Wake Lock API is available
- Fix 3: ITIS backfill completed — 286 accepted / 159 no_match / 25 synonym / 37 still-pending (API timeout errors)
- Fix 4: map.py geojson — added longitude.isnot(None) guards to both species and landscape queries; index.html lasso — added null-coordinate guard before latLngToContainerPoint to prevent NaN pixels bypassing spatial check
**Files:** `app/services/enrichment.py`, `frontend/scan.html`, `app/api/map.py`, `frontend/index.html`

### 2026-06-05 22:12
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260605_221249.sqlite`

### 2026-06-05 22:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_220929.sqlite`

### 2026-06-05 22:09
**Session ended** — Session ended from Settings page

### 2026-06-05 21:54
**Species chat panel — POST /api/species/{name}/chat + collapsible frontend panel**

**Built:**
- app/api/chat.py: stateless single-turn endpoint, loads Species + CulinaryInfo + raw iNat/Trompenburg sources, builds context via _build_context/_context_to_text, routes to Ollama or Anthropic with fallback, 400-token cap on Anthropic
- app/main.py: registered chat_api router
- species.html CSS: .chat-panel, .chat-msg (user/assistant/thinking), .chat-input-row, .chat-section-heading
- species.html HTML: #sec-chat after #sec-other-resources, collapsible panel with #chat-history + input row
- species.html JS: toggleChat() open/close + chevron flip, sendChat() appends user bubble immediately then thinking placeholder then response, Enter key on input, _chatAppend(), _chatScrollBottom()
**Files:** `app/api/chat.py`, `app/main.py`, `frontend/species.html`
**Pending:**
- Wake Lock fix: _initWakeLock sets display=empty-string instead of inline-block — button stays hidden
- Items 3 and 4 of the earlier four-item prompt were not received
- Prompt E: Caffeinate to scan page
- Prompt F: ITIS backfill run

### 2026-06-05 21:36
**Enrichment queue per-card Repopulate + per-section Repopulate on species card**

**Built:**
- review.html: restored Repopulate button on each enrichment queue card (alongside Send for re-ID); enrichRepopulateCard() refreshes textareas and confidence badge inline
- species.html: small Repopulate buttons added to Taste & Texture, Recipe Bank, Medicinal section headings (hidden until species loads, suppressed for toxic)
- culinary.py enrich_species_now: optional ?section=taste/recipe/medicinal query param — section path skips PFAF/Wikidata, calls _section_ai_draft only
- enrichment.py _section_ai_draft(): single-field AI draft generator — respects edibility gate, loads existing ci context, calls active backend (ollama or anthropic), invalidates existing pending draft before queuing new one
**Files:** `frontend/review.html`, `frontend/species.html`, `app/api/culinary.py`, `app/services/enrichment.py`
**Pending:**
- Items 3 and 4 from the prompt were cut off — not implemented
- Prompt E: Caffeinate to scan page
- Prompt F: ITIS backfill run

### 2026-06-05 21:15
**Ollama integration: local Mistral 7B backend with Anthropic fallback for enrichment draft generation**

**Built:**
- app/integrations/ollama_draft.py: HTTP-based Ollama client, same edibility gate as claude_draft, imports system prompts from claude_draft, raises OllamaConnectionError on unreachable server
- settings_service.py: enrichment_backend (anthropic/ollama) and ollama_model settings in AI group
- enrichment.py _maybe_generate_ai_drafts: reads enrichment_backend at call time, routes to ollama_draft or claude_draft, catches OllamaConnectionError and falls back to Anthropic with warning log
- aiohttp installed to venv for async HTTP to Ollama
- API key guard updated: skipped when backend=ollama so Ollama runs without ANTHROPIC_API_KEY
**Files:** `app/integrations/ollama_draft.py`, `app/services/settings_service.py`, `app/services/enrichment.py`
**Pending:**
- Settings page dropdown renders via existing _buildControl choices renderer — no HTML change needed
- Prompt E: Caffeinate to scan page
- Prompt F: ITIS backfill run

### 2026-06-05 20:59
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_205913.sqlite`

### 2026-06-05 20:59
**Session ended** — Session ended from Settings page

### 2026-06-05 20:34
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_203432.sqlite`

### 2026-06-05 20:34
**Session ended** — Session ended from Settings page

### 2026-06-05 20:33
**Durable background_processes infrastructure: schema, service, API, enrichment/ITIS wiring, settings diagnostic, enrichment tab banner**

**Built:**
- Migration 0026: background_processes table (process_id, process_type, status, started/updated/heartbeat, progress_current/total, detail, error)
- app/models/process.py: BackgroundProcess SQLAlchemy model
- app/services/background_processes.py: bp_start, bp_progress, bp_heartbeat, bp_finish, bp_set_status, bp_active_count, bp_active_row helpers (fire-and-forget safe)
- app/api/processes.py: GET /api/processes/active, POST /{id}/pause, POST /{id}/cancel
- app/main.py: registered processes_api router + BackgroundProcess model noqa import
- culinary.py enrichment: 409 concurrency guard returns structured error with BP detail; bp_start on run start; bp_progress every 5 items; bp_finish on complete/failed
- itis.py backfill: bp_start on trigger; bp_progress every 5 items; bp_finish on complete/failed; cancel signal via _backfill_state[_cancelled]
- settings.html: Background Processes group — one-time load on page open, shows running/stalled rows, Cancel button for stalled only
- review.html: enrich-process-banner div with progress bar, detail, Pause button; _enrichStartBgPoll/_enrichStopBgPoll tied to enrichment tab switch; polls /api/processes/active every 5s
**Files:** `migrations/versions/0026_add_background_processes.py`, `app/models/process.py`, `app/services/background_processes.py`, `app/api/processes.py`, `app/main.py`, `app/api/culinary.py`, `app/api/itis.py`, `frontend/settings.html`, `frontend/review.html`
**Pending:**
- Data Trust fixes (scenery cards, toxic species flagging)
- Caffeinate to scan page
- ITIS backfill run
- Scan page overlay (left as-is per spec — existing mechanism stable)

### 2026-06-05 19:56
**Data Trust Integrity Checks: unified checkbox select + bulk action bar, replace per-category batch buttons**

**Built:**
- Removed Send all / Reject all buttons from breakdown table and all category panel headers (Re-enrich all kept for missing_common_name)
- Added checkbox column to per-category detail tables (only categories with bulk actions)
- Select all in category checkbox in each panel column header
- Sticky bulk action bar (#audit-bulk-bar) — appears when ≥1 checked, shows contextual buttons
- Contextual buttons: Send to review, Reject, Mark as landscape, Clear culinary content
- _AUDIT_SEND_TO_REVIEW_TYPES updated: removed non_plant_approved, added missing_gps + ai_field_no_draft
- _AUDIT_REJECT_TYPES, _AUDIT_LANDSCAPE_TYPES, _AUDIT_CULINARY_TYPES type sets added
- Bulk JS: _auditBulkSend, _auditBulkReject, _auditBulkLandscape, _auditBulkClearCulinary, _auditClearSelection, _auditUpdateBulkBar
- Selection reset on results re-render
- POST /api/trust/bulk-landscape: sets obs_category=landscape, review_status=not_applicable, clears species
- POST /api/trust/bulk-clear-culinary: nulls 8 culinary fields, creates SpeciesAIDraft audit records per field
- audit.py send-to-review _demote() now sets review_label=data_trust
**Files:** `frontend/scan.html`, `app/api/trust.py`, `app/api/audit.py`
**Pending:**
- Data Trust fixes (scenery cards, toxic species flagging — confirmed bulk-clear now in place)
- Caffeinate to scan page
- ITIS backfill

### 2026-06-05 18:26
**Add review_label column to observations — controlled vocabulary for review queue reason**

**Built:**
- Alembic migration 0025: adds review_label VARCHAR(32) to observations
- Backfill: 18 existing needs_review rows labelled (failed_id:12, low_confidence:4, non_plant:2)
- Observation model: review_label field with comment
- ObservationOut schema: review_label field
- scan.py: all needs_review write paths now set review_label (failed_id, low_confidence, non_plant)
- trust.py bulk-send: sets data_trust; kingdom-audit: sets non_plant
- observations.py category→landscape: sets manual_review; label-counts endpoint added; review_label filter param
- review.html: Queue reason dropdown (hidden if all zero), label pill on cards, _LABEL_DISPLAY map
**Files:** `migrations/versions/0025_add_review_label_to_observations.py`, `app/models/observation.py`, `app/api/observations.py`, `app/api/scan.py`, `app/api/trust.py`, `frontend/review.html`
**Pending:**
- culinary.py needs_enrichment label (no needs_review write path found in culinary.py — confirm with Melvin)
- Data Trust fixes (scenery cards, toxic species flagging)
- Caffeinate to scan page
- Group 4 Data Trust bulk select/actions
- ITIS backfill

### 2026-06-05 18:08
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_180820.sqlite`

### 2026-06-05 18:08
**Session ended** — Session ended from Settings page

### 2026-06-05 18:07
**Group 3 species card fixes: foraging notes save, edit toggle, other resources**

**Built:**
- Foraging notes: removed onblur auto-save, added explicit Save button; saveForagingNotes() now snapshots _profCurrentSciName at click time, removes _fnNotesDirty guard
- Edit toggle: desktop-only button (>700px) next to Rename; toggleEditMode() converts all [data-field-key] value divs to textareas; saveEditMode() PATCHes only changed fields with changed_by=human; cancelEditMode() restores or reloads profile; floating sticky save bar at bottom
- _renderFields() and _field() now emit data-field-key + data-field-orig on value divs; safety warn spans, taste_notes, and medicinal_notes blocks also tagged
- Other resources section: species_resources table (SpeciesResource model, created by create_all); GET/POST/DELETE /api/species/{name}/resources + /upload endpoints; media stored at media/species_resources/; served at /media/species-resources/; collapsible Add resource form with link input and file upload
- toast() function and #sp-toast element added to species.html; window._lastProfileData stored in renderProfile for edit mode
**Files:** `frontend/species.html`, `app/models/species.py`, `app/config.py`, `app/api/resources.py`, `app/main.py`

### 2026-06-05 17:40
**Enrichment review queue redesign — bulk actions, no per-card save/repopulate**

**Built:**
- Bulk bar: Save changes, Repopulate, Resolve flag, Reject buttons with danger styling
- enrichBulkSave(): saves changed fields (change-detected via data-orig), auto-repopulates, resolves flags, removes from queue
- enrichBulkRepopulate(): per-species narration line, refreshes textareas + confidence badge inline, data-orig updated after fill
- enrichBulkReject(): calls clear-review, removes from local _enrichData
- _enrichNarration() helper: narration div below bulk bar, auto-hides after 4s
- _enrichField(): removed Save button, textarea is full-width, data-orig attribute for change detection
- _renderEnrichCard(): removed per-card Repopulate button and pop-result span
- enrichBulkResolveFlags(): updated endpoint URL, always removes resolved cards from _enrichData
- Removed populateSpecies() and saveEnrichField() dead code entirely
**Files:** `frontend/review.html`

### 2026-06-05 17:27
**Data sovereignty enforcement — low severity fixes**

**Fixed:**
- _ensure_medicinal_default: checks culinary_info_history for human-edited medicinal_notes before auto-writing; routes to pending SpeciesAIDraft if human history found
- Whisper foraging_notes append: checks culinary_info_history for human-edited foraging_notes; routes transcript to pending SpeciesAIDraft (field=foraging_notes, model=whisper) instead of direct append if human history found
- _apply_wikidata_to_species: made async (one caller updated); for non-toxic edibility values, checks edibility_verified; if True queues wikidata suggestion as pending SpeciesAIDraft (field=edibility_status, model=wikidata) instead of overwriting
**Files:** `app/services/enrichment.py`, `app/api/encounters.py`

### 2026-06-05 17:21
**Data sovereignty enforcement — high and medium severity fixes**

**Fixed:**
- Batch enrichment: run_enrichment_batch() now queries culinary_info_history per species and passes protected_fields to enrich_species(), preventing human-edited culinary fields from being overwritten on re-enrich
- Kingdom gate: auto-reject in _identify_scanned() now skips observations where review_status=manually_verified or human_corrected=True
- handle_species_rename: added is_rename=True parameter; edibility_status/edibility_verified reset only when is_rename=True; trust.py bulk-reassign passes is_rename=False to preserve curated edibility on merge
**Files:** `app/services/enrichment.py`, `app/api/scan.py`, `app/api/trust.py`

### 2026-06-05 17:13
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_171308.sqlite`

### 2026-06-05 17:13
**Session ended** — Session ended from Settings page

### 2026-06-05 17:01
**Batch section buttons made contextual**

**Built:**
- Process delta: visible only after rescan when new+retryable > 0 (unchanged — already correct)
- Pause: visible when _reprocessActive or session.status=running+not stalled
- Resume: visible when session.status=running AND is_stalled (heartbeat lost)
- Reprocess pending: visible when pending count > 0 (removed !_reprocessActive guard)
**Fixed:**
- _renderP2StatusBadge now handles _reprocessActive priority before checking session state
- Paused sessions no longer show Resume button (user must re-select folder)
**Files:** `frontend/scan.html`
**Pending:**
- Group 2 review queue fixes

### 2026-06-05 16:56
**Scan page 5-part cleanup: remove rescan button, ALL TIME section, dot reconciliation → batch chips, badge colour, upsert rescan sessions by source_path**

**Built:**
- Rescan folder button removed from action row
- ALL TIME collapsible (s2-breakdown) removed; loadBreakdown(2) calls removed
- Reconciliation data folded into batch chips: New / Retryable / Already done added; Skipped renamed Non-image
- RESCANNED badge now neutral dark (#1c1c1c) matching complete
- POST /api/scan/rescan upserts by source_path — finds most recent session for folder, updates it instead of creating new row
**Fixed:**
- Removed _runBucket, _sumHtml, p2-rescan-summary div/CSS, sessionStorage p2_rescan_summary persist/restore
- _processFolder progress now goes through _showNarration
**Files:** `frontend/scan.html`, `app/api/scan.py`
**Pending:**
- Group 2 review queue fixes

### 2026-06-05 16:44
**Remove scan-session-banner and all associated JS**

**Fixed:**
- Removed #scan-session-banner HTML element and CSS
- Removed _SCAN_KEY, _initScanSession, _updateScanSession, _clearScanSession, _restoreScanSession, _renderScanBanner
- Removed all _updateScanSession() call sites from _uploadFile()
- Removed _restoreScanSession() from page init
**Files:** `frontend/scan.html`
**Pending:**
- Group 2 review queue fixes

### 2026-06-05 16:32
**Add GET /api/scan/p2-stats + replace P2 top chips with 6 observation-level chips**

**Built:**
- GET /api/scan/p2-stats — queries observations WHERE upload_source=file_upload, returns total_seen/auto_approved/manually_approved/in_review/pending/rejected
- P2 status bar: 6 chips fed from /api/scan/p2-stats on same poll as existing stats
**Fixed:**
- Used _sqla_text alias (not text) to match existing import in scan.py
**Files:** `app/api/scan.py`, `frontend/scan.html`
**Pending:**
- Group 2 review queue fixes

### 2026-06-05 16:12
**P2 scan page restructure — top chips, batch section reorder, reconciliation row, badge colours**

**Built:**
- Top status bar reduced to 4 passive chips: Today / Identified / Needs Review / All Time
- Batch section: session dropdown + live-coloured badge + Pause + Reprocess pending buttons in This batch row
- Reconciliation row below batch table: rescan summary + Rescan folder button + Process delta + Resume stalled batch
- Narration below reconciliation row
- Status badge CSS: dark green running, dark red paused/stalled, near-black complete
**Fixed:**
- Removed all btn-pause-chip references (element removed from DOM)
- u-stat-pending-id kept as hidden span in batch row so JS still works
**Files:** `frontend/scan.html`
**Pending:**
- Group 2 review queue fixes

### 2026-06-05 16:06
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260605_160611.sqlite`

### 2026-06-05 16:06
**Session ended** — Session ended from Settings page

### 2026-06-05 16:04
**iNat kingdom gate in scan.py + breakdown refresh on session change**

**Built:**
- iNat kingdom gate in _identify_scanned: rejects non-plant/fungi taxa at ≥5% confidence before candidate merge
- onP2SessionChange now calls loadBreakdown(2) so lifetime breakdown re-fetches on selection change
**Files:** `app/api/scan.py`, `frontend/scan.html`

### 2026-06-04 15:50
**Fix reprocess state, chip colour, pause button, button layout**

**Built:**
- _reprocessActive flag with stall detection (300s no change → red)
- Pause during reprocess calls concurrency:0 to drain queue
- Init sequence awaits loadP2Sessions before loadUploadStats
**Fixed:**
- Buttons wrapped in flex-shrink:0 div — no mobile overflow
- Chip colour now driven by _reprocessActive when session row absent
- Page-load race fixed
**Files:** `frontend/scan.html`

### 2026-06-04 15:05
**Scan page: remove source selector, move buttons to stat bar, fix chip colours**

**Fixed:**
- Source selector HTML removed; getIdSource() hardcoded to both; inline source read hardcoded to both
- Identifying chip colour: dark green=running, dark red=paused, default near-black=else (no grey-zero suppression via direct className)
- Buttons already in stat chip row as direct children of status-bar — no structural change needed
**Files:** `frontend/scan.html`

### 2026-06-04 14:56
**Scan page: reprocess pending button + identifying chip colour fix**

**Built:**
- Reprocess pending button visible when pending-id > 0, fires POST /api/scan/reprocess-pending, starts active polling
- Identifying chip colour fix: reads _p2Sessions (most recent running) not _p2SelectedSession; polling loop calls loadUploadStats on every tick not just on session stop
**Fixed:**
- _startP2Polling now calls loadUploadStats() every tick so chip colour updates during active runs
- loadUploadStats uses _p2Sessions.find(running) instead of stale _p2SelectedSession
**Files:** `frontend/scan.html`

### 2026-06-04 14:46
**Scan page: identifying chip colour + pause chip button + narration persistence**

**Built:**
- Identifying chip turns green when session running, red when stalled
- Pause button added next to Identifying chip, synced with session panel pause button via _renderP2StatusBadge
- _freezeNarration() keeps last narration line greyed with complete/paused label instead of hiding on SSE done or pause
**Files:** `frontend/scan.html`

### 2026-06-04 14:34
**Fix Select all button not selecting visible cards**

**Fixed:**
- selectAllVisible() was querying .obs-card[data-obs-id] but cards have id=card-N with no data-obs-id attribute; fixed selector to .obs-card[id^=card-] with id.replace parse, matching selectNoMatch pattern
**Files:** `frontend/review.html`

### 2026-06-04 14:32
**Fix bulkAction removeCard cascade causing multiple loadPage races**

**Fixed:**
- bulkAction now animates cards out and calls loadPage once instead of per-card removeCard which raced N loadPage calls
**Files:** `frontend/review.html`

### 2026-06-04 14:30
**Fix rejected obs reappearing in Status=All queue**

**Fixed:**
- list_observations now implicitly excludes review_status=rejected when no status filter provided; rejected rows only surface via explicit Manually rejected filter
**Files:** `app/api/observations.py`

### 2026-06-04 14:18
**Bulk unlock pre-filter button in review queue**

**Built:**
- bulkUnlockPrefilter() JS function calling POST /api/scan/{id}/override-prefilter for each selected obs
- Unlock pre-filter selected button in bulk-bar toolbar
**Files:** `frontend/review.html`

### 2026-06-04 14:15
**Map controls shift with sidebar open/close**

**Built:**
- Leaflet zoom, GPS, and scale controls shift left 300px when sidebar pane opens, transition matches sidebar animation (0.25s cubic-bezier)
**Files:** `frontend/index.html`

### 2026-06-04 13:58
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260604_135854.sqlite`

### 2026-06-04 13:58
**Session ended** — Session ended from Settings page

### 2026-06-04 13:34
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260604_133448.sqlite`

### 2026-06-04 13:34
**Session ended** — Session ended from Settings page

### 2026-06-04 13:16
**Add POST /api/scan/reprocess-pending endpoint**

**Built:**
- POST /api/scan/reprocess-pending — queries observations by review_status + file_path filter, resets identification_status, queues batches of 20 through _identify_scanned via asyncio.create_task
- _reprocess_pending_batch helper — batched gather with per-batch logging, respects existing _INAT_SEMAPHORE
**Files:** `app/api/scan.py`
**Pending:**
- Verify chanterelle appearing in species search + enrichment triggered
- Verify approved obs bounce guard
- Re-run 2024 delta cleanly
- Phase 12 Prompt 3 — participant copy generation (WeasyPrint)
- ITIS backfill status check
- Google Drive token refresh

### 2026-06-04 12:51
**Snapshot** — End of session — Extensive Walk UI fixes: bottom sheet show/hide logic, record button (onpointerup, stopPropagation, _walkTouchStart button bail-out), draw controls merged into single row inside #walk-mode-toggle, #walk-draw-banner removed, HUD repositioned above handle, walk exit cleaned up (no sidebar pop, tab highlight cleared), pin legend via _pinsExplicit flag
DB: `snapshots/db_20260604_125105.sqlite`

### 2026-06-04 12:51
**Session ended** — Extensive Walk UI fixes: bottom sheet show/hide logic, record button (onpointerup, stopPropagation, _walkTouchStart button bail-out), draw controls merged into single row inside #walk-mode-toggle, #walk-draw-banner removed, HUD repositioned above handle, walk exit cleaned up (no sidebar pop, tab highlight cleared), pin legend via _pinsExplicit flag

### 2026-06-04 12:50
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260604_125004.sqlite`

### 2026-06-04 12:50
**Session ended** — Session ended from Settings page

### 2026-06-04 11:38
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260604_113849.sqlite`

### 2026-06-04 11:38
**Session ended** — Session ended from Settings page

### 2026-06-04 10:26
**Walk recording UI — float button placement + bottom sheet on mobile**

**Built:**
- Confirmed #wrec-float-btn is a direct child of #map (position:absolute, phone-only)
- Added #walk-bottom-sheet (position:fixed, phone-only via @media max-width:700px)
- Bottom sheet has drag handle bar + bold chevron (▴/▾) at top centre
- Sheet starts collapsed (only 44px handle visible); walk tab tap expands it; second tap or chevron tap collapses
- Bottom sheet contains: draw mode Rect/Circle buttons (reuses .wmt-btn, auto-synced by setWalkDrawMode), saved walks list, recorded walks list
- setLayer(walk) on mobile opens bottom sheet instead of right panel/sidebar
- setLayer(walk) on desktop unchanged (right panel/sidebar behavior)
- _exitWalkMode() calls _closeWalkSheet() to hide the sheet
- loadSavedWalksList() and loadRecordedWalksList() now also populate #wbs-saved-walks-list and #wbs-recorded-walks-list mobile copies
**Files:** `frontend/index.html`
**Pending:**
- Verify chanterelle appearing in species search + enrichment triggered
- Verify approved observations no longer bouncing
- Re-run 2024 delta cleanly with fixed pipeline
- Phase 12 Prompt 3 — participant copy generation (WeasyPrint)
- ITIS backfill status check

### 2026-06-04 09:50
**Walk recording UI — full-screen map mode refactor**

**Built:**
- Removed Record walk button and Cache area button from Walk panel
- Added floating circular Record button (#wrec-float-btn) on map top-right, phone-only (hidden >700px)
- Idle state: outlined circle with footprint icon; recording state: solid red pulsing
- HUD changed from position:absolute to position:fixed with safe-area-inset-bottom for mobile browser chrome
- HUD audio note button now opens inline MediaRecorder — tap to start, tap again to stop
- Audio recorded via HUD button is preserved through to save modal (not cleared on _openSaveModal)
- Walk tab mobile comment updated
**Files:** `frontend/index.html`
**Pending:**
- Verify chanterelle appearing in species search + enrichment triggered
- Verify approved observations no longer bouncing
- Re-run 2024 delta cleanly with fixed pipeline
- Phase 12 Prompt 3 — participant copy generation (WeasyPrint)
- ITIS backfill status check

### 2026-06-04 09:46
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260604_094622.sqlite`

### 2026-06-04 09:46
**Session ended** — Session ended from Settings page

### 2026-06-04 08:52
**Full fixes batch — scan, review, map**

**Built:**
- Fix 4: Clickable bucket counts (new/retryable) run only that subset; reconciliation bar persists via sessionStorage
- Fix 5: Keep Mac Awake moved from Settings to Scan page between P1 and P2 sections
- Fix 8: Recently added sort option in review queue
- Fix 12: Walk toolbar button opens right panel on mobile
**Fixed:**
- Fix 1: Session dropdown now uses /sessions/all — shows all sessions, no limit=10 cap
- Fix 2: _p2_auto_close + _p2_tick use files_new+retryable as target/total — prevents processed>received and shows correct progress count
- Fix 3: Resume button shows when session is running but SSE is not connected (post-page-refresh mid-batch)
- Fix 6: Pipeline 1 -> Phone, Pipeline 2 -> Folder in scan page labels and sessions modal
- Fix 7: Defensive AND filter in needs_review query — approved/manually_verified/rejected explicitly excluded
- Fix 9: Cantharellus cibarius obs_category set to fungi, kingdom set to Fungi, common_names added, edibility_status=edible, enrichment triggered
- Fix 10: Leaflet top-right controls (zoom+GPS) pushed below toolbar on mobile (top:82px)
- Fix 11: Tab strip chevrons made bolder (font-weight:700, opacity:0.75)
**Files:** `app/api/scan.py`, `app/api/observations.py`, `frontend/scan.html`, `frontend/review.html`, `frontend/index.html`

### 2026-06-04 08:27
**Phase 12 Prompt 2 — Session/Foray model**

**Built:**
- Alembic migration 0024: foraging_sessions, session_species, session_attendees tables
- SQLAlchemy models: ForagingSession, SessionSpecies, SessionAttendee
- API router /api/sessions: list, create, get, patch, delete
- POST /api/sessions/{id}/auto-populate: populates from walk obs_ids_json
- POST/DELETE /api/sessions/{id}/species + PATCH reorder
- POST/DELETE /api/sessions/{id}/attendees
- Session panel in /lists: 4th toolbar tab (Session)
- New session form: name, date, walk dropdown, location override, status, notes
- Auto-populate triggers on walk save; shows auto/manual species counts
- Species list with source badges (auto/manual) and remove button
- Species search autocomplete from _baseSpecies
- Attendee list with add/remove
- Load session into list button: replaces ForagingList content
- Cover page pre-fill from session name/date/location on load
- Active session persisted in localStorage
**Files:** `migrations/versions/0024_add_foraging_sessions.py`, `app/models/foray_session.py`, `app/api/foray_sessions.py`, `app/main.py`, `frontend/lists.html`

### 2026-06-04 06:27
**Fix session dropdown missing 2024 batch**

**Fixed:**
- rescan_folder now regenerates label from new source_path + total when updating existing session — prevents stale folder name persisting in dropdown
- Dropdown label builder uses source_path fallback and appends state suffix (interrupted/ready/paused) per session
- Direct DB patch: session 31 label corrected from Photos from 2025 to Photos from 2024
**Files:** `app/api/scan.py`, `frontend/scan.html`

### 2026-06-04 06:22
**Fix process-delta pre-filtering — only upload new files**

**Fixed:**
- rescan endpoint now returns new_sha256s list alongside counts
- Frontend filters imageFiles to only new ones before storing in _p2FolderState
- _runProcessPass narration uses local filtered count instead of server files_to_process
- Re-running 2024 folder will show Identifying X of 1053 not X of 18456
**Files:** `app/api/scan.py`, `frontend/scan.html`

### 2026-06-04 06:19
**ITIS name-match banners in review queue**

**Built:**
- Yellow synonym banner with Rename to accepted name button on Species ID cards
- Red no_match banner on Species ID cards
- Green ITIS verified badge on Species ID cards
- Same three banners on Enrichment Review cards
- itisAcceptRename() JS function calling POST /api/itis/accept-rename/{species_primary}
**Fixed:**
- list_observations now outer-joins Species table to return itis_name_match, itis_accepted_name, itis_tsn
- Added Species import and ITIS fields to ObservationOut schema
**Files:** `frontend/review.html`, `app/api/observations.py`

### 2026-06-04 06:03
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260604_060314.sqlite`

### 2026-06-04 06:03
**Session ended** — Session ended from Settings page

### 2026-06-03 22:56
**Phase 12 Prompt 1 — /lists fixes + print page**

**Built:**
- Preloader defaults: PRELOADER_DEFAULTS map (field/workshop/workshops), setLayout resets all content toggles to preloader defaults on every press
- Workshop mode fix: removed stub (hasWorkshops → mode-stub) that blocked all rendering; workshop mode now renders per-species content via _workshopPage
- _workshopPage: isWorkshopHandout=true adds exercise placeholder (section heading + 4 ruled lines) and personal observations placeholder (section heading + ruled box); suppresses generic My notes block
- _combinedPage: passes isWorkshopHandout flag to _workshopPage
- renderPreview: workshop label corrected to singular Workshop
**Fixed:**
- Print: .print-map-snap gets break-after:avoid + page-break-after:avoid — prevents blank page after map snapshot
- Print: .print-map-snap + .fg-entry / .ws-page get break-before:avoid — prevents species content starting mid-page
- Workshop mode: stub removed, all species now render in Workshop layout
**Files:** `frontend/lists.html`

### 2026-06-03 22:31
**Scan page active batch rehydration + Make default layer button**

**Built:**
- P2 session selector: auto-selects running/queued session on initial page load (_p2AutoSelectDone flag, fires once)
- Layers panel: Make default star button (☆/★) next to each base layer — saves to localStorage
- Map load: reads foragingid_default_layer from localStorage, applies saved default for static layers
- _initMapConfig: shows bls-row-outdoors (row + star), only auto-switches to Outdoors if no saved default or saved default is outdoors
**Files:** `frontend/scan.html`, `frontend/index.html`

### 2026-06-03 22:27
**End-session server kill fix**

**Fixed:**
- Replace synchronous subprocess.run git calls in create_snapshot with asyncio.create_subprocess_exec — prevents deferred SIGINT from firing as KeyboardInterrupt when git blocks the event loop
- Fix DB_PATH from PROJECT_ROOT/foragingid.db to PROJECT_ROOT/data/foragingid.db (wrong path was causing silent DB snapshot skips)
- Add asyncio import to dev.py
**Files:** `app/api/dev.py`

### 2026-06-03 22:10
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_221005.sqlite`

### 2026-06-03 22:10
**Session ended** — Session ended from Settings page

### 2026-06-03 22:04
**Map UI Fixes Round — Prompt 1 (fixes 0–9)**

**Built:**
- Fix 0: map click on background closes detail panel to collapsed tab strip
- Fix 1: Place names toggle button in top toolbar (visible only on geology/soil/landuse layers)
- Fix 2+6: Tab strip reordered Layers/Controls/Filters + black ‹ chevrons pointing inward
- Fix 3: Layers panel single column (flex-direction:column)
- Fix 4: Controls panel vertical sliders (writing-mode:vertical-lr, side-by-side columns)
- Fix 5: Species filter → searchable multi-select; Month → multi-select; Source dropdown added; no-GPS panel hidden
- Fix 5: filterState.source added, _passesFilters/_heatPassesFilters/_countActiveFilters updated
- Fix 7: Search bar dropdown fixed — #layer-toggle overflow:hidden → overflow:visible
- Fix 8: Pin legend moved to bottom-left, minimisable with Legend header + ▾/▸ arrow
- Fix 9: Diagnostic only — see report
**Fixed:**
- Search dropdown was clipped by overflow:hidden on #layer-toggle
**Files:** `frontend/index.html`

### 2026-06-03 21:46
**GPS Walk Recording: Playback + Display (Prompt B)**

**Built:**
- Backend: GET /api/recorded-walks/{id} enriched with observation lat/lng/thumbnail/species via JOIN
- Backend: /media/recorded-walks static mount for audio note files
- Recorded walks list section in Walk panel (red header, list with name/date/distance/duration/elevation)
- Delete recorded walk with confirm (DELETE /api/recorded-walks/{id})
- loadRecordedWalkTrace: draws dark red polyline on click, no fitBounds
- Thumbnail pins: 40px circular photo thumbnails at observation GPS coords, click opens walk detail
- _showWalkDetail: rp-detail pattern, walk-detail-view alongside detail-view
- Walk detail content: name/date, 4-stat row (distance/duration/↑gain/↓loss), elevation SVG chart, 3-col photo grid, audio player
- Elevation SVG: polyline + fill, uses track point altitude + cumulative haversine distance for X axis
- Photo grid: tapping cell opens shared Lightbox with species name
- Walk panel minimise button: collapses sidebar to thin persistent bottom bar showing name+distance
- Minimise bar: tap to restore (calls setLayer walk)
- Walk panel tab switcher: Route stops (existing) / Walk stats (distance/duration/stops count)
- Walk panel live recording view: distance/duration/encounters shown instead of route controls during recording
- WalkRecorder.onStateChange wired to walk panel live stats; tabs hidden during recording
- walk-detail-view hidden when openSidebar/backToFilters/other views activate
**Files:** `app/api/recorded_walks.py`, `app/main.py`, `frontend/index.html`

### 2026-06-03 21:31
**GPS Walk Recording: Infrastructure + Capture (Prompt A)**

**Built:**
- Alembic migration 0022: recorded_walks + recorded_walk_observations tables
- SQLAlchemy models: RecordedWalk, RecordedWalkObservation
- FastAPI router: POST/GET/GET-id/DELETE /api/recorded-walks + /audio-upload + /id/elevation
- Background elevation enrichment via Open-Topo-Data API (up to 100 sampled points)
- walk-record.js: persistent WalkRecorder module (GPS watch, track points, wake lock, proximity log)
- Walk panel: Record Walk button (phone only) + Cache Area button
- GPS accuracy warning modal (>30m threshold, dismissible)
- HUD overlay: live distance/duration, audio note button, stop button
- Recording trace polyline on map: dark red/terracotta, 3px, semi-transparent
- Save modal: name input, voice note via MediaRecorder, save to DB
- Proximity alerts hooked: WalkRecorder.logProximityEncounter on each alert
- Observation photo linking: observations within walk time window linked on save
- Service worker: cache-tiles message handler for on-demand tile download
- media/recorded_walks/ directory for audio notes
**Files:** `migrations/versions/0022_add_recorded_walks.py`, `app/models/recorded_walk.py`, `app/api/recorded_walks.py`, `app/main.py`, `frontend/static/js/walk-record.js`, `frontend/static/sw.js`, `frontend/index.html`
**Pending:**
- Prompt B: Recorded walks list/detail/playback UI

### 2026-06-03 20:52
**Review queue filter bar tidy — Named/Unnamed checkboxes to dropdown, source checkbox + Phone only to dropdown**

**Built:**
- Named/Unnamed checkboxes replaced with single Named dropdown (All/Named/Unnamed)
- Source group: Phone only checkbox replaced with Source dropdown (All/Syncthing/Phone)
- No GPS checkbox kept as standalone
- buildUrl and getFilteredCount updated to read from new dropdowns
**Files:** `frontend/review.html`

### 2026-06-03 20:32
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_203255.sqlite`

### 2026-06-03 20:32
**Session ended** — Session ended from Settings page

### 2026-06-03 20:25
**Walk + Map controls fixes: zoom visibility, lasso cursor, clear walk, lasso toggle, walk recall viewport, circular routing**

**Built:**
- Fix 2: Clear walk button in walk panel (calls _exitWalkMode)
- Fix 5: Circular fallback dashed polyline now closes loop; toggle re-routes without fitBounds
**Fixed:**
- Fix 0: Leaflet topright controls offset 44px from right edge — no longer hidden by tab strip
- Fix 1: Tiny lasso drag now calls _exitLassoSelect() before returning — cursor always restored to grab
- Fix 3: selectAllVisible() exits lasso mode first — two selection tools are mutually exclusive
- Fix 4: loadSavedWalk no longer calls fitBounds — user viewport preserved on recall
- Fix 5: _buildWalkRoute accepts suppressFitBounds param; toggleWalkLoop passes true — no map pan on mode switch
**Files:** `frontend/index.html`

### 2026-06-03 20:14
**Review queue category filter — Plants / Fungi / Scene dropdown**

**Built:**
- obs_category query param added to GET /api/observations (backend filter, maps scene→landscape)
- Category dropdown (All / Plants / Fungi / Scene) in filter bar between Status and Source groups
- buildUrl() includes obs_category param when set
- getFilteredCount() handles category-active case via page-response estimate
- loadPage() and refreshStats() pass obs count to getFilteredCount
**Files:** `app/api/observations.py`, `frontend/review.html`

### 2026-06-03 19:55
**Fixes Round: walk circular, lasso hit-test, lightbox consolidation, photo→map nav, review select-all, shared ID source, print tweaks, walk recall, near-me pan**

**Built:**
- Fix 0: Walk circular/point-to-point toggle — close loop via ORS coords[0] appended, toggle button in walk panel, re-routes on toggle
- Fix 1: Lasso hit-test — pixel-space check (latLngToContainerPoint) instead of geographic bounds, exact match to visual rectangle
- Fix 2: Shared lightbox — static/js/lightbox.js with zoom+wheel+pin+enrich, duplicate JS removed from index/review/species
- Fix 3: Photo→pin navigation — review.html geo coordinates now link to /?highlight=obs_id
- Fix 4: Review Select all — selectAllVisible() button, shown in select mode alongside existing buttons
- Fix 5: Shared ID source — getIdSource() helper in scan.html, both inline expressions replaced
- Fix 6: PDF print tweaks — pt-based font sizes, preserved ws-page inner padding, larger field-guide column gap, print-color-adjust, cover sizing
- Fix 7: Walk recall — loadSavedWalk now sets _walkActive=true, calls _applyLayer(), marks Walk button active before drawing route
- Fix 8: Near me — scrim restricted to touch devices (pointer:fine hides it), map.flyTo after GPS fix, improved denied-permission error message
**Fixed:**
- Lasso outside-area pin selection bug fixed
- Walk recall redraw/pins broken fixed
- Near me dims page fixed (scrim z-index + pointer:fine guard)
- Near me map does not pan fixed
**Files:** `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/scan.html`, `frontend/lists.html`, `frontend/static/js/lightbox.js`
**Pending:**
- Shared lightbox CSS deduplication across review/species (low priority)
- Lasso outside-area pin selection bug
- PDF print styling tweaks

### 2026-06-03 19:36
**Map UI — full-width map with floating right panel overlay**

**Built:**
- #sidebar position:absolute width:0 — completely out of flex layout, map is always full-width
- #rp-tabs position:absolute right edge, full height, 40px, justify-content:space-around (tabs fill height evenly), font-size:0.82rem
- #rp-pane position:absolute right:40px, slides in with transform translateX(300px→0), pointer-events:none when hidden
- rp-open class on pane controls open/close — no rp-collapsed needed
- rp-detail class hides tab strip and extends pane to right:0 for pin detail
- No open-by-default — map starts full-width, panel closed on all devices
- Mobile and desktop identical behaviour — tab strip always visible at right edge
**Fixed:**
- toggleToolbarPanel, openSidebar, closeSidebar, showDetailView, showFilterView all updated to rp-open pattern
- _closeTabPanels now also removes rp-open and hides scrim
- toggleNotePanel and controls auto-close updated
- Mobile media query stripped of old bottom-sheet/rp-collapsed overrides
**Files:** `frontend/index.html`
**Pending:**
- Lasso outside-area pin selection bug
- Shared lightbox consolidation
- Photo to pin map navigation
- ID review Select all
- Shared identification-source function
- PDF print styling tweaks

### 2026-06-03 19:24
**Map UI — Right Panel Restructure: toolbar tabs moved into right sidebar with vertical tab strip**

**Built:**
- Vertical tab strip (#rp-tabs) on left edge of sidebar — Filters, Controls, Layers, 36px wide, writing-mode:vertical-rl
- #rp-pane content wrapper added inside sidebar
- panel-filters, panel-controls, panel-layers moved from #map-toolbar into #rp-pane
- #toolbar-row-2 removed from toolbar HTML
- Desktop: sidebar open (300px) by default with Filters tab active
- Mobile: sidebar collapsed (translateX(264px)) showing only 36px tab strip at right edge
- rp-detail class hides tab strip during pin detail view
- rp-collapsed class collapses pane; clicking active tab collapses, clicking again expands
- _closeTabPanels() helper for walk/nearme/find view transitions
- _initRightPanel() initialisation at page load
**Fixed:**
- Controls panel auto-close on layer switch now also collapses sidebar
- exitNearMeMode restore uses showFilterView()
- _exitWalkMode uses showFilterView()
- walk/nearme/find view show paths call _closeTabPanels() first
**Files:** `frontend/index.html`
**Pending:**
- Lasso outside-area pin selection bug
- Shared lightbox consolidation
- Photo to pin map navigation
- ID review Select all
- Shared identification-source function
- PDF print styling tweaks

### 2026-06-03 18:50
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_185059.sqlite`

### 2026-06-03 18:50
**Session ended** — Session ended from Settings page

### 2026-06-03 18:42
**Thunderforest Outdoors map layer + Settings API card**

**Built:**
- thunderforest_api_key field in config.py
- Thunderforest entry in API_REGISTRY with probe (_probe_thunderforest tile fetch)
- GET /api/map/config endpoint returns key to frontend
- Outdoors button in map layer switcher (hidden when no key)
- Outdoors tile layer created and set as default when key present
**Files:** `app/config.py`, `app/services/api_dashboard.py`, `app/api/map.py`, `frontend/index.html`
**Pending:**
- Lasso outside-area pin selection bug
- Shared lightbox consolidation
- Photo to pin map navigation
- ID review Select all
- Shared identification-source function
- PDF print styling tweaks

### 2026-06-03 18:36
**Phase 10.9 Prompt 2 — Folder reconciliation + Process delta + Live progress**

**Built:**
- Reconciliation shows bucket summary then stops — no auto-run
- Process delta button appears after reconciliation with file count label
- onProcessDeltaClick() handler arms session and runs pipeline on user click
- Button hidden on new folder select, on resume click, and after click
**Files:** `frontend/scan.html`
**Pending:**
- Lasso outside-area pin selection bug
- Shared lightbox consolidation
- Photo → pin map navigation
- ID review Select all
- Shared identification-source function
- PDF print styling tweaks

### 2026-06-03 18:24
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_182424.sqlite`

### 2026-06-03 18:24
**Session ended** — Session ended from Settings page

### 2026-06-03 17:28
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_172808.sqlite`

### 2026-06-03 17:28
**Session ended** — Session ended from Settings page

### 2026-06-03 17:13
**Lists page repair: diagnosed and fixed Bug 1 (map-select transfer + print preview snap)**

**Fixed:**
- Removed <img src=""> from static #map-snapshot-wrap HTML (spurious page request on load)
- Fixed renderPreview() snap check: snap.data → _mapSnapHtml(snap) so tile-based snaps show in print preview
**Files:** `frontend/lists.html`
**Pending:**
- Bug 2: species without common names tick - cannot reproduce from code, needs browser testing + symptom description
- Bug 3: print modes not rendering - cannot reproduce from code, needs browser testing + symptom description

### 2026-06-03 16:18
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_161800.sqlite`

### 2026-06-03 16:18
**Session ended** — Session ended from Settings page

### 2026-06-03 15:59
**Layer 4 — Stage-driven shared live display**

**Built:**
- _renderSessionChips(prefix, session, inflight) — shared chip renderer for both pipelines; optional fields silently skipped if element absent
- _renderSessionStatusBadge(badgePrefix, session) — shared badge + stalled/paused info for both pipelines
- _renderP1SessionChips now calls shared function; P1 in_flight passed as live overlay from syncthing status
- _renderP2SessionChips now calls shared function; P2 buttons (pause/resume) in slim _renderP2StatusBadge
- renderSyncthingState builds synthetic session object from in-memory _syncState during processing, passed to shared renderer
- P1 session row: added s1-status-badge and s1-stalled-info elements matching P2 structure
- Both breakdown tables converted to <details> collapsed by default, labelled ALL TIME
- Unaccounted row relabelled Pre-tracking legacy (irrecoverable) with tooltip explaining it cannot be reconstructed
- lb-arrow span with CSS rotate animation for breakdown disclosure triangle
**Files:** `frontend/scan.html`

### 2026-06-03 15:44
**P2 durable state, polling loop, button consolidation, git prompt removal, delete session, large-folder crash fix (Layers 1-3)**

**Built:**
- Layer 1: session_heartbeat() called in _p2_tick() every 10 files during P2 processing
- Layer 1: stall detection fixed — NULL heartbeat now counts as stalled (removed heartbeat is not None guard)
- Layer 1: session_reopen() helper for Resume path (sets status=running, clears ended_at, stamps heartbeat)
- Layer 1: process-delta accepts stalled running sessions (Resume path) with freshness check
- Layer 1: DELETE /api/scan/sessions/{id} endpoint (P2 only, no FK to observations, blocks active sessions)
- Layer 2: P2 polling loop (_startP2Polling) at 4s active / 15s idle — chip counts update from durable DB state
- Layer 2: SSE onmessage fires _scheduleP2SessionRefresh() on every progress event (not just done)
- Layer 3: btn-rescan + btn-process-delta removed; replaced with single btn-process-folder
- Layer 3: onProcessFolderClick() — folder picker → hash in 50-file chunks with yield → classify → arm → upload/retry in one action
- Layer 3: Large-folder crash fix — chunk size 50, warn >10k files, hard cap 50k files
- Layer 3: Resume button now shows when is_stalled=true (was blocked by null last_heartbeat)
- Layer 3: git-banner.js script tag removed; showGitBanner call removed
- Layer 3: Delete session button on P2 selector row with confirm dialog
**Fixed:**
- stall detection silently disabled for all P2 sessions (heartbeat is not None guard) — fixed
- Running badge persisting forever on P2 sessions — fixed via stall detection fix
- P2 counts only updating from browser upload callbacks — fixed by polling loop + SSE per-event refresh
- git-banner regression — removed entirely
- Resume requiring prior rescan state — fixed; now only blocks if session is not stalled
**Files:** `app/services/scan_sessions.py`, `app/api/scan.py`, `frontend/scan.html`
**Pending:**
- Layer 4 (stage-driven shared live display) — awaiting confirmation that Layers 1-3 are clean

### 2026-06-03 15:25
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_152527.sqlite`

### 2026-06-03 15:25
**Session ended** — Session ended from Settings page

### 2026-06-03 15:16
**Map Fix: upgrade identification_status on manual verification — backfill + source fix**

**Fixed:**
- Step 1 — Confirmed all uses of identification_status=identified are display/filtering only; no automation fires on the transition. Safe to proceed.
- Step 2 — Backfilled 13 observations (9 below_threshold + 4 failed_identification) where review_status=manually_verified; all now have identification_status=identified. Snapshot taken first: db_20260603_151421.sqlite.
- Step 3 — Fixed 3 code paths that set review_status=manually_verified without upgrading identification_status: observations.py correct-species endpoint, reidentify.py confirm-species endpoint, trust.py accept-species bulk path. All now set identification_status=identified in the same operation.
- Step 4 — Verified: all 11 Taraxacum officinale (species_id=286) observations are now map-visible (map count=11, card count=11). Sheffield obs 15942 and 15983 confirmed visible.
**Files:** `app/api/observations.py`, `app/api/reidentify.py`, `app/api/trust.py`
**Pending:**
- Run 31832 Takeout batch through rescan -> process delta

### 2026-06-03 15:14
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260603_151421.sqlite`

### 2026-06-03 13:13
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_131340.sqlite`

### 2026-06-03 13:13
**Session ended** — Session ended from Settings page

### 2026-06-03 13:09
**Fix 7: lookup merges iNat vision results, filters genus-level, boosts common-name matches**

**Built:**
- iNat vision runs in parallel with name search when obs_id supplied; vision results appended after name-search results, deduped by scientific name
- Empty q triggers vision-only mode (no name-search calls)
- Genus-level results filtered from all sources (species rank and below only)
- Name-search results boosted when search term appears in common name
- Vision results show 👁 vision badge + score% in dropdown
**Files:** `app/api/reidentify.py`, `frontend/review.html`
**Pending:**
- Run 31832 Takeout batch through rescan → process delta

### 2026-06-03 12:56
**Fix 6: P1 routing never auto-rejects on confidence; rescue existing below_threshold/failed_identification P1 obs**

**Fixed:**
- scan.py _identify_scanned no-candidates branch: removed force_review ternary — always sets needs_review (previously syncthing got rejected). P2 file_upload was already going to needs_review here.
- database.py init_db: idempotent rescue UPDATE sets review_status=needs_review for syncthing obs where identification_status IN (below_threshold, failed_identification) and review_status=rejected. 2 rows rescued on first reload.
**Files:** `app/api/scan.py`, `app/database.py`
**Pending:**
- Run 31832 Takeout batch through rescan → process delta

### 2026-06-03 12:49
**Fix 5: total and geotagged counts now exclude rejected and not_plant observations**

**Fixed:**
- /api/observations/stats: total and geotagged now filter to identification_status IN (identified, below_threshold, pending_identification) — excludes not_plant, failed_identification, and manually rejected rows
**Files:** `app/api/observations.py`
**Pending:**
- Run 31832 Takeout batch through rescan → process delta

### 2026-06-03 12:45
**Fix 4: lookup selection now pushes common name to card header**

**Fixed:**
- _applyCorrectionName now accepts and applies common name arg — updates .sp-common in species-block, creating or removing the element as needed. Both call sites (_corrSaveFromLookup, _sopApply) updated to pass common through.
**Files:** `frontend/review.html`
**Pending:**
- Run 31832 Takeout batch through rescan → process delta

### 2026-06-03 12:35
**Fix 3: inline thumbnails in rejection log rows on scan page**

**Built:**
- Thumbnail column in P1 rejection log table
- Minimal scan-page lightbox (click thumbnail to enlarge, Esc/backdrop to close)
**Files:** `frontend/scan.html`
**Pending:**
- Run 31832 Takeout batch through rescan → process delta as first real test of 10.9 infrastructure

### 2026-06-03 12:33
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_123304.sqlite`

### 2026-06-03 12:33
**Session ended** — Session ended from Settings page

### 2026-06-03 12:29
**Fix review queue lookup name transfer — two bugs**

**Fixed:**
- Bug 1 (unnamed cards): _applyCorrectionName injects a species-block before .badges when .sp-name missing. Unnamed cards had empty speciesHtml so querySelector returned null and the name never appeared on the card face.
- Bug 2 (named cards / apostrophes): _corrLookup result onclick args now escape single quotes with .replace to match the second-opinion panel pattern. Common names like Shepherds purse caused SyntaxErrors that silently swallowed the click entirely.
**Files:** `frontend/review.html`
**Pending:**
- Run 31832 Takeout batch through rescan to process delta
- iNat 500 test batch
- Phase 10.9 further prompts

### 2026-06-03 12:09
**Phase 10.9 Prompt 2 — Rescan + Process Delta + SSE progress + stalled detection**

**Built:**
- POST /api/scan/rescan — read-only folder reconciliation; classifies files as already_processed/new/retryable/skipped via SHA256 DB lookup; creates or updates scan_sessions row with bucket counts + status=rescanned; returns retryable_obs list with obs_ids for retry-id calls
- POST /api/scan/process-delta — validates session status=rescanned, sets running, creates SSE queue (_p2_progress), returns files_to_process count; frontend then uploads new files via POST /api/scan and calls retry-id for retryable obs
- GET /api/scan/progress/{session_id} — SSE stream of live narration events {current,total,filename,status}; immediate terminal event if session already complete/failed; 30s keep-alive pings; stalled detection via periodic DB re-check
- POST /api/scan/{obs_id}/retry-id — re-queues identification for failed/pending observations; accepts session_id for SSE wiring
- _p2_tick updated to push SSE events to per-session asyncio.Queue; _p2_auto_close pushes done event and tears down queue
- _p2_obs_session now stores (session_id, filename) tuples for SSE narration; backward-compat int fallback retained
- _p2_progress + _p2_session_counter module-level dicts added to scan.py
- scan_sessions._row_to_dict: is_stalled computed at read time (status=running AND heartbeat >5min ago); display_status=legacy for pre-migration rows
- scan.html: Rescan + Process Delta + Resume buttons with correct enable/disable logic; onRescanClick hashes image files with Web Crypto in batches of 20 with progress display; onProcessDeltaClick arms session + opens SSE + uploads new files; _p2OpenSse subscribes to EventSource for live narration
- scan.html: status badge (Running/Complete/Rescanned/Stalled/Failed/Legacy) on P2 session row; stalled heartbeat age shown; Resume button for stalled sessions
- scan.html: breakdown table gains new/retryable/already-processed rows (shown only after a rescan); _renderP2UnaccountedWarn shows amber warning when buckets dont sum to received
**Files:** `app/api/scan.py`, `app/services/scan_sessions.py`, `frontend/scan.html`
**Pending:**
- Run 31,832 Takeout batch through rescan→process delta as first real test (user to trigger)
- Phase 10.9 Prompt 3+ (subsequent roadmap items)
- iNat 500 deliberate test batch
- Second edibility source integration

### 2026-06-03 11:55
**Phase 10.9 Prompt 1 — Durable Batch State + P2 copy-on-ingest**

**Built:**
- Migration 0021: added status, last_heartbeat, files_new, files_retryable, files_already_processed to scan_sessions (all idempotent ADD COLUMN IF NOT EXISTS). Existing P1 rows backfilled to status=complete. All stale pipeline=2 rows deleted.
- ScanSession model: 5 new columns added matching migration 0021
- scan_sessions service: session_create now writes status=running + last_heartbeat on INSERT; session_close writes status=complete on close; new session_set_status() and session_heartbeat() helpers added; _allowed, _SELECT, _row_to_dict all updated for new columns
- Config: pipeline2_dir property added (photos/pipeline2/), wired into ensure_dirs
- syncthing.py Option B copy-on-ingest: _ingest_file now copies source file to photos/pipeline2/<uuid>_<stem><ext> before creating observation record; file_path stores local copy path; early SHA dup-check skips the copy for duplicates; race-guard secondary check cleans up redundant copies; shutil imported at top
- syncthing.py heartbeat: _process_all passes heartbeat_cb to _process_one; every 10 files stamps last_heartbeat on the session row
**Files:** `migrations/versions/0021_add_batch_state_to_scan_sessions.py`, `app/models/scan_session.py`, `app/services/scan_sessions.py`, `app/config.py`, `app/api/syncthing.py`
**Pending:**
- Phase 10.9 Prompt 2 onwards (rescan/process two-step, stalled detection UI)
- iNat 500 deliberate test batch
- Second edibility source integration

### 2026-06-03 07:03
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_070327.sqlite`

### 2026-06-03 07:03
**Session ended** — Session ended from Settings page

### 2026-06-03 06:32
**iNat vision HTTP 500 investigation and fix (3 changes)**

**Fixed:**
- Change 2: inaturalist.py — log response body (up to 300 chars) on any non-200 status; added 500 hint noting iNat returns 500 on soft rate-limit/quota exhaustion
- Change 1: scan.py — _identify_scanned now imports and uses _INAT_SEMAPHORE + INAT_DELAY_S from services/identification.py (same module-level singleton, not a new instance); _get_inat() wraps the call in async with _INAT_SEMAPHORE and sleeps INAT_DELAY_S after — scan path now shares the same sequential queue as the re-ID path
- Change 3: inaturalist.py — MIME type now derived from file extension (.png→image/png, .webp→image/webp, else image/jpeg) instead of always sending image/jpeg
**Files:** `app/integrations/inaturalist.py`, `app/api/scan.py`
**Pending:**
- Run a deliberate test batch to read logs and confirm 500s are eliminated — do not auto-run; user will trigger
- iNat vision HTTP 500 during large scans (monitoring)
- durable batch state + rescan/process split
- second edibility source integration

### 2026-06-03 06:27
**Fix map name search not working**

**Fixed:**
- Species search now zooms/fitBounds to species observations using _heatAll (global, not bbox-bounded) — fixes case where species pins are outside current viewport
- Common name search expanded: checks preferred_common_name and all common_names entries (was only checking common_names[0])
- Dropdown shows up to 5 species results (was 3)
**Files:** `frontend/index.html`
**Pending:**
- iNat vision HTTP 500 during large scans
- durable batch state + rescan/process split
- second edibility source integration

### 2026-06-03 06:24
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260603_062405.sqlite`

### 2026-06-03 06:24
**Session ended** — Session ended from Settings page

### 2026-06-03 06:19
**JSON sidecar + non-image filter for Pipeline 2**

**Built:**
- Migration 0020: files_skipped INTEGER column added to scan_sessions
- scan_sessions.py: files_skipped added to session_inc allowlist, _SELECT, _row_to_dict, session_create INSERT, sessions_breakdown (returned as skipped field)
- scan.py: non-image files (wrong ext or MIME) now return {skipped:true, reason:non_image} 200 JSON instead of HTTPException 400/415 — never enter pipeline, never reach pre-filter or ID
- _p2_auto_close: counts files_processed + files_skipped >= files_received so Takeout batches with JSON sidecars auto-close correctly
- scan.html: _isAccepted tightened to .jpg/.jpeg/.png/.webp only (removed .heic/.heif/.gif/.bmp/.tiff and catch-all empty-type pass)
- scan.html: _uploadFile handles result.skipped===true — marks card as skipped, calls _updateScanSession(skipped) not failed
- scan.html: skipped count added to session banner, s2-sess-skipped chip, s2-lb-skipped lifetime breakdown row
**Files:** `migrations/versions/0020_add_files_skipped_to_scan_sessions.py`, `app/services/scan_sessions.py`, `app/api/scan.py`, `frontend/scan.html`
**Pending:**
- Second edibility source integration (Food Plants International, FAO, ITIS)

### 2026-06-02 23:43
**Fix species not appearing on /lists after map selection**

**Fixed:**
- Wrapped renderMapSnapshot() call in render() with try/catch — prevents any snapshot bug from aborting render() before species list is built
- Rewrote renderMapSnapshot() to be idempotent: no replaceWith, no stale getElementById lookup, sets wrap.innerHTML directly each call — eliminates TypeError on second+ render() call caused by dead container line accessing parentElement of already-removed element
**Files:** `frontend/lists.html`

### 2026-06-02 23:31
**Fix blank tiles on map select — replace canvas capture with tile URL grid**

**Fixed:**
- Removed leaflet-image CDN script from index.html
- Removed all crossOrigin options from tile layers (standard, satellite, terrain, geology, soil, placeNames) — restores normal tile rendering
- finishSelectMode() now saves a 3x3 grid of OSM tile URLs (zoom-3 centred on viewport) to localStorage instead of canvas toDataURL — no CORS needed for <img> tag display
- renderMapSnapshot() in lists.html updated to render tile grid div instead of single base64 img
- _mapSnapHtml() in lists.html and print.html updated to output print-map-snap-grid for tile arrays, with legacy data: fallback
- Added .map-snap-grid and .print-map-snap-grid CSS (3-col grid) to lists.html and both stylesheets in print.html
**Files:** `frontend/index.html`, `frontend/lists.html`, `frontend/print.html`
**Pending:**
- Second edibility source integration (Food Plants International, FAO, ITIS)

### 2026-06-02 23:19
**Multi-select print modes on /lists — additive mode combinations**

**Built:**
- lists.js: mode string → modes array; migration from legacy mode string; min-one enforcement; derives .mode for backward compat
- lists.html: mode buttons changed to toggles (toggleMode()); syncToolbar() checks list.modes array
- lists.html: renderPreview() reads modes array, derives layout from highest-priority mode, labels show all active modes
- lists.html: _combinedPage() routes each species to the right renderer based on active modes
- lists.html: _fieldGuideBlock() helper — compact ID notes + lookalike + edible parts as ws-section
- lists.html: _workshopPage(name, withFieldBlock) — injects Field ID notes above recipe, suppresses duplicate foraging section when field block present
- print.html: same modes-array logic; _workshopPage updated with withFieldBlock param; toolbar label shows all active modes
**Files:** `frontend/static/js/lists.js`, `frontend/lists.html`, `frontend/print.html`
**Pending:**
- Second edibility source integration (Food Plants International, FAO, ITIS)

### 2026-06-02 23:11
**Map snapshot on reach-back selection — capture, store, display, print**

**Built:**
- leaflet-image CDN script added to index.html
- crossOrigin: anonymous added to all tile layers (standard, satellite, terrain, geology, soil, placeNames) to unblock canvas export
- finishSelectMode() captures map via leafletImage(), stores {data, date} JSON in foragingid_list_map_snapshot localStorage key, then navigates to /lists
- lists.html: #map-snapshot-wrap block displayed above species list after reach-back return, with Selected from map — [date] caption
- lists.html: renderMapSnapshot() called from render(); clearList() removes snapshot key
- lists.html: _mapSnapHtml() helper injects snapshot full-width after cover in print preview (all 3 modes), column-span:all for 2-col field guide layout
- print.html: snapshot injected after cover in main() render, CSS added to both stylesheet and openPrintWindow() inline CSS
**Files:** `frontend/index.html`, `frontend/lists.html`, `frontend/print.html`
**Pending:**
- Second edibility source integration (Food Plants International, FAO, ITIS)

### 2026-06-02 22:48
**Add 5 new data source registry entries (v2 seed batch)**

**Built:**
- Migration 0019_add_data_source_seeds_v2.py — idempotent INSERT OR IGNORE seed
- Food Plants International (ID 35) — status:pending, future edibility source (plants)
- FAO Wild Edible Fungi (ID 36) — status:pending, future edibility source (fungi)
- ITIS (ID 37) — status:pending, future name-validation source
- GBIF (ID 38) — status:active, link-out
- Falling Fruit (ID 39) — status:active, link-out
**Files:** `migrations/versions/0019_add_data_source_seeds_v2.py`
**Pending:**
- Second edibility source integration (Food Plants International, FAO, ITIS) — fetcher + schema work

### 2026-06-02 22:43
**Edibility Review tab polish — F-fixes**

**Built:**
- Lightbox wired to edibility card thumbnails via openEnrichLightbox()
- Consistent sort/filter toolbar (already added in previous pass)
**Fixed:**
- Fixed "> literal text rendering — onerror attribute used unescaped double-quotes inside double-quoted HTML attribute; changed to &quot; entity
- Card border changed from 2px solid #e5e7eb to 1px solid #ddd to match Species ID convention
- Grid gap reduced from 14px to 12px to match Species ID convention; padding reduced to 14px
- Added align-self:start to prevent vertical blank gaps within cards in the grid
- Added cursor:pointer to .edib-thumb
**Files:** `frontend/review.html`
**Pending:**
- Second edibility source integration (Food Plants International, FAO, ITIS)

### 2026-06-02 22:39
**Review queue UI consistency pass — frontend only**

**Built:**
- Enrichment Review tiles moved to CSS grid (minmax 460px, 2-column on wide screens)
- AI Draft Review tiles moved to CSS grid (minmax 480px)
- AI Draft cards collapsible — click header to toggle fields
- Enrichment Review: sort + filter toolbar (confidence/name/flagged, flagged-only/no-pfaf filter)
- Enrichment Review: multi-select mode with bulk Resolve Flags action
- Edibility Review: sort (conf/obs/name) + filter (all/suggested/pfaf/no_pfaf) toolbar added
- All queues now have consistent side-by-side toolbar layout with filter-group dividers
**Files:** `frontend/review.html`
**Pending:**
- Second edibility source integration (Food Plants International for plants, FAO for fungi, ITIS for name validation) — unlocks true two-source agreement

### 2026-06-02 22:30
**Enrichment run results table — per-species, per-source breakdown**

**Built:**
- GET /api/enrich/last-run-table — returns per-species run_status (from _state progress log) + per-source (pfaf/wikidata/inat/trompenburg/culinary_links) filled/no-data/not-attempted status from most-recent enrichment_sources rows
- Fallback mode when no session run recorded: shows 100 most-recently touched species
- Collapsible <details> panel on Enrichment Review tab — lazy-loads on expand
- Table columns: species, run status badge, PFAF/Wiki/iNat/Tromp/Links icon circles
- _erdLoaded flag resets after run completes so table refreshes automatically
- Sorted by severity: failed > not_found > partial > enriched > skipped
**Files:** `app/api/enrich.py`, `frontend/review.html`

### 2026-06-02 22:26
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_222626.sqlite`

### 2026-06-02 22:26
**Session ended** — Session ended from Settings page

### 2026-06-02 22:24
**AI Draft generate/regenerate controls on AI Draft Review tab**

**Built:**
- POST /api/drafts/generate — single-species generate (re_enrich=False fills gaps) or regenerate (re_enrich=True bypasses approved-draft guard, invalidates pending, calls Claude directly)
- POST /api/drafts/bulk-generate — same logic for a list of species names, sequential with per-species commit
- AI Draft Review toolbar: + Generate input, ↻ Regenerate selected bulk button
- Per-species card: checkbox for multi-select + ↻ Regen all button
- Per-field: ↻ Regenerate taste notes button on taste_notes fields
- aiDraftToggleSelect, aiDraftBulkRegenerate, aiDraftRegenerate, aiDraftRegenerateField, aiDraftGenerateSingle JS functions
- Edibility gate respected: toxic/inedible blocked at endpoint level
- Placeholder filter applied at regenerate path (same phrases as enrichment.py, culinary fields only)
**Files:** `app/api/culinary.py`, `frontend/review.html`

### 2026-06-02 22:17
**Blank AI-draft non-answers in taste_notes — tighten placeholder filter**

**Fixed:**
- enrichment.py: added not enough information, no sourced information, cannot determine to _PLACEHOLDER_MARKERS
- enrichment.py: filter now explicitly scoped to taste_notes and recipe only — medicinal_notes excluded by design
- Retroactive sweep: 8 culinary_info.taste_notes blanked (Larix kaempferi, Populus tremula, Vicia sativa, Medicago lupulina, Valeriana officinalis, Dactylorhiza majalis, Polygonum aviculare, Larix decidua)
- 8 corresponding approved species_ai_drafts invalidated
- medicinal_notes: 133 set rows verified unchanged
**Files:** `app/services/enrichment.py`, `data/foragingid.db`

### 2026-06-02 22:15
**Recipe edibility gate: tighten AI draft suppression + retroactive recipe sweep**

**Built:**
- claude_draft.py: caution (conditionally edible) now generates recipe+taste_notes with edibility_conditions caveat injected into prompt
- claude_draft.py: gate tightened — null/unknown/unclear suppresses culinary; toxic/inedible/not_edible suppresses all; caution/edible permit culinary
- enrichment.py: fetches SpeciesEdibilityCondition rows for caution species and passes as edibility_conditions to generate_ai_drafts
**Fixed:**
- Retroactive sweep: 12 approved recipes archived on species with unconfirmed/null/unknown edibility (excluding Chaerophyllum temulum already handled)
- 12 species flagged in culinary_info enrichment review queue with note recipe on unconfirmed edibility
**Files:** `app/integrations/claude_draft.py`, `app/services/enrichment.py`, `data/foragingid.db`

### 2026-06-02 22:12
**Build Edibility Review tab — replaces Location Review tab in /review**

**Built:**
- GET /api/edibility/review-queue — enriched unknown-edibility queue with PFAF context, suggested_status, sort by edibility_confidence desc
- PATCH /api/edibility/bulk-status — bulk confirm multiple species at once
- Edibility Review tab (tab-pane-edibility) in review.html replacing Location Review tab
- Card grid: photo, common name, family, PFAF confidence badge, edible_parts/warnings/look-alike context (collapsible), 5 status buttons
- Status buttons highlight active choice, card fades out on confirm, badge count updates
- Multi-select with bulk confirm for suggested-status cards
- suggested_status: pre-flags toxic when PFAF preparation_warnings contain toxicity language
**Files:** `app/api/edibility.py`, `frontend/review.html`

### 2026-06-02 22:06
**Safety fix: Chaerophyllum temulum — set toxic, archive recipe, clear AI drafts**

**Fixed:**
- species.edibility_status set to toxic, edibility_verified=True
- Recipe Rough Chervil Butter with Salt Cod and Charred Leeks archived with safety note
- All AI drafts (taste_notes, medicinal_notes, recipe) invalidated
- culinary_info.taste_notes and recipe cleared
**Files:** `data/foragingid.db`

### 2026-06-02 19:58
**Goethean borders: remove repeat-y, use cover + 100vh for single seamless image**

**Fixed:**
- Goethean ::before and ::after borders switched to no-repeat / cover with height:100vh — eliminates tiling seam
**Files:** `frontend/print.html`

### 2026-06-02 19:56
**Fix nav logo in print.html — replace emoji with dandelion SVG**

**Fixed:**
- Replaced 🌿 emoji in print.html toolbar h1 with dandelion-icon.svg img tag, white-filtered to match dark green nav
**Files:** `frontend/print.html`

### 2026-06-02 19:44
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_194428.sqlite`

### 2026-06-02 19:44
**Session ended** — Session ended from Settings page

### 2026-06-02 18:15
**Replace print overlay system with dedicated /lists/print page**

**Built:**
- frontend/print.html — minimal print page: no nav, no overlays, no procedural SVG. Reads ForagingList + style from localStorage (same origin), fetches /api/species/.../profile, renders field guide or workshop layout
- Border images as <img> tags with position:fixed — corners for botanical, side strips for herbalist/goethean, print-color-adjust:exact
- GET /lists/print route in app/main.py → frontend/print.html
- ↗ Print page button on /lists toolbar opens /lists/print in a new tab
- Removed all old overlay print CSS blocks from frontend/lists.html (PRINT BORDERS section gone)
**Fixed:**
- Eliminated the fragile background-image + procedural SVG conflict that caused muddy border rendering
**Files:** `frontend/print.html`, `app/main.py`, `frontend/lists.html`

### 2026-06-02 17:51
**Print borders — switched from base64 to static file URLs**

**Fixed:**
- Removed all 5 base64-encoded image blobs from print CSS (~1.5MB of data)
- Replaced with direct /static/print/ URLs (URL-encoded for filenames with spaces)
- lists.html shrunk from 1561KB back to 66KB
- All 5 URLs confirmed 200 OK from running server before wiring into CSS
**Files:** `frontend/lists.html`

### 2026-06-02 17:36
**Print style borders — botanical assets into /lists print CSS**

**Built:**
- Split watercolour oakleaf PNG vertically into left/right halves (watercolour-oakleaf-left.png, watercolour-oakleaf-right.png)
- Field Guide print borders: real corner PNGs (light TL/TR, bold BL/BR) replace procedural SVG at print time
- Workshop/Herbalist print borders: full-height serrated-leaf side strips via ::before/::after pseudo-elements
- Goethean print borders: split watercolour oakleaf left/right side strips via ::before/::after pseudo-elements
- All borders print-only (@media print) — zero screen-view change
- All images embedded as base64 (no new static routing needed)
**Files:** `frontend/static/print/watercolour-oakleaf-left.png`, `frontend/static/print/watercolour-oakleaf-right.png`, `frontend/lists.html`

### 2026-06-02 16:50
**Fix dandelion logo not displaying — static file path was correct but never referenced**

**Built:**
- Dandelion SVG favicon added to all HTML pages
- Dandelion SVG nav logo replacing emoji in all pages
**Fixed:**
- Added <link rel=icon type=image/svg+xml href=/static/icons/dandelion-icon.svg> to all 11 HTML files
- Replaced 🌿 emoji h1 with <img> tag referencing dandelion-icon.svg in all 10 nav pages
- Added dandelion-icon.svg to SW precache APP_SHELL list
- Bumped SW CACHE_VERSION foragingid-v3 → foragingid-v4 to force cache refresh
**Files:** `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/lists.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`, `frontend/encounters.html`, `frontend/my-season.html`, `frontend/upload.html`, `frontend/landing.html`, `frontend/static/sw.js`

### 2026-06-02 15:42
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_154214.sqlite`

### 2026-06-02 15:42
**Session ended** — Session ended from Settings page

### 2026-06-02 15:35
**Resumed and completed the paused Field Recipes + Auto-Transcribe build (Phase 12), ported cleanly onto main from a stale May-29-based worktree**

**Built:**
- Encounter.field_recipes column + migration 0018 (additive, idempotent, depends 0017)
- encounters.py: GET /pending-transcripts, GET /field-recipes (ingredient species_id filter), PATCH+DELETE /field-recipe, _parse_field_recipe + field_recipe in _enc_to_dict
- encounter_extract.py rewrite: field_recipe/foraging_note/safety_note suggestion types, recipe cue pre-check, ingredient->species reconciliation, legacy recipe type kept
- auto-transcribe.js owner-only badge on Encounters nav link (count of audio-without-transcript); script tag on 7 nav pages (not encounters.html)
- species.html: read-only Field Recipes section (hidden when empty) with matched-ingredient chips linking to species cards
- encounters.html: FINISHED the incomplete interaction layer - _SUGG_META new types, field_recipe save-card in _renderSuggestions, saved field-recipe-block with inline edit/delete, saveFieldRecipeFromSuggestion/editFieldRecipe/saveFieldRecipeEdit/deleteFieldRecipe, _encById cache
**Fixed:**
- Worktree was based on stale 2026-05-29 commit; ported only field-recipe-specific pieces onto current main rather than overwriting a week of divergent work
- encounters.html field-recipe UI was CSS-only stub in worktree (no JS, _SUGG_META not updated) - built the missing rendering/save logic fresh
**Files:** `app/models/encounter.py`, `app/api/encounters.py`, `app/integrations/encounter_extract.py`, `migrations/versions/0018_add_encounter_field_recipes.py`, `frontend/static/js/auto-transcribe.js`, `frontend/species.html`, `frontend/encounters.html`, `frontend/index.html`, `frontend/review.html`, `frontend/lists.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`
**Pending:**
- Live in-browser click-through of Save/Edit/Delete recipe buttons (preview server sandbox-blocked from reading venv/pyvenv.cfg, as in all prior sessions) - backend verified end-to-end via curl, JS verified balanced vs HEAD
- Field Recipe save UI only appears after an encounter audio is Transcribed then Extracted and Claude detects a recipe cue (needs OPENAI_API_KEY + ANTHROPIC_API_KEY set)
- Two locked git worktrees remain (agent-a0f5b0a... = already-merged five-cluster fix; agent-a63e1c... = this Field Recipes work, now fully ported) - safe to prune when ready
- Next: roadmap v15 + new planning thread for Phase 12

### 2026-06-02 15:19
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_151938.sqlite`

### 2026-06-02 15:19
**Session ended** — Session ended from Settings page

### 2026-06-02 14:40
**Review Queue + Species Card Fixes — all 5 clusters**

**Built:**
- C1: SUGGESTED review cards now show confidence score + CSS class, rename button, and Second Opinion button (identical to named cards). Save button removed from correction row; helper text updated to "then Approve to confirm".
- C2: Enrichment tab converted from stacked <details> to side-by-side inner sub-tabs (Enrichment Review | AI Draft Review) with lazy loading. Rescan button added to AI Draft pane. Medicinal no-uses placeholder drafts suppressed from AI draft queue.
- C3: approve_ai_draft endpoint: CulinaryInfoHistory write guarded by `if ci.id:` (prevents culinary_info_id=0). approveAllDrafts uses data-sci/data-field/data-did dataset attributes instead of parsing onclick with regex. approveDraftField catch block robustened.
- C4: Lightbox: click-to-zoom (1x/2.5x toggle) and wheel zoom (1-4x). Pin button in footer — shows only when obs has GPS, clicks scroll+highlight the species mini-map. Delete button already had confirm dialog (showDeleteDialog), no change needed.
- C5: Mini-map defaults to ~50km radius (zoom 10) centred on last-known user location (GPS.getLast() → foragingUser → localStorage fid_map_pos). Falls back to fit-all-pins when no location available.
**Fixed:**
- approve_ai_draft: removed culinary_info_id=0 fallback that could corrupt history rows
- approveAllDrafts: replaced fragile onclick regex parsing with data-attribute lookup
**Files:** `frontend/review.html`, `frontend/species.html`, `app/api/culinary.py`

### 2026-06-02 14:39
**Five-cluster UI/bug fixes: review card unification, enrichment sub-tabs, approve flow hardening, lightbox zoom+pin, map default view**

**Built:**
- SUGGESTED block now renders like named block with score, rename, second-opinion
- Enrichment tab inner sub-tabs (Enrichment Review | AI Draft Review) with Rescan button
- Medicinal no-uses placeholder suppression in AI Draft queue
- Lightbox click/wheel zoom and pin-to-map button on species card
- Species mini-map centres on last-known user location by default
**Fixed:**
- Removed Save button from correction row (helper text updated)
- Fixed culinary_info_id=0 fallback in approve_ai_draft (guard on ci.id)
- approveAllDrafts uses dataset attributes instead of onclick regex parsing
- approveDraftField catch block re-enables buttons with block syntax
**Files:** `frontend/review.html`, `frontend/species.html`, `app/api/culinary.py`

### 2026-06-02 11:06
**Botanical print style fix — corners and border now anchor to physical page**

**Fixed:**
- Added position: fixed; inset: 0 to #bot-overlay in @media print. Root cause: #bot-overlay inherited position: absolute from screen CSS, making its containing block #preview-wrap (the content area, 14mm in from the paper edge) rather than the physical page. Fixed children then measured from the wrong origin — corners offset by the page margin, and bottom/right offsets relative to the full document height instead of each page edge, so the border was invisible on all but the very last page.
**Files:** `frontend/lists.html`

### 2026-06-02 10:48
**Obsidian vault sync added to End Session flow**

**Built:**
- obsidian_vault_path setting in registry (Cloud Sync group, hidden=True, default /Users/melvinjarman/Documents/Obsidian) — persisted to app_settings DB via existing settings service
- End Session (POST /api/dev/end-session) step 6: writes Current State.md (overwrite, # date header) and appends to Decisions Log.md in the vault. Creates dir if missing. All exceptions caught as log.warning — never blocks the flow. Silently skips if path is blank.
- Settings page: single text input for vault path inside existing end-session-row, Save path button (PUT /api/settings/obsidian_vault_path), pre-filled from GET /api/settings on page load
**Files:** `app/services/settings_service.py`, `app/api/dev.py`, `frontend/settings.html`

### 2026-06-02 10:41
**Snapshot** — End of session — Built all three Phase 12 print styles (Botanical, Herbalist, Goethean) plus the style selector UI for lists.html. Botanical uses inline SVG bezier corner clusters with CSS mirror transforms and a fixed border/credit overlay. Herbalist uses JS-generated filled leaf shapes with 4 layered green shades and margin trailing. Goethean ports the runcinate dandelion geometry from encounters.html into a 15-form metamorphosis sequence as full-width header/footer strips.
DB: `snapshots/db_20260602_104126.sqlite`

### 2026-06-02 10:41
**Session ended** — Built all three Phase 12 print styles (Botanical, Herbalist, Goethean) plus the style selector UI for lists.html. Botanical uses inline SVG bezier corner clusters with CSS mirror transforms and a fixed border/credit overlay. Herbalist uses JS-generated filled leaf shapes with 4 layered green shades and margin trailing. Goethean ports the runcinate dandelion geometry from encounters.html into a 15-form metamorphosis sequence as full-width header/footer strips.

### 2026-06-02 10:41
**Phase 12 Prompt 3 — Goethean print style**

**Built:**
- Goethean print style (data-style=goethean): leaf metamorphosis header + footer strips (full page width, 25mm tall each), #3a5a28 forest green at opacity 0.55 header / 0.35 footer
- _initGoeOverlay() IIFE: 15-form progression (cotyledon → oval → lobed → runcinate peak forms 9-11 using exact dandelion geometry from encounters.html → contracting bracts), each leaf a distinct SVG path with organic tilt variation
- Runcinate forms use ported dandelion lobe algorithm (same rnd(), grow/irr/env/lean/sinus parameters); footer uses reversed sequence + seedAdd=300 for related-but-distinct forms
- Footer strip vertically flipped via SVG group transform so leaves hang downward from baseline; baseline rule at content boundary on both strips
- Credit bottom centre, very quiet (7pt, 0.45 opacity); Georgia serif throughout; no borders, no corner ornaments
**Files:** `frontend/lists.html`

### 2026-06-02 10:33
**Phase 12 Prompt 2 — Herbalist print style**

**Built:**
- Herbalist print style (data-style=herbalist): lush watercolour leaf-cluster corners, 4 green shades (#3d6e35/#4a7c3f/#5a9a4a/#6ab055) layered at 0.30-0.55 opacity, fine dark-green stems, left/right margin trailing strips
- _initHerbOverlay() IIFE: JS-generated filled organic bezier leaf shapes (18 per corner, 5 per margin trail), CSS scaleX/scaleY mirroring for TR/BL/BR, split credit line (Melvin Jarman left / Hofgut LEO right)
- Updated _STYLE_OVERLAY map and setPrintStyle() to manage all 3 overlay divs cleanly
**Files:** `frontend/lists.html`
**Pending:**
- Goethean style (prompt 3)

### 2026-06-02 10:29
**Phase 12 Prompt 1 — Botanical print style + 3-button style selector**

**Built:**
- Botanical print style (data-style=botanical): Georgian serif, #fdfbf6 warm background, organic bezier corner decorations, fine rule border inset 12mm, credit Melvin Jarman · Hofgut LEO bottom centre, page counter bottom right
- 3-button style selector (Botanical / Herbalist / Goethean) in toolbar, persists to localStorage (foragingid_list_style), default botanical
- Same selector exposed in cover-page panel for phone use
- _initBotOverlay() IIFE builds 4 mirrored SVG corner clusters (14 paths each: 2 main stems, 2 branches, 8 leaves, 2 buds) via CSS scaleX/scaleY transforms
- Bot overlay: position:absolute on screen (inside #preview-wrap), position:fixed per-page on print
**Files:** `frontend/lists.html`
**Pending:**
- Herbalist style (prompt 2)
- Goethean style (prompt 3)

### 2026-06-02 10:15
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_101509.sqlite`

### 2026-06-02 10:15
**Session ended** — Session ended from Settings page

### 2026-06-02 09:39
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_093919.sqlite`

### 2026-06-02 09:39
**Session ended** — Session ended from Settings page

### 2026-06-02 09:26
**New app icon — runcinate dandelion leaf SVG (Taraxacum officinale botanical style)**

**Built:**
- frontend/static/icons/dandelion-icon.svg: 512×512 SVG, transparent background, single runcinate dandelion leaf using the exact JS geometry ported to Python (same LOBES=9, rnd(), grow/irr/lean/sinus parameters as the waveform visualiser). -25° rotation fills the canvas. Linear gradient fill (#1a3a0e→#2d5016→#3a6a1c). Pronounced midrib (#7ec850, 7px) with fine highlight (#c8f090). 2.5KB.
- frontend/static/icons/icon-192.png: 192×192 RGBA PNG rendered via Chrome CDP (omitBackground:true). 13.7KB. Transparent background confirmed (90% transparent pixels, corner alpha=0).
- frontend/static/icons/icon-512.png: 512×512 RGBA PNG. 52KB. Same transparency.
**Files:** `frontend/static/icons/dandelion-icon.svg`, `frontend/static/icons/icon-192.png`, `frontend/static/icons/icon-512.png`
**Pending:**
- manifest.json already references /static/icons/icon-192.png and icon-512.png — no change needed. No favicon ref in app/main.py. No other files touched per spec.

### 2026-06-02 09:16
**Waveform visualiser leaf-shape refinement: soft rounded leaf -> classic runcinate dandelion (Taraxacum) silhouette**

**Fixed:**
- Redesigned the dandelion-leaf waveform geometry to the botanical runcinate (lion-tooth) style: backward-pointing triangular lobes that enlarge toward the apex, deep irregular sinuses cut almost to the midrib, per-lobe depth + angle + position variance via a deterministic per-index pseudo-random (stable silhouette, no flicker), asymmetric top/bottom (different seeds), pronounced central midrib with a short petiole tail, elongated narrow silhouette.
- Amplitude mapping unchanged: audio drive still scales serration length (env*(0.55 resting + 0.45*drive*wob)); only the geometry changed.
- Applied identically to all three recorder contexts: encounters.html _drawDandelion (New Encounter + Season tabs share it) and species.html _fnStartViz (Foraging Notes).
**Files:** `frontend/encounters.html`, `frontend/species.html`
**Pending:**
- Verified via canvas.toDataURL capture (headless + fake mic): resting silhouette + a drive=0.85 preview both render the runcinate backward-toothed leaf with pronounced midrib. No console errors on either page. Purely visual; no backend/schema/data changes.

### 2026-06-02 09:03
**Foraging Notes section redesign on species card: editable notes field + inline dandelion recorder + recordings list, with species.foraging_notes schema addition**

**Built:**
- Schema: added species.foraging_notes (Text, nullable) via Alembic 0017 (additive, idempotent); added to Species model. Live DB migrated to head 0017.
- Editable notes text area (About-page textarea pattern: auto-grow, serif, dirty state). Reads/writes species.foraging_notes, placeholder Your notes on this species…, auto-save on blur via new PATCH /api/species/{name}/foraging-notes. foraging_notes also added to the species profile response.
- Backend: transcribe endpoint (encounters.py) now auto-appends a foraging_note encounter transcript to its species.foraging_notes with a datestamp separator (— DD Mon YYYY —), idempotent (skips if text already present).
- Small red record button in the top-right corner of the text area; tap expands an inline recorder below with the dandelion-leaf waveform (ported from encounters recorder) + Stop. On stop: Play/Discard/Save row with optional name input. Save POSTs encounter_type=foraging_note, species_id, encounter_date(+00:00), name->text_note; inline confirmation.
- Recordings list: foraging_note encounters for the species — name (or Recording N), date, client-resolved duration (webm Infinity-duration workaround), inline audio player, expandable transcript. Empty state: No recordings yet.
**Fixed:**
- Dandelion waveform never showed because .fn-waveform is a CLASS rule with display:none; setting canvas.style.display='\'='\'' falls back to it. Changed to explicit display='block'. (Encounters works by accident: its canvas#waveform id selector does not match the suffixed waveform-N ids.)
**Files:** `app/models/species.py`, `migrations/versions/0017_add_species_foraging_notes.py`, `app/api/culinary.py`, `app/api/encounters.py`, `frontend/species.html`
**Pending:**
- Verified end-to-end via CDP+fake-mic: notes blur-save, dandelion record, stop, named save, recordings list (name/date/duration/player), transcript expand, transcript auto-append + idempotency. Test data cleaned up (notes cleared, test encounter deleted).
- Note: did NOT touch encounters.html (the page) or the encounters table schema, per spec. The transcribe-append is a backend API behaviour only.
- Kept the + My Season toggle in the section header (not in the new 3-part spec but removing it would regress functionality) — flag if you want it gone.
- encounter_date sent as toISOString().replace(Z,+00:00) not bare toISOString() — the spec said toISOString() but bare Z 422s on Python 3.9 fromisoformat (established gotcha).

### 2026-06-02 08:06
**Added Re-enrich all batch action to the Species missing a common name integrity check**

**Built:**
- POST /api/audit/reenrich-common-name: re-enriches one species via enrich_species(re_enrich=True, fill_empty_only=False) — direct enrichment, NOT review queue. Returns had/has_common_name + populated flag.
- iNaturalist common-name fallback in the endpoint: enrich_species fills common_names from Wikidata only, so when Wikidata has no entry (or is rate-limited) the endpoint falls back to taxa_autocomplete() (iNaturalist). Only fills when empty — never overwrites.
- Frontend: green Re-enrich all button on the missing_common_name category only (breakdown batch column + category header), matching the Send all button geometry. Loops per species with live progress (Re-enriching X/N) and a completion alert (X re-enriched, Y common names populated).
**Files:** `app/api/audit.py`, `frontend/scan.html`
**Pending:**
- Verified live: 3 species (Astrantia major great masterwort, Calocera viscosa Jelly-antler, Bellis annua Annual Daisy) populated via iNat fallback; audit count dropped 34->31. Button render confirmed via CDP screenshot. NOTE: fill_empty_only=False (per spec) means a re-enrich could refresh other culinary fields too; common_names itself is only-fill-when-empty so existing names are safe, but human-edited culinary fields are not protected (no protected_fields passed) — flag if that matters.

### 2026-06-02 07:51
**Fix 3 resolved: species-card Foraging Notes recorder now usable over ngrok (phone)**

**Fixed:**
- Fix 3: removed data-guest-hide from #fn-recorder-wrap on the species card. Root cause was NOT a width/CSS condition (section renders fully at 390px) — it was guest-mode: phone mic needs HTTPS (ngrok), ngrok sessions are is_guest=true, and data-guest-hide hid the recorder. The guest middleware (app/main.py:178-180) already allows POST /api/encounters, so guests/owner-on-phone can save. Kept data-guest-hide on the My Season toggle (its endpoint is guest-blocked, returns 403). Verified: guest POST /api/encounters returns 422 not 403 (reaches endpoint); my-season toggle returns 403.
**Files:** `frontend/species.html`
**Pending:**
- Optional: encounters-page My Season Record section (encounters.html:368) is still data-guest-hide; the New Encounter recorder there is already guest-visible. Left as-is (owner-only personal-season pipeline) unless you want it on phone too.
- Test encounter row id=1 (text_note __viztest__) from date verification still needs manual deletion — DELETE was blocked by auto-mode classifier

### 2026-06-02 07:47
**Four encounter-recorder fixes: ISO date format, remove View notes link, investigate phone visibility, fix New Encounter recorder not rendering (root cause: JS syntax error)**

**Fixed:**
- Fix 1: species + encounters recorders now send encounter_date as toISOString().replace(Z,+00:00) so Python 3.9 datetime.fromisoformat() accepts it (bare Z was rejected -> 422). Backend untouched.
- Fix 2: removed View notes link from species-card Foraging Notes (recordings show inline); removed dead fn-view-link JS wiring
- Fix 4: New Encounter recorder was missing because a JS SyntaxError (Unexpected identifier season) at _seasonCard line 949 aborted the whole IIFE, so _mountCapture/switchTab/loadEncounters/loadMySeason never defined. Caused by bad escaping class=\047 in onerror; fixed both occurrences (season-thumb + pc-photo placeholders) using &quot; entities. Whole encounters page (recorder, My Season grid, species dropdown) now works.
**Files:** `frontend/species.html`, `frontend/encounters.html`
**Pending:**
- Fix 3 (species Foraging Notes not visible on phone): could NOT reproduce — section renders fully and functionally at 390px in served HTML (headless Chrome screenshot confirms record button present). No desktop-only CSS condition exists. Only conditional hide is data-guest-hide on the recorder (ngrok guest sessions). Awaiting user confirmation of phone access method.
- Test encounter row id=1 (text_note __viztest__) created during +00:00 verification; DELETE blocked by auto-mode classifier — needs manual removal

### 2026-06-02 07:21
**Encounters page restructured into two clean pipelines + species-card foraging recorder hardened (waveform, empty state, transcript)**

**Built:**
- Encounters: New Encounter tab now first/default (observation pipeline), My Season second
- Each tab has its own recordings list split client-side by encounter_type (field vs season) with No recordings yet empty state
- Species card Foraging Notes: inline live waveform visualiser during recording
- Species card: list of saved recordings with read-only Transcript block per recording + No recordings yet empty state + inline audio players
**Fixed:**
- Encounters empty-state hang: lists render No recordings yet on empty [] response instead of staying on Loading
- Removed mixed-pipeline Record a field note widget + Foraging Notes species/date filter from My Season tab
- Species card recent-notes list: fixed curly-quote (U+201D) bug that broke class names and hrefs
- Trimmed dead _populate calls for removed capture/filter species selects
**Files:** `frontend/encounters.html`, `frontend/species.html`
**Pending:**
- Browser click-through (record/waveform/transcript) blocked by sandbox venv permission; verified via served HTML + live API (encounters=[] empty state, my-season grid renders)

### 2026-06-02 06:59
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_065921.sqlite`

### 2026-06-02 06:59
**Session ended** — Session ended from Settings page

### 2026-06-02 06:48
**Snapshot** — End of session — Built species card inline recorder (no nav away, saves foraging_note type with species_id + GPS), rationalised Foraging Notes section with note count/inline record/view-notes/My Season toggle. Confirmed prior-session items: GPS on both encounter contexts, season-tab recorder, in-season filter on species page, map in-season toggle, Foraging Notes rename.
DB: `snapshots/db_20260602_064859.sqlite`

### 2026-06-02 06:48
**Session ended** — Built species card inline recorder (no nav away, saves foraging_note type with species_id + GPS), rationalised Foraging Notes section with note count/inline record/view-notes/My Season toggle. Confirmed prior-session items: GPS on both encounter contexts, season-tab recorder, in-season filter on species page, map in-season toggle, Foraging Notes rename.

### 2026-06-02 06:48
**Species card inline recorder (fix nav bug), rationalised Foraging Notes section, My Season toggle; plus verification of items 3-5 from prior session**

**Built:**
- Species card inline recorder: 52px mic button, GPS auto-capture on record-start, saves to /api/encounters with species_id + encounter_type=foraging_note, shows Recording saved confirmation inline, never navigates away
- Rationalised Foraging Notes section: heading + note count badge, inline record button, View notes link (/encounters?species=ID opens personal card), My Season toggle (add/remove, shows current state)
- My Season toggle replaces the old + My Season button: tappable to add or remove, reads current state from /api/personal-lists/my-season in parallel with encounter fetch, updates instantly on tap
- foraging_note added as valid encounter_type (alongside field and season)
- gps.js added to species.html for GPS auto-capture on species card recorder
- Confirmed items 3-5 from prior session: GPS in both encounter contexts (3 calls), In season now chip on species page, Map in-season toggle, Season-tab recorder, Foraging Notes rename
**Fixed:**
- Removed navigation away from species card when Record is tapped (was linking to /encounters) - now records inline
- Replaced cluttered section (record link, open personal card link, + My Season button) with compact phone-first layout
**Files:** `frontend/species.html`, `app/api/encounters.py`
**Pending:**
- Browser click-through of species card inline recorder blocked by sandbox venv; verified via live API (foraging_note POST with species_id persists correctly) + served HTML marker checks

### 2026-06-02 06:42
**Encounters Prompt 2 (GPS auto-capture, recording-saved confirmation, season-tab record button, Foraging Notes rename) + Prompt 3 (species in-season filter) + Prompt 4 (map in-season toggle)**

**Built:**
- Silent GPS auto-capture: GPS.getOnce() fires in background on record-start, stored to lat/lng on save, never blocks
- Recording saved confirmation beneath record button with timestamp + duration (e.g. Recording saved 02 Jun 2026, 06:14 0:43)
- Season-tab record button: identical context-aware capture widget, saves encounter_type=season
- Context-aware capture widget (_buildCaptureHTML/_mountCapture) reused by New Encounter (field) and My Season (season) tabs
- encounter_type column (model + Alembic 0016 + live DB) with field/season validation
- In season now filter chip (first) on species page: phenology-only, excludes no-phenology species when active, combines with existing filters
- Map In season now toggle in filter controls: per-pin in_season from server, hides no-phenology pins, additive with existing filters
- phenology.in_season_now() + parse_peak_season_months() best-effort peak_season month parsing
**Fixed:**
- Renamed Your Encounters -> Foraging Notes on species card and encounters page (display only)
- Removed orphaned _show/_hide helpers after capture refactor
**Files:** `app/models/encounter.py`, `app/api/encounters.py`, `app/api/culinary.py`, `app/api/map.py`, `app/services/phenology.py`, `migrations/versions/0016_add_encounter_type.py`, `frontend/encounters.html`, `frontend/species.html`, `frontend/index.html`
**Pending:**
- Browser click-through of capture/record/GPS/confirmation + in-season filters (preview MCP blocked by sandbox venv permission); verified via live API + served HTML + phenology unit checks

### 2026-06-02 06:21
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_062155.sqlite`

### 2026-06-02 06:21
**Session ended** — Session ended from Settings page

### 2026-06-02 05:39
**Encounters page: fix blocking bugs (tab/loading), make species_id optional, strip capture UI to record-first**

**Built:**
- Decoupled init: loadMySeason, loadEncounters, and URL tab/species params now fire immediately in DOMContentLoaded — no longer gated on _loadSpecies fetch. Fixes both root bugs.
- Record-first capture UI: large 80px circular record button as primary element; playback/discard row appears only after recording stops; waveform visualiser + wake lock preserved
- Upload-file fallback kept as clearly secondary control beneath a dashed separator with muted label
- Stage 1 prompt (What do you actually see?) stays with its disappearing placeholder; text note demoted to optional/secondary
- Species field removed from capture form entirely — species linking belongs in laptop/archive view only
**Fixed:**
- Root cause 1 (New Encounter tab does nothing): loadMySeason/loadEncounters/tab-switch gated on _loadSpecies().then() — decoupled so tab switch is immediate
- Root cause 2 (My Season stuck on loading): same gate — now fires independently
- Backend: species_id made optional (Form(None)) on POST /api/encounters — model already nullable=True, no schema change needed
- _resetForm: removed species-select reference (element removed from DOM)
- saveEncounter: removed species validation; requires audio or text content instead; uses current time (no datetime-local input)
**Files:** `frontend/encounters.html`, `app/api/encounters.py`
**Pending:**
- Server restart needed for encounters.py change to go live (species_id Optional — server currently running old Form(...) code)
- Browser click-through of: tab switch, record button, upload fallback, save without species
- GPS / season-tab changes deferred per prompt instructions

### 2026-06-02 04:53
**P7 follow-up — show English common names on the suggested-species review card**

**Built:**
- Suggested-species card now renders common names (.sp-common) from the candidate whose scientific_name exactly matches species_suggested, between the italic name and the muted suggested label
- Exact-match only: never attributes another candidate species common names to the suggestion; omits the line when no match or no common names
**Files:** `frontend/review.html`
**Pending:**
- Browser screenshot verification still blocked by sandbox venv; verified via live API (matching-candidate common names resolve for #8200/#8217, gracefully empty for #8229) + served HTML

### 2026-06-02 04:47
**P7 — review card shows species_suggested in tile header (italic) with muted suggested label when species_primary is null; display only, no promotion**

**Built:**
- Review card fallback species block: when species_primary is null but species_suggested is non-null, renders species_suggested in italic via .sp-name with a muted uppercase "suggested" label (.sp-suggested-label) beneath
- New .sp-suggested-label CSS rule
**Files:** `frontend/review.html`
**Pending:**
- Browser screenshot verification blocked by sandbox venv (preview server cannot read venv/pyvenv.cfg); change verified via live API serialization of species_suggested + served HTML grep
- Next per roadmap: roadmap update, then Phase 12 scoping

### 2026-06-02 04:43
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260602_044303.sqlite`

### 2026-06-02 04:43
**Session ended** — Session ended from Settings page

### 2026-06-02 04:34
**P6: Pipeline breakdown consistency + label clarifications — 4 changes to scan page and review queue**

**Built:**
- Change 1: .ss-scope-label CSS class + This batch subtitle above session chip rows on both P1 and P2
- Change 3: P1 (Syncthing) gains a Prefilter Rejects accordion matching P2 structure — _fetchPrefilterRejects shared helper, loadP1PrefilterRejects() fetches ?source=syncthing, loadPrefilterRejects() now fetches ?source=file_upload (P2-scoped)
- Change 4: Status dropdown option renamed Rejected → Manually rejected in review.html; internal value=rejected unchanged
**Fixed:**
- GET /api/scan/prefilter-rejects gained optional ?source= query param (syncthing / file_upload / empty=all) — used to scope the two accordions independently
**Files:** `frontend/scan.html`, `frontend/review.html`, `app/api/scan.py`
**Pending:**
- Server restart required for ?source= param on /api/scan/prefilter-rejects to go live
- Change 2 (breakdown table labels): already consistent between P1 and P2 — no change needed

### 2026-06-02 04:25
**Confirm and fix the live code-path vulnerability that produced 22 approved+null-species_primary observations**

**Fixed:**
- Root cause identified: NOT a race condition in set_observation_species. Two distinct failure paths: (1) recheck-threshold cleared species_primary for needs_review rows, reviewer then approved via unguarded PATCH /review endpoint; (2) _gs referenced-before-assignment bug → below-threshold reprocess → same unguarded approval path.
- Fix: update_review (PATCH /{id}/review) now auto-promotes species_suggested → species_primary via set_observation_species() when approving with null species_primary but non-null species_suggested. Guard is a no-op for landscape/unknown approvals (both fields null). Covers both single and bulk approve (bulk routes through same endpoint).
- reject_undo path intentionally not guarded — restores a previously-approved-then-rejected obs; species_primary is already set before rejection in that flow.
- All 4 correctness cases verified: bug case (promote), landscape (no-op), normal (no-op), manually_verified+suggested (promote).
**Files:** `app/api/observations.py`
**Pending:**
- Server restart required for the fix to go live
- P6: Pipeline 2 summary table format (waiting for screenshot)

### 2026-06-02 04:17
**P0 follow-up: audit all identified+null observations, fix approved+null data integrity issue, bulk correct below_threshold status**

**Fixed:**
- 22 approved observations (May 27-29) with null species_primary repaired: species_primary set from species_suggested, species_id FK linked where species record exists (19/22 linked; 3 have no species record yet: Abies grandis, Crepis tectorum, Alchemilla vulgaris)
- 1188 observations with identification_status=identified AND species_primary=null corrected to identification_status=below_threshold
- 0 legacy identified+null rows remain
- June 1 06:52 batch: all 47 observations confirmed accounted for — 15 approved, 9 manually_verified, 3 below_threshold/needs_review, 20 below_threshold/rejected. No silent failures.
**Files:** `data/foragingid.db (1210 rows touched: 22 species_primary repaired + 1188 identification_status corrected)`
**Pending:**
- 3 species without records (Abies grandis id=9436, Crepis tectorum id=9460, Alchemilla vulgaris id=9497) have species_primary set but no species_id FK — these will be linked when enrichment next runs for those species
- P6: Pipeline 2 summary table format (waiting for screenshot)

### 2026-06-02 04:00
**P0-P5 fixes: missing observation investigation + logging, edibility folded into ID pipeline, named-only filter fix, settings collapsibles, near-me zoom, review filter bar grouping**

**Built:**
- P1: PFAF edibility auto-resolution at ID time (_apply_pfaf_to_species_edibility in enrichment.py)
- P1: Edibility tab removed from review queue (tab, pane, JS all removed)
- P2: /api/observations/{id}/suggest PATCH endpoint — saves species_suggested on lookup
- P2: _corrLookup now fire-and-forgets suggest PATCH before searching
- P3: API Dashboard collapsible (starts collapsed), Data Sources starts collapsed, Share with Guests collapsible (starts collapsed)
- P4: setNearMeRadius zooms map to fit L.circle bounds for selected radius
- P5: Toolbar filter controls grouped: Status+Named/Unnamed as identity group, Phone+NoGPS as source group
**Fixed:**
- P0: obs#15983 reviewer_notes corrected (was wrong audit message), identification_status set to below_threshold
- P0: scan.py no-match branch now sets identification_status=below_threshold (was inconsistently identified with null species_primary)
- P0: scan.py and syncthing.py add explicit logger.warning/logger.error for files seen but not assigned a species
- P0: no-candidates branch also sets identification_status=below_threshold and logs warning
**Files:** `app/api/scan.py`, `app/api/syncthing.py`, `app/api/observations.py`, `app/services/enrichment.py`, `frontend/review.html`, `frontend/settings.html`, `frontend/index.html`, `data/foragingid.db (obs#15983 backfilled)`
**Pending:**
- P6: Pipeline 2 summary table format (waiting for screenshot)
- Server restart needed for new /suggest endpoint and scan.py/enrichment.py changes to go live
- PFAF edibility auto-resolution will apply on next enrichment run for new species
- Existing unknown-edibility species can be backfilled by running POST /api/edibility/rescan

### 2026-06-01 19:53
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_195334.sqlite`

### 2026-06-01 19:53
**Session ended** — Session ended from Settings page

### 2026-06-01 19:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_194707.sqlite`

### 2026-06-01 19:47
**Session ended** — Session ended from Settings page

### 2026-06-01 19:05
**Consolidation — merge Encounters and My Season into one page at /encounters**

**Built:**
- Merged encounters.html: two tabs (My Season default, New Encounter on demand) with switchTab(); URL params ?tab=new and ?species=ID handled on load
- My Season tab: standing list grid + add/remove (data-guest-hide), filterable encounter list using full _renderCard (transcript/suggestions shown), personal card overlay with print stub
- New Encounter tab: full capture form (recorder, GPS, Stage 1 prompt, audio upload, save); auto-switches to My Season after save so new encounter appears immediately
- All 11a.4 features (Transcribe/Extract/confirm-dismiss) preserved in merged _renderCard
- /my-season → /encounters 301 redirect (query-string-preserving) so all deep links and inbound URLs still work
- Removed My Season nav link from all 8 other pages; /encounters link present on all 9; encounters.html itself marks /encounters as active
**Fixed:**
- species.html Record one → link updated to /encounters?tab=new so it opens the capture tab directly
**Files:** `frontend/encounters.html`, `app/main.py`, `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/lists.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`
**Pending:**
- my-season.html kept on disk but no longer served — /my-season 301 → /encounters. Can be deleted later if desired.
- Browser click-through of tabs, personal card, capture-to-season flow pending user verification

### 2026-06-01 18:51
**11a.4 completion pass — species suggestion confirm sets encounter.species_id; species match links to card; phone transcript confirmed read-only**

**Fixed:**
- resolve_suggestion: confirmed species suggestion now sets encounter.species_id to matched_species_id (only when encounter.species_id is None — never overwrites capture choice, never writes species record)
- Suggestion card UI: species match now renders as clickable /species?s= link with confirm-links-this-encounter hint (no match shows updated copy)
- Confirmed phone/guest view: transcript block has no data-guest-hide — renders read-only on phone; only Transcribe/Extract/confirm-dismiss buttons are guest-hidden via CSS
**Files:** `app/api/encounters.py`, `frontend/encounters.html`

### 2026-06-01 18:37
**11b refinement — rank + cap the seasonal-returns bell (trigger/dedup unchanged)**

**Built:**
- Ranking: in-season-now before starting-soon, then most-recent last sighting, then highest sighting count (obs+encounter); added sighting_count to each item; string-proxy descending-date sort key
- Cap: endpoint returns top 10 by default; response shape {shown,total,lead_days,items}; ?all=true returns full ranked list; ?limit=N override (1-200)
- Bell UI: shows top 10, header reads N of TOTAL, badge = total; Show all (N) button fetches ?all=true and re-renders without losing state; dismiss now decrements total
**Files:** `app/services/seasonal_returns.py`, `app/api/notifications.py`, `frontend/static/js/seasonal-returns.js`
**Pending:**
- Trigger logic (phenology + anniversary) and dismissal/dedup behaviour deliberately unchanged
- Browser click-through of the bell + Show all expander is the users verification pass; endpoint verified: default shown=10/total=80, ?all=true=80, ?limit=3=3, ranking now>recency>count confirmed via unit test

### 2026-06-01 18:11
**Prompt 11b — Seasonal return notifications (in-app bell, phenology + anniversary triggers, per-season dedup)**

**Built:**
- app/services/seasonal_returns.py — computes returning species from confirmed observations + encounters; phenology trigger (fruit>flower>leaf, now + 2-week lead soon) with anniversary-of-last-sighting fallback where phenology blank; dedup via season_key (year:category / year:anniversary)
- notification_dismissals table + NotificationDismissal model (Alembic 0015, idempotent) — per-species-per-season dismissals
- GET /api/notifications/seasonal-returns?lead_days (default 14, clamped 0-60) and POST /seasonal-returns/dismiss
- frontend/static/js/seasonal-returns.js — owner-only header bell (guest-guarded via /api/me), badge count, dropdown listing returns with reason/last-seen/place, View on map + My Season links, per-item Dismiss; injects own styles
- Bell script included on all 9 header pages (index, review, species, lists, encounters, my-season, scan, settings, about)
**Files:** `app/models/notification.py`, `app/services/seasonal_returns.py`, `app/api/notifications.py`, `migrations/versions/0015_add_notification_dismissals.py`, `app/main.py`, `frontend/static/js/seasonal-returns.js`, `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/lists.html`, `frontend/encounters.html`, `frontend/my-season.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`
**Pending:**
- Server restarted; endpoint live (count=80 returning species for 1 June from real phenology data). Browser click-through of the bell/dropdown/dismiss is the users verification pass.
- Tuning note: with 80 species currently in season the badge is large — defaults are lead=14d, in-season-now persists until dismissed (deduped per season). Consider narrowing to season-OPENING only (drop the in-season-now persist) if too noisy.
- Defaults used per user: both triggers (phenology + anniversary fallback), header bell app-wide, 2-week lead, dedup per species per season

### 2026-06-01 17:58
**Prompt 11a.4 — Transcription (Whisper) + Extraction (Claude) layer for encounters**

**Built:**
- OPENAI_API_KEY + whisper_model in config; OpenAI (Whisper) card added to API Dashboard (pasteable key, live probe of /v1/models)
- encounters.transcript + encounter_suggestions columns (Alembic 0014, additive/idempotent)
- app/integrations/whisper.py — httpx Whisper REST client (no new dep), typed WhisperError, 120s timeout
- app/integrations/encounter_extract.py — lightweight Haiku extraction -> species/phenology/recipe/location suggestions JSON, species reconciled to confirmed-species index
- POST /api/encounters/{id}/transcribe (deliberate laptop step, never auto on capture)
- POST /api/encounters/{id}/extract (suggestions only, never writes species cards)
- POST /api/encounters/{id}/suggestions/{sid}/{confirm|dismiss} — confirm logs + enriches empty location_name; dismiss discards
- encounters.html archive view: Transcribe/Extract buttons, transcript block, confirm/dismiss suggestion cards (data-guest-hide)
**Fixed:**
- Applied pending Alembic migrations: DB was stamped 0012; 0013 (personal_lists) and 0014 both upgraded to head idempotently
**Files:** `app/config.py`, `app/models/encounter.py`, `app/api/encounters.py`, `app/integrations/whisper.py`, `app/integrations/encounter_extract.py`, `app/services/api_dashboard.py`, `migrations/versions/0014_add_encounter_transcript.py`, `frontend/encounters.html`
**Pending:**
- Server restart needed: running uvicorn (no --reload) predates the new routes — /transcribe /extract /suggestions are 404 until restart. Updated HTML already served live; columns already migrated to head.
- OPENAI_API_KEY must be pasted in Settings -> API Dashboard (OpenAI/Whisper card) before Transcribe works
- Browser click-through of transcribe->extract->confirm/dismiss pending restart + keys; all backend contracts verified in-process (httpx ASGITransport): 400/404/422 guards, list fields, location enrichment on confirm, dismiss discard, no-key graceful paths

### 2026-06-01 17:50
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_175045.sqlite`

### 2026-06-01 17:50
**Session ended** — Session ended from Settings page

### 2026-06-01 17:47
**Review Queue UI fixes — 4 items: nav label, compact thumbnail cards for Edibility+Location Review, Repopulate cancel, skip empty enrichment cards**

**Built:**
- 1. Page/nav label: title + all-page nav links changed from Species ID to Review; tab inside stays Species ID
- 2. Location Review: compact thumbnail grid layout (minmax 200px, auto-fill) — thumbnail at top like obs-card, loc-card-body with name/date/badges, inline Set GPS/No GPS/Delete buttons, collapsible loc-map-panel (hidden until Set GPS clicked), lazy Leaflet init on toggle
- 2. Edibility tabs: compact thumbnail grid layout (minmax 190px) — edib-thumb/edib-card-body/edib-curate-btn for conditional curation; edib-unk-body/edib-unk-save for unknown triage; thumbnail from new API field
- 3. Repopulate cancel: _popControllers Map + AbortController per species — clicking Running button cancels and resets; AbortError is silent
- 4. Enrichment review filter: all-empty species (edible_parts + preparation_warnings + look_alike_warnings all null) skipped silently; review_requested always shown
**Fixed:**
- edibility.py: added bulk thumbnail lookup to /api/edibility/species and /api/edibility/unknown (single query per endpoint, first confirmed-obs thumbnail per species)
**Files:** `frontend/review.html`, `frontend/about.html`, `frontend/encounters.html`, `frontend/index.html`, `frontend/lists.html`, `frontend/my-season.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/species.html`, `frontend/upload.html`, `app/api/edibility.py`

### 2026-06-01 17:18
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_171842.sqlite`

### 2026-06-01 17:18
**Session ended** — Session ended from Settings page

### 2026-06-01 17:14
**Snapshot** — End of session — Built Prompt 11a.3: My Season standing personal list (server-side, workshop-of-one), personal card (read-only species scaffold join with encounters), Stage 1 Goethean prompt on encounter entry, browser-print stub on /my-season, My Season nav across all pages. Also fixed /api/species/ missing id field. All 5 check groups passed via curl/httpx verification.
DB: `snapshots/db_20260601_171428.sqlite`

### 2026-06-01 17:14
**Session ended** — Built Prompt 11a.3: My Season standing personal list (server-side, workshop-of-one), personal card (read-only species scaffold join with encounters), Stage 1 Goethean prompt on encounter entry, browser-print stub on /my-season, My Season nav across all pages. Also fixed /api/species/ missing id field. All 5 check groups passed via curl/httpx verification.

### 2026-06-01 17:11
**Prompt 11a.3 — My Season standing personal list (server-side), personal card (read-only species⋈encounters join), Stage 1 Goethean prompt on encounter entry, browser-print stub**

**Built:**
- PersonalList + PersonalListSpecies models + migration 0013 (idempotent); standing My Season list auto-created per user (slug=my-season, user_id=1)
- app/api/personal_lists.py: GET/POST/DELETE /api/personal-lists/my-season(/species), GET /api/personal-lists/card/{species_id} (read-only scaffold join + your encounters)
- Stage 1 prompt: encounters create accepts prompt_response, stores prompt_stage=1; other 3 Goethean stages deferred
- GET /api/encounters gains species_id/date_from/date_to filters (powers species-card panel + personal view)
- frontend/my-season.html: standing list grid, filterable personal view, personal card overlay with @media print stub (Cmd+P)
- species.html: read-only Your encounters panel + Add to My Season, links out to /my-season?species=ID
- My Season nav link added across all pages
**Fixed:**
- /api/species/ now returns id (was absent) — the existing encounters.html species dropdown relied on sp.id and data.species and was silently broken; fixed both encounters.html and my-season.html to read the array shape and skip null-id entries
**Files:** `app/models/personal_list.py`, `migrations/versions/0013_add_personal_lists.py`, `app/api/personal_lists.py`, `app/api/encounters.py`, `app/api/culinary.py`, `app/main.py`, `frontend/my-season.html`, `frontend/encounters.html`, `frontend/species.html`, `frontend/index.html`, `frontend/review.html`, `frontend/lists.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`
**Pending:**
- Server restart needed: running uvicorn (started 16:53, no --reload) predates the new router/page-route/encounters changes — /api/personal-lists and /my-season are 404 until restart. New tables already created in data/foragingid.db via init_db; migration 0013 is idempotent.
- Browser click-through of /my-season + species-card panel pending restart; all backend contracts verified in-process against the real app+DB (httpx ASGITransport): auto-create, add/idempotent/remove, card join, Stage 1 prompt_stage=1 round-trip, date+species filters, 404/422 guards

### 2026-06-01 16:56
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_165655.sqlite`

### 2026-06-01 16:56
**Session ended** — Session ended from Settings page

### 2026-06-01 16:48
**Prompt B — Data Trust deep audit + fixes (B1 audit, B2 send-to-review fix + Accept button, B3 no removals, B4 DB Overview consolidation)**

**Built:**
- B2: Accept button on top-10 confidence table — POST /api/trust/accept-species marks all auto-approved obs for a species as manually_verified + human_corrected, removes row on success
- B4: Database Overview moved from standalone Database tab into Data Trust tab as collapsible Section E; Database tab button removed; loadDbSummary now triggered on Trust tab first open and on Section E expand (lazy); 30s auto-interval removed
**Fixed:**
- B2: trSendSpeciesToReview read d.updated (always undefined → 0); corrected to d.queued. Now shows correct count and removes the row immediately on success
- B3: no removals — B1 audit found no dead UI and no fundamentally broken tools; all Section B/C/D functions work correctly (confirmed endpoint contracts); only bug was the B2 key typo
- B4: removed empty Database tab (data-tab=database, switchTab branch, tab-database pane); no duplicate element IDs; DB section collapsed by default, expands lazily
**Files:** `app/api/trust.py`, `frontend/scan.html`
**Pending:**
- Server restart needed for POST /api/trust/accept-species to go live (currently 404); all frontend changes already served
- B1 audit note: POST /api/trust/kingdom-audit has no UI — harmless unused backend, left in place

### 2026-06-01 15:32
**Prompt A — Review Queue fixes A1-A7 (rename tab, candidate auto-update, Lens uploadbyurl, enrichment edit+approve+repopulate, medicinal auto-fill, edibility persist+rescan, location map fix)**

**Built:**
- A1: "Review Queue" tab renamed to "Species ID" (nav link on all 9 pages, page title, tab button) — routes + JS keys unchanged
- A2: lookup/second-opinion candidate selection now updates the species name field + card header immediately and persists, leaving the card for Approve; removed the second-opinion confirm overlay
- A3: Open Lens builds lens.google.com/uploadbyurl?url={origin}/api/observations/{id}/photo (works over public/ngrok URL), opens new tab, falls back to Lens home
- A4: enrichment edit+approve marks field approved (ai_approved_fields_json) + verifies species via mark_reviewed (leaves queue); Populate renamed Repopulate and refreshes the card fields inline from the enrich response
- A6: Edibility tab gains an Unknown-edibility triage queue (GET /api/edibility/unknown), a persisting status correction (PATCH /api/edibility/status/{id}) that clears the card immediately, and a background Rescan (POST /api/edibility/rescan + /rescan-status polling) for all unknown species with confirmed sightings
- A7: Location Review maps now render — added Leaflet invalidateSize() after map build (150ms+600ms) and on tab re-open (root cause: map built inside a display:none tab pane measured 0x0)
**Fixed:**
- A4 backend: PATCH /api/culinary/{name}/field now adds the field to ai_approved_fields_json (was landing in limbo) and accepts mark_reviewed to set edibility_verified
- A5: enrichment auto-fills medicinal_notes with "No known traditional medicinal uses" + marks approved when no medicinal data from any source; retroactively backfilled 19 confirmed species (no dupes, valid JSON)
- A6 backend: added _VALID_EDIBILITY status setter, unknown queue (confirmed-obs scoped), background rescan worker re-running enrichment
**Files:** `frontend/review.html`, `frontend/index.html`, `frontend/scan.html`, `frontend/about.html`, `frontend/encounters.html`, `frontend/settings.html`, `frontend/species.html`, `frontend/upload.html`, `frontend/lists.html`, `app/api/culinary.py`, `app/api/edibility.py`, `app/services/enrichment.py`, `scripts/backfill_medicinal_default.py`
**Pending:**
- Server restart required for A4/A5/A6 backend (new endpoints + enrichment logic) to go live; A5 backfill already applied to data/foragingid.db
- Verified offline: py_compile clean; SQL contract checks for A4 (queue 139->138) + A6 (status persist + unknown scope 217) + A5 backfill (19, no dupes); review.html backtick parity even, /review 200, A1 nav across 9 pages; live HTTP + browser click-through pending restart (sandbox venv blocks restart)
- A3 caveat: Google fetches the URL server-side, so Lens only loads the image when the app is opened over a public/ngrok URL (not bare localhost) — chosen approach per user
- Ready for Prompt B

### 2026-06-01 15:01
**Data Sources registry — Settings card + table/API + reachability test (registry only, no scraping)**

**Built:**
- data_sources table (Alembic 0012): label, url(unique), data_types(JSON), species_scope, region, status, notes, last_tested, last_test_status, created_at — seeded with agreed 10 sources (deduped from 12-line list)
- API router app/api/data_sources.py: GET/POST/PATCH/DELETE /api/data-sources + POST /{id}/test (HEAD->GET reachability, 8s timeout, follow_redirects; updates last_tested + last_test_status ok/unreachable)
- Settings Data Sources card (collapsible, beneath API Dashboard): table with label/url/data-type chips/scope/region/status toggle/last-tested dot/Test/Delete, plus Add+Test form that adds then immediately probes and reflects the status dot inline
- Status dot mapping: ok=green, untested=amber, unreachable=red
**Files:** `app/models/data_source.py`, `app/api/data_sources.py`, `migrations/versions/0012_add_data_sources_table.py`, `app/main.py`, `frontend/settings.html`
**Pending:**
- Server restart needed for new router/model to go live (/api/data-sources currently 404). Table + 10 seeds already applied to data/foragingid.db; Alembic 0012 is idempotent (CREATE guard + INSERT OR IGNORE) and will no-op-then-stamp on alembic upgrade head
- Verified offline: py_compile clean; reachability classification via curl (pfaf.org/foragerchef.com -> ok, bogus domain -> unreachable); DB write contract simulated (last_tested+last_test_status persist, reset to untested); settings.html backtick parity even, /settings 200, all JS wiring present. Live endpoint+inline-dot click-through pending restart (sandbox venv block)
- No scraping logic built (registry + reachability only, as specified)

### 2026-06-01 14:52
**11a.2 — lock down species cards to a single canonical write path (remove inline enrichment editing; add admin-only Send to review)**

**Built:**
- Admin-only Send to review button on species card (data-guest-hide): POST /api/culinary/{name}/request-review flags species into enrichment review queue with optional curator note, then offers to jump to /review#enrichment
- Enrichment review queue now surfaces manually-flagged species (review_requested=1) regardless of confidence, newest flags first; review card shows a Manually flagged banner + note + Resolve flag button (POST /clear-review)
- CulinaryInfo gains review_requested / review_requested_at / review_request_note (Alembic 0011, additive, idempotent guards)
**Fixed:**
- Removed inline edit/save from species card enrichment fields and safety warnings — now display-only (_renderFields, _warnBlock); deleted openFieldEdit/closeFieldEdit/saveSpeciesField
- Removed Lists enrichment dropdown inline editor (Save to species record, 10.7 C4) — now status + Include-in-PDF only; deleted openEnrichEdit/saveEnrichEdit and orphaned SECTION_FIELDS/SECTION_HINTS/_getFieldValue
- PATCH /api/culinary/{name}/field retained but now invoked solely from the enrichment review tab (the single canonical write path)
**Files:** `app/models/culinary.py`, `app/api/culinary.py`, `migrations/versions/0011_add_enrichment_review_flag.py`, `frontend/species.html`, `frontend/lists.html`, `frontend/review.html`
**Pending:**
- Scientific-name rename form (#prof-rename-form) intentionally kept — taxonomic identity correction, distinct from enrichment editing, already admin-gated, no equivalent in review tab
- Server restart needed for new ORM columns + endpoints to go live; columns already applied to data/foragingid.db via sqlite3 (Alembic 0011 will no-op-then-stamp on alembic upgrade head)
- Queue receive-item contract verified directly in SQLite (flag in->appears, out->drops); live HTTP verification of request-review/clear-review pending restart (sandbox venv blocks restart)
- 11a.3 next

### 2026-06-01 11:31
**11a.1 UI Addendum — native recorder visualiser + Wake Lock + upload fallback in encounter capture**

**Built:**
- Dandelion-leaf waveform visualiser: AnalyserNode RMS amplitude animates runcinate leaf serrations on a canvas while recording (fftSize 1024, requestAnimationFrame, non-critical/fails silently)
- Wake Lock toggle (Keep screen on while recording, checked by default): navigator.wakeLock.request(screen), released on stop + pagehide, re-acquired on visibilitychange while recording, silent where unsupported
- Upload fallback: file picker accepting mp3/m4a/wav/ogg, routes through the same FormData->/api/encounters->audio_path write path as the native recorder
**Fixed:**
- Track _audioName so uploaded files keep their real filename/content-type through FormData (recorder still defaults to recording.webm)
- Backend _AUDIO_EXTENSIONS: added audio/x-m4a, audio/aac, audio/x-wav, audio/wave aliases so uploaded m4a/wav get correct on-disk extension (additive, no schema change)
**Files:** `frontend/encounters.html`, `app/api/encounters.py`
**Pending:**
- Live browser click-through blocked by sandbox venv permission (preview server cannot read venv/pyvenv.cfg) — verified via served HTML + JS brace-balance parse + py_compile; manual mic/upload test recommended
- 11a.2 next

### 2026-06-01 11:12
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_111219.sqlite`

### 2026-06-01 11:12
**Session ended** — Session ended from Settings page

### 2026-06-01 11:08
**Fix F — Lists: rename Workshop→Recipe Booklet, refocus Field Guide on ID notes, add Workshops stub tab**

**Built:**
- Tab/button/label rename: Workshop → Recipe Booklet (internal mode key unchanged for localStorage compat)
- Field Guide refocused: id_notes as primary text (200 chars), lookalike warnings with ⚠ prefix, edible parts/harvest as note, optional photo thumbnail (respects Show photos toggle), recipe title demoted to secondary
- Workshops tab: third mode-toggle button, stub placeholder text per spec, print button disabled in this mode
**Files:** `frontend/lists.html`
**Pending:**
- Fix G or next item in queue

### 2026-06-01 11:04
**Fix E — location-aware ID bias (iNaturalist Geomodel)**

**Built:**
- score_image() now accepts lat/lng/observed_on; sends them as form fields so iNaturalist Geomodel weights results by spatio-temporal frequency
- iNat candidates ranked by geo-weighted combined_score (geo_score) so locally plausible species surface higher
- INatCandidate gains vision_score + geo_score fields for transparency
- All 3 iNat call sites (identification.py, scan.py, reidentify.py x3) now pass observation coordinates + photo date
**Fixed:**
- Safety: gating score = pure vision_score (geo-independent), so location bias is ranking-only and can never create/suppress an auto-approval; gating byte-identical with vs without geo (verified)
- PlantNet unchanged (does not accept coordinates per A2)
**Files:** `app/integrations/inaturalist.py`, `app/services/identification.py`, `app/api/scan.py`, `app/api/reidentify.py`
**Pending:**
- Server restart to pick up changes
- Blackberry test #15961: geo did NOT push Rubus fruticosus above Rubus armeniacus — armeniacus genuinely scores higher in Sheffield iNat data (geo 0.568 vs 0.152); fix surfaced fruticosus from absent to rank #2
- Fix F — Lists rename + third tab

### 2026-06-01 10:50
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_105005.sqlite`

### 2026-06-01 10:50
**Session ended** — Session ended from Settings page

### 2026-06-01 10:34
**Review queue: Retry ID bulk button, inline confirm on Approve/Reject/Delete, lookup common names, Request ID for unnamed**

**Built:**
- 1. Bulk 'Retry ID selected' button in select-mode toolbar — confirms count, fires POST /api/observations/{id}/retry-identify for all selected, shows ok/fail toast, does not change review_status
- 2. Inline confirmation on Approve / Reject / Delete card buttons — button area transforms to confirm msg + Yes/No pair; clicking again cancels; Delete no longer uses the modal dialog
- 3. Lookup common-name backfill — species_lookup now applies iNat common_name to GBIF-first results that returned no vernacular name (e.g. Urtica dioica now shows 'great stinging nettle')
- 4. 'Request ID' for unnamed — renamed Retry ID to '🔍 Request ID'; isUnnamed condition now based on species_primary+species_suggested both null (catches identified-status obs with no confirmed name); routes plants to PlantNet+iNat, fungi to iNat+MO; never auto-approves
**Files:** `frontend/review.html`, `app/api/reidentify.py`

### 2026-06-01 10:24
**Confidence Dashboard — add manually_verified category row + per-category distribution tabs**

**Built:**
- Manually confirmed row in Section A: shows count (74), lowest confidence score, and 'View distribution' button — distinct from auto-approved, never conflated
- Distribution chart tabs: Auto-approved / Manually confirmed / Needs review / Rejected — clicking any tab switches the chart to that category's distribution
- Backend: _bucket_scores() helper; per-category distributions (auto_approved, manually_verified, needs_review, rejected) returned as d.distributions; manually_verified_count + manually_verified_lowest added to chips payload
- Auto-approved queries now use review_status='approved' AND human_corrected=False (was incorrectly including manually_verified rows); backward-compat 'distribution' key preserved
**Files:** `app/api/trust.py`, `frontend/scan.html`
**Pending:**
- Server restart required to pick up trust.py changes

### 2026-06-01 10:06
**Fix B — Named only / Unnamed only filter bugs in review queue**

**Fixed:**
- Named only now matches species_primary OR species_suggested (was species_primary only — missed 70 observations with a below-threshold pipeline suggestion but no confirmed name)
- Unnamed only now requires BOTH species_primary IS NULL AND species_suggested IS NULL (was species_primary IS NULL only — incorrectly included observations that had a suggested name)
- Phone uploads filter: frontend now sends upload_source=file_upload (was 'phone' which matched 0 rows — all browser uploads are stored as file_upload in the DB); stats endpoint phone_uploads count fixed to match
- Named + Unnamed are now exhaustive and mutually exclusive: 496 + 7313 = 7809 (all observations)
**Files:** `app/api/observations.py`, `frontend/review.html`

### 2026-06-01 09:59
**Fix PlantNet 400 regression — lat/lng params not supported by API**

**Fixed:**
- Removed lat/lng query params from PlantNet identify_image() — PlantNet v2 API rejects them with 400 Bad Request; geotagged photos were silently failing identification
- Updated docstring to document the API limitation
**Files:** `app/integrations/plantnet.py`
**Pending:**
- Fix B — named/unnamed filter bug

### 2026-06-01 09:40
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_094011.sqlite`

### 2026-06-01 09:40
**Session ended** — Session ended from Settings page

### 2026-06-01 08:05
**Make /encounters and /lists available to phone (guest) app**

**Built:**
- guest-mode.js: removed /lists from BLOCKED nav array — Lists link now visible to guests
- main.py guest middleware: POST /api/encounters added to allowed writes alongside export-walk — guests can create encounters but not delete (DELETE /api/encounters/{id} path stays blocked)
- encounters.html: data-guest-hide on delete button — hidden in guest mode
- encounters.html: guest-mode.js script tag added
**Files:** `frontend/static/js/guest-mode.js`, `app/main.py`, `frontend/encounters.html`

### 2026-06-01 06:27
**Prompt 11a.1 — Encounters foundation + field capture**

**Built:**
- Alembic migration 0010_add_encounters_table (17 columns, 3 indexes)
- app/models/encounter.py — Encounter SQLAlchemy model
- app/api/encounters.py — POST/GET/GET-id/DELETE endpoints with multipart audio upload
- app/config.py — encounters_media_dir property + ensure_dirs wiring
- app/main.py — router registered, model noqa import, /media/encounters StaticFiles mount, /encounters page route
- media/encounters/ directory created
- frontend/encounters.html — field-capture form (species dropdown, datetime-local, GPS.getOnce location detect, MediaRecorder audio, text note) + My Encounters list view
- Nav link added to all 8 pages (index, review, species, lists, scan, settings, about, encounters)
**Files:** `migrations/versions/0010_add_encounters_table.py`, `app/models/encounter.py`, `app/api/encounters.py`, `app/config.py`, `app/main.py`, `frontend/encounters.html`, `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/lists.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`
**Pending:**
- Browser click-through of encounters capture form (server restart needed to pick up new routes)
- 11a.2 and 11a.3 (My Season list integration) not yet built

### 2026-06-01 05:48
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260601_054807.sqlite`

### 2026-06-01 05:48
**Session ended** — Session ended from Settings page

### 2026-06-01 04:43
**Prompt G — Retry ID button for unnamed observations in the review queue**

**Built:**
- POST /api/observations/{id}/retry-identify — re-runs ID by obs_category (plant: PlantNet+iNaturalist; fungi: iNaturalist image + Mushroom Observer name cross-check), returns candidates grouped by API source, never auto-approves
- POST /api/observations/{id}/retry-confirm — sets identification_status=identified + species_primary (via set_observation_species), logs edits + ProcessingLog, triggers standard enrichment (trigger_ai_drafts_for_species)
- Retry ID button (purple) in card-actions for unnamed observations (not identified, not not_plant, non-landscape)
- Grouped candidate dropdown panel beneath card mirroring the Second Opinion visual pattern; per-candidate Approve button; No-candidates state shows No identification returned — try manual rename
**Fixed:**
- JS-escape single quotes in retry approve onclick args so apostrophes in common names cannot break the handler
**Files:** `app/api/reidentify.py`, `frontend/review.html`
**Pending:**
- Full browser click-through still blocked by sandbox venv permission (preview server cannot launch); verified via live HTTP: retry-identify returns correct grouped JSON, retry-confirm guards 404/400/422 correct, both routes in openapi, backend py_compile clean
- iNaturalist token refresh still pending for dual-source coverage

### 2026-05-31 21:50
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260531_215032.sqlite`

### 2026-05-31 21:50
**Session ended** — Session ended from Settings page

### 2026-05-31 21:35
**Phase 10a Session C — offline tile caching, species pre-caching, read-only offline mode, cache management UI**

**Built:**
- Task 1: sw.js rewritten to v2 — TILE_CACHE (cache-on-request, bulk 30-day expiry, all three tile CDNs), SPECIES_CACHE (cache-first, per-response 7-day TTL via x-sw-cached-at header), SW message channel for clear-species-cache and get-cache-status
- Task 2: offline.js — pre-caches /api/species/{name}/profile for every confirmed species on page load (deferred 6s) and on reconnect; respects 6-day re-cache interval; rate-limited in batches of 5; stores last-cached timestamp+count in localStorage
- Task 3: offline.js — persistent Offline banner (position:fixed, nudges body padding), body.offline-mode class, injected CSS disabling all write controls (approve/reject/save/edit/upload) across review/species/scan pages, MutationObserver to catch dynamically-rendered buttons, title tooltip on each disabled element
- Task 4: Settings Offline cache card — species profile count + age, storage estimate via navigator.storage.estimate(), Refresh species cache button that clears SW cache and re-pre-caches; tile cache described as auto-managed
**Files:** `frontend/static/sw.js`, `frontend/static/js/offline.js`, `frontend/settings.html`, `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/scan.html`, `frontend/lists.html`, `frontend/about.html`
**Pending:**
- Manual browser verification required (sandbox cannot access venv): navigate map to cache tiles, simulate offline with DevTools, confirm banner + write-action disabling + species card reads from cache
- SW update requires hard-reload or DevTools unregister on first visit after deploy (browser needs to detect new sw.js)

### 2026-05-31 21:21
**Prompt D — D1 sync session 5-min coalescing window (Pipeline 1) + D2 lifetime pipeline file-count breakdown**

**Built:**
- D1: session_open_p1() coalescing helper — Syncthing batches arriving within 5 min of the previous session closing merge into one session (files_received summed, label recomputed, reopened) instead of fragmenting into multiple rows
- D2: files_duplicate column on scan_sessions (migration 0009) separating duplicate-hash skips from pre-filter rejects
- D2: GET /api/scan/lifetime-breakdown?pipeline=N — received / prefilter-rejected / duplicates / failed / completed, summing to files received with an unaccounted balancing term
- D2: scan-page breakdown panels on both pipelines with tracking-since note and pre-tracking unaccounted row + tooltip
**Fixed:**
- D1: _process_all now calls session_open_p1 instead of always creating a new session row
- D2: _ingest_file (P1) returns int|"duplicate"|"prefilter"|None so _process_one counts duplicates vs prefilter rejects distinctly
- D2: P2 duplicate early-return now increments files_processed+files_duplicate and auto-closes the session
**Files:** `app/services/scan_sessions.py`, `app/api/syncthing.py`, `app/api/scan.py`, `app/models/scan_session.py`, `migrations/versions/0009_add_scan_session_duplicate_count.py`, `frontend/scan.html`
**Pending:**
- Manual browser check of the breakdown panels on /scan (preview sandbox cannot read venv)
- Duplicate counts only accrue going forward; historical duplicates show under Unaccounted (pre-tracking)

### 2026-05-31 21:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260531_210942.sqlite`

### 2026-05-31 21:09
**Session ended** — Session ended from Settings page

### 2026-05-31 20:45
**A1-API audit: verified 6.5/7 fixes already implemented in prior sessions; closed the one genuine gap (A1.1 server-start iNat JWT expiry warning)**

**Built:**
- A1.1 server-start JWT expiry warning: main.py lifespan decodes INATURALIST_API_TOKEN on boot and logs WARNING if expired or <4h remaining (reuses _inat_token_status / INAT_EXPIRY_WARN_SECONDS)
**Fixed:**
- Corrected stale Current State block in CHANGELOG that wrongly listed A1-API as not-yet-run
**Files:** `app/main.py`, `CHANGELOG.md`
**Pending:**
- Audit confirmed already-done (no change needed): A1.2 kingdom gate 0.05, A1.3 dual_source_agreement semantics+backfill, A1.4 single-source 0.92, A1.5 API Dashboard, A1.6 Health Scan, A1.7 #13+#9, plus A1.1 semaphore/delay/logging/top_score guard
- iNaturalist token expired — refresh to re-enable dual-source ID
- Manual browser verification of reconnect banner + new review filters

### 2026-05-31 20:09
**Offline behaviour hardening (8s fail-fast timeouts + pending_connection state + reconnect banner) and review-queue filter changes (No GPS / Named only / Unnamed only)**

**Built:**
- Fix 1: All external API clients (PlantNet, iNaturalist, Mushroom Observer, PFAF, Wikidata) now hard-timeout at 8s
- Fix 1: identify_observation routes offline failures to identification_status=pending_connection, review_status=needs_review, routing_reason=Awaiting connection — identification not run; never auto-rejected
- Fix 1: PlantNetError.is_connection_error flag; new INatConnectionError + score_image(raise_on_connection_error=) opt-in
- Fix 1: batch runner treats pending_connection as always-eligible and counts it separately
- Fix 2: GET /api/identify/pending-connection (count) and POST /api/identify/run-pending (auto-detect source, trigger batch)
- Fix 2: shared pending-connection.js dismissible reconnect banner (guest-guarded), wired into index/review/scan
- Fix 3: review card shows Awaiting connection label for pending_connection observations
- Fix 3: backend list_observations gains no_gps, named_only, unnamed_only filter params
- Fix 3: review.html replaces Geotagged only checkbox with No GPS, adds Named only + Unnamed only
**Fixed:**
- External calls no longer hang behind a never-resolving spinner when offline
- Offline observations are no longer silently dropped or left ambiguous
**Files:** `app/integrations/plantnet.py`, `app/integrations/inaturalist.py`, `app/integrations/pfaf.py`, `app/integrations/wikidata.py`, `app/integrations/mushroom_observer.py`, `app/services/identification.py`, `app/models/observation.py`, `app/api/identify.py`, `app/api/observations.py`, `frontend/static/js/pending-connection.js`, `frontend/index.html`, `frontend/review.html`, `frontend/scan.html`
**Pending:**
- Live browser verification of the reconnect banner and new filter checkboxes (manual)

### 2026-05-31 17:57
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260531_175733.sqlite`

### 2026-05-31 17:57
**Session ended** — Session ended from Settings page

### 2026-05-31 17:47
**Phase 10.7 Part 2 C2-C5 — map lasso select, enrichment dropdown, inline field editor, cover page**

**Built:**
- C2: Map select mode — Lasso (rect draw) and Select all visible buttons added to select-bar; lasso disables map drag while drawing, exits automatically after each selection; both methods additive with tap-individual
- C3: Enrichment dropdown per species card — 6-category summary table (recipes/medicinal/foraging/lookalikes/conditions/phenology) with filled/empty status indicators and Include-in-PDF checkboxes; empty categories auto-deselected; prefs gate _fieldEntry and _workshopPage output; medicinal section added to workshop render
- C4: Inline edit per enrichment category — Edit button per row opens inline textarea pre-filled from profile cache; Save writes to DB via PATCH /api/culinary/{name}/field; cache + prefs invalidated on save so fill status refreshes; all 6 categories mapped to specific culinary_info fields
- C5: Cover page — toolbar Cover page button opens a fixed panel (event name, date, location, intro paragraph); persists in localStorage (foragingid_list_cover); Field Guide renders as column-spanning header block; Workshop renders as full Pein-aesthetic A4 cover page (serif centred); preview updates live on keystroke
**Files:** `frontend/index.html`, `frontend/lists.html`
**Pending:**
- C1 visual print check — sandbox venv blocks preview; user to verify Field Guide two-column layout and Workshop A4 page breaks manually in browser (Cmd+P)

### 2026-05-31 16:57
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260531_165717.sqlite`

### 2026-05-31 16:57
**Session ended** — Session ended from Settings page

### 2026-05-31 16:53
**B1 — remove Pipeline 2 individual file list; B2 — remove git push reminder**

**Fixed:**
- B1: Pipeline 2 no longer shows individual per-file upload cards during batch processing — card is created as a detached element (so all pipeline logic still runs) but never appended to the DOM. Session stats chips (Received/Processed/Approved/Review/Rejected/Failed) remain and update in real time. Removed #uq-toolbar and #upload-queue HTML containers, their CSS, and the dead JS batch-select/reject functions (toggleUcSelectMode, _ucUpdateToolbar, _ucToggleCard, _ucRejectSelected, _ucSelectMode var, _ucSelectedIds var). Also removed stray _ucSelectMode reference that would have thrown ReferenceError.
- B2: Removed Push to GitHub section from Settings (HTML block, pushToGitHub() JS function, and the wifi-dependent step mention in the End Session success status line).
**Files:** `frontend/scan.html`, `frontend/settings.html`
**Pending:**
- iNaturalist token expired — refresh + paste in API Dashboard

### 2026-05-31 16:34
**Deferred filter fixes #22, #13, #9**

**Fixed:**
- #22: null-kingdom species now default to Plant in species type filter — removed the edibility_status guard from _matchesTypeFilter so unenriched species (null kingdom + null edibility) are visible under the Plant chip
- #13: GET /api/observations with review_status=approved now includes manually_verified rows via .in_(["approved","manually_verified"]) — list count now matches queue badge count (340+63=403)
- #9: find-edible-only checkbox now has onchange=_runFindMode(_findMode) so toggling re-runs Mode 1 (in-season) immediately without needing to click Go
**Files:** `frontend/species.html`, `app/api/observations.py`, `frontend/index.html`
**Pending:**
- iNaturalist token expired — refresh + paste in API Dashboard
- Live browser verification blocked by sandbox venv permission issue

### 2026-05-31 16:30
**Review-queue UX batch A4-A8 (sort, pagination, sticky toolbar, no-match memory) + top_score backfill**

**Built:**
- A7: server-side sort param on GET /api/observations (date_desc/date_asc/conf_desc/conf_asc via top_score) + Sort <select> in review toolbar; removes page-local-only confidence sort so ordering is now global across pages (fixes audit #16)
- A7 data: backfilled Observation.top_score from candidates[0].score for 70 legacy NULL rows (scripts/backfill_top_score.py); scan.py syncthing pipeline now persists obs.top_score so new imports are sortable (upload path already did via identification.py)
- A5: results-per-page <select> (12/24/48/96); PAGE_SIZE now mutable, changePageSize() resets to page 0
- A6: First/Last pagination buttons (firstPage/lastPage/_lastOffset) with correct disabled states at both ends
- A8: bulk/reject toolbar now position:sticky top:0 with shadow while active so Reject/Approve stay reachable scrolling a long queue
- A4: no-match memory per session (sessionStorage key foragingid_nomatch_handled) — deselecting a genuine no-match card marks it handled, re-selecting clears it, and Select no-match skips handled ids with a skipped-count toast
**Fixed:**
- top_score column was NULL for all needs_review rows; backfill + scan.py write path make confidence sort meaningful (note: ObservationOut does not serialize top_score, which masked the column during testing)
**Files:** `app/api/observations.py`, `app/api/scan.py`, `scripts/backfill_top_score.py`, `frontend/review.html`
**Pending:**
- Deferred filter fixes: #22 (null-kingdom species default to Plant), #13 (Approved list include manually_verified), #9 (Find edible-only onchange)
- iNaturalist token expired — refresh + paste in API Dashboard
- Live browser verification of A4-A8 blocked by sandbox venv permission issue (verified via HTTP + DB + JS parse)

### 2026-05-31 16:10
**A3 — Select no-GPS toggle button in review queue**

**Built:**
- toggleSelectNoGPS() toggles selection of all visible cards with no GPS coordinates (detected via presence of .gps-row inline lat/lng entry row)
- select-nogps-btn shown/hidden alongside select mode in toggleSelectMode(), pressed state reset on entry/exit
- aria-pressed toggle: press selects all no-GPS cards, press again clears them; toast feedback for each outcome
**Fixed:**
- A3 button markup existed but toggleSelectNoGPS() was undefined and toggleSelectMode did not surface the button — completed the wiring
**Files:** `frontend/review.html`
**Pending:**
- A4 No-match memory per observation (sessionStorage)
- A5 Results-per-page selector
- A6 First/Last pagination buttons
- A7 Server-side sort order selector
- A8 Sticky reject toolbar in select mode
- iNaturalist token expired — refresh + paste in API Dashboard
- Live browser verification of A3 blocked by sandbox venv permission issue

### 2026-05-31 16:06
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260531_160638.sqlite`

### 2026-05-31 16:06
**Session ended** — Session ended from Settings page

### 2026-05-31 16:05
**API Dashboard + Health Scan + A1 iNat fixes + A2 select-mode toggle**

**Built:**
- GET /api/settings/api-meta — instant registry metadata, no probing
- GET /api/settings/api-status — concurrent live probe of all 7 APIs
- GET /api/settings/api-status/{api_id} — single API probe with timing (ms)
- POST /api/settings/api-key — safe .env upsert + live config update (DB for Drive)
- API Dashboard section in settings.html: standardised cards, status dots, paste-box, how-to popout
- API Health Scan button: fires per-API requests concurrently, patches each card as it resolves (real-time streaming UI pattern)
- Summary banner: X of N healthy · N expired · N not_configured
- Silent auto-scan on Settings page load
- Per-card Test button for individual re-tests
- iNaturalist card: JWT expiry decode, expiring-soon warning (<4h), direct token page link
- State vocabulary: live / expired / invalid / unreachable / not_configured + dot colours
- A1 Fix 1: kingdom gate threshold 5.0 → 0.05 (post-normalisation scale)
- A1 Fix 2: top_score normalisation guard on write; corrected 14 stray legacy rows
- A1 Fix 3: dual_source_agreement = 1 only on genuine cross-source name+threshold agreement
- A1 Fix 4: iNat logging (401/429/timeout/no-token) + rate-limit semaphore + 1.0s delay
- A1 Fix 5: single-source auto-approve at PlantNet >= 0.92, flagged in reviewer_notes
- api_source_syncthing default changed from plantnet to both
- A2: Select mode checkbox replaced with distinct toggle button (aria-pressed, pressed=dark green)
**Fixed:**
- iNat kingdom gate was comparing normalised 0-1 score against raw 5.0 threshold — dead code
- top_score had 14 rows with 0-100 range values; corrected + write guard added
- dual_source_agreement was set on merely-both-returned, not genuine agreement
- iNat silent failures (401/429/timeout) now logged with actionable hints
**Files:** `app/services/api_dashboard.py`, `app/services/identification.py`, `app/services/settings_service.py`, `app/integrations/inaturalist.py`, `app/api/settings.py`, `frontend/settings.html`, `frontend/review.html`
**Pending:**
- iNaturalist token is expired — user must refresh at inaturalist.org/users/api_token and paste in API Dashboard
- Google Drive token not configured
- A3: Select no-GPS toggle button in review queue
- A4: No-match memory per observation (sessionStorage)
- A5: Results-per-page selector
- A6: First/Last pagination buttons
- A7: Server-side sort order selector
- A8: Sticky reject toolbar in select mode

### 2026-05-31 10:52
**Phase 10.7 Part 2 — /lists page (Species List) with two print modes and select-mode reach-back from map & species**

**Built:**
- New /lists route + page: filter summary, empty state, species cards (edibility/season/recipe/photo), tap-to-expand, reach-back buttons, bottom toolbar (mode toggle, photo toggle, clear, print); auto-populates from URL filters when empty
- Lists nav link added after Species on all pages; hidden in guest mode (/lists added to guest-mode.js BLOCKED)
- Shared lists.js helper (window.ForagingList) backed by localStorage key foragingid_current_list — selection, per-species photo choices, mode/showPhotos prefs
- Map select mode (/map?select=1): sticky green bar, tap pins to toggle species (green ring), X selected/Done returns to /lists; normal map behavior untouched
- Species select mode (/species?select=1): sticky bar, tap card to toggle, per-card photo strip (sorted by confidence, default highest) to choose the PDF photo; normal list/nav untouched
- Field Guide print mode: dense two-column, per species sci name/common/edibility/season strip/key recipe/brief foraging note
- Workshop print mode: one A4 per species, serif Pein aesthetic, photo, safety box (edibility + lookalike/prep warnings), full recipe (Markdown-lite), foraging notes, ruled My notes section, Melvin Jarman credit
- Live screen print-preview reflecting mode/photos/list; dedicated @media print stylesheet (A4, page breaks per workshop page, two-col field guide)
**Files:** `app/main.py`, `frontend/lists.html`, `frontend/static/js/lists.js`, `frontend/static/js/guest-mode.js`, `frontend/index.html`, `frontend/species.html`, `frontend/review.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`
**Pending:**
- Visual/print verification of /lists (Field Guide columns, Workshop A4 page breaks) blocked by sandbox venv preview issue — manual Cmd+P check recommended
- Deferred filter fixes from earlier session still pending: #22 (null-kingdom species default to Plant), #13 (Approved list query include manually_verified), #9 (Find edible-only onchange)

### 2026-05-31 06:17
**Filter audit across all app surfaces (read-only, no fixes)**

**Pending:**
- Audit found 28 filter controls: 21 working, 5 partial, 0 fully broken
- Partial #9: Find in-season edible-only checkbox has no onchange — toggling does not re-run
- Partial #13: Review queue Approved count includes manually_verified but list query excludes them (count/list mismatch)
- Partial #16: Review queue confidence sort is page-local only, not global
- Partial #22: Species type filter hides unenriched species (null kingdom + null edibility) from Plant/Fungi
- Cross-cutting: no filter-state persistence (in-memory only) except ?species= (map) and ?status= (review) deep-links
- Next: serialize map filterState to URL; fix #22, #13, #9 in that order

### 2026-05-31 05:57
**Fix View Changelog modal not opening**

**Fixed:**
- View Changelog button onclick was rendered with JSON.stringify(commit), whose double quotes collided with the double-quoted onclick attribute and produced a syntax-error handler; switched to single-quoted, _esc-wrapped commit so the handler is valid and the modal opens
**Files:** `frontend/settings.html`

### 2026-05-31 05:52
**Add View Changelog button + modal to each snapshot in Settings**

**Built:**
- GET /api/dev/snapshot-changelog?commit=<hash> — returns CHANGELOG.md from that snapshot commit via git show, with hash validation
- View Changelog button on each snapshot row (secondary outline style, subordinate to Restore)
- Scrollable changelog modal with close button, overlay-click and Escape to dismiss
**Files:** `app/api/dev.py`, `frontend/settings.html`

### 2026-05-31 05:37
**Two Settings fixes: collapsible snapshot list + End Session button completion state**

**Built:**
- Snapshot list collapsed by default showing only most recent, with Show all (N) / Show less toggle (toggleSnapshotList)
**Fixed:**
- End Session button no longer hangs on Saving… — on successful commit it switches to green ✓ Session saved and stops the spinner
- Status line clarifies that Push to GitHub is a separate wifi-dependent step
**Files:** `frontend/settings.html`
**Pending:**
- Live browser verification of Settings UI blocked by sandbox venv permission — manual check recommended

### 2026-05-30 23:41
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260530_234150.sqlite`

### 2026-05-30 23:41
**Session ended** — Session ended from Settings page

### 2026-05-30 23:37
**Scan page — Processing Sessions (additive session tracking for P1 and P2 pipelines)**

**Built:**
- scan_sessions DB table + Alembic migration (0008_add_scan_sessions)
- ScanSession SQLAlchemy model
- scan_sessions service: session_create, session_inc, session_close, sessions_list
- P1 (syncthing.py): session created at batch start, incremented per-file, closed at end
- P2 (scan.py): _p2_obs_session registry, _p2_tick / _p2_auto_close helpers
- P2 prefilter-rejected path: session_inc(processed+rejected) directly
- P2 identification callbacks: _p2_tick at all exit points (approved, review, rejected, failed)
- API endpoints: POST /api/scan/sessions, GET /api/scan/sessions, GET /api/scan/sessions/all
- scan.html: session selector dropdown (P1 + P2) with View All button
- scan.html: RECEIVED chip added to P1 session-stats row
- scan.html: P2 session-stats row (received, processed, approved, review, rejected, failed)
- scan.html: View All sessions modal with full history table
- scan.html: batch-collect-then-upload flow for accurate files_received count
- scan.html: _scheduleP2SessionRefresh debounce after each upload completes
**Fixed:**
- _row_to_dict in scan_sessions.py: handle SQLite string datetimes via _to_dt()
- _ssVal in scan.html: handle null values (show dash placeholder)
**Files:** `app/models/scan_session.py`, `app/services/scan_sessions.py`, `app/api/scan.py`, `app/api/syncthing.py`, `app/main.py`, `migrations/versions/0008_add_scan_sessions.py`, `frontend/scan.html`

### 2026-05-30 23:06
**Fix review queue confidence score display — iNat scores were 0–100 not 0–1**

**Fixed:**
- app/integrations/inaturalist.py: divide combined_score by 100.0 to normalise to 0.0–1.0 scale (iNat API returns 0–100)
- DB backfill: normalised 102 existing observations with iNat scores in 0–100 range
- frontend/review.html: changed Math.round(score*100) to (score*100).toFixed(1) for 1 decimal place display
**Files:** `app/integrations/inaturalist.py`, `frontend/review.html`

### 2026-05-30 22:58
**Phase 10.6 Prompt B — phenological bulk-populate from PFAF + culinary_info**

**Built:**
- scripts/populate_phenology.py — dry-run/live script extracting flower/fruit/leaf months from PFAF HTML sentences and peak_season from culinary_info.seasonal_peak
**Files:** `scripts/populate_phenology.py`

### 2026-05-30 22:41
**Snapshot** — End of session — Phase 10.6 complete — Conditional Edibility Schema (conditions + lookalikes + phenology), Edibility review tab, species card gating, Intent-Based Find tab (4 modes), and full audit (48/48 checks passed)
DB: `snapshots/db_20260530_224132.sqlite`

### 2026-05-30 22:41
**Session ended** — Phase 10.6 complete — Conditional Edibility Schema (conditions + lookalikes + phenology), Edibility review tab, species card gating, Intent-Based Find tab (4 modes), and full audit (48/48 checks passed)

### 2026-05-30 22:41
**Phase 10.6 Section 7 — Audit & Verification: all 48 checks pass**

**Fixed:**
- Section 7 audit: identified test script used wrong species (id=5, no confirmed obs) — fixed to use id=186 (Thymus pulegioides, 11 confirmed obs)
- Section 7 audit: identified test used wrong param radius_km (should be radius_m) — fixed
- Section 7 audit: identified test used wrong culinary endpoint path — fixed to /api/species/{name}/profile
- Full 48-check audit pass: schema, CRUD round-trip, phenology, Find modes 1-3, nearby backward-compat, species card profile

### 2026-05-30 22:26
**Phase 10.6 Section 6: intent-based Find tab with 4 search modes**

**Built:**
- GET /api/find/in-season — all confirmed species in season (phenology + photo proxy fallback)
- GET /api/find/recipes — recipe search by ingredient free-text
- GET /api/find/medicinal — medicinal prep search by symptom/use
- Find layer button in map toolbar
- find-view div in sidebar with 4 mode buttons
- Mode 1: In season now (auto-runs, edible-only filter)
- Mode 2: What can I make? (ingredient search, grouped by species)
- Mode 3: Medicinal use (symptom/use search)
- Mode 4: Near me + in season (GPS + /api/nearby + in_season filter)
- _exitFindView() wired into all mode transitions
- setLayer find case in override
**Fixed:**
- r.thumbnail KeyError — fixed to sp[thumbnail]
**Files:** `app/api/find.py`, `app/main.py`, `frontend/index.html`
**Pending:**
- Section 7: audit checks

### 2026-05-30 22:07
**Phase 10.6 Section 5: phenological schema — model, migration, service, nearby update**

**Built:**
- flower_months / fruit_months / leaf_months / peak_season columns on species table
- Alembic migration 0007_add_phenological_fields
- app/services/phenology.py — species_in_season(), active_months_display(), parse_months()
- nearby.py updated to carry phenological fields and use species_in_season() with fallback
- species profile API includes phenology block
- PATCH /api/edibility/phenology/{species_id} — curator endpoint
**Files:** `app/models/species.py`, `migrations/versions/0007_add_phenological_fields.py`, `app/services/phenology.py`, `app/api/nearby.py`, `app/api/culinary.py`, `app/api/edibility.py`
**Pending:**
- Section 6: Find tab intent search
- Section 7: audit

### 2026-05-30 22:02
**Phase 10.6 Section 4: species card edibility gating update**

**Built:**
- loadEdibilitySummary() — async post-render fetch of /api/edibility/summary/{id}
- _renderEdibilitySummary() — updates prof-pills and safety-content in place
- _buildConditionalPillHtml() — per-part conditional badges replacing flat edible pill
- _buildStructuredLookalikeHtml() — structured lookalike warning block in Safety section
- edib-pending-note for edible/caution species with no conditions set
- condition_count + lookalike_count added to /api/species/ list response
- Species grid card: conditional chip replaces flat edible badge when conditions exist
**Files:** `frontend/species.html`, `app/api/culinary.py`
**Pending:**
- Section 5: phenological schema
- Section 6: Find tab
- Section 7: audit

### 2026-05-30 21:39
**Phase 10.6 Sections 1-3: schema audit, conditional edibility tables, edibility review tab**

**Built:**
- SpeciesEdibilityCondition model (species_edibility_conditions table)
- SpeciesLookalike model (species_lookalikes table)
- Alembic migration 0006_conditional_edibility_schema
- GET/POST/DELETE /api/edibility/conditions endpoints
- GET/POST/DELETE /api/edibility/lookalikes endpoints
- GET /api/edibility/species curation list
- GET /api/edibility/summary/{species_id} card gating endpoint
- Edibility tab in /review with inline condition+lookalike curation forms
**Files:** `app/models/species.py`, `app/models/__init__.py`, `app/api/edibility.py`, `app/main.py`, `migrations/versions/0006_conditional_edibility_schema.py`, `frontend/review.html`
**Pending:**
- Section 4: species card edibility gating
- Section 5: phenological schema
- Section 6: Find tab intent search
- Section 7: audit

### 2026-05-30 19:00
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260530_190021.sqlite`

### 2026-05-30 19:00
**Session ended** — Session ended from Settings page

### 2026-05-30 18:57
**Fix 1: iNaturalist kingdom gate; Fix 2: prefilter threshold direction label**

**Built:**
- Kingdom gate in identification pipeline: auto-reject non-Plantae/Fungi iNat top result ≥5% confidence
- Store iconic_taxon_name (kingdom) in iNat candidate dict for future audits
- POST /api/trust/kingdom-audit: retroactive scan with live iNat taxa lookup, dry-run and apply modes
- Retroactive audit applied: 9 obs sent to review (5×Canis familiaris, capercaillie, rabbit, wolf, red deer)
**Fixed:**
- prefilter_pipeline2_green_threshold description now explicitly states Higher values require more green
- scan.html pf-threshold-note now shows higher = stricter inline
**Files:** `app/services/identification.py`, `app/api/trust.py`, `app/services/settings_service.py`, `frontend/scan.html`

### 2026-05-30 18:45
**Phase 10.5 Data Trust — complete: frontend JS for 3-tab layout and full Trust tab**

**Built:**
- switchTab() with localStorage persistence and lazy Trust tab init
- trustCollapse() for all four Trust card sections
- Section A: loadTrustStats, _renderTrustChips, _renderTrustDist, _renderTrustTop10
- trSendSpeciesToReview() from top-10 table using /api/audit/send-to-review
- Section B: trLoadReview, _renderTrList, _renderTrPager, trSendToReview, trExpandRouting
- Section C Tool 1: bcBandChange, bcPreview, bcConfirm with dry-run preview
- Section C Tool 2: brPreview, brConfirm, _brFillDatalist from /api/species/
- Section D: runAllAudit (toggleAllChecks + runAudit), lazy initAuditChecks
- All write actions behind window.confirm()
**Fixed:**
- Removed eager initAuditChecks() page-load call; now lazy on Trust tab open
**Files:** `frontend/scan.html`

### 2026-05-30 17:23
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260530_172343.sqlite`

### 2026-05-30 17:23
**Session ended** — Session ended from Settings page

### 2026-05-30 17:09
**Build walk proximity alerts (10a.5)**

**Built:**
- Walk proximity alert system (_startProxWatch, _stopProxWatch, _onProxPosition, _fireProxAlert, _dismissProxAlert, _renderProxPanel)
- In-app notification panel (#walk-prox-panel) — max 3 stacked, oldest auto-dismissed
- 5-minute cooldown per pin (keyed by obs_id or stop index)
- Bounding-box pre-filter on walk stops before haversine check
- Goethean prompt placeholder (structural only, Phase 11c)
- Field mode section in Settings — on/off toggle + 10/20/30/50m threshold selector
- Both field mode settings persist in localStorage (foragingid_field_mode, foragingid_prox_threshold)
- GPS.startWatch wired at _activeWalkRoute assignment (fresh build + saved walk load)
- GPS.stopWatch wired in _exitWalkMode
**Files:** `frontend/index.html`, `frontend/settings.html`

### 2026-05-30 13:08
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260530_130818.sqlite`

### 2026-05-30 13:08
**Session ended** — Session ended from Settings page

### 2026-05-30 13:05
**Regression fix: review tile selection in select mode**

**Fixed:**
- Added card-level onclick to obs-card div — clicks anywhere on the tile surface toggle selection in select mode
- Exclusion list prevents double-fire: img (has own handler), button, input, textarea, a, .sop-panel, .corr-lookup-results, .rename-row
**Files:** `frontend/review.html`
**Pending:**
- Pipeline 2 Fix 3: prefilter threshold direction pending user decision
- Server restart required to register GET /api/syncthing/rejected route

### 2026-05-30 12:59
**Pipeline 2 Fix 5: Prefilter threshold note in Pipeline 2 panel**

**Built:**
- pf-threshold-note div in Pipeline 2 panel body (between source selector and drop zone)
- loadPrefilterThreshold() fetches /api/settings and renders green threshold % with (custom)/(default) tag and link to Settings
- Called at page init alongside loadUploadStats()
**Files:** `frontend/scan.html`
**Pending:**
- Pipeline 2 Fix 3: prefilter threshold direction pending user decision
- Server restart required to register GET /api/syncthing/rejected route

### 2026-05-30 12:53
**Pipeline 2 Fix 4: toggleSelectMode race condition in review.html**

**Fixed:**
- toggleSelectMode now re-renders synchronously from cached _reviewObs instead of firing async fetch — eliminates race where btn-select-nomatch was clickable before checkboxes existed in DOM
**Files:** `frontend/review.html`
**Pending:**
- Pipeline 2 Fix 3: prefilter threshold direction pending user decision
- Pipeline 2 Fix 5: prefilter threshold note in Pipeline 2 panel

### 2026-05-30 12:43
**Pipeline 2 Fix 2: Scan session summary persisted in sessionStorage**

**Built:**
- scan-session-banner HTML element above uq-toolbar
- CSS for banner and dismiss button
- _initScanSession / _updateScanSession / _clearScanSession / _restoreScanSession / _renderScanBanner JS functions
- Folder button clears session and sets folder name via _initScanSession
- _updateScanSession called at all 8 terminal branches of _uploadFile (queued + 7 outcomes)
- Banner restored on page load via _restoreScanSession
**Files:** `frontend/scan.html`
**Pending:**
- Pipeline 2 Fix 3: prefilter threshold direction pending user decision
- Pipeline 2 Fix 4: toggleSelectMode race condition in review.html
- Pipeline 2 Fix 5: prefilter threshold note in Pipeline 2 panel

### 2026-05-30 12:32
**Pipeline 2 Fix 1: Batch reject in upload queue**

**Built:**
- Batch select toolbar above upload queue (hidden until first card added)
- Select toggle button enters/exits select mode
- Click-to-select on upload cards (skips links/buttons)
- Reject selected button calls POST /api/audit/reject for each selected obs
- Cards animate out after rejection; toolbar hides when queue empties
**Files:** `frontend/scan.html`
**Pending:**
- Pipeline 2 Fix 2: sessionStorage persistence for folder scan summary
- Pipeline 2 Fix 3: prefilter threshold decision pending user input
- Pipeline 2 Fix 4: toggleSelectMode race condition in review.html
- Pipeline 2 Fix 5: prefilter threshold note in Pipeline 2 panel

### 2026-05-30 12:18
**Three map UI fixes: pin legend visibility, sightings label, Near me placeholder**

**Built:**
- Fix 1: pin legend hides on heatmap/clusters, shows on pins/walk — one display toggle in _applyLayer()
- Fix 2: stat bar Visible → In view with tooltip explaining viewport+filter semantics
- Fix 3: 10a.4 Near me placeholder comment in sidebar view-switching with filter-notice HTML spec and _countActiveFilters hook
**Files:** `frontend/index.html`

### 2026-05-30 12:03
**Heatmap zoom sync — live opacity pulse + debounced recalibration on mobile pinch-zoom**

**Built:**
- _heatZoomFeedback(): zoom listener — pulses canvas opacity to 65% of brightness setting for immediate visual feedback; debounces _recalcHeatMax at most once per 300ms
- _heatZoomEnd(): zoomend handler — cancels pending debounce, restores opacity, runs authoritative _recalcHeatMax
- Replaced map.on(zoomend, _recalcHeatMax) with map.on(zoom, _heatZoomFeedback) + map.on(zoomend, _heatZoomEnd)
**Files:** `frontend/index.html`

### 2026-05-30 08:05
**Pipeline 1 rejection log — expandable table on Rejected stat click with send-to-review**

**Built:**
- GET /api/syncthing/rejected endpoint — lists review_status=rejected syncthing obs with filename/date/reason/sendable
- Rejected stat chip made clickable (toggleRejectionLog), amber open-state highlight
- Expandable rejection-log table: date / filename / reason / checkbox per row
- Select all / deselect toggle in table header
- Send selected to review button — calls /api/audit/send-to-review per obs, refreshes log + stat chip
- Rejection log CSS: amber-toned, scrollable 360px max, sticky headers, hover rows
**Files:** `app/api/syncthing.py`, `frontend/scan.html`
**Pending:**
- Server restart required to register /api/syncthing/rejected route

### 2026-05-30 07:47
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260530_074717.sqlite`

### 2026-05-30 07:47
**Session ended** — Session ended from Settings page

### 2026-05-30 07:35
**include-related-images in Second Opinion — on-demand toggle, per-candidate photo strips, quota display, settings note**

**Built:**
- PlantNetCandidate.images field (list[dict] with url/organ/author, default empty)
- identify_image() include_related_images param (False by default — batch pipelines unaffected)
- _parse_response() extracts images array from PlantNet response (url.m preferred, falls back to s/o)
- /second-opinion endpoint include_related_images query param passed through to PlantNet
- _add_img() carries reference_images through merge dict (PlantNet images kept if iNat also matches)
- remaining_quota extracted from remainingIdentificationRequests in raw PlantNet response
- reference_images and remaining_quota included in /second-opinion JSON response
- _sopRefImages Map for per-card toggle state (reset on panel close)
- _sopFetch appends &include_related_images=true when toggle is on
- _sopToggleRefImages() panel-level toggle — re-fires API call, preserves organ selection
- _sopToggleRowPhotos() per-row expand/collapse, stopPropagation so select still works
- _renderSOPResults wrapped in .sop-card, per-candidate .sop-img-section when images present
- Reference photo footer: active-state toggle button + quota counter after each call
- CSS: .sop-card, .sop-img-section, .sop-img-toggle-link, .sop-img-strip, .sop-ref-img, .sop-ref-footer, .sop-ref-toggle-btn, .sop-quota
- Settings quota note injected into Identification group after render
**Fixed:**
- Batch pipelines (scan.py, identification.py) confirmed unaffected — no include_related_images param
**Files:** `app/integrations/plantnet.py`, `app/api/reidentify.py`, `frontend/review.html`, `frontend/settings.html`

### 2026-05-30 07:17
**Add organ type selector to Second Opinion panel + lat/lng to PlantNet calls (investigation + implementation)**

**Built:**
- Organ type selector (auto/leaf/flower/fruit/bark/habit) pill row in Second Opinion panel
- Per-card organ selection persists via JS Map while card is in DOM
- Switching organ chip re-fires the API call automatically
- organ query param added to /second-opinion endpoint
- organ field added to ReidentifyRequest model for /reidentify endpoint
- PLANTNET_ORGANS frozenset for safe input sanitisation on both endpoints
- Results sub-div sop-results-{id} keeps organ selector visible while results load
**Files:** `app/api/reidentify.py`, `frontend/review.html`

### 2026-05-30 07:07
**PlantNet lat/lng + Web Share API Google Lens bridge**

**Built:**
- PlantNet lat/lng: identify_image() in plantnet.py now accepts lat/lng params and passes them to the API as query params — narrows results to species recorded in that geographic area
- All 4 call sites updated: identification.py (upload pipeline), scan.py (syncthing pipeline), reidentify.py (manual re-ID, two paths) — all pass obs.latitude/obs.longitude
- Web Share API bridge: 📤 share button overlaid top-right on each review card thumbnail (thumb-wrap + btn-share-photo CSS)
- shareCardPhoto() function: tries file share (navigator.canShare files — Android PWA native share sheet → Google Lens), falls back to URL share, then clipboard copy with toast
- Correction helper text updated to reference the 📤 button as the Lens bridge; keeps desktop Lens link as secondary option
**Files:** `app/integrations/plantnet.py`, `app/services/identification.py`, `app/api/scan.py`, `app/api/reidentify.py`, `frontend/review.html`

### 2026-05-30 07:01
**Settings page audit — 10 fixes applied**

**Built:**
- Fix 1: enrichment.py + recipes.py read get_setting(anthropic_model); model choices updated to haiku-4-5/sonnet-4-6(default)/opus-4-7; stale DB override migrated; Haiku warning label in settings UI
- Fix 2: Already wired (verified both pipelines call get_setting for api_source); no change needed
- Fix 3: Single-source auto-approve removed from scan.py + identification.py; auto_approve_threshold removed from registry; upload_auto_approve_threshold now governs all dual-agree checks; doc comment added
- Fix 4: wikidata_delay_s applied in enrich_species non-cached (individual) path
- Fix 5: scan.py, syncthing.py, ingest.py all read get_setting(thumbnail_size/batch_size) instead of settings.*
- Fix 6: Caffeinate bar removed from scan.html top; moved to Settings Snapshots section as System subsection with identical JS behaviour
- Fix 7: _gdrive_status dict in dev.py tracks last_sync_at + last_error; GET /api/dev/gdrive-status endpoint; settings.html GDrive header shows last-synced timestamp and amber warning on failure
- Fix 8: loadLanUrl() always re-detects on call; 🔄 refresh button added next to LAN URL field
- Fix 9: prefilter_indoor_dark_threshold + prefilter_indoor_bright_threshold added to settings registry; prefilter.py reads them via get_setting with fallback to constants
- Fix 10: Standalone Save snapshot button removed from Snapshots & Session section; underlying function intact
**Fixed:**
- Stale DB override claude-sonnet-4-5-20251001 migrated to claude-sonnet-4-6
- Single-source Syncthing auto-approve path eliminated
- Stale auto_approve_threshold registry entry and LOW_CONFIDENCE_THRESHOLD import removed
**Files:** `app/services/enrichment.py`, `app/api/recipes.py`, `app/config.py`, `app/services/settings_service.py`, `app/api/scan.py`, `app/services/identification.py`, `app/api/syncthing.py`, `app/api/ingest.py`, `app/api/dev.py`, `app/services/prefilter.py`, `frontend/settings.html`, `frontend/scan.html`

### 2026-05-30 01:48
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260530_014829.sqlite`

### 2026-05-30 01:48
**Session ended** — Session ended from Settings page

### 2026-05-30 01:46
**Complete scan page fixes 3–9**

**Built:**
- Fix 3: Prefilter rejects recoverable — save file+record, Override button on rejection card, Prefilter Rejects collapsible list in Pipeline 2 panel
- Fix 4: SHA256 dedup message updated to "Already in archive — skipped"
- Fix 5: Slider clarification text (new IDs only), re-check description, audit summary shows actionable findings prominently with info count subdued
- Fix 6: Removed all hardcoded ≥80% comment references in scan.py and syncthing.py; added pipeline asymmetry comment block; user-facing reason string uses dynamic threshold
- Fix 7: iNaturalist token status indicator (green/amber/red badge) in Pipeline 2 header; checks token via /v1/users/me on page load; shows login name when valid
- Fix 8: Server-side Syncthing auto-scan loop (60s tick) via asyncio background task started in lifespan; last_auto_scan field in status; Last auto-scan indicator in Pipeline 1 panel
- Fix 9: Lenient prefilter for Pipeline 1 — rejects screenshot/ui_blank/person_animal only; rejects saved as not_plant and recoverable; prefilter-rejects endpoint now includes syncthing source; 4/387 existing obs would have been caught (all person_animal)
**Fixed:**
- Fix 3 backend was already done — completed frontend: override button on rejection card, prefilter rejects list section, overridePrefilterCard/overridePrefilterItem/loadPrefilterRejects JS functions
- Pipeline 2 description no longer says "never saved to disk"
- scan.py: httpx import added for inat token ping endpoint
**Files:** `frontend/scan.html`, `app/api/scan.py`, `app/api/syncthing.py`, `app/main.py`

### 2026-05-30 00:42
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260530_004225.sqlite`

### 2026-05-30 00:42
**Session ended** — Session ended from Settings page

### 2026-05-30 00:27
**Audit renamed observations after UI consolidation — found and fixed 2 data issues**

**Fixed:**
- #8356 Epilobium tetragonum: species_primary was NULL despite the 10:17 rename — suspicious_correction audit demoted it and something cleared the name (no log trail). Restored to Epilobium tetragonum via system:name_restore edit, stays needs_review for user to re-confirm
- #9477 Sisymbrium orientale: trailing colon typo removed — Sisymbrium orientale: → Sisymbrium orientale, logged via system:typo_fix
- Correction box pre-fill already safe: uses obs.species_primary (truthy check) before falling back to AI candidate — NULL name on #8356 would have shown wrong AI name, now avoided by restore
**Files:** `data/foragingid.db`
**Pending:**
- Fix 5: enrichment skipping 27 + re-enrich skipped button

### 2026-05-30 00:20
**Re-evaluate Fix 2 + Fix 3 after reprocess and UI consolidation**

**Fixed:**
- Hoisted candidates parse above both species block and correction box so it is available to both
- Correction box now pre-fills from candidates[0].scientific_name when species_primary is null — 49 obs with AI suggestion but no confirmed name now show the suggestion pre-filled, so reviewer can Save in one click
**Files:** `frontend/review.html`
**Pending:**
- Fix 5: enrichment skipping 27 + re-enrich skipped button

### 2026-05-30 00:15
**Consolidate review card ID tools — remove ReID panel, merge manual entry into correction box**

**Built:**
- _corrLookup — queries GBIF+iNaturalist by name, shows validated candidates inline
- _corrSaveFromLookup — clicking a lookup result auto-confirms via confirm-species + enrich + badge update
- Google Lens link embedded in correction box helper text
- Species identification box now shown on ALL non-landscape cards (was only shown when obs already had an ID)
**Fixed:**
- Removed <details class=reid-details> block (Identify/Re-identify accordion) from review cards
- Removed reidentify.js script tag from review.html (still loaded on map/index.html)
- Removed _reidOnConfirmed callback (no longer called by anything)
- Removed reidDetail references and ReID.updateCategory call from category-change handler
**Files:** `frontend/review.html`
**Pending:**
- Fix 2: proposed name + confidence missing from review cards
- Fix 3: species name missing from review cards
- Fix 5: enrichment skipping 27 + re-enrich skipped button

### 2026-05-30 00:09
**Align manual species correction with second-opinion enrichment flow**

**Fixed:**
- saveCorrection now fires POST /api/culinary/{name}/enrich after saving — same as second-opinion path
- Triggers re_enrich=True fill_empty_only=True PFAF+Wikidata refetch for missing common names
**Files:** `frontend/review.html`
**Pending:**
- Fix 2: proposed name + confidence
- Fix 3: species name on review cards
- Fix 5: enrichment re-enrich skipped

### 2026-05-29 23:33
**Verify iNaturalist token now set and working, fix auto-enrich logger NameError**

**Fixed:**
- iNaturalist token verified: authenticates as melvin56342, Urtica dioica lookup returns taxon id=51884 (149135 research-grade obs)
- Server restarted to pick up token from .env — dual-agree path now active
- Ran reprocess with iNat live: db_failed_id 8→3 (3 truly unreadable photos remain)
- Fixed NameError: name log not defined in _enrich_new_species_card — added import logging + log = logging.getLogger(__name__) to scan.py imports
**Files:** `app/api/scan.py`
**Pending:**
- Fix 2: proposed name + confidence missing from review cards
- Fix 3: species name missing from review cards
- Fix 5: enrichment skipping 27 + re-enrich skipped button

### 2026-05-29 23:28
**Reprocess Pipeline 1 IDs, add confirmed-species chip, fix 387 math, lower auto-approve threshold to 70%**

**Built:**
- POST /api/syncthing/reprocess — batch re-identification endpoint (added previous session)
- db_rejected + db_confirmed_species + db_pending_review added to /api/syncthing/status
- Pipeline 1 panel: Rejected chip + Confirmed species chip so 387 math reconciles (113+197+77=387)
- upload_auto_approve_threshold lowered 0.80→0.70 via settings API (persists in DB/cache, no restart needed)
- Panel description updated to reflect ≥70% threshold
**Fixed:**
- _gs UnboundLocalError fix (hoisted import) — was silently failing ID on 150+ syncthing photos
- Reprocessed 152 failed-ID observations; 25 auto-approved, 127 to review, 0 crashes, only 8 still failed
- db_confirmed_species now = 76 (was effectively 0 visible); db_failed_id dropped 155→8
**Files:** `app/api/syncthing.py`, `frontend/scan.html`
**Pending:**
- Fix 2: proposed name + confidence missing from review cards
- Fix 3: species name missing from review cards
- Fix 5: enrichment skipping 27 + re-enrich skipped button
- User must set INATURALIST_API_TOKEN in .env to unlock dual-agree auto-approvals

### 2026-05-29 22:57
**Snapshot** — Manual snapshot
DB: `snapshots/db_20260529_225743.sqlite`

### 2026-05-29 22:48
**Prompt 10a.3b — two mobile UI fixes. Fix 1 resolved as policy decision (Stop=revoke) with no code change; Fix 2 fixed map toolbar controls overflowing off the left edge on narrow phones (~390px).**

**Fixed:**
- Map toolbar no longer clips off-screen at <=480px: added a @media (max-width:480px) block that anchors #map-toolbar with left:8px/right:52px/transform:none (clearing the topright zoom+locate controls), wraps #layer-toggle buttons, drops #map-search-wrap to its own full-width line, and shrinks #toolbar-row-2 button padding/font
- Corrected CSS cascade bug: relocated the new @media block to AFTER the base #map-toolbar rules so it wins on equal specificity (media queries add no specificity)
- ngrok link rotation: resolved as Stop=revoke policy (ngrok free tier pins one static domain, so rotation is impossible); no refresh button added
**Files:** `frontend/index.html`
**Pending:**
- Sheffield: retest PWA install prompt + standalone mode on Pixel over secure context (deferred from 10a.3 due to router client isolation)
- Session B: prompts 10a.4-10a.6 (Near me / in season, reads window.foragingUser)
- Session C: prompts 10a.7-10a.9 (offline tile + species caching in sw.js)

### 2026-05-29 22:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260529_220908.sqlite`

### 2026-05-29 22:09
**Session ended** — Session ended from Settings page

### 2026-05-29 21:47
**Prompt 10a.3 — PWA install verification (verification-only; PARTIAL PASS)**

**Fixed:**
- Rebound dev server 127.0.0.1 -> 0.0.0.0 so the LAN IP (192.168.1.142:8000) is actually reachable; manifest + /sw.js confirmed served over the LAN IP
**Pending:**
- PWA install prompt + standalone-mode test on Pixel DEFERRED — router AP/client isolation blocks direct LAN connection; will retest in Sheffield
- When retesting: plain http://LAN-IP is NOT a secure context on Android, so SW + beforeinstallprompt will not fire. Use Chrome flag chrome://flags/#unsafely-treat-insecure-origin-as-secure (full owner app) OR ngrok HTTPS (note: ngrok host = guest/read-only mode)
- macOS firewall must allow Python incoming connections for LAN access

### 2026-05-29 20:01
**Prompt 10a.2 — GPS locate button on the map**

**Built:**
- Custom Leaflet locate control (top-right, under zoom; leaflet-bar styled; inline crosshair SVG, no new dependency)
- locateMe(): getCurrentPosition -> setView zoom 16 + pulsing blue you-are-here divIcon marker (white-bordered #1a73e8 core + @keyframes fid-locate-pulse halo); persists; re-click refreshes via setLatLng
- window.foragingUser = {lat,lng,timestamp} set on success (for prompt 10a.4 near-me)
- Location unavailable toast on denied/error (matches #geo-toast pattern, 3s auto-hide, no unhandled throw)
- Button locating-spin + active(blue) states
**Files:** `frontend/index.html`
**Pending:**
- 10a.3 (remaining Session A item)
- Session B: 10a.4-10a.6 Near me / in season

### 2026-05-29 19:57
**Prompt 10a.1 — PWA shell: installable manifest, icons, service worker, install prompt**

**Built:**
- manifest.json (standalone, theme #2d5a1b, 192+512 maskable icons)
- Placeholder PWA icons (green field + white leaf, PIL-generated)
- Service worker sw.js: app-shell precache, network-first /api/*, cache-first /static/*, navigations network-first->cached /, no tile/species caching yet
- pwa.js: SW registration at root scope + beforeinstallprompt Install-app button
- GET /sw.js root-scope route (application/javascript, Service-Worker-Allowed: /, no-store)
- PWA head tags (manifest/theme-color/apple-touch-icon) + pwa.js include on all 7 frontend pages
**Files:** `frontend/static/manifest.json`, `frontend/static/icons/icon-192.png`, `frontend/static/icons/icon-512.png`, `frontend/static/sw.js`, `frontend/static/js/pwa.js`, `app/main.py`, `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/scan.html`, `frontend/settings.html`, `frontend/about.html`, `frontend/landing.html`
**Pending:**
- 10a.2 GPS locate button
- 10a.3 you-are-here marker

### 2026-05-29 19:35
**Snapshot** — End of session — Final phase 9 fix: resolved Pipeline 1 (Syncthing Import) hang. _find_new_files() now excludes content-duplicates by sha256 (not just exact file_path). Syncthing re-imports under suffixed names (foo (1).jpg) were reported new forever, skipped silently as hash-dupes by _ingest_file, causing the frontend to auto-retrigger /process endlessly with no visible status. new_count corrected from 26 phantom files to 0; /process now returns nothing_to_do.
DB: `snapshots/db_20260529_193547.sqlite`

### 2026-05-29 19:35
**Session ended** — Final phase 9 fix: resolved Pipeline 1 (Syncthing Import) hang. _find_new_files() now excludes content-duplicates by sha256 (not just exact file_path). Syncthing re-imports under suffixed names (foo (1).jpg) were reported new forever, skipped silently as hash-dupes by _ingest_file, causing the frontend to auto-retrigger /process endlessly with no visible status. new_count corrected from 26 phantom files to 0; /process now returns nothing_to_do.

### 2026-05-29 19:33
**Fixed Pipeline 1 (Syncthing Import) hang on Process button**

**Fixed:**
- Pipeline 1 no longer hangs on Starting… — _find_new_files() now excludes content-duplicates by sha256, not just exact file_path. Syncthing re-imports under suffixed names (e.g. foo (1).jpg) were reported as new forever, skipped silently by _ingest_file as hash-dupes, and caused the frontend to auto-retrigger /process endlessly with no visible status. new_count now reflects reality (26 phantom files → 0).
**Files:** `app/api/syncthing.py`

### 2026-05-29 19:18
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260529_191821.sqlite`

### 2026-05-29 19:18
**Session ended** — Session ended from Settings page

### 2026-05-29 19:17
**Snapshot** — Manual save from Settings
DB: `snapshots/db_20260529_191728.sqlite`

### 2026-05-29 19:06
**New About page feature: editable Mac admin page + guest landing page, backed by an about_content table and /api/about endpoints**

**Built:**
- about_content single-row table (id=1) with full_description + snappy_summary, Alembic migration 0004 seeding the copy via INSERT OR IGNORE
- GET /api/about resolves [SPECIES_COUNT]/[OBSERVATION_COUNT] to live counts (distinct confirmed species + approved observations)
- PUT /api/about (owner-only) and POST /api/about/regenerate-summary (owner-only, Claude Sonnet)
- frontend/about.html admin page: editable full-description (auto-expand min 400px) + Save; guest-summary textarea with Save + Regenerate-with-Claude (loading state)
- About nav link added (last, after Settings) on all pages; hidden from guests via guest-mode.js
- frontend/landing.html guest landing page (welcome + toggleable read-only Learn-more view), responsive, no nav/admin
- Guest middleware serves landing.html for bare guest '/'; deep links (/?species=) and /map still serve the map; /map route alias added
**Fixed:**
- Deduplicated the triple '## Current State' header in CHANGELOG.md
- Regenerate model corrected from the spec's claude-sonnet-4-20250514 (404 not_found on this account) to claude-sonnet-4-6
**Files:** `app/models/about.py`, `app/models/__init__.py`, `migrations/versions/0004_add_about_content.py`, `app/api/about.py`, `app/main.py`, `frontend/about.html`, `frontend/landing.html`, `frontend/static/js/guest-mode.js`, `frontend/index.html`, `frontend/review.html`, `frontend/species.html`, `frontend/scan.html`, `frontend/settings.html`, `CHANGELOG.md`
**Pending:**
- Visual/browser confirmation of about.html + landing.html (preview sandbox cannot launch the venv server; verified via HTTP + JS parse instead)
- Decision: placeholder staleness — full-description placeholders bake into literal numbers on first Save (per spec); revisit if undesired
- Hardening pass (Alembic FK constraint + map bbox) still outstanding from prior session

### 2026-05-29 13:56
**Snapshot** — End of session — Completed three queued fixes plus follow-ups: (1) integrity-audit results rendering with breakdown/send/reject/batch; (2) investigated enrichment full-run (units mismatch, not a cap) and fixed query+overview metric; (3) species-card map thumbnail beside photos that opens the main map in Pins view filtered+centred on the species. Also fixed a latent corrupted Leaflet SRI hash that had blocked the species map entirely, and reworked the Database Overview to exclude rejected/filter-rejected records (Total 1200->539) with a new Pending column.
DB: `snapshots/db_20260529_135641.sqlite`

### 2026-05-29 13:56
**Session ended** — Completed three queued fixes plus follow-ups: (1) integrity-audit results rendering with breakdown/send/reject/batch; (2) investigated enrichment full-run (units mismatch, not a cap) and fixed query+overview metric; (3) species-card map thumbnail beside photos that opens the main map in Pins view filtered+centred on the species. Also fixed a latent corrupted Leaflet SRI hash that had blocked the species map entirely, and reworked the Database Overview to exclude rejected/filter-rejected records (Total 1200->539) with a new Pending column.

### 2026-05-29 13:39
**Database Overview now excludes rejected records entirely and adds a Pending column (A+B combined)**

**Built:**
- Added Pending column to Database Overview table (counts review_status=pending)
- Added transparency caption showing count of rejected/filtered records hidden from the overview
**Fixed:**
- db_summary now excludes ALL rejected records from every column and the Total: manual (review_status=rejected) AND filter-rejected (prefilter_category in no_plant_signal/person_animal), NULL-safe so legit un-prefiltered rows are kept. Total 1200 -> 539, 661 excluded
**Files:** `app/api/ingest.py`, `frontend/scan.html`
**Pending:**
- Fix 3 — species card map thumbnail

### 2026-05-29 13:29
**Fix 2 — enrichment full-run investigation: resolved the 1021-vs-96 confusion (units mismatch, not a broken batch) and removed a query filter that silently dropped confirmed species**

**Fixed:**
- Broadened enrichment query in enrichment.py: removed identification_status==identified requirement that dropped confirmed species with stale status (e.g. Epilobium tetragonum); eligible species 98 -> 99
- Fixed db_summary Not Enriched metric in ingest.py to count only confirmed observations (was counting rejected+pending+needs_review, producing the misleading 1021 figure)
- Backfilled species_id on 2 observations whose species_primary matched a species row by name but had NULL/mismatched FK
**Files:** `app/services/enrichment.py`, `app/api/ingest.py`, `data/foragingid.db`
**Pending:**
- Fix 3 — species card map thumbnail (Leaflet, click opens main map filtered+centred to species)

### 2026-05-29 13:20
**Hotfix: scan.html went blank (no data loading) due to JS syntax error in reject-button ternary**

**Fixed:**
- Reject-all batch buttons used an inline ternary inside string concatenation with a leading + on the ? and : lines, producing (obsLevel + ? ...) — a SyntaxError that broke the entire <script> block, so no page data loaded. Replaced with precomputed rejectBtn/rejectHdrBtn variables. Validated with JavaScriptCore new Function() parse check (PARSE OK). No data was lost — DB intact at data/foragingid.db (1200 observations).
**Files:** `frontend/scan.html`

### 2026-05-29 13:04
**Fix 1 addition: Reject-from-database action on audit results (single + batch)**

**Built:**
- POST /api/audit/reject endpoint — non-destructive reject (sets review_status=rejected, appends audit reason to notes), supports obs_id or species (rejects all live obs of a species)
- Per-row Reject button shown only on observation-level issues (those with an obs_id)
- Reject all batch button in both the breakdown panel and each category header for observation-level categories
- Reject confirms first; row/group removal and count/banner updates reuse the send-to-review delegation plumbing
**Files:** `app/api/audit.py`, `frontend/scan.html`

### 2026-05-29 12:47
**Fix 1 follow-up: working Send-to-review (row removal), detailed breakdown panel, per-category batch send**

**Built:**
- Breakdown-by-category panel above results: category, severity, count, and a Send all batch button per type
- Per-group Send all to review button (also in each category header)
- Single Send to review now removes the row, decrements category + breakdown counts, removes the group when emptied, and refreshes the top banner totals
**Fixed:**
- Root cause of dead Send to review button: JSON.stringify(issId) injected raw double-quotes into a double-quoted onclick attribute, breaking the handler. Replaced fragile inline onclick with event delegation on #audit-output keyed by data-idx/data-type
**Files:** `frontend/scan.html`

### 2026-05-29 12:38
**Fix 1: Integrity audit rendered no output — consolidated duplicate audit UIs and added missing table renderer**

**Built:**
- _renderAuditIssues(): grouped results-table renderer for audit issues (severity icon, item, issue+suggestion, View/Send-to-review actions)
**Fixed:**
- Removed duplicate standalone Data Integrity Audit section (#audit-section) which created duplicate #audit-summary/#audit-output IDs
- Removed dead runAudit(btn) function that was shadowed by the checkbox-based runAudit()
- Implemented the previously-undefined _renderAuditIssues() that runAudit() called — this ReferenceError was silently swallowed, leaving results blank
**Files:** `frontend/scan.html`

### 2026-05-29 10:09
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260529_100908.sqlite`

### 2026-05-29 10:09
**Session ended** — Session ended from Settings page

### 2026-05-29 10:08
**Add current_phase/next_steps inputs and Push to GitHub button to End Session UI**

**Built:**
- Two new text inputs in End Session form: current_phase and next_steps
- endSession() now sends current_phase and next_steps fields to /api/dev/end-session
- Push to GitHub button section with pushToGitHub() JS calling POST /api/dev/git-push
- Confirm dialogs for both actions; success/failure status spans inline
**Files:** `frontend/settings.html`
**Pending:**
- Obs #8367 (Boletus edulis) still needs_review — manual approval needed to appear on map
- Obs 8366 (Malus domestica) species_id is NULL — may need re-identify or manual link

### 2026-05-29 09:53
**Snapshot** — End of session — Session ended from Settings page
DB: `snapshots/db_20260529_095346.sqlite`

### 2026-05-29 09:53
**Session ended** — Session ended from Settings page

### 2026-05-29 09:48
**Auto-approve safety fix: require two-source agreement; audit and re-queue 56 single-source approvals**

**Fixed:**
- identify_observation: candidate lists built per-source (pn_candidates, inat_candidates) before merging — no more deduplication across sources
- Auto-approve now requires BOTH PlantNet AND iNaturalist to return same species >= threshold. Fungi always routed to review (Mushroom Observer has no image-scoring API).
- Audit: 152 approved non-human-corrected observations checked. 96 skipped (manually approved via review queue). 56 re-queued as needs_review with reviewer_notes=auto-approve re-review. All 56 were PlantNet-only candidates (iNat agreement unknown or absent under old dedup code).
**Files:** `app/services/identification.py`
**Pending:**
- Mushroom Observer image scoring not available — fungi auto-approve permanently disabled until a second image-scoring source is integrated

### 2026-05-29 09:42
**Rename cascade fix: handle_species_rename() in enrichment service, migration 0003 for species_recipes.notes, wired into rename_species_by_name, retroactive apply to Boletus edulis and Amanita muscaria**

**Built:**
- handle_species_rename() in app/services/enrichment.py — single function called by all rename paths
- Alembic migration 0003: species_recipes.notes column
**Fixed:**
- rename_species_by_name now calls handle_species_rename() on scientific-name change: resets all enrichment fields, clears timestamps, resets edibility_status=unknown, flags recipes needs_review, cancels pending AI drafts as stale, writes _rename_event audit
- Retroactive cascade applied to Boletus edulis (species 160): timestamps reset, drafts staled, audit written
- Retroactive cascade applied to Amanita muscaria (species 155): timestamps reset, drafts staled, audit written
**Files:** `app/api/culinary.py`, `app/services/enrichment.py`, `app/models/species.py`, `migrations/versions/0003_add_species_recipes_notes.py`

### 2026-05-29 09:25
**Fix approve flow: identification_status promoted to identified on approve; backfill 6 affected rows**

**Fixed:**
- Fix A: update_review endpoint in observations.py now sets identification_status=identified when approving/manually_verifying an observation that has a species_primary but identification_status != identified
- Fix B: backfilled 6 observations (8359, 8366, 8375, 8377, 8391, 8394) — all had review_status approved/manually_verified + valid species_primary but identification_status=failed_identification
**Files:** `app/api/observations.py`
**Pending:**
- obs 8366/8375/8377/8391/8394 have obs_category=plant but are fungi — separate fix if needed

### 2026-05-29 08:57
**Five fixes: category override routing, look-up box gating, PFAF artifact cleanup, approve-all restore, rename field fix**

**Fixed:**
- Fix 1: Verified — reidentify.js already reads panel.dataset.category at click time; updateCategory() sets it correctly; no code change needed
- Fix 2: Verified — #reid-manual-body-{id} already has style=display:none; no code change needed
- Fix 3: PFAF scraper _section_text() already skips bare <a> siblings and stops at References/More on regex; DB cleaned: 111 rows updated (41 nulled, 65 stripped, 5 unchanged legitimate)
- Fix 4: Verified — _renderAIDraftCard() renders Approve all button; approveAllDrafts() handler is present; no regression found
- Fix 5: DB — Amanita muscaria obs #8419 moved to needs_review with orphaned reviewer notes; Code — saveSpeciesRename in index.html line 2988 changed new_scientific_name to new_name to match RenameRequest Pydantic model
**Files:** `app/integrations/pfaf.py`, `data/foragingid.db`, `frontend/index.html`
**Pending:**
- Amanita muscaria obs #8419 queued for re-review — user must set identification_status=identified and re-approve to restore map pin

### 2026-05-29 08:41
**Scale note pins proportionally with zoom level**

**Built:**
- _noteIconSize(): returns zoom-proportional diameter — 4px at zoom ≤7, 16px at zoom ≥19, linear (zoom-3 clamped)
- _rescaleNotePins(): lightweight zoomend handler that calls marker.setIcon() in-place — no clearLayers, no renderMarkers side-effect
- renderNotes() now passes _noteIconSize() when creating markers so initial render matches current zoom
- map.on(zoomend, _rescaleNotePins) registered alongside existing _recalcHeatMax listener
**Files:** `frontend/index.html`

### 2026-05-29 08:12
**Note flow: crosshair + Select location button, not map-click placement**

**Fixed:**
- Restored #note-placing-confirm button with label Pan map to position crosshairs / Select location — user confirms placement via button not map click
- Removed map.on(click, _placeNotePinAtClick) from toggleNotePanel — map can now be panned freely during placement without accidentally triggering pin placement
- Removed matching map.off from _cancelNote (no listener registered)
- Updated bar instruction text to Pan map to position crosshairs
- Added touch-action:manipulation to confirm and cancel buttons for mobile
**Files:** `frontend/index.html`

### 2026-05-29 08:03
**Fix note location indicator always hidden in step-2 panel**

**Fixed:**
- _placeNotePin: locEl.style.display = empty-string replaced with display:block — empty string falls back to the CSS rule display:none so the location indicator was never visible after pin placement
- _cancelNote: added reset of note-placed-loc (textContent=empty, display=none) so stale location does not bleed through on subsequent note creation
- _submitNote: same reset of note-placed-loc after successful save
**Files:** `frontend/index.html`

### 2026-05-29 07:53
**Reverse note pin creation flow: place pin first, write note second**

**Fixed:**
- Moved #note-placing-bar from bottom:44px to top:86px so bar appears at top of map (below toolbar, matching walk-draw-banner pattern) rather than bottom
- Removed the extra Place here button (#note-placing-confirm) from the placing bar — pin is now placed exclusively by clicking/tapping the map via the existing _placeNotePinAtClick handler
- Changed cancel button label from just X to X Cancel for clarity
- Added touch-action:manipulation to #note-placing-bar for reliable mobile tap on the cancel button
**Files:** `frontend/index.html`

### 2026-05-29 07:47
**Fix two post-Pass3 regressions: stale server + viewport-only max calibration**

**Fixed:**
- Issue 1 (heatmap showing one cluster): root cause was stale server process predating Pass 3 — /api/map/heat route was not registered in the running process. Restarted uvicorn; /heat now returns all 143 archive points. _heatAll feeds all points to heatLayer.setLatLngs regardless of viewport, as required.
- Issue 2 (Sightings/Species showing dashes): same root cause — loadHeat() was receiving a 404, silently returning early, never writing d.total or d.species_count to stat-confirmed/stat-species. Server restart resolves both: /heat returns total:143 species_count:90.
- _recalcHeatMax viewport-relative max calibration (inner loop iterates visible, not _heatPoints) retained — this was correct and is not reverted.

### 2026-05-29 07:38
**Fix heatmap max calibration: viewport-relative density instead of whole-archive**

**Fixed:**
- _recalcHeatMax: inner neighbour-count loop now iterates over visible (viewport-bounded subset of _heatPoints) instead of all _heatPoints. max now reflects the densest cluster within the current viewport, giving density-relative-to-view behaviour. Whole-archive endpoint wiring and _heatAll data source unchanged.
**Files:** `frontend/index.html`

### 2026-05-29 01:16
**Four map/review fixes: land-use base layer, soil pH legend z-index, place-names toggle, dead buildCards() check**

**Built:**
- Fix C: place-names labels overlay (CARTO light_only_labels) given explicit zIndex 350 so labels stay above geology/soil/landuse overlays when switching overlay->overlay
**Fixed:**
- Fix A: Land use base layer now loads live ESRI Sentinel2_10m_LandCover ImageServer via custom L.TileLayer.extend getTileUrl (per-tile exportImage); old dead MapServer URL removed; selected button cleared of bls-unavailable state so it goes active/bold
- Fix B: removed will-change:transform from #soil-legend and #landuse-legend so the legends (z-index 2000) no longer drop behind tiles during pan/zoom compositing
- Fix D: verified no dead buildCards() reference exists anywhere in frontend/ or app/; review deep-link path already correct (loadPage(0) + _makeCardHtml), card-${id} convention matches getElementById query
**Files:** `frontend/index.html`, `frontend/review.html`

### 2026-05-29 01:00
**Hardening pass — ran Pass 1 (Alembic), Pass 2 (species_id FK additive), Pass 3 (map bbox pins + whole-archive heat) in sequence with verification**

**Built:**
- Alembic migrations: no-op baseline (0001) + additive species_id migration (0002), create_all retained for fresh DBs
- observations.species_id FK (additive) with set_observation_species() sync helper keeping species_primary as display cache
- /api/map/geojson now accepts optional bbox (min_lng/min_lat/max_lng/max_lat) — viewport-bounded pins
- /api/map/heat — lightweight whole-archive heat points carrying filter metadata [lat,lng,species,human_corrected,workshop,month] + totals
- Frontend: bbox pins refetched on moveend (debounced), whole-archive filter-responsive heatmap, stats from heat endpoint, deep-link highlight via unbounded fallback
**Fixed:**
- Heat decoupled from allFeatures — added loadHeat() refresh after every archive mutation (reject/undo/delete/sendToReview/rename/re-id/correction/approve) to avoid stale heat points
**Files:** `alembic.ini`, `migrations/env.py`, `migrations/versions/0001_baseline.py`, `migrations/versions/0002_add_observations_species_id.py`, `app/database.py`, `app/models/observation.py`, `app/services/species_link.py`, `app/services/identification.py`, `app/api/scan.py`, `app/api/observations.py`, `app/api/reidentify.py`, `app/api/culinary.py`, `app/api/ingest.py`, `app/api/map.py`, `frontend/index.html`, `requirements.txt`
**Pending:**
- Live browser smoke-test of map (preview sandbox cannot launch the venv server) — needs a manual visual check
- Server-side clustering (deferred)

### 2026-05-29 00:25
**Snapshot** — End of session — Strategic audit of ForagingID across UX gaps, technical debt, the Phase 10–13 roadmap, and the Goethean layer (Phase 11). Then scoped a 3-workstream hardening pass — Alembic, additive species_id FK, and map bbox/heat endpoint split — as the agreed next priority. No code changes; memory updated with the scope and the additive-only FK decision.
DB: `snapshots/db_20260529_002547.sqlite`

### 2026-05-29 00:25
**Session ended** — Strategic audit of ForagingID across UX gaps, technical debt, the Phase 10–13 roadmap, and the Goethean layer (Phase 11). Then scoped a 3-workstream hardening pass — Alembic, additive species_id FK, and map bbox/heat endpoint split — as the agreed next priority. No code changes; memory updated with the scope and the additive-only FK decision.

### 2026-05-28 23:47
**Snapshot** — End of session — Six prompts: four map fixes (Prompt 18), walk upgrade with ORS routing + circle draw + save/recall + heatmap restore (Prompt 19), note pin flow reversed (Prompt 20), five bug fixes covering category re-routing, look-up gating, PFAF artifact, and rename data integrity (Prompt 21)
DB: `snapshots/db_20260528_234754.sqlite`

### 2026-05-28 23:47
**Session ended** — Six prompts: four map fixes (Prompt 18), walk upgrade with ORS routing + circle draw + save/recall + heatmap restore (Prompt 19), note pin flow reversed (Prompt 20), five bug fixes covering category re-routing, look-up gating, PFAF artifact, and rename data integrity (Prompt 21)

### 2026-05-28 23:36
**Five fixes: category re-routes re-identify, gate look-up box, fix PFAF scraping artifact, verify approve-all, rename re-links all data**

**Fixed:**
- Fix 1: setCategory() now calls ReID.updateCategory() so re-identify reads the current category (fungi→iNat only, plant→both)
- Fix 2: Look up manual entry row hidden by default — click or enter manually header to toggle open
- Fix 3: PFAF _section_text() skips bare <a> siblings and stops at References/More on footer, eliminating artifact text
- Fix 4: Approve all button per species already correctly present in enrichment review (no regression found)
- Fix 5: _auto_merge_into now migrates SpeciesAIDraft and SpeciesRecipe to target species; _update_map_note_tags helper updates MapNote.species_tags on both rename and merge paths
**Files:** `frontend/static/js/reidentify.js`, `frontend/review.html`, `app/integrations/pfaf.py`, `app/api/culinary.py`

### 2026-05-28 23:22
**Prompt 20 — Reverse note pin creation flow (place first, write second)**

**Built:**
- Clicking Note button now enters pin-placement mode immediately — crosshair + bottom bar shown at once
- Bottom bar: Move map to location, then tap to place note — with Place here confirm and ✕ cancel
- Tapping the map background OR pressing Place here places the pin at that exact location
- Note form panel opens after placement with amber marker at chosen location + coordinates displayed
- Save commits to DB; ✕ Discard or second Note tap cancels and removes pending marker
- Temporary amber marker (size 20) shown while form is open so user can see the chosen location
**Fixed:**
- Removed dead _dropNoteHere, _confirmNotePlacement, _cancelNotePlacement functions
- _closeNotePanel now cancels full note flow if placement is in progress
**Files:** `frontend/index.html`

### 2026-05-28 23:03
**Prompt 19 — Walk feature upgrade (circle selection, ORS routing, save/recall)**

**Built:**
- Circle draw mode alongside existing rectangle — mode toggle (▭ Rect / ◯ Circle) shown while drawing
- ORS foot-hiking route replaces straight-line polyline — solid line via /api/walk/ors-route; fallback note shown when key missing
- Save walk button — prompts for name, stores to SQLite (name, waypoints, distance, duration)
- Saved walks collapsible section — lists walks by name/date, click to reload on map, delete per walk
**Fixed:**
- Removed Apple Maps button (no multi-waypoint support in URL scheme)
- Sub-header now shows ORS duration when available, otherwise ~walking estimate
**Files:** `frontend/index.html`, `app/api/walk.py`, `app/models/walk.py`, `app/config.py`, `app/main.py`

### 2026-05-28 22:45
**Prompt 18 — four map/review fixes**

**Built:**
- Place names toggle (CartoDB light labels overlay for geology/soil/landuse layers)
**Fixed:**
- Fix A: removed _watchLayerHealth auto-fallback from setBaseLayer — land use tiles now load without being marked unavailable on first tile error; _markLayerUnavailable now syncs legends
- Fix B: soil pH and land use legend z-index raised to 2000 + will-change:transform prevents drop-behind during pan/zoom
- Fix C: Place names toggle button in Layers panel for geology/soil/landuse layers; CartoDB light_only_labels overlay; resets to off when switching to standard/satellite/terrain
- Fix D: extracted _makeCardHtml(obs) helper from renderGrid in review.html; replaced dead buildCards([obs]) with _makeCardHtml(obs); review page deep-link now works
**Files:** `frontend/index.html`, `frontend/review.html`

### 2026-05-28
**Prompt 17 — Google Drive CHANGELOG sync**

**Built:**
- `app/integrations/gdrive.py` — Drive MCP client: `sync_changelog(token)` finds-or-creates `ForagingID/` folder in Drive root, then creates/overwrites `CHANGELOG.md` via `search_files` → `create_file` / `update_file` MCP tool calls against `https://drivemcp.googleapis.com/mcp/v1`
- `app/api/dev.py` — GDrive sync wired into `create_snapshot()` as a best-effort step (non-fatal); new `POST /api/dev/gdrive-sync` manual-trigger endpoint
- `app/services/settings_service.py` — `gdrive_access_token` registry entry (`type: str`, `hidden: True`, stored via existing settings API, excluded from generic renderer)
- `frontend/settings.html` — Google Drive card: password token input + reveal toggle, Save token, Sync now, status indicator; `_renderSettings()` skips `hidden: true` entries

**Fixed:**
- `frontend/index.html` — `#map-legend` moved to bottom-right (was bottom-left), resolving overlap with `#soil-legend` / `#landuse-legend`; `#geo-toast` raised to `bottom: 150px`

**Files:** `app/integrations/gdrive.py`, `app/api/dev.py`, `app/services/settings_service.py`, `frontend/settings.html`, `frontend/index.html`

**Pending:**
- OAuth token must be obtained externally (Google OAuth Playground) and pasted into Settings → Google Drive
- Token refresh / expiry not handled — user must re-paste when token expires

### 2026-05-28
**Prompt 16 — CHANGELOG.md, snapshot system, session continuity**

**Built:**
- `CHANGELOG.md` (this file) with ## Current State + ## History structure
- `app/services/changelog_service.py` — read/write/append helpers
- `app/api/dev.py` — `/api/dev/log`, `/api/dev/snapshot`, `/api/dev/snapshots`, `/api/dev/restore`, `/api/dev/end-session`, `/api/dev/changelog`, `/api/dev/current-state`
- `CLAUDE.md` — session-start/end protocol for Claude Code
- `settings.html` — Snapshots section with Save Snapshot, history list, Restore, End Session button

**Files:** `app/api/dev.py`, `app/services/changelog_service.py`, `app/main.py`, `CHANGELOG.md`, `CLAUDE.md`, `frontend/settings.html`

### 2026-05-28
**Prompt 15c — Review queue JS card rendering (category toggle, landscape layout, ReID with category)**

**Built:**
- `review.html` `renderGrid()`: category toggle (Plant/Fungi/Scene), species block hidden for landscape, `.corr-wrap` with "Confirmed species name" label + enrichment-queued message
- `review.html` `setCategory()`: PATCH category, live card DOM update
- `review.html` `saveCorrection()`: shows enrichment-queued message before card removal
- `review.html` `selectNoMatch()`: excludes landscape cards
- `index.html` `_pinColor()`: category → pin colour (green/amber/blue)
- `index.html` `renderMarkers()`: landscape excluded from heatmap
- `index.html` `showDetail()`: landscape description block instead of species block

**Files:** `frontend/review.html`, `frontend/index.html`

### 2026-05-28
**Prompt 15b — Base category system (Plant/Fungi/Landscape)**

**Built:**
- `obs_category`, `category_suggested`, `species_suggested` columns on Observation model
- `app/api/observations.py`: `PATCH /{id}/category` endpoint, `ObservationOut` fields
- `app/api/map.py`: landscape pins exposed (relaxed WHERE clause), `obs_category` + `description` in GeoJSON
- `app/api/reidentify.py`: sources param, fungi default to iNaturalist
- `app/services/identification.py`: landscape skip, fungi routing, category-aware min threshold
- `app/api/scan.py`: category routing in `_identify_scanned`, fungi auto-detect from `iconic_taxon_name`
- `app/integrations/inaturalist.py`: `iconic_taxon_name` field on `INatCandidate`
- `frontend/review.html`: category toggle CSS, landscape description CSS, correction label CSS
- `frontend/static/js/reidentify.js`: API selector (PlantNet/iNaturalist checkboxes per observation)

**Files:** `app/models/observation.py`, `app/database.py`, `app/api/observations.py`, `app/api/map.py`, `app/api/reidentify.py`, `app/services/identification.py`, `app/api/scan.py`, `app/integrations/inaturalist.py`, `frontend/review.html`, `frontend/static/js/reidentify.js`

### 2026-05-28
**Prompt 15a — Min identification confidence threshold**

**Built:**
- `min_identification_confidence` setting (default 50%) in settings registry
- `species_suggested` field: stores API top guess when below threshold
- `PATCH /api/scan/recheck-threshold`: retroactively clears species_primary for existing review queue items
- `scan.py` + `identification.py`: threshold applied to both pipelines
- `scan.html`: slider + Re-check queue button

**Files:** `app/services/settings_service.py`, `app/models/observation.py`, `app/api/scan.py`, `app/services/identification.py`, `frontend/scan.html`

## Archive — earlier Current State blocks

_Moved here 28 Oct 2026 from the top of the file: four superseded Current State snapshots (21–22 Oct 2026) that End Session had left stacked under the live block; kept unchanged; headings demoted one level._

### Current State — 22 Oct 2026, evening

#### Build
- Alembic head 0057 (encounters.shared_with_guests) — applied to the live DB after snapshot db_20261022_162240. CLAUDE.md still says 0050 (fix in batch 17).
- Tests: 25 files, 303 counted + test_taxonomy, all pass. Service worker foragingid-v13 (hard refresh once).
- Uncommitted until this End Session: enrichment scope, handout rule, batch 8, Fix A, Fix B.

#### Done this session (22 Oct)
- Tidy route order on walk 5 "Morning sunshine Gresgen to Adelsberg": crossings 3→0, 13 legs changed, 11,499→7,609 m / 93 min, members unchanged (108). Snapshot db_20261022_132801, commit 45c81a9. Straight dashed legs: 38→12, 32→27.
- Removed CHANGELOG placeholder line in the older 22 Oct block.
- Enrichment scope (app/services/enrichment_scope.py): one resolver; scope = saved walk (walk_membership) / Current list (Foraging List) / all eligible; no default; no scope = 400. Cap 25 per run, walk species first, remainder reported. dry-run.js scope picker on every bulk button. Scoped on enrich/run, re-enrich-empty, enrichment/run, drafts/backfill (incl. ID notes), redraft-medicinal, backfill-fungi-edibility (both now have a dry run + button on Scan → Backfill). enrichment_run saves its species list with the paused/interrupted run record; resume stays within it; old unscoped bp 203 is never resumed.
- Handout rule (safety_decision): a caution species prints culinary content with a curator prep OR look-alike warning. Withheld→shown: 817 Agaricus campestris, 295 Allium ursinum, 98 Artemisia vulgaris, 363 Gentiana lutea, 816/821/405/820 Macrolepiota, 711 Marasmius oreades, 590 Pimpinella major, 603 Pimpinella saxifraga.
- Fix A: redraft-medicinal eligible only when medicinal_notes is empty or a placeholder (medicinal_notes_redraftable), not curator-written, no pending draft; toxic skipped.
- Fix B: SafetyGate.culinaryWarnings / culinary_warnings (look-alike + preparation) with all culinary content — species page culinary/taste/recipes/field recipes, Lists panel, workshop foraging + recipe (Lists, print, PDF), experience Recipes tab, Find, encounter field recipes, personal card. Not repeated where the species block sits beside (map pop-up, Export summary, field-guide entries, PDF booklet, experience plant panel).
- Batch 8: guest access deny-by-default (app/services/guest_access.py in the middleware); media gate (thumbnails/uploads: confirmed only; encounter audio: visible encounters only; recorded-walk audio: never). is_guest_visible_observation predicate. Encounters: shared_with_guests + encounter_visible_to; curator "Share with guests" toggle; Participant notes tab. Guest notes (guest-notes.js) on species page + walk stops, text only (audio/photo refused), escaped; own notes print in Lists/print/PDF (guest PDF now allowed). Record tab hides audio for participants.
- Recon files: RECON_enrichment_scope_22oct.md, RECON_batch8_22oct.md.

#### Next (order)
1. Browser walkthroughs for this session's work (A, B, C, E, F, G additions below).
2. Small follow-ups: Record tab Photo button still shown to participants (server refuses participant photos); POST /api/recorded-walks still open to guests (table has no owner column).
3. Stage C publish panel.
4. Batches 9, 10, 11, 11b, 12, 13, 15, 15b, 16, 17 per REPORT.md section 9.

#### Settled (Melvin, 22 Oct)
- "Enrich selected" = scope "Current list" (Foraging List). Encounter field recipes carry the warnings.
- Handout rule: curator prep OR look-alike warning. All cautionary text travels with culinary content; no duplicate where the species block sits beside it.
- Redraft-medicinal button on Scan → Backfill. Participant devices: text notes only, no audio.
- Pimpinella major/saxifraga keep culinary content on handouts via curator look-alike warning; no carrot-family rule (Melvin, 22 Oct).

#### Open decisions (Melvin)
- None.

#### Rules learned
- Don't run a full enrichment; use a scope + the 25 cap.
- Auto-enrichment after an ID correction has no dry run but goes through the same guards.
- Renaming a helper used under app/ crashes the uvicorn reload until all callers are updated — make such edits in one pass.
- Tests that start the redraft task write logs/redraft_medicinal_jq*.json into the real logs/ (not gitignored) — the test now removes what it wrote.

#### Scope added (keep)
- 11b, 15b, 17 as in the previous Current State (merges, genus/family sweep, non-European card sweep, G3-held drafts, English common-name backfill; empty saved walk stops; Lists lookalike toggle, reload banner, thumbnail field, CLAUDE.md Alembic head, scan.html:1795, curator-device list refresh).

#### Melvin's review queue
- Warning review cards (all verdicts, walk species first). Edit Oxalis grandis 3493. Text tidy-up (352 edible_parts / 689 id_notes with no history). 347 Takeout person_animal rejects (mount DIGIERA). Draft #3252 Amaranthus hybridus.

#### Browser checks: walkthroughs
Test species: Conium maculatum, Oenanthe crocata, Sambucus nigra, 229 St John's wort, 295 Ramsons, 97 Aspen, Pineapple weed.
- A. Species page: three views, safety sort, filters kept, capitalised names, test species pages; species resources load. NEW: Culinary section, Taste notes, every recipe card and field recipe show look-alike + preparation warnings (uncurated labelled "Source text — not yet reviewed"); a species with none looks unchanged.
- B. Map + walks: Conium pin full look-alike; Ramsons labelled; ☠ on 155/688/745; walk stop cards; Edit walk → Save → Re-route; Tidy route order; Export summary; published Rümmelsbühl page; Discover/Find cards, ✎ rename, Enrich, note tags. NEW: walk 5 shows the tidied order, 7.6 km, dashed 38→12 and 32→27; map pop-up warnings once; Export summary species block once (none inside the recipe box); Find → Make? cards carry both warnings; participant phone: walk stops show "📝 Add a note" and it saves.
- C. Handouts: Lists → print (field guide, workshop) + PDF in 3 layouts: Conium uncut, 229 withheld label, no PFAF Folklore, corners present. NEW: field-guide entries show warnings once; workshop pages show warnings before Foraging and Recipe; booklet PDF warnings once; Ramsons and a Macrolepiota print culinary content, 229 still withheld; a participant's PDF/print shows only their own notes under the right species, yours shows none.
- D. Review: Critical section; verdict queue; warning cards (Approve / Edit / Remove); Regenerate side by side; Run now dry run + Cancel; AI-draft card buttons; reviewer notes.
- E. Phone: pair via Add device; installed app signed in; used link → "Link already used"; bare URL → "Ask Melvin"; Revoke works; unpaired shows "not signed in", not "offline"; List view at 390px; proximity alert folds; airplane-mode short walk (outbox). NEW (participant phone): species page note box with "Type, or dictate using the mic on your keyboard." and keyboard dictation works; a pending/rejected photo URL gives 404; species gallery shows confirmed photos only; Record tab has no 🎙 button and a typed note saves; on your laptop the 🎙 button still records.
- F. Settings/system: "Your devices & sharing"; no guest toggle; device list (no Add device on phone); every enrichment button asks first; paused run shows "paused — no network"; run summary skip counts; DeepSeek key; Jobs pop-up; caffeinate exits. NEW: every bulk button opens the scope dialog first; Continue disabled until a scope is chosen; walk dropdown lists saved walks; dry run shows "Scope: … queued (cap 25); N not queued"; 🍄 Fungi edibility and 💊 Re-draft medicinal notes buttons work (Cancel writes nothing); Review run summary shows "Not queued (cap 25)".
- G. Workshops: participant link uses the ngrok address; guest view loads on a second phone; used link refused; revoke works; works on mobile data. NEW: tick "Share with guests" on one of your encounters — a participant sees its text, transcript, confirmed photos and audio; your unshared encounters and other participants' notes stay hidden; Participant notes tab groups by session and person, names with <b> show as plain text.
Rule: Code tests whatever it can; new browser checks go into a walkthrough, not numbered.

### Current State — 22 Oct 2026, afternoon

#### Build
- Alembic head 0056 (CLAUDE.md still states an older head — fix in batch 17). 288 tests pass (24 files). Service worker foragingid-v11 (hard refresh needed once).
- No app/ or frontend/ changes this session.

#### Done this session (22 Oct)
- Context-warning hook + status line (config only): scripts/dev/context_check.py — UserPromptSubmit hook prints CONTEXT WARNING at 400k–500k and CONTEXT LIMIT above 500k (raised from 120k/150k: the app shows 141k as 15% of the window); --statusline prints "ctx ~Nk"; one shared context_tokens() helper; never fails a prompt. Wired in .claude/settings.local.json (not committed). Tested on this session's transcript and fake 130k/160k transcripts; the hook fired live (~149k, ~150k at the old thresholds).
- CLAUDE.md: "If a CONTEXT WARNING or CONTEXT LIMIT note appears, follow it before anything else." (Session Start) and "The End Session block is always complete and paste-ready. Never placeholders, never instructions for Melvin to edit it." (Session End).
- Enrichment scope / handout rule / prep-warnings-with-recipes: Step 1 recon only → RECON_enrichment_scope_22oct.md (file:line quotes). Nothing built.

#### Next (order)
1. Build from RECON_enrichment_scope_22oct.md (Melvin's 22 Oct prompt, Steps 2–3): scope picker on every bulk enrichment + backfill endpoint through dry-run.js — scopes: a saved walk (walk_membership, same members as the map), "Current list" (the Foraging List species), all eligible (never the default); no scope = nothing runs; per-run cap 25, walk species first, remainder reported in the run summary; persist the scoped list so resume keeps it; id_notes backfill gets a names filter; dry run counts the chosen scope only; handout rule in safety_decision (curator prep OR look-alike warning) + withheld→shown species list; one shared prep-warning-with-recipe helper (JS + Python twin) on every recipe surface incl. encounter field recipes; tests + full suite.
2. Confirm the walk tidy-order / warning cards / UI fixes report; then Tidy route order on Morning sunshine walk.
3. Batch 8 (guest visibility), then Stage C publish panel.
4. Batches 9, 10, 11, 11b, 12, 13, 15, 15b, 16, 17 per REPORT.md section 9.

#### Settled (Melvin, 22 Oct)
- Handout culinary rule: a caution species may print culinary content on handouts when it has a curator-authored preparation_warnings OR look_alike_warnings (to be built, Next #1).
- "Enrich selected" = a scope called "Current list" (the Foraging List species). No new select mode on the Species page.
- Encounter field recipes (encounters-main.js:1063, species.html:3348) carry the prep warning too.

#### Open decisions (Melvin)
- None.

#### Rules learned
- Don't run a full enrichment: the dry run shows ~900 new drafts. Run it for walk species only, in small batches (the cap in Next #1 builds this in).
- Auto-enrichment after an ID correction has no dry run, but goes through the same guards.

#### Scope added (keep)
- 11b: merges 704→457, 758↔757, 708↔412, 608↔589, 103↔531, 600↔749, 82↔200; relink Collybia nuda (obs 8410) and Conyza canadensis; GBIF check 187; genus/family sweep (Aconitum, Alchemilla, Bellis, Erigeron, Imleria, Matricaria, "Rubus subg. Rubus", "Rosa sect. Caninae", 494 puffball) + find the fill that wrote them; non-European card sweep (Rubus occidentalis, Quercus bicolor/velutina, Acer macrophyllum, Juglans nigra, Picea mariana, Tilia americana, Salix barclayi, Erigeron aliceae, Chrysosplenium americanum, Luffa, Ulmus davidiana, Viburnum trilobum, Carpinus caroliniana, Larix lyallii, Pinus radiata, Hydrocotyle, 808 Ambrosia confertiflora); G3-held drafts decided after the sweep; English common-name backfill (Dianthus carthusianorum → Carthusian pink).
- 15b: empty saved walk stops hide or drop.
- 17: Lists "Lookalike warnings" toggle dead; reload banner on new app version; thumbnail field on /api/species/; CLAUDE.md Alembic head; scan.html:1795 loadPrefilterThreshold; curator-device list refreshes itself; enrichment species-limit option (covered by the Next #1 cap).

#### Melvin's review queue
- Warning review cards (all verdicts, walk species first).
- Edit Oxalis grandis 3493.
- Text tidy-up (on the simmer): 352 edible_parts / 689 id_notes with no history, many long PFAF dumps or "North America" text.
- 347 Takeout person_animal rejects (mount DIGIERA). Draft #3252 Amaranthus hybridus.

#### Browser checks: walkthroughs
Test species: Conium maculatum, Oenanthe crocata, Sambucus nigra, 229 St John's wort, 295 Ramsons, 97 Aspen, Pineapple weed.
- A. Species page: three views, safety sort, filters kept, capitalised names, test species pages; species resources load.
- B. Map + walks: Conium pin full look-alike; Ramsons labelled; ☠ on 155/688/745; walk stop cards; Edit walk → Save → Re-route; Tidy route order; Export summary; published Rümmelsbühl page; Discover/Find cards, ✎ rename, Enrich, note tags.
- C. Handouts: Lists → print (field guide, workshop) + PDF in 3 layouts: Conium uncut, 229 withheld label, no PFAF Folklore, corners present.
- D. Review: Critical section; verdict queue; warning cards (Approve / Edit / Remove); Regenerate side by side; Run now dry run + Cancel; AI-draft card buttons; reviewer notes.
- E. Phone: pair via Add device; installed app signed in; used link → "Link already used"; bare URL → "Ask Melvin"; Revoke works; unpaired shows "not signed in", not "offline"; List view at 390px; proximity alert folds; airplane-mode short walk (outbox).
- F. Settings/system: "Your devices & sharing"; no guest toggle; device list (no Add device on phone); every enrichment button asks first; paused run shows "paused — no network"; run summary skip counts; DeepSeek key; Jobs pop-up; caffeinate exits.
- G. Workshops: participant link uses the ngrok address; guest view loads on a second phone; used link refused; revoke works; works on mobile data.
Rule: Code tests whatever it can; new browser checks go into a walkthrough, not numbered.

### Current State — 22 Oct 2026, afternoon

#### Build
- Alembic head 0056 (CLAUDE.md still states an older head — fix in batch 17). 288 tests pass (24 files). Service worker foragingid-v11 (hard refresh needed once).
- No app/ or frontend/ changes this session.

#### Done this session (22 Oct)
- Context-warning hook + status line (config only): scripts/dev/context_check.py — UserPromptSubmit hook prints CONTEXT WARNING at 120k–150k and CONTEXT LIMIT above 150k; --statusline prints "ctx ~Nk"; one shared context_tokens() helper; never fails a prompt. Wired in .claude/settings.local.json (not committed). Tested on this session's transcript and fake 130k/160k transcripts; the hook fired live at ~149k. CLAUDE.md: "If a CONTEXT WARNING or CONTEXT LIMIT note appears, follow it before anything else."
- Enrichment scope / handout rule / prep-warnings-with-recipes: Step 1 recon only → RECON_enrichment_scope_22oct.md (file:line quotes). Nothing built.

#### Next (order)
1. Build from RECON_enrichment_scope_22oct.md (Melvin's 22 Oct prompt, Steps 2–3): scope picker (walk / selected / all, never default; no scope = nothing runs) on every bulk enrichment + backfill endpoint through dry-run.js; per-run cap 25, walk species first, remainder reported; persist the scoped list so resume keeps it; id_notes backfill gets a names filter; handout rule in safety_decision (curator prep OR look-alike) + withheld→shown list; one shared prep-warning-with-recipe helper (JS + Python twin) on every recipe surface; tests + full suite.
2. Confirm the walk tidy-order / warning cards / UI fixes report; then Tidy route order on Morning sunshine walk.
3. Batch 8 (guest visibility), then Stage C publish panel.
4. Batches 9, 10, 11, 11b, 12, 13, 15, 15b, 16, 17 per REPORT.md section 9.

#### Open decisions (Melvin)
- "Enrich selected": reuse the Species page Foraging List selection (select=1 picker) or a separate enrichment selection?
- Should encounter field recipes (encounters-main.js:1063, species.html:3348) also carry the prep warning?
- (Settled 22 Oct: a caution species may print culinary content on handouts with a curator prep OR look-alike warning — to be built.)

#### Rules learned
- Don't run a full enrichment: the dry run shows ~900 new drafts. Run it for walk species only, in small batches (the cap in Next #1 builds this in).
- Auto-enrichment after an ID correction has no dry run, but goes through the same guards.
- Big multi-surface prompts: start them in a fresh session (the context hook warns at 120k).

#### Scope added (keep)
- 11b: merges 704→457, 758↔757, 708↔412, 608↔589, 103↔531, 600↔749, 82↔200; relink Collybia nuda (obs 8410) and Conyza canadensis; GBIF check 187; genus/family sweep (Aconitum, Alchemilla, Bellis, Erigeron, Imleria, Matricaria, "Rubus subg. Rubus", "Rosa sect. Caninae", 494 puffball) + find the fill that wrote them; non-European card sweep (Rubus occidentalis, Quercus bicolor/velutina, Acer macrophyllum, Juglans nigra, Picea mariana, Tilia americana, Salix barclayi, Erigeron aliceae, Chrysosplenium americanum, Luffa, Ulmus davidiana, Viburnum trilobum, Carpinus caroliniana, Larix lyallii, Pinus radiata, Hydrocotyle, 808 Ambrosia confertiflora); G3-held drafts decided after the sweep; English common-name backfill (Dianthus carthusianorum → Carthusian pink).
- 15b: empty saved walk stops hide or drop.
- 17: Lists "Lookalike warnings" toggle dead; reload banner on new app version; thumbnail field on /api/species/; CLAUDE.md Alembic head; scan.html:1795 loadPrefilterThreshold; curator-device list refreshes itself; enrichment species-limit option (superseded by Next #1 cap).

#### Melvin's review queue
- Warning review cards (all verdicts, walk species first).
- Edit Oxalis grandis 3493.
- Text tidy-up (on the simmer): 352 edible_parts / 689 id_notes with no history, many long PFAF dumps or "North America" text.
- 347 Takeout person_animal rejects (mount DIGIERA). Draft #3252 Amaranthus hybridus.

#### Browser checks: walkthroughs
Rule: Code tests whatever it can; new browser checks go into a walkthrough, not numbered.

### Current State — 21 Oct 2026, evening

#### Build
- Alembic head 0055 (CLAUDE.md still states an older head — fix in batch 17).
- 202+ tests pass (plus 13 new orphan tests). Service worker v9 (species cache renamed, old cached profiles dropped).

#### Done since 16:00
- Batch 6: one shared warnings helper. In-app shows full text; uncurated text is labelled "Source text — not yet reviewed" and is never dropped. Handouts (Lists, print, PDF, Export summary, experience page) show curator text only, uncut, read from the DB. Caution species with no curator prep warning print no culinary content ("⚠ caution — warning not yet reviewed"): 25 of 45 caution species. Marker writes are refused by a DB trigger (0055).
- Aspen (97) edible + edible_parts (edibility history #2229, culinary history #3388). Recipe #48 shows. David's-harp stays toxic, recipe #37 hidden.
- Oenanthe crocata (653) look-alike text, curator-authored (#3389).
- E-14 cleanup: 10 marker fields got a real human row (#3390–3399); drafts 3181/3194/3202/3209/3223/3232 approved. Melvin read the Keck and Meum texts.
- Common names in sentence case through the shared helpers (no DB writes).
- Species page: Large / Grid / List views; List sorts by every column, including safety.
- 1b: dual-API-agreed harmless species are now included on published walks (rule 7 hazard blocker unchanged). Walk 4 republished: ed3b4d9, 63 species, 31 stops, 244 photos with clean EXIF/GPS, live pages byte-identical to the build. w/walk-4/ not published.
- Orphan species cards: one shared rule (species_has_live_observation / species_is_reference); rejected photos no longer back a card; GC runs on every reject and un-reject path; verdict and edibility queues filtered; kingdom gate at card creation (no card for non-plant/fungi top candidates). 44 cards orphan-marked, 72 drafts invalidated (snapshot db_20261021_193804). Stale markers cleared on 808 and 810 (db_20261021_194150). Verdict queue 33 → 5 (Hoheria, Fagus × taurica, Ulmus laciniata, Aspalathus, Bowlesia — fix the photo IDs in Species ID review).
- Grid "toxicity unknown" everywhere was a stale browser cache, not a bug.

#### Next (order)
1. Batch 7: share-link secret gates LAN/ngrok (localhost exempt) + escape source text on all pages (review.html:1962 first).
2. Batch 8.
3. Stage C publish panel (in-app republish) after batch 8.
4. Batches 9, 10, 11, 11b, 12, 13, 15, 15b, 16, 17 per REPORT.md section 9.

#### Scope added (keep)
- 11b, first:
  - Merges: 704→457 Trametes versicolor; 758↔757 Coronilla varia; 708↔412 Thelypteris limbosperma; 608↔589 Cota tinctoria; 103↔531 Chamaenerion angustifolium; 600↔749 Mycelis muralis; 82↔200 Cirsium ferox.
  - Relink the Collybia nuda and Conyza canadensis observations (incl. obs 8410 species_primary vs species_id 505). GBIF check on 187 "Hypericum perfoliatum".
  - Genus/family sweep (family column holding a genus: Aconitum, Alchemilla, Bellis, Erigeron, Imleria, Matricaria, "Rubus subg. Rubus", "Rosa sect. Caninae"; 494 puffball as Caprifoliaceae) + find the fill that wrote them.
  - Non-European species card sweep against data/reference/plantnet_europe_species.json (e.g. Rubus occidentalis, Quercus bicolor/velutina, Acer macrophyllum, Juglans nigra, Picea mariana, Tilia americana, Salix barclayi, Erigeron aliceae, Chrysosplenium americanum, Luffa, 808 Ambrosia confertiflora/obs 24222). Junk cards carrying a human census verdict are protected as reference cards and need deliberate removal. "norway spruce" 685 stays marked (C-04).
  - English common-name backfill (e.g. Dianthus carthusianorum → Carthusian pink).
- 15b: empty saved walk stops (walk 5 stop 35) hide or drop.
- 17: the Lists "Lookalike warnings" toggle is now dead (remove or relabel); a reload banner on a new app version; a thumbnail field on /api/species/ (Large/List views currently load all map data); CLAUDE.md Alembic head; scan.html:1795 loadPrefilterThreshold.

#### Open decisions (Melvin)
- Should a curator look-alike warning (not only prep) let a caution species print culinary content on handouts? Affects 817 Meadow Mushroom, 711 Marasmius.

#### Melvin's review queue
- Caution species with no warning text: 817, 460, 810, 677, 381, 702, 816, 821, 405, 820, 711, 411.
- Uncurated caution text to review: 295 Ramsons, 764, 98, 672, 639, 149, 363, 229, 148, 590, 603, 194, 399.
- 5 verdict-queue photos to re-ID (above). 92 medicinal drafts + Verbena 3544; edit Oxalis grandis 3493. Refusal drafts to reject. 347 Takeout person_animal rejects (mount DIGIERA). Draft #3252 Amaranthus hybridus.

#### Browser checks: six walkthroughs (replace the old numbered list)
Test species: Conium maculatum, Oenanthe crocata, Sambucus nigra, 229 St John's wort, 295 Ramsons, 97 Aspen, Pineapple weed.
- A. Species page: three views, safety sort, filters kept, capitalised names, test species pages (badges, full warnings, labels, recipe #48).
- B. Map + walk 4: Conium pin full look-alike; Ramsons labelled; ☠ on 155/688/745; walk panel stop cards (817 look-alike, Sambucus open, "Also here" lines); Edit walk → Save → Re-route; Export summary; published Rümmelsbühl page (Stellaria graminea present, caution recipes withheld).
- C. Handouts: Lists → browser print (field guide with ID notes off; workshop) + PDF in 3 layouts: Conium uncut, 229 withheld label, no PFAF Folklore section, corners present.
- D. Review: Critical section + red badge; verdict queue shows 5; warning drafts; Second Opinion 24149; capitalised names.
- E. Phone: SW v9; List view at 390px; proximity alert folds and opens; guest /api/settings 403 over ngrok.
- F. Settings/system: DeepSeek key set; API dashboard; species chat; About regenerate; Jobs pop-up drag; caffeinate exits with the server.
Rule: Code tests whatever it can (real JS via jsc, real PDFs); new browser checks are added to a walkthrough, not numbered.


_Moved here 16 Oct 2026 from the top of the file: superseded Current State snapshots (3 Jul – 15 Oct 2026), kept unchanged for reference; headings demoted one level._

### Current State — 15 Oct 2026 (end of session 2)

#### Build status
Server: START_ForagingID.command — uvicorn foreground + tee to logs/server_<ts>.log; port check (no kill -9); cleanup trap; tee survives Ctrl+C. Claude Code never starts the server; reads the log.
Alembic head: 0052. WAL on; busy_timeout 30000 + synchronous=NORMAL on every connection.

#### Completed 14–15 Oct
- Health check after Aug–Oct dormancy (DB ok, invariant ok)
- Syncthing: Pixel 8 Pro paired; "Foraging Pics" (39ds2-kdty9) Mac = Receive Only + ignoreDelete; phone = Send Only curated folder; duplicate folder entry removed; Pixel7pro entry kept
- iNat token refreshed (expires ~24h — refresh before each processing session)
- Leaflet SRI fixed (1.9.4, verified hashes on review/index/species)
- SQLite lock contention fixed: enrichment two short transactions (no lock across LLM calls); enrich_gate.py ingest priority (enrichment deferred during P1/P2/re-identify batches, Semaphore(1)); P1 classify-before-insert + to_thread + cleanup on failed insert. Verified 0 locks on 90-file batch
- Follow-up data: re-enriched Alnus alnobetula / Melampyrum nemorosum / Salix aurita; obs 24065 → needs_review; orphan copies + thumbnails deleted
- Launcher rewritten (foreground); ngrok subprocess stopped on graceful shutdown
- Identification Stage A (dry-run verified, live untouched): iNat gating score = min(combined, vision) (CLAUDE.md now matches code; can only lower scores); disagreement promotion (iNat location-ranked #1 if in PlantNet top 5 → suggested ID, always needs_review, never counts as agreement); iNat combined + vision scores stored per candidate; dual_source_agreement written again (1 agree / 0 disagree or single source / NULL none). Stage A item 3 (cards only on approval) DECLINED — dependencies (accept-species, auto-approve, species_id backfill, taxonomy tree, Edibility Review)
- Walk builder Stage 1: typed waypoints (notes not saved as obs), circular flag persisted, route geometry saved + redrawn without ORS, toxic guard on walk panel
- Walk builder Stage 2: centroid stops (default 30 m, slider 10–100 m, radius saved in route_geojson.foragingid v2); 50-waypoint cap (49 circular) with Increase radius; real ORS failure reasons + opt-in labelled straight-line; Google Maps export first 10 points with notice. Browser-tested by Melvin: selection + routing work
- First Gresgen walk saved: "little foray" (20 stops, 22 species, ~13.5 km circular)

#### Pending / next
1. Walk fixes from Melvin's test: (a) Save gives no confirmation — show a clear "Saved as <name>" and avoid duplicate saves (he created 3); (b) after saving, the build-walk header still shows "20 stops" — should show the saved name ("little foray"); (c) duplicate summary header ("Walk Route (20 stops)" + "Walk route · 20 stops"); (d) centre-drift second pass: reassign pins beyond R to nearest stop or new stop — APPROVED; (e) delete the 2 duplicate "little foray" saves (with OK)
2. SAFETY next: walk panel (and app-wide) shows "edible" badge + recipes for UNVERIFIED Apiaceae (Daucus carota on "little foray" stop 1). Walk panel: Apiaceae edibility/recipes only if human-verified; same review for other unverified "edible" species. Then app-wide Apiaceae/unverified-toxic fix
3. Walk Stage 3: accumulating selection → undo / reset+confirm / subtract (touch toggle) / side panel (remove, reorder via pointer events)
4. Walk Stage 4: walk filters (human-verified only, kingdom, months, min obs)
5. Walk Stage 5 (backend, server stopped): ORS elevation, PUT saved walk (edit), draft autosave
6. Foraging Experience export: walk = "little foray". Next: Code lists its 22 species with edibility/toxicity/verified status → Melvin verifies shortlist. Then scripted export (scripts/experience_export/) → separate public GitHub Pages repo (Melvin creates; gh not installed) → Hostinger Builder embed. Gates: edible claims only edibility_verified_by='human'; toxic → warning, no recipe; Apiaceae no edibility text unless human-authored; EXIF stripped (~1200px re-encode); disclaimer + link to site Impressum; export only species with approved obs. Open: recipe depth, language (DE/EN)
7. PWA: ngrok static domain negligee-raft-shiny.ngrok-free.dev — Start sharing, install from Chrome
8. Launcher live checks after next Ctrl+C: pgrep -fl ngrok (empty); log tail shows shutdown complete
9. Proximity alerts + 📋 summary export read only first species of multi-species stops

#### Known issues / backlog
- SAFETY: Aruncus dioicus edibility 'edible', unverified, toxicity none — Melvin to decide status (cooked young shoots only?), check live recipes, own-words prep warning. (Supersedes stale "goat's beard drafts 2182/2183 pending" — approved 14 Jun)
- SAFETY: unverified "edible" Apiaceae (Daucus carota, Heracleum sphondylium, Aegopodium podagraria); unverified toxic species (Digitalis purpurea, Chaerophyllum hirsutum/aureum, Sambucus ebulus, Lupinus polyphyllus, Hypholoma fasciculare, Iris pseudacorus)
- Toxic guard still missing: stop-card culinary hint, walk-summary export, walk sheet species list; backend one-liner: toxicity_severity on GET /api/culinary/{name}
- T. dubius edibility_status NULL (invalid); T. pratensis unknown
- Identification Stage B: GBIF "out of range" review label (~150 km, flag only, cached per species × 0.5° cell); test PlantNet weurope vs all on a sample before switching. Needed for 24221 (Aspalathus) / 24222 (Ambrosia) type cases
- Junk species cards (Aspalathus retroflexa 807, Ambrosia confertiflora 808, Larix occidentalis 803, Larix lyallii 791, Verbascum boerhavii 792; Gentiana verna 789 season-implausible) — cleanup of zero-approved cards needs OK
- Enrichment paths not gated: culinary.py enrichment-run batch, trigger_ai_drafts_for_species, ITIS lookup task
- Enrichment queue in-memory: after restart, check backfill panel for un-enriched cards
- Re-enrich of a fungus wipes its pending edibility suggestion
- Identify — 2013 job interrupted at 90/2367 (gated; rerun when convenient)
- Google Drive token invalid
- Disk tight — move to DIGIERA: Facebook/Instagram exports, all but 2 newest snapshots (2 byte-identical pairs), old data/ backups
- Ollama default 'mistral' not installed (llama3.1 present)
- Docs drift: CLAUDE.md Alembic head (says 0050), PhoneForaging path (~/Local(unsynced)/PhoneForaging)
- Tracked leftovers: your_db.db, current.txt; review_status 'not_applicable' (1 row) undocumented

session_summary:
Identification Stage A (stricter min() gating score, iNat location-ranked promotion on disagreement, scores + dual_source_agreement stored; card-deferral declined). Walk builder Stages 1–2 (typed waypoints, circular + geometry persisted, toxic guard, centroid stops with radius slider, 50-waypoint cap, honest ORS errors, Google export notice). First Gresgen walk "little foray" saved for the promo page. Test feedback logged: save confirmation, saved-name header, duplicate header, centre-drift pass, unverified-Apiaceae "edible" badge.

### Current State — 15 Oct 2026

#### Build status
Server: START_ForagingID.command — uvicorn foreground + tee to logs/server_<ts>.log; port check (no kill -9); cleanup trap. Claude Code never starts the server; reads the log.
Alembic head: 0052. WAL on; busy_timeout 30000 + synchronous=NORMAL on every connection.

#### Completed today (14–15 Oct)
- Health check after Aug–Oct dormancy (DB ok, invariant ok, git clean)
- Syncthing: Pixel 8 Pro paired; "Foraging Pics" (39ds2-kdty9) Mac = Receive Only + ignoreDelete; phone = Send Only on curated folder; duplicate "ForagingID" folder entry removed; Pixel7pro entry kept (old phone)
- iNat token refreshed (expires ~24h — refresh before each processing session)
- Leaflet SRI: 1.9.4 pinned, verified hashes on review/index/species (review.html JS hash was truncated)
- SQLite lock contention fixed: enrichment no longer holds write lock across LLM/network calls (two short transactions); enrich_gate.py — ingest priority (enrichment deferred while any P1/P2/re-identify batch active, Semaphore(1)); P1 ingest classify-before-insert + to_thread + cleanup of copy/thumbnail on failed insert. Verified: 0 locks on 90-file batch (vs 30 before); enrichment deferred and serialised; no edibility written
- Follow-up data: re-enriched Alnus alnobetula / Melampyrum nemorosum / Salix aurita; obs 24065 → needs_review; 2 orphan pipeline2 copies + thumbnails deleted
- Launcher rewritten (foreground, tee survives Ctrl+C, port check); ngrok subprocess stopped on graceful shutdown (sharing.py stop_ngrok_subprocess + lifespan)
- Walk builder Stage 1 (frontend/index.html): note IDs no longer saved as obs IDs (typed waypoints, old walks still load); circular flag persisted in route_geojson.foragingid; route geometry saved + redrawn without ORS; toxic guard on walk panel (no recipes for toxic/deadly, ☠ badge)
- Snapshots: db_20261015_072953 (+ earlier today)

#### In progress
- Identification Stage A: iNat gating score = min(combined, vision) per docs; disagreement promotion (iNat location #1 if in PlantNet top 5, stays needs_review, never counts as agreement); store iNat combined score; fill dual_source_agreement; no species cards for disputed IDs (pending dependency check)

#### Pending / next
1. Verify walk Stage 1 in browser (toxic badge; save/reload circular walk with note — SQL check; no ORS call on load)
2. Walk Stage 2: stops via centroid clustering (default 30 m, slider 10–100 m), 50-waypoint ORS cap with message (no silent straight-line fallback)
3. Walk Stage 3: accumulating selection → undo / reset+confirm / subtract mode (touch toggle) / side panel (remove, reorder via pointer events)
4. Walk Stage 4: walk filters (human-verified only, kingdom, months, min obs)
5. Walk Stage 5 (backend, server stopped): ORS elevation, PUT saved walk (edit), draft autosave
6. Foraging Experience export (Gresgen): scripted export (scripts/experience_export/) → separate public GitHub Pages repo (Melvin creates repo; gh not installed) → Hostinger Builder embed. Needs: Gresgen walk drawn; walk species shortlist human-verified; gates: edible claims only edibility_verified_by='human', toxic → warning/no recipe, Apiaceae no edibility text unless human-authored; EXIF stripped (re-encode ~1200px); existing disclaimer + link to site Impressum. Open: recipe depth (full/teaser), language (DE/EN)
7. PWA install on Pixel 8 via ngrok static domain (negligee-raft-shiny.ngrok-free.dev) — Start sharing first, install from Chrome
8. Launcher live checks after next Ctrl+C: pgrep -fl ngrok (empty); log tail shows shutdown complete

#### Known issues / backlog
- SAFETY: Aruncus dioicus edibility_status='edible', unverified, toxicity none — Melvin to decide status (cooked young shoots only?), check live recipes, rewrite prep warning in own words. CHANGELOG "goat's beard drafts 2182/2183 pending" is stale (approved 14 Jun) — replaced by this
- SAFETY: unverified "edible" Apiaceae (Daucus carota, Heracleum sphondylium, Aegopodium podagraria); unverified toxic species (Digitalis purpurea, Chaerophyllum hirsutum/aureum, Sambucus ebulus, Lupinus polyphyllus, Hypholoma fasciculare, Iris pseudacorus) — app-wide
- Toxic guard still missing: stop-card culinary hint, walk-summary export, walk sheet species list; backend one-liner to add toxicity_severity to GET /api/culinary/{name}
- T. dubius edibility_status NULL (invalid); T. pratensis unknown
- Orphan/implausible species cards from disputed IDs (Aspalathus retroflexa 807, Ambrosia

### Current State — 19 July 2026

**Session focus:** Opus phase-boundary audit → full remediation of the 
guard-coverage defect class, plus repair of the 6 invariant-drifted rows. 
All audit findings closed. Invariant clean: card_counted 2158 = map_eligible 
2158, zero drift.

**Landed and verified this session (all harness- or live-verified per fix):**

STRUCTURAL — _identify_scanned_inner guard-coverage fix (scan.py)
- Root-cause fix for the guard-coverage defect class (4 prior instances in 
  2 weeks: kingdom gate, blacklist gate, force_review-in-else, terminal 
  guard). Compute `terminal = is_terminal_review_status(obs.review_status)` 
  ONCE up front; every human-decision mutation gated on it; diagnostics/
  append-only rows left unconditional. All hand-rolled terminal variants 
  retired (grep for `!= "manually_verified"` returns nothing).
- Closed A1 (min-confidence branch: species-wipe + review_status revert, 
  zero guard, executed on live manually_verified rows), A2 (unguarded 
  species overwrite), A3 (reviewer_notes overwrite — now append-never-
  overwrite; also fixed an auto-approve `reviewer_notes = None` blanket 
  wipe), A5 (missing-file path), A6 (kingdom gate now covers all 3 terminal 
  states), A7 (6 review_label writes via single apply point). Two sites the 
  audit missed (pause check, no-credential exit) also found and guarded.
- A6 behaviour signed off: approved/rejected rows are now immune to 
  automated re-ID pull-back. Human override stands — finalized is finalized.

EDIBILITY — rename safety bypass (enrichment.py, A4)
- Rename path was silently downgrading human-confirmed toxic → unknown and 
  clearing the human-lock, bypassing _enforce_edibility_write_rules(). 
  Found routing-through-the-gate would NOT fix it (gate permits toxic→
  unknown by design, off-ladder). Removed the automated edibility mutation 
  entirely — verdict/lock never written by this path for any row. Rename 
  now flags for review (existing review_requested triple) on any established 
  verdict, locked or not. Verified: locked toxic + locked edible both 
  preserved + flagged; unlocked correctly not flagged. AST-walk confirms 
  zero edibility writes remain in the rename function.

PHONE-ORIGIN — reconciled to one definition (A8, all parts)
- Root finding: `is_phone` never meant "phone origin" — it meant "must 
  force review". Tuple produced correct routing; the NAME lied. 
  Renamed → `requires_forced_review` (zero behaviour change, proven by 
  reconstruction-diff). Added canonical `is_phone_origin(obs) → 
  upload_source == 'syncthing'`; retired 12 scattered string literals.
- identify.py bulk-act filter (`.isnot("phone")`, 0-row no-op) removed as 
  obsolete — the case it guarded no longer exists; documented why. 
- Fail-closed on unknown provenance: `requires_forced_review = not 
  is_phone_origin(obs)` — auto-approve is now opt-in for syncthing ONLY; 
  file_upload, legacy phone, NULL, and any future source fail closed to 
  review. 26 NULL-provenance rows moved from auto-approve-eligible to 
  review-bound. Added an "Unknown origin — needs review" label so those 
  rows aren't mislabelled "File upload".

APPROVED-NO-SPECIES — named the legitimate state (both approve paths)
- "approved, identified, no species" is now a named valid state for 
  landscape/scene rows. Factored `qualifies_as_identified(obs)` (species 
  set OR obs_category=='landscape') into observation.py; both bulk_actions 
  and the shared observation_service helper use it. Fixed a second 
  instance the audit reported as clean — single-approve had the identical 
  gap (fix-one-twin-miss-the-other). One predicate, 4 call sites, zero 
  duplicated logic.

DATA REPAIR — the 6 drifted rows (all fixed)
- 3 landscape (8771/9645/9827): repaired to approved+identified+NULL.
- 9827 stale candidates cleared (10 Canis lupus rows + json); row retained 
  as hazard reference.
- 8771 unlogged species-primary clear: backfilled the missing audit row 
  (timestamp unrecoverable — git reset 6 July — stamped honestly, inference 
  in a log, not fabricated).
- 3 plant (21562/21770/21771): were P1 rows that failed ID only on PlantNet 
  timeouts. Deliberately re-opened (logged repair:reopen_for_reid) and 
  re-identified through the standard path with force_review=True. All three 
  identified this time (Thymus praecox, Campanula rotundifolia, Lactuca 
  muralis) — the (5,25)+retry fix worked where it previously timed out. 
  Now in review queue awaiting confirmation; none auto-approved.

DOCS — consistency pass (CLAUDE.md, architecture.md, scan.py comment)
- uploads/ corrected to primary-image-store; scan.py identification.py 
  stale ref replaced; architecture.md date + canonical start command; 
  timestamp convention (UTC DB vs local filenames) documented; the three 
  shared predicates and the scene-state exception recorded as canonical, 
  with "do not "fix" this as drift" flagged.

**In the review queue (awaiting your confirmation, not urgent):**
21562 Thymus praecox (edible), 21770 Campanula rotundifolia (edible), 
21771 Lactuca muralis (CAUTION) — all edibility_verified=0, provisional 
species links, low_confidence. The caution one wants a conscious confirm.

**Carried, unchanged:** 3 damaged map rows (17052/17737/18709); Retry-ID 
buttons absent on below_threshold cards; snapshots gzip option (~700M win); 
thumbnails_quarantine purge.

**Pending / next:** none from this session's audit — all findings closed. 
Next work is a separate fix (new thread).

### Current State — 19 July 2026

**Session focus:** Checkpoint list follow-through — P1 auto-scan hardening, 
identification.py:324 fix verification (now scan.py:1343), terminal-status 
guard bug, defence-in-depth species-card count filter, watch-dir silent-skip 
logging, launch.json port documentation.

**Completed and verified this session:**

- Confirmed identification.py:324 no longer exists; live no-candidate gate 
  is scan.py:1343-1379. Harness-verified: transport failure → needs_review, 
  file intact, cause named in log. Branch fires ~4,574 times total (335 
  syncthing, 4,239 file_upload) — corrects earlier "rare" framing, which 
  described the now-deleted old path.

- Fixed terminal-status guard bug at scan.py:1343-1379: only review_status 
  was protected against a retry-identify re-run on a finalized row; 
  identification_status, species_id, species_candidates_json, and 
  processing_stage were unguarded and could silently wipe a human-locked 
  species assignment on any approved/manually_verified/rejected row. All 
  four now gated by is_terminal_review_status(). Verified across all three 
  terminal statuses plus a non-terminal control (still routes normally). 
  Log message corrected — no longer claims "sent to review queue" on a row 
  that wasn't.

- Recon on 6 rows matching the pre-fix corruption signature (8771, 9645, 
  9827, 21562, 21770, 21771): audit trail confirms none were caused by 
  this bug — all deliberately human-approved landscape/scenery photos with 
  no species ever assigned, or (9827) a deliberately-removed bad ID (dog 
  misID at 1866% score). Nothing to restore. Real drift cause identified 
  instead: bulk_actions.py:107 (_bulk_review_task) sets review_status 
  without syncing identification_status — deferred, see Pending.

- Added defence-in-depth two-field filter to species-card count query 
  (culinary.py:88-96), matching map.py's identification_status='identified' 
  clause. Verified no-op on current data (2,114 before/after, ORM and live 
  endpoint both confirmed) — guards a currently-unreached state.

- PlantNet timeout confirmed correct, no drift: (5,25) tuple + bounded 
  retry live at plantnet.py:60/253-276. Apparent conflict with a 16 July 
  httpx form was a different module (inaturalist.py) — false alarm, closed.

- uploads/ recon: nothing reclaimable, 0 orphaned bytes. Confirmed still 
  the primary image store (12,239 of 13,836 observation file_paths), not 
  "browser-uploaded pending photos" per CLAUDE.md — doc correction still 
  outstanding (see Pending). 36G→3.7G explained: cumulative 
  delete_observation_file() on rejected rows over time, not a migration.

- ~11 "never-ingested" P1 photos: recon reversed the premise. All 11 were 
  previously ingested, human-reviewed, and deliberately deleted — now 
  correctly blacklisted. Not lost data; do not re-ingest without an 
  explicit DELETE FROM deleted_hashes decision (not made this session).

- Fixed bare except: pass at syncthing.py _auto_scan_loop tick: now logs 
  via three channels (stderr w/ traceback, _state["errors"], 
  processing_logs) through a must-not-raise helper. Verified via harness 
  and live production.

- Fixed unlogged blacklist skip in _find_new_files: blacklisted-hash skips 
  now log via ingest_guard.blacklisted_skip(), source="p1_autoscan_filter", 
  deduped once per hash per process lifetime. Ordinary duplicate skips 
  remain silent, unchanged. Verified live: 12 rows / 12 distinct hashes, 
  held steady across ~45 ticks.

- Fixed watch-dir silent skip (photo_library_path missing/misconfigured): 
  now logs via _record_watch_dir_missing, same three-channel bar, latched 
  on path value not per-tick. Harness-verified 4 cases incl. no false 
  positives.

- launch.json port 8001 (vs documented 8000): confirmed deliberate — 
  separates tool-launched preview servers from the manually-run dev server 
  on 8000. Left as-is, added an inert in-file comment. No change needed.

**Retracted this session (both self-caught before any write):**

- The 2,161 vs 2,155 map/card-count "discrepancy" that drove the 
  culinary.py fix did not exist in the app — it came from an ad-hoc query 
  reported as app behaviour without being run through the live code path. 
  Real numbers: card count 2,114, map pins 2,131 (map shows more, not 
  fewer — inverse of what was assumed). Gap judged not worth pursuing.
- A reported "raw control character in /api/species/ JSON" was a 
  diagnostic-harness artifact (zsh's echo interpreting \n as a literal 
  newline), not an app defect. Live endpoint parses cleanly.
- Pattern to carry forward: any anomalous number from an ad-hoc diagnostic 
  script needs to be reproduced through the real code path before being 
  reported as a finding — both retractions shared this root cause.

**Known issues / notes:**

- Unplanned live write: editing syncthing.py under --reload --reload-dir 
  app hot-reloaded the running production server mid-session, firing 12 
  real blacklisted_hash_skip rows to the live DB before any deliberate 
  test ran. Append-only audit rows only, nothing destructive, no snapshot 
  taken beforehand. Going forward: any edit to a module backing an active 
  background loop should be flagged as a live write before editing, not 
  discovered after.
- scan.py:1380 log message still says "no species assigned" on the 
  terminal-guard path, where the species is now correctly retained — 
  one-line wording fix, left alone deliberately, not urgent.

**Working tree — uncommitted:**
Modified: app/api/culinary.py, app/api/scan.py, app/api/syncthing.py
Untracked/edited: .claude/launch.json (comment added, port unchanged)
All changes harness- and/or live-verified individually. Nothing committed 
yet — this End Session should commit all four together.

**Pending / next (priority order):**
1. bulk_actions.py:107 — sync identification_status on bulk-approve, or 
   formalize "approved, no species" as a legitimate state. Deferred design 
   call, currently inert in practice.
2. CLAUDE.md's uploads/ description is wrong — it's the primary image 
   store (88% of observations), not "browser-uploaded pending photos." 
   Fold into next doc-accuracy pass.
3. scan.py:1380 log wording — cosmetic, whenever convenient.

**Carried, unchanged from prior sessions:** 3 damaged map rows 
(17052/17737/18709); Retry ID buttons absent on below_threshold cards; 
snapshots gzip option (~700M win); thumbnails_quarantine purge.

### Current State — 10 July 2026

Fixes session across three areas: species-card save integrity, safety/edibility 
editing, and taxonomy tree species-link crossing.

SPECIES CARD — save integrity + SW cache:
- Tansy (Tanacetum vulgare, sp 194) investigated for a "saved but not showing" 
  report. Write integrity was CLEAN — human edit landed correctly (history 2780, 
  changed_by='human'), matched live, no race, prefix is stored not rendered. Root 
  cause was the service worker: SPECIES_CACHE (foragingid-species) is deliberately 
  version-independent, cache-first, 7-day TTL, with NO invalidation hook in the 
  save flow — so every species-card edit showed stale until hard-reset.
- FIX shipped: extended sw.js 'clear-species-cache' message handler to accept an 
  optional targeted url (single-entry delete); wired species.html saveEditMode() to 
  invalidate the current species' /profile cache entry after save, before 
  loadProfile() re-fetches. offline.js's existing whole-cache-clear caller unchanged.
  NOTE: needs Melvin's normal-reload verification (edit field, save, F5, confirm 
  fresh) — not yet confirmed live.

POLYGALA ALPESTRIS (sp 696, "Mountain milkwort") — content write:
- edible_parts + preparation_warnings written (human-dictated, verbatim, 
  old_value=NULL confirmed true-empty, changed_by='human', read-back verified). 
  Snapshot db_20260709_210257.
- edibility_status: unknown → edible, on explicit confirmation only (separate 
  snapshot db_20260709_210551). edibility_verified left 0 deliberately.
- OPEN CONTENT ITEM: edible_parts text names "Polygala amara" (not in DB) and 
  "Polygala vulgaris" (a different species, sp 221) in a parenthetical now attached 
  to alpestris's card. Left as-is pending Melvin's decision on whether to trim it.

SAFETY/EDIBILITY EDITING — bug found, two fixes queued:
- Root cause of "can't edit safety warnings": read-view SAFETY branching only emits 
  an editable [data-field-key] element when species is hazardous OR a warning field 
  has content. Non-hazardous + empty species (unknown status, severity none) expose 
  no edit target at all — not a lock, a render gap.
- PROMPT B (safety fields always editable in edit mode) — WRITTEN, RUNNING as of 
  session end. Frontend-only; both fields already allowlisted in the existing 
  culinary field endpoint. Needs Melvin's live verify.
- PROMPT C (edibility_status editing with confirm dialog) — WRITTEN, NOT RUN. To 
  check tomorrow. Adds migration 0046 species_edibility_history (field/old/new/
  changed_by/note, forward-only), status-only mode on existing PATCH 
  /api/edibility/status/{id} (verified: Optional[bool]=None, only writes verified 
  when not None), retrofits history logging to both /status/{id} and /bulk-status, 
  confirm dialog on the badge with current→new + relax-warning + optional note + 
  cache invalidation. Toxic/caution route through the coupled (verified:true) path 
  by design — status-only toxic would create a deadly verdict the review queue never 
  flags (queue catches caution+unverified but not toxic+unverified). Recon confirmed 
  decoupling status from verified is safe (all 9 read sites walked).

TAXONOMY TREE (frontend/taxonomy.html) — species-link crossing RESOLVED:
- Budget lifted this session (PLANT_ARC no longer fixed at 207°). Replaced last 
  session's genus/species min-gap (PAVA) blocks — which hit a hard ceiling because 
  genus spacing is uniform tree-wide with no slack — with proportional angular SLOTS: 
  genus slot = GENUS_SLOT_UNIT(0.65°) × max(1, species_count), species fanned strictly 
  within own slot. Removed dead _enforceMinAngularGap helper.
- Final arcs: PLANT_ARC 297.700°, FUNGI_ARC 59.300° (+ 2×1.5° gap = 360.000° exact). 
  FUNGI_ARC now computed, not the old fixed 150°. Fungi internal crowding at its new 
  width NOT yet reviewed — flagged as separate future pass.
- Crossing had a second cause one tier up: family nodes sat at stale pre-slot 
  cluster angles (81/84 families off >1°, up to −27°) while genera moved to slots. 
  Genus↔species was already exact by construction. FIX: family-only bottom-up 
  recenter (family.ang = midpoint of genus children's span), recompute px/py. 
  Order/class deliberately EXCLUDED — recentering them would clobber the 8-July 
  hand-tuning (locked-anchor class redistribution, order PAVA min-gap); Code hit 
  the guard, stopped, reported, did not override.
- Radii unchanged throughout (RING=200, TRUNK_RING=230, FAMILY_RADIUS=600, 
  species=1000). Verified live at rest + on family/order/class/species click — all 
  read clean, no crossing. Melvin sitting with the shifted genus layout before 
  deciding if the slot spread is right.

Pending / next:
- Verify SW cache fix + Prompt B live (normal-reload checks)
- Run Prompt C tomorrow (edibility_status edit UI) — check output before verifying
- Decide Polygala alpestris "Polygala amara/vulgaris" parenthetical
- Structural gap (logged, not urgent): species.edibility_status has no history 
  table today — Prompt C's migration 0046 addresses this going forward
- Deferred, not urgent: GENUS_SLOT_UNIT tuning if genus spread feels off after 
  living with it; genus/species label crowding in big families (needs radius-lock 
  lift or zoom-gated genus labels); fungi-fan internal crowding at new 59.3° width
- Pre-existing (predates this work, not introduced): "flag for review" button shows 
  misleading state for 55/65 verified species (edibility_human_verified depends on a 
  history row nothing currently writes)

### Current State — 8 July 2026

Taxonomy tree (frontend/taxonomy.html) — spacing, highlighting, and colour 
passes complete for this session.

Spacing (class + order tiers):
- Class tier (6 nodes): evenly redistributed, Magnoliopsida + Bryopsida locked 
  as anchors, Pinopsida included after diagnostic showed it was near-crowded 
  too. Now always-visible (removed from zoom-gated visibility function) — no 
  crowding left to gate against.
- Order tier (~40 nodes): minimum-gap enforcement, not uniform redistribution — 
  preserves d3.cluster's density-proportional spacing where it already works, 
  only pushes apart nodes below the minimum readable gap. Stays zoom-gated 
  (correct — not all ~40 need to show at rest).
- d.rad/RING/TRUNK_RING/FAMILY_RADIUS untouched throughout — angle-only changes.

Highlighting:
- Click/focus now lights up full ancestor path (parent chain to root), not 
  just the selected node + descendants.
- Sibling tier (same immediate parent) gets intermediate opacity, midpoint of 
  existing bright/dim values.
- Intermediate tier propagates down through sibling's own subtree (e.g. 
  sibling genus's species also go intermediate, not just the sibling genus 
  node itself).

Species-tier links:
- Changed from enter/exit-toggled to persistently visible at low ambient 
  opacity, always in the DOM. Deliberate design choice (Melvin likes the look) 
  that also structurally closes a recurring residue bug (see below).
- Known follow-up, not yet actioned: species links from different sibling 
  genera can visually cross in the fixed species ring when highlighted 
  together, since species aren't locally grouped by genus in that ring. 
  Deferred — real fix would be sorting species order within the ring to match 
  sibling-genus adjacency. Revisit only if it becomes a visible problem.

Colour:
- Class/order/family labels now get distinct, subtle white-based tints 
  (blue/red/yellow) instead of flat white — first attempt used bark-derived 
  amber tones and was a legibility regression, corrected on the spot.
- Same tint-per-rank scheme extended to fungi-fan class/order/family labels — 
  reused the exact same CSS rules (rank-keyed, kingdom-agnostic), not new 
  values. Fungi node-dot colour and lichen species colour-carve-out untouched.
- Legend updated to match.
- Brown-appearing genus/species dots investigated: confirmed NOT a colour 
  scheme bug — species and genus share identical fill (#3f9e52); "brown" is 
  the collapsed-ring stroke artifact on collapsed genus nodes. No fix applied, 
  none needed.

Bug fixed: recurring unnamed-D3-transition collision (3rd occurrence in this 
file) caused a full label blackout after the initial class-tier edit, and was 
the suspected (not fully live-confirmed) cause of a deselect residue bug — 
made moot once species links stopped exit/entering the DOM.

Standing process change: CLAUDE.md updated with new "Frontend / D3 Rendering 
Discipline" section — mandatory named transitions on shared elements, loud-fail 
on anchor lookups, honest unverified-vs-confirmed declaration language, and 
blast-radius tracing before declaring a shared-function change done. Applies 
project-wide, not just taxonomy.html.

Pending / minor:
- Hex values for the new white-tint rank colours weren't printed in Code's 
  report as instructed — worth holding Code to this next time rather than 
  chasing it down now.
- Species-link crossing (above) — watch, not yet a confirmed problem.

### Current State — 03 July 2026

Audit-completion + snag cleanup session. Closed this session:
- _auto_merge_into edibility_rating AttributeError (stray non-existent field in merge copy-list, removed)
- Snapshot path divergence — confirmed none; End Session and /api/dev/snapshot share one code path
- End Session UI — removed redundant phase/next-steps boxes, single Current State textarea only
- primary_source_url unprotected overwrite — guarded at both call sites (enrichment.py main path + trigger_ai_drafts_for_species gap)
- CLAUDE.md stale snapshot path — both occurrences (line 85, 174) corrected to project-local path
- Guest-token coverage gap (audit finding #1 addendum) — save_api_key + 2 about.py mutating endpoints migrated from host-only is_guest_request() to token-aware get_identity(), closing a real gap where a local-wifi workshop guest token could overwrite owner API keys
- 625 (Betony) medicinal_notes — stale "Betonica officinalis" text corrected to "Stachys officinalis" (identity columns already flipped under finding #2; only the field text lagged)
- obs 9409 species_primary/species_id desync — resynced (same pattern as earlier Lepista/Collybia case)

Still open:
- GDrive token — parked; re-paste attempt didn't persist (updated_at unchanged), needs Melvin to retry and confirm the save actually lands
- Species 412 (Thelypteris limbosperma) — primary_source_url points to Oreopteris quelpartensis, a taxon documented as East Asian/Pacific Northwest, likely NOT the same plant as the European Mountain Fern this card describes. Elevated risk of wrong-species-source (finding #3 pattern), not a naming/synonym issue. Recommended for #3b's verification scope.
- Hypericum genus — 11 approved observations correctly identified, no systemic confusion found; one desync fixed (above); 3 observations (17172, 17178, 21554) have no persisted candidate data (minor, unresolved). Validated stem cross-section distinguishing feature (2-ridged perforatum vs 4-ridged/hollow maculatum, also separates tetrapterum) ready to add via species_lookalikes/look_alike_warnings — pending decision on who drafts the verbatim text.
- Audit finding #3b (silent text-substitution detection) — not started; scope decision pending, now concretely includes verifying 412
- Audit finding #5 (card-level approval design) — unblocked, design conversation not yet started
- Enrichment gap remediation — 9 AI drafts pending approval, 6 species never scanned, 79 no-PFAF species need alt-source decision
