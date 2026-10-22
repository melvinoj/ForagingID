# Recon — enrichment scope + handout culinary rule + prep warnings with recipes (22 Oct)

Step 1 of Melvin's 22 Oct prompt. Read-only; nothing has been built. Line numbers are as of 22 Oct (commit 66d73d5 + this session's uncommitted CLAUDE.md/script edits).
Built in this session: nothing in app/ or frontend/.

## 1. Enrichment / backfill endpoints and how each picks species

| Endpoint | Button (frontend) | Species source | Dry run |
|---|---|---|---|
| POST /api/enrich/run — app/api/enrich.py:219 | scan.html:4627 "Run enrichment" | `batch_species_names()` (enrichment.py:530): every distinct species_primary on approved/manually_verified obs, sorted. Real run passes `None` → runner re-derives the same list | `plan(session, batch_species_names())` enrich.py:222-227 |
| POST /api/enrich/re-enrich-empty — enrich.py:307 | scan.html:1441 / 4752 | confirmed species with culinary_info.edible_parts NULL (enrich.py:318-336) | `plan(target)` enrich.py:339-342 |
| POST /api/enrich/resume — enrich.py:235 | (paused auto_enrich) | `_state["resume"]["species_list"]` in memory | none |
| POST /api/enrichment/run — culinary.py:3203 | review.html:4734 (start), 4695 (resume banner) | `run_enrichment_batch(resume_after=…)` → `batch_species_names()`; resume by name via `bp_resume_point("enrichment_run")` (culinary.py:3147-3200). **The run's species list is not persisted** — only `resume_after` is in the bp payload (culinary.py:3051) | culinary.py:3223-3233: batch names filtered `> resume_after` |
| POST /api/drafts/backfill — culinary.py:3835 | scan.html:4946 (per field), 4972 (field=all), 5763/5804 (queue resume/re-run), settings.html:1496 | `_collect_backfill_targets(db, field)` culinary.py:3342 (confirmed obs + edible/caution-type verdict + field not covered). `identification_notes`: SQL inside `_run_id_notes_backfill_task` culinary.py:3609-3618 (**every species row** with empty id_notes, no obs filter, no list param). `field=all`: `_run_backfill_all_task` culinary.py:3804 (id_notes then combined) | culinary.py:3858-3875 — own shape `{fields, species_count}`, not `plan()` |
| POST /api/drafts/bulk-generate — culinary.py:2966 | review.html:4327 | explicit `body.species` | `plan(body.species, sources=False)` |
| POST /api/drafts/redraft-medicinal — culinary.py:4041 | (check caller) | explicit `body.species_ids` | **none** |
| POST /api/culinary/backfill-fungi-edibility — culinary.py:183 | **no frontend caller** (one-off) | kingdom Fungi or obs_category fungi, verdict null/unknown, not verified | **none**, runs inline |
| Single-species: /api/culinary/{name}/enrich culinary.py:2294 (review.html:5379), /api/drafts/generate 2936, /api/species/{name}/recipes/regenerate recipes.py:262, /api/audit/reenrich-common-name audit.py:684 | per-species buttons | the one species | plan([name]) (audit: none) |
| Auto-enrich after ID correction | — | `species_list=[name]` via enrich.py `_run_enrichment_task` | leave unchanged (prompt) |

Dry-run shape: app/services/enrichment_plan.py:24 `plan(db, names, …)` — takes a names list, so scoping = pass the scoped names.
Frontend dry-run modal: frontend/static/js/dry-run.js — `lmDryRunConfirm` / `lmDryRunCheck` (POST url + `dry_run=true`, `confirm()` text). Loaded by review, index, scan, settings, species (+ sw.js cache list). **One place to add the scope picker.**

## 2. Species page select mode
species.html:1459 `_selectMode = params.get('select') === '1'` — it is the **Foraging List picker** (ForagingList.has/getPhoto, species.html:1843-1888): tapping toggles membership in a list + photo choice. No enrichment action exists. "Enrich selected" would need its own selection set, or reuse ForagingList's selected names (decide — they're different intents).

## 3. safety_decision handout rule
- app/models/species.py:556 `safety_decision(severity, verdict, caution_warning=None)`; :570 `caution_unreviewed = level == "caution" and warning is None`; :572 `handout_culinary_allowed`, :573 `handout_label`.
- `caution_warning` comes from app/services/safety_gate.py:57-60 (curator-authored preparation text only) and scripts/experience_export/gates.py:190 `caution_warning()` → :308 rule 8.
- Change: add the curator look-alike (`warnings["look_alike"]["reviewed"]`) as a second input to safety_decision; both callers pass it. `warning` field stays prep-only.
- Readers of handout_culinary_allowed: app/api/sharing.py:492 (Export summary / walk share), app/api/lists_pdf.py:148 (PDF), frontend/static/js/safety-gate.js:66/84 (`handoutAllowed`, `handoutBadge` → lists.html:1242, print.html:451), gates.py:309 (experience page).
- Test to update: tests/test_batch6_warnings.py:160 `test_handout_culinary_rule`.
- Withheld→shown list: not yet computed (run safety_for_species over caution species before/after).

## 4. Recipe surfaces — does the prep warning travel with the recipe?
Shared frontend helpers: SafetyGate.warnings (in-app, all warnings, safety-gate.js:121), SafetyGate.handoutWarningsHtml (outgoing, :138). Neither is attached *to the recipe*; they're per-species blocks.

| Surface | Recipe code | Prep warning next to recipe? |
|---|---|---|
| Species page recipe bank | species.html:4714 `_renderRecipeBank` | no (warnings shown elsewhere on page) — confirm |
| Map pop-up | index.html:4913 area (`SafetyGate.warnings(safety)`) | species-level block, not by recipe — confirm recipe presence |
| Walk stop cards | index.html:6445 (`warnings collapse:'auto'`) | species-level, not by recipe |
| Walk Export summary | index.html:6280 `_summaryRecipe`, used 7652; warnings 7868 (`collapse:'all'`) | not adjacent |
| Lists print | lists.html:1241 `_printRecipes`, used 1343/1959/2009; warnings 1253 | species-level line, not by recipe |
| Browser print | print.html:450, used 472/509; warnings 462 | species-level |
| PDF | app/api/lists_pdf.py:162-190 key_recipe title/body | check template |
| Experience page | scripts/experience_export/export.py:706-712 recipe_teaser | no |
| Find → What can I make? | index.html:9571 `_findRecipes` ← app/api/find.py:163 | **no safety payload at all** — confirm |
| Encounters field recipes | encounters-main.js:1043/1063, species.html:3348 | not in prompt list — ask |

## Proposed build (not started)
- `app/services/enrichment_scope.py`: one resolver — scope ∈ {walk, selected, all}; walk via walk_membership (same as map); intersect with each endpoint's eligible list; order walk species first; cap (default 25) → (names, remaining). No scope → 400, nothing runs.
- Query params on every bulk endpoint above: `scope`, `walk_id`, `species_ids`, `cap`. Persist the scoped list in the bp payload so resume keeps the scope; id_notes task gains a names filter.
- dry-run.js: scope picker (walk dropdown / selected / all, cap input) before the dry run; species.html: "Enrich selected".
- One helper for prep-warning-with-recipe: JS `SafetyGate.recipeWarning(safety, {handout})` + Python twin for PDF/experience.
