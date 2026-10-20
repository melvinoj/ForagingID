# Deep audit 2026-10-20 — STATUS

Read-only audit. No fixes. Evidence-labelled findings in REPORT.md.

**Audit complete — all phases done (session 3).** Next: the fix pass, in REPORT.md section 9 order (batch 1 = D3-01, then 1b = republish Rümmelsbühl foray, id 4).

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

## Open — Melvin decides
- B5-01, B5-02 (S0 guest reads; batch 8).
- A-03 (LAN trust; batch 13).
- B5-03 / B5-05.
- The 19 "source unknown" caution texts.
- Whether in-app GPS recording can be removed before the index.html split (E-08).

Scratch DB copy (session 3): `<scratchpad>/audit.db` taken 20 Oct 2026 17:01 local via `sqlite3 .backup` (integrity_check ok). Scratch is session-specific.
