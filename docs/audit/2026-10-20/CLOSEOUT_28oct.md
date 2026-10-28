# Audit closeout + GPT UI digest, 28 Oct 2026

Read-only. No DB or code writes were made for this report. Every count below comes from `sqlite3 -readonly data/foragingid.db` or from read-only GETs against the running server on localhost (curator tier). The SQL is shown where a count is involved. "CL" means a CHANGELOG History entry, identified by its timestamp.

Part A of the same session (removeFromList → lmJsArg, sw v20, loadFeatures timer guard) is commit `3403705` and is not repeated here.

---

## 1. Section 9: batch status

| Batch | Status | Evidence |
|---|---|---|
| 1 | done | CL 2026-10-20 21:11 (D3-01 drafts 3178–3238, B3-02 old_value fix) |
| 1b | done | CL 2026-10-21 19:05: walk 4 republished (site `ed3b4d9`) |
| 2 | done | CL 2026-10-20 21:21 (E-01/E-02 backup API) |
| 3 | done | CL 2026-10-20 21:32 (B2-02, B2-05 data) |
| 3b | done | CL 2026-10-21 04:44 (verdict-draft approve path, 212 drafts) |
| 4 | done | CL 2026-10-21 10:23 (A-02, D1-01) |
| 5 | done | CL 2026-10-21 12:28 (B2-01, B2-04, B2-09, safety-gate.js) |
| 6 | done | CL 2026-10-21 16:24 (B2-03, E-14) + 16:26 E-14 cleanup |
| 7 | done | CL 2026-10-21 20:45 (token-layer access, A-03 loopback-peer rule, escaping sweep) |
| 8 | done (B5-01, B5-02, B5-05); **B5-03 open** | CL 2026-10-22 16:46 (deny-by-default guest API, `app/services/guest_access.py`). B5-03 is in §2 |
| 9 | done | Code in snapshot commit `b1138f0` (22 Oct 21:11). That session has **no "Built" History entry**; the evidence is `tests/test_followups_batch9_10.py` (kingdom-audit guard, reject-undo, terminal evidence). B1-02 data: CL 2026-10-22 21:40. Read back today: obs 17052 and 17737 are `needs_review`/`identified` (still waiting for your review) |
| 10 | done | Same commit and test file (C-02, E-05c, E-05g). C-01 data: CL 2026-10-22 21:40. Read back today: 131/131 rows from `c01_copy_plan_2026-10-22.json` have `confirmed_copy_path` set |
| 11 | done | CL 2026-10-25 18:58 (C-06, B2-07, B2-08 data, new-card helper) |
| 11b | done | CL 2026-10-28 03:17 (merges, genus/family pass), plus 03:27 / 04:00 / 04:13 follow-ups |
| 12 | partly | CL 2026-10-25 19:57: C-05 done, D3-02 done. **D3-04 open** (decision: redirect). **D3-05 partly** (the plan shows renumbering; labels are not frozen) |
| 13 | **superseded** (A-04 done) | A-04: CL 2026-10-25 19:57 (secrets in `.env`). B4-01/B4-02: see §2 |
| 14 | done | CL 2026-10-20 21:43 + 22:17 |
| 15 | done | commit `94afbbe` (CL 2026-10-28 09:10) |
| 15b | done except item (4) | commit `0f47e98`. Item (4), the route-line zoom/drag bug, is in the Backlog (needs your repro) |
| 16 | done (unverified live) | commits `0cf780e` (prep) + `2b49db7` (split), CL 2026-10-28 13:24 |
| 17 | done | commit `5830833`. Spot checks: `APP_VERSION` at `app/config.py:14`; the 4 dead `app_settings` rows are gone; `your_db.db`/`current.txt` are untracked; no "80%" left in `app/api/syncthing.py` |

### ✅ corrections to the REPORT.md §9 table (report text only; applied 28 Oct on Melvin's OK)

