# ForagingID — Current Phase
*Last updated: 2026-06-03 13:13*

## Status

—

---

## What's Running Now

Phase 10.9 complete. Fixes round complete (Fixes 1–7).
Completed this session:

Migration 0021: durable batch state on scan_sessions, P2 sessions wiped, P1 backfilled to complete
Option B copy-on-ingest: Pipeline 2 copies to photos/pipeline2/, HD-independent
Rescan + process-delta endpoints, SSE progress stream, status badges, stalled detection, resume button
Fix 1: unnamed review cards inject .sp-name element on lookup selection
Fix 2: apostrophe escaping in lookup result onclick args
Fix 3: inline thumbnails on rejection log rows (P1 + P2), minimal lightbox
Fix 4: common name now pushes to card header alongside scientific name on lookup selection
Fix 5: total and geotagged counts exclude not_plant and rejected observations
Fix 6: Pipeline 1 routing removes confidence-based auto-rejection; below_threshold and failed_identification routed to needs_review; existing P1 records rescued
Fix 7: lookup merges iNat vision results, filters genus-level matches, boosts common-name matches, empty search triggers vision-only
Live DB confirmed at data/foragingid.db
CHANGELOG "next steps" to be written as "awaiting prompt" not task list to prevent auto-execution on session start

Awaiting prompt (do not start until explicitly prompted):

Takeout batch: rescan → process delta (operational, not a code task)
Roadmap update to v20
Fix 5 total/geotagged count — confirm correct thresholds with Melvin
Google Drive token refresh

---

## Next Up

Awaiting prompt (do not start until explicitly prompted):  Takeout batch: rescan → process delta (operational, not a code task) Roadmap update to v20 Fix 5 total/geotagged count — confirm correct thresholds with Melvin Google Drive token refresh

---

## Critical Discipline Notes

- Every write of `species_primary` **must** also set `species_id` or the cache desyncs silently
- `species_id` FK is additive only — do not break the 121 read-sites that use `species_primary`
- Auto-approve must NOT trigger on a single API source — this is an edibility-safety issue
- Map bbox split is a prerequisite for scale beyond ~5,000–10,000 observations

---

## After Phase 9 — Coming Next

**Phase 10a** — PWA + installable + GPS + Near me/in season + read-only offline (target: before October workshop)
**Phase 10b** — Offline write queue + sync (after 10a is proven in the field — do not conflate)
**Phase 10.5** — Data trust & bulk correction dashboard (must precede any teaching use)
**Phase 11a** — Goethean observation entry (build for Melvin first, use through one full season before generalising)

---

## October 2026 Hofgut LEO Workshop — Hard Deadline

Phase 10a (Near me / in season) is the field-use killer feature for this session.
Phase 12 (Handout/export) formalises the participant takeaway concept.
Neither requires Phase 13 (multi-tenant).
