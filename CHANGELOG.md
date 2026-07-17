## Current State

## Current State

Two small corrections to your End Session block, since it's already submitted and these are now stale:

"Restart uvicorn manually / nothing confirmed live until this happens" — done, and the fresh server proved the deletions.
"Dead endpoint cleanup — prompt written, not run" — run, verified live.

## Current State — 10 July 2026

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

## Current State — 8 July 2026

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

## Current State — 03 July 2026

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

## History

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
- GAP (unfixed, reported): deleted_hashes is irreversible — no code path removes a row. Manual DELETE FROM only
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