The table currently marks only 1, 2, 3, 14 and 3b as ✅. Proposed:
1. **1b** → "✅ done 21 Oct (walk 4 republished, ed3b4d9)"
2. **4** → "✅ done 21 Oct"
3. **5** → "✅ done 21 Oct"
4. **6** → "✅ done 21 Oct"
5. **7** → "✅ done 21 Oct"
6. **8** → "✅ done 22 Oct (B5-03 still open)"
7. **9** → "✅ done 22 Oct (code b1138f0, data B1-02)"
8. **10** → "✅ done 22 Oct (code b1138f0, data C-01)"
9. **11** → "✅ done 25 Oct"
10. **11b** → "✅ done 28 Oct"
11. **12** → "◐ partly 25 Oct (D3-04 open, D3-05 partly)"
12. **13** → "superseded by batches 7 + 8 (deny-by-default); A-04 done 25 Oct"
13. **15, 15b, 16, 17** → "✅ done 28 Oct" (15b: "item 4 in Backlog")

---

## 2. Every finding ID

**Settled (no action):** B1-01 (no veto), A-01 (curator link by default; refreshable link built in batch 7), B3-01 (rename clears text), E-13 (no finding).

| ID | Status | Evidence |
|---|---|---|
| A-02 | done | batch 4 |
| A-03 | done | batch 7 (`app/services/access.py`: localhost = local Host + loopback peer + no X-Forwarded-For) |
| A-04 | done | batch 12 entry (CL 25 Oct 19:57). Still pending: rotate the DeepSeek key |
| A-05 | done | batch 17 (tracked junk `git rm`'d). The `data/` deletions are yours (decision 17) |
| A-06 | superseded | decision 18: document only |
| A-07, A-09 | done | batch 17 (4 rows deleted, snapshot db_20261028_082151) |
| A-08 | settled | mark-verified kept as a 410 stub (Current State 28 Oct) |
| A-10 | done | batch 17 |
| B1-02 | done | batch 9 data; rows are in Review for you |
| B1-03, B1-05, B1-06 | done | batch 9 (b1138f0, tests) |
| **B1-04** | **open** | Obs 8196 is still `review_status='not_applicable'`; `trust.py:732` still writes that value |
| B1-07 | done | batch 17 (stale comment fixed) |
| B1-08 | done | batch 14 part 2 |
| B2-01 … B2-05 | done | batches 3 / 5 / 6 |
| B2-06 | done (data) | census chunk_01 (CL 21 Oct 14:18), recon 22 Oct |
| B2-07, B2-08 | done | batch 11 |
| B2-09 | done | batch 5 |
| B2-10 | done | CL 21 Oct 14:18: "one culinary rule". `culinary_allowed` delegates to `safety_decision` (`app/models/species.py:493`) |
| B3-02 | done | batch 1 |
| **B3-03** | **open** | `approved_by` has `default="human"` (`app/models/species.py:131`). `SELECT status, COUNT(*) FROM species_ai_drafts WHERE approved_by='human' AND approved_at IS NULL GROUP BY status` gives pending 229, invalidated 1804, rejected 301, stale 3 |
| B3-04 | done | batch 3b |
| B3-05 | done | recon 22 Oct ("fixed") |
| **B4-01** | **superseded** | The guest gate is deny-by-default for writes (`guest_access.py`, 3 allowed paths). I evaluated `guest_api_allowed()` directly: POST `/api/dev/restore`, DELETE `/api/observations/1` and POST `/api/recipes` are all refused. A curator-tier device can still reach all 116 endpoints, which is by design (A-01 settled). The "dependency on the 116" was never built; it would add defence in depth only (recon 22 Oct: "B4-01 still worth it?" was never decided) |
| **B4-02** | **superseded** | Same middleware. DELETE `/api/notes/5`, POST `/api/edibility/lookalikes` and POST `/api/walk/saves` are refused for guests. The handler-level inconsistency remains (`notes.py:74` has no guard), but is unreachable by a guest |
| **B5-03** | **open** | `app/api/map.py:264` `"description": row.reviewer_notes` for every pin, and `/api/map/geojson` is on the guest allowlist. 444 confirmed non-landscape pins carry notes (`SELECT COUNT(*) FROM observations WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND review_status IN ('approved','manually_verified') AND identification_status='identified' AND species_primary IS NOT NULL AND reviewer_notes<>''` → 444, 0 landscape), e.g. "Auto-rejected: iNat kingdom=Insecta …", "13% — check T. officinale vs Hyoseris …" |
| B5-01, B5-02 | done | batch 8 |
| **B5-04** | **open** (design gap) | No sensitive-species concept (grep finds none). Walk 4 had no exposure; walk 5 is not checked |
| **B5-05** | **superseded / done** | Batch 8 allowlist. `guest_api_allowed('GET', …)` is refused for `/api/dev/changelog`, `/current-state`, `/snapshots`, `/api/queue/list`, `/queue/sse`, `/api/identify/test-connection` and `/api/sharing/lan-url`; `tests/test_batch8_guest_and_culinary_warnings.py:373` covers `queue/list` |
| C-01, C-02 | done | batch 10 |
| C-03, C-04 | done | batch 14 part 2 |
| C-05 | done | batch 12 |
| C-06 | done | batch 11 |
| C-07 | done | `resolve_species_id` falls back to name_key (`species_link.py:138-139`) |
| C-08 | open (low) | disk residue; any delete is yours |
| D1-01, D1-03 | done | batches 4 / 14 |
| **D1-02** | **partly** | The 140-character look-alike cut was removed (batch 6). Browser print still has no disclaimer (`grep -ci disclaimer frontend/print.html` = 0) |
| **D1-04** | **partly** | *Rosa dumalis* family is now Rosaceae. Species 486 *Acer pseudoplatanus* `preferred_common_name` is still "Acer ser. Acer" |
| D2-01 | done | batch 14 |
| D3-01, D3-02, D3-05 | done / done / partly | batches 1, 12 |
| D3-03 | accepted | Still regex-coupled, but fails loud (`StyleDrift`); repointed in batch 16 |
| **D3-04** | **open** | `export.py:590` mirror_dir `w/<slug>` (decision pending) |
| E-01 … E-04 | done | batches 2 / 14 |
| E-05 | mostly done | a/b/c/g done (batches 10, 15). The rest is inventory |
| E-06 | partly | E-05c logging done. The job/heartbeat `except: pass` sites are not revisited |
| E-07, E-09, E-12 | done | batch 17 |
| E-08 | partly | index.html split (batch 16). Other large files remain |
| E-10 | superseded | 45 test files, plain scripts + jsc (decision 30) |
| E-11 | open (known) | Reload cancels jobs; mitigated by procedure (check `/api/processes/active`) |
| E-14 | done | batch 6 + CL 21 Oct 16:26 |

---

## 3. GPT UI audit digest

### 1. Booklet Seasonal Returns — **confirmed (safety)**
- **Default 10:** `lists.html:1832` `_loadSrLimit()` returns `'10'`, and `<option value="10" selected>` is at `lists.html:1018`.
- **Selection rule:** `_fetchAndCacheSr` (`lists.html:1841-1858`) fetches `/api/notifications/seasonal-returns?all=true` and keeps the top N of the **whole archive** (`items.slice(0, limit)`). It is independent of the species on the list; only "Foray only" filters to the list. So selecting only elder still adds 10 archive species.
- **Ranking** is in `app/services/seasonal_returns.py:206-212`: now before soon, then most recent, then count. Candidates are any species with a confirmed observation or an encounter.
- **Gate: none.** Neither `compute_seasonal_returns` nor `_seasonalReturnsHtml` (`lists.html:1867`) reads `edibility_status`, `toxicity_severity` or SafetyGate. Curator-picked list species go through `_workshopPage`/SafetyGate; Seasonal Returns entries do not.
- **Live (GET, today), top 10:**
  - #3 *Digitalis purpurea* (toxic / **deadly**)
  - #8 *Dryopteris filix-mas* (toxic)
  - #9 *Heracleum sphondylium* (edible; Apiaceae)
  - Further down the full list: *Aconitum napellus* #33 and *Taxus baccata* #76 (both deadly). They are reachable via "Foray only" when they're on the list.
- **Print view and PDF use the same items:**
  - `print.html:645` reads the cached `foragingid_sr_data` that Lists wrote.
  - The PDF gets the same array (`print.html:716` → `lists_pdf.py:289` → `print_pdf.html:266-276`).
  - The rule is the same everywhere, and there's no gate on any surface.

### 2. Workshop booklet preview — **confirmed**
- **"..." identification:**
  - The data holds `id_notes = '[iNaturalist] ...'`. `LmMd.stripCitations` removes the bracket, which leaves "...". It's printed under "Identification" (`lists.html:2059-2063`) and "Field ID notes" (`_fieldGuideBlock`, `:1942`).
  - Elder (107) is one of these. `SELECT COUNT(*) FROM culinary_info WHERE trim(id_notes)='[iNaturalist] ...'` → **9**.
  - Separately, 113 `id_notes` end in "..." / "…" (truncated iNat summaries).
- **Repeated caution:** one workshop page prints the warnings up to **3 times**:
  - the safety box `_printWarnings` (`:2036`, full text),
  - then `_printCulinaryWarnings` before Foraging/Culinary (`:2120`),
  - then again inside Recipe (`:2046`).
  - Batch 8's own rule was "no repeat where the species block sits beside", and the safety box sits on the same page.
- **Medicinal preparations:**
  - `lists.html:2054` (and `print.html:545`) push `cul.traditional_uses` into the Medicinal section. For elder that's PFAF's "Other uses" ("Compost Cosmetic Dye Fungicide Hedge … Wood").
  - 352 species have non-empty `traditional_uses` (`SELECT COUNT(*) FROM culinary_info WHERE traditional_uses IS NOT NULL AND trim(traditional_uses)<>''`).
  - The PDF (`lists_pdf.py`) does not use `traditional_uses`, so this is browser Lists + print only.
- **Empty sections** are skipped when there's no text (`medBits.length`, `idn` checks). "..." is non-empty text, so it isn't skipped.

### 3. Data Trust "688 auto-approved below 60%" — **confirmed as a label bug, not auto-approvals**
- `trust.py:62-66` and `:89-96` define "auto-approved" as `review_status='approved' AND human_corrected=0`. That includes every human ✓ approval.
- The score field is `top_score`, the top candidate's listed score (`scan.py:1805-1807`), **not** the gating `min(combined, vision)`.
- Breakdown (set `B` = `review_status='approved' AND human_corrected=0 AND top_score<0.60 AND top_score IS NOT NULL`, 688 rows):
  - **upload_source:** syncthing 543, file_upload 145. All 688 have `reviewed_at` set.
  - **Import month (created_at) × source:**

    | Month | syncthing | file_upload |
    |---|---|---|
    | 2026-05 | 149 | 15 |
    | 2026-06 | 184 | 126 |
    | 2026-07 | 110 | 4 |
    | 2026-08 | 5 | 0 |
    | 2026-10 | 95 | 0 |

  - **Approval path** (latest `observation_edits` row with field_name='review_status', new_value='approved'): `human` 664, `system:fix1_restore` 23 (29 May), `hazard_review:22oct-revert` 1.
  - **Processing log:** exactly **1** of the 688 has a real auto-approve log (`message GLOB '*— Auto-approved —*'`). Obs **9536** *Prunus brigantina*, 30 May, "Auto-approved — plantnet 81.57%": the old single-source rule, before dual agreement. Its stored `top_score` is now 0.0059.
  - **Overall:** of all currently approved rows with a real auto-approve log, 191 are ≥0.70 and 1 is <0.60 (9536).
- Threshold settled: history only, as asked.

### 4. Photo viewer / "fungi detected" — **confirmed (both)**
- **Viewer:**
  - `sightings.html:356` builds the lightbox caption from `displayName(o)` + date only. The grid tile shows "pending review" (`:260-263`), but the viewer drops it.
  - The map deep-link marker shows only "Observation #id" (`pins-filters.js:577`). The species-page observations endpoint is confirmed-only (`culinary.py:1663`).
- **"fungi detected":**
  - `review.html:1952-1953` shows "⚡ fungi detected" exactly when `category_suggested` ≠ `obs_category`.
  - `scan.py:1636-1638` sets it when iNat's top hit is Fungi and the row is plant. It is a suggestion by design, but the wording reads as a fact.
  - `SELECT review_status, obs_category, category_suggested, COUNT(*) FROM observations WHERE category_suggested IS NOT NULL AND category_suggested <> COALESCE(obs_category,'plant') AND review_status IN ('needs_review','pending') GROUP BY 1,2,3` → needs_review / plant / fungi **46**.
  - Minor: `${obs.category_suggested}` is not escaped (fixed vocabulary).

### 5. Source links — **confirmed (all five)**
- **Elder → ground-elder page:**
  - Source is `culinary_links_json` from the site-search fetcher (`app/integrations/culinary_links.py`; the search for "elder" also matched Galloway's ground-elder page).
  - Elder (107) has 7 links: the ground-elder page and 3 generic Brill pages (curriculum / day-camp / scout).
  - Brill generic pages across species: `SELECT COUNT(*) FROM culinary_info WHERE culinary_links_json LIKE '%wildmanstevebrill.com/curriculum%' OR … day-camp … OR … scout …` → **45**.
- **Duplicate PFAF:**
  - `species.html:2858-2869` `_renderSources` adds a chip for `primary_source_url`, then one for each `sources_json` entry with no dedupe against it (only `enrichmentSources` are deduped).
  - `SELECT COUNT(*) FROM culinary_info WHERE primary_source_url LIKE '%pfaf.org%' AND sources_json LIKE '%pfaf.org%'` → **442**.
- **"iNaturalist" → Wikipedia:**
  - The source entry stores iNat's `wikipedia_url` under the label "iNaturalist" (elder: `{"source": "iNaturalist", "url": "http://en.wikipedia.org/wiki/Sambucus_nigra"}`).
  - `SELECT COUNT(*) FROM culinary_info WHERE id_notes_sources_json LIKE '%"source": "iNaturalist", "url": "%wikipedia.org%'` → **593**.
- **Bare domains:** `settings.html:2029` `href="${_esc(s.url)}"`. `SELECT id,label,url FROM data_sources WHERE url NOT LIKE 'http%'` → **14 rows (ids 21–34)**, e.g. `gallowaywildfoods.com`, which resolves to `/gallowaywildfoods.com`.

### 6. Taxonomy / thumbnails / Background Processes — **not reproduced; one cause structural**
- **Taxonomy:**
  - `GET /api/species/taxonomy-tree` → 200, 0.46 s, 44 KB.
  - The "Failed to load" branch (`taxonomy.html:1385-1393`) fires only on a fetch, HTTP or JSON failure. The console line `taxonomy-tree fetch failed:` names which one.
  - Likely an app/ reload window or a 401 on another origin. **Needs your browser console.**
- **Seasons/Discover thumbnails:**
  - Not reproduced as curator: 1,239 unique thumbnail URLs from `/api/timeline/at` (every 10th day of the year) all return OK, including 19 with spaces.
  - Discover (`map-core.js:794-796`, `/api/nearby`) also returned OK.
  - Suspect the guest media gate (only confirmed observations) or offline. **Needs your browser:** which device or tier, and one broken image's URL.
- **Background Processes:**
  - `settings.html:2242-2303`: one `try` wraps the fetch **and** the row rendering, so any render exception shows "Could not reach server." (`:2302`).
  - Today `/api/processes/active` → `[]` ("No processes running").
  - **Needs your browser console** at the moment it appears.

### 7. Recipes — **confirmed**
- **Warning as title:**
  - Recipe 258 (species 355) has no title. Its body starts "Always cook well; some people react, so try a little first. …", and `recipe_display_title` (`app/models/species.py:797`) takes that first sentence.
  - `is_safety_note_line` (`:780`) matches only lines starting safety/caution/warning.
  - Live `/api/recipes`: 238 recipes, **22 `needs_title`**, 1 warning-like title (258).
- **"Spring Beech Leaf Salad" under Autumn:**
  - Recipe 74 (*Fagus sylvatica* 329) has `season='autumn'`.
  - Cause: the season is guessed at draft-approve time by keyword counts over the text (`culinary.py:2445-2458`; "beechnut", "autumn", "harvest" outnumber "spring"). Species 329's `peak_season` is "Spring, Summer".

### 8. Import summary 288 = 15 + 178 + 0 — **confirmed**
- Session `scan_sessions` id 120 (28 Oct 05:19, pipeline 1): received 288, processed 288, approved 15, review 178, failed 0, **files_duplicate 95**.
- Duplicates increment `files_processed` (`syncthing.py:799-800`).
- The P1 chips (`scan.html:2011-2018`) render received / total / approved / review / failed and never `files_duplicate`. The only reader is the "accounted" check at `scan.html:2549`.

### 9. ID review queue count — **reconciled**
- `SELECT COUNT(*) FROM observations WHERE review_status='needs_review'` → **588** (GPT's 589 was one row earlier). The badge reads the same `REVIEW_QUEUE` (`app/services/observation_counts.py:41-44`).
- **By `review_label`:**

  | review_label | rows |
  |---|---|
  | low_confidence | 349 |
  | failed_id | 107 |
  | non_plant | 55 |
  | 11b_review | 28 |
  | hazard_candidate | 20 |
  | hazard_review | 18 |
  | genus_reid | 6 |
  | manual_review | 2 |
  | none | 2 |
  | bryony_check | 1 |

- **By category / named:** plant + a name (species or suggestion): 414 (syncthing 332, file_upload 82). Plant, unnamed: 167. Fungi: 5. Landscape: 2.
- Your "~300" fits `low_confidence` (349) or named syncthing plants (332), not the whole queue.

### 10–14 (one line each)
- **10 Vocabulary:** status words are spread across sightings.html:255-263, review.html and scan.html chips, and Data Trust's "auto-approved" (item 3). There's no single label map. **M.**
- **11 Walk "93 min" / location prompt:** `walk-panel.js:117-119`, `:316` use the ORS duration, else `distance/80 m·min⁻¹`, with no stop time. A label change is cheap (**S**). The location prompt comes from `gps.js:47` `getCurrentPosition` (when it fires needs your browser).
- **12 Offline "not cached yet":** `settings.html:2166` reads `OfflineCache.getStatus()`. That's localStorage per browser and per origin, written by `offline.js:242` after the 6 s precache (`:322`). A new origin (ngrok vs localhost) or a skipped precache shows it. **S** (needs your browser for which device).
- **13 Branding / dev refs / overlaps:** most rename group 1 is done (batch 17). "ForagingID" left in user text: `settings.html:689` (a real backup path, kept on purpose). Dev words (P1/P2, batch) appear in scan, settings and review. Overlaps are visual only, so they need your browser. **M.**
- **14 Workshop vs foray vs walk objects:** `SavedWalk` (4 rows), `RecordedWalk` (7), `ForagingSession`/foray_session (0 rows), `ExperiencePublication` (2), `WorkshopSite` (0), `WorkshopParticipant` (2), `GuestToken`. Five overlapping concepts, two of them empty. Merging them is **L** and a design decision.

### Side notes found while checking
- 7 confirmed map pins have `reviewer_notes` starting "Auto-rejected:" (`… WHERE review_status IN ('approved','manually_verified') AND identification_status='identified' AND reviewer_notes LIKE 'Auto-rejected:%'`). The notes are stale; guests can see them via B5-03.
- `lists.html:2450` `addSessionSpecies('${safe}')` still uses the old escape-then-apostrophe pattern. It wasn't in Part A's scope.

---

## 4. One list, deduplicated (safety first)

| # | Item | Effort | Needs your decision |
|---|---|---|---|
| 1 | **Seasonal Returns ungated**: toxic/deadly species (*Digitalis* #3) printed "in season" with no safety status in Lists, print and PDF; the top 10 is archive-wide, not from the list (GPT 1) | S–M | **yes**: exclude toxic/deadly, show the ☠ badge + warnings, or limit to list species; and should the default stay 10 |
| 2 | **Wrong-species source link**: elder links the ground-elder page (different plant). Plus 45 generic Brill links (GPT 5) | M | **yes**: cleanup rule for `culinary_links_json` (per-link review vs title must name the species) |
| 3 | **Safety sentence as recipe title** (recipe 258); `is_safety_note_line` misses "Always…" (GPT 7) | S | **yes**: widen the predicate, or you type titles for the 22 `needs_title` |
| 4 | **Warnings printed up to 3× on a workshop page** (GPT 2) | S | **yes**: keep the safety box only on that page (doctrine: at least one full copy stays) |
| 5 | **"Medicinal preparations" holds traditional/other uses** in Lists + print (GPT 2) | S | **yes**: separate "Other uses" section, or drop |
| 6 | **B5-03 reviewer notes to guests** (444 pins) | S | **yes** (open since 20 Oct): curator-only, or landscape-only |
| 7 | **Viewer hides pending status** (`sightings.html:356`) (GPT 4) | S | no |
| 8 | **Data Trust "auto-approved" mislabel**: 687/688 are human/system approvals; the score is `top_score`, not gating (GPT 3) | S | **yes**: label/definition (use the auto-approve log or `edited_by`); and whether obs 9536 goes back to Review |
| 9 | "fungi detected" reads as a fact (46 rows) (GPT 4) | S | wording only |
| 10 | id_notes "[iNaturalist] ..." prints "..." (9 rows); 113 truncated summaries (GPT 2) | S | **yes**: clear the 9 to NULL (DB write, snapshot first) / hide placeholder text on render |
| 11 | Duplicate PFAF chip (442) + "iNaturalist" label on Wikipedia URLs (593) (GPT 5) | S | label choice ("Wikipedia via iNaturalist"?) |
| 12 | Bare-domain data source links (14 rows) (GPT 5) | S | render-time `https://` vs a DB fix |
| 13 | B1-04: obs 8196 `not_applicable` + `trust.py:732` still writes it | S | yes (convert to the scene doctrine) |
| 14 | B3-03: `approved_by` default "human" on 229 pending drafts | S | no (code), yes (backfill) |
| 15 | D1-02 rest: no disclaimer in browser print | S | yes |
| 16 | D1-04: *Acer pseudoplatanus* common name "Acer ser. Acer" | S | yes (your name) |
| 17 | Import summary hides 95 duplicates (GPT 8) | S | no |
| 18 | Background Processes catch-all says "Could not reach server" for render errors (GPT 6) | S | no |
| 19 | Recipe season keyword guess (recipe 74 under Autumn) (GPT 7) | S | yes (fix 74 by hand vs change the guess) |
| 20 | Walk duration has no stop time (GPT 11) | S | yes (label vs model) |
| 21 | `addSessionSpecies` old escape pattern | S | no |
| 22 | 7 approved pins with stale "Auto-rejected:" notes | S | yes (note cleanup is a DB write) |
| 23 | D3-04 mirror copy / D3-05 frozen labels | S / M | yes (pending since 22 Oct) |
| 24 | B5-04 sensitive-species concept | M | yes |
| 25 | Vocabulary / dev refs / branding (GPT 10, 13) | M | yes (word list) |
| 26 | Workshop / foray / walk objects (GPT 14) | L | yes |
| 27 | Needs your browser: taxonomy "Failed to load", broken thumbnails, location prompt, offline "not cached", overlaps (GPT 6, 11, 12, 13) | — | console line + device/tier |
| 28 | B4-01 defence in depth (per-endpoint curator dependency) | M | yes (worth it?) |
| 29 | Route-line zoom/drag bug (15b item 4) | — | your repro |
