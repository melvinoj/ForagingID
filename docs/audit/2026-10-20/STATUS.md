# Deep audit 2026-10-20 — STATUS

Read-only audit. No fixes. Evidence-labelled findings in REPORT.md.

**Audit complete — all phases done (session 3).** Fix pass in REPORT.md section 9 order. **Batches 1 (D3-01), 2 (E-01/E-02) and 3 (B2-02 + B2-05 data) done 20 Oct evening** — results in section 9. Next: 1b (Melvin: walk-4 drafts, verify *Rosa dumalis*, republish Rümmelsbühl foray, id 4), then 3b. **Batch 14 done 20 Oct (late evening)** — part 1: E-03 Second Opinion 500 + Review badge = queue count; part 2: GBIF-only names sort last with no score (Melvin's decision), E-04, B1-08 (code + 666-row backfill), C-03 (code + 5 rows), C-04 (cause confirmed by reproduction; code + obs 21585), D1-03, D2-01; report on the 1,667 `pending` rows — results in section 9. Open for Melvin: obs 15957 (*Taraxacum sect. Taraxacum* named, linked to *T. officinale*); enrich the 2 new bare species cards (848 *Filipendula vulgaris*, 849 *Ganoderma applanatum*); reject AI draft 2335 (junk 'norway spruce' card 685, now orphan-marked); triage of the 1,667 pre-filter rejects.

**Decided 20 Oct (evening, batch 3):**
- Species merges are allowed again, but only via a merge that re-keys `species_resources` and every other species-keyed table to the kept species, with tests and a snapshot first. The CLAUDE.md rule is updated when batch 11b lands, not now.
- Batch 14 (E-03 Second Opinion 500 + Review badge count) runs straight after batch 3.

**Severity since batch 3:** `toxicity_severity` is written only with the verdict (`severity_for_verdict`). `'unknown'` = never assessed and fails closed (230 species set by the backfill; new species are born `unknown`). Expect "⚠ toxicity unknown" on walk cards and species pages until 3b's verdict sweep resolves them.

**Snapshots (since batch 2):** the Settings snapshot goes through the SQLite backup API and is WAL-consistent. **Later batches no longer need the manual `sqlite3 .backup` copy** — the Settings snapshot alone is the Write Protocol's pre-write snapshot. Restore is WAL-safe and takes a `db_<ts>_prerestore.sqlite` first.

**Fix order additions (Melvin, 20 Oct evening — placed in section 9, not implemented):**
- 3b verdict sweep (review drafts for NULL/unknown or out-of-sync verdict/severity, e.g. *Atropa bella-donna*).
- 5 + "☠ deadly" / "☠ toxic" label on every surface (rides on batch 5's shared safety gate).
- 11b data/taxonomy: duplicate-species merges (⚠ clashes with the CLAUDE.md "do not attempt merges" rule — needs re-keying of `species_resources` or Melvin lifting the rule), GBIF synonym sweep, English common-name backfill.
- 14 + E-03 repro on obs 24149 and the Review badge count (2,080 vs 386).
- 15b walk batch: Edit-walk tap/lasso, Loop/One-way label instead of the toggle, Start here on every stop, route-line zoom/drag bug (reproduce first), GPS recording removal — before the index.html split.

| Phase | State | Notes |
|---|---|---|
| A — Map | done (session 1) | A-01..A-10; Appendix A1 endpoint table |
| B — Safety-critical logic | done (session 1) | B1 routing (+ B1-08), B2 gate matrix (R1–R9 + surface matrix), B3 safety-field writers, B4 identity (Appendix A2), B5 privacy |
| C — Data integrity | done (session 2) | C-01..C-08; changed_by lock table in C.1; A-09 confirmed; C-05 |
| D — Outputs | done (session 2) | D1 parity + scratch PDFs + D1-01; D2 Export summary/GPX/Google; D3 gates parity, walk-4 plan/build, D3-01..05; D4 proposals P1–P11 |
| E — Tidy | done (session 3) | E-01..E-14. New: E-01/E-02 snapshot + restore not WAL-safe (S1, reproduced in scratch); E-03 Second Opinion 500 on GBIF-only names (S2, in log); E-14 six marker-only human rows (S1) |
| F — Rename inventory | done (session 3) | 6 groups. User-facing leftovers: rename now. Internals (folder, DB file, venv, storage keys, GeoJSON key): never / Phase 14 |
| G — Report assembly | done (session 3) | REPORT.md sections 0–9: decisions, top 10, 12 S0s, matrices, parity, proposals P1–P18, tidy list, rename summary, SUSPECTED list, fix order (17 batches + 1b) |

## Settled — do not raise
- 20 Oct 2026 (Melvin): no family- or toxicity-specific auto-approve veto, and no app-side Apiaceae culinary rule (B1-01).
- 20 Oct 2026 (Melvin): auto-approve threshold stays 0.70.
- 20 Oct 2026 (Melvin): A-01 — the ngrok share link stays curator by default (mitigation: refreshable link, batch 7).
- 20 Oct 2026 (Melvin): B3-01 — a species rename clearing species text stays.

## Decided — fix (in REPORT.md section 0 and section 9)
- B2-01 + B2-04: no edible-parts text for toxic/deadly in the map pop-up and Lists / browser print; ☠ badge (batch 5).
- B2-03: printed outputs always include preparation warnings, incl. caution species (batch 6).
- B2-02 / P2: setting a verdict also sets toxicity_severity (batch 3).
- A-02: guests never read secret settings; /api/settings never returns secret values (batch 4).
- Refreshable share link: rotate a server-side secret, keep the ngrok origin (batch 7; mechanism in section 0).
- D3-01: option C with B as fallback (batch 1, then 1b republish of walk 4).
  - Review load: 36 caution species with a PFAF warning.
  - Plus 6 E-14 confirmations, and 19 "source unknown" texts if Melvin agrees.
  - 47 have no text, so their recipes are withheld.
  - Walk 4: 15 caution species; 7 PFAF drafts, 2 confirmations, 5 without text.
- Data, after the severity fix: Amanita muscaria 155, Heracleum mantegazzianum 688, Hedera helix 745 → toxic; reject drafts 2920 and 2921 (batch 3).

## Decided 20 Oct 2026 (evening) — in REPORT.md section 0
- The 19 "source unknown" caution texts and the 6 E-14 rows go into the same review queue as the 36 PFAF ones (batch 1 — done: drafts 3178–3238).
- B5-01, B5-02: close both — guests see confirmed plant photos only; encounters/voice notes curator-only (batch 8).
- A-03: the batch-7 share-link secret also gates LAN access; only localhost without it (batch 7).
- E-08: in-app GPS walk recording can be removed (batch 15b, before the index.html split).

## Open — Melvin decides
- B5-03 / B5-05.

Scratch DB copy (session 3): `<scratchpad>/audit.db` taken 20 Oct 2026 17:01 local via `sqlite3 .backup` (integrity_check ok). Scratch is session-specific.
