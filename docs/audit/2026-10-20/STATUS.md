# Deep audit 2026-10-20 — STATUS

Read-only audit. No fixes. Evidence-labelled findings in REPORT.md.

**Resume at Phase E.**

| Phase | State | Notes |
|---|---|---|
| A — Map | done (session 1) | A-01..A-10; Appendix A1 endpoint table |
| B — Safety-critical logic | done (session 1) | B1 routing (+ B1-08 obs 24353 score explanation, fresh DB copy 16:04), B2 gate matrix (R1–R9 + surface matrix), B3 safety-field writers, B4 identity (Appendix A2), B5 privacy |
| C — Data integrity | done (session 2) | C-01..C-08; changed_by lock table in C.1; A-09 confirmed; experience_publications explained (C-05) |
| D — Outputs | done (session 2) | D1 parity table + 9 scratch PDFs + D1-01 file-read; D2 Export summary/GPX/Google; D3 gates parity, walk-4 plan/build (B5-04 settled for walk 4), D3-01..05; D4 proposals P1–P11 |
| E — Tidy | **next** | see carry-over notes for E below |
| F — Rename inventory | not started | |
| G — Report assembly | not started | |

## Settled during the audit — do not raise
- 20 Oct 2026 (Melvin): no family- or toxicity-specific auto-approve veto, and no app-side Apiaceae culinary rule. The high-threshold dual-API agreement is the safeguard for all species. (B1-01 recorded as "Decided — not a finding".)

## Carry-over notes for Phase E (found in sessions 1–2, not yet written up)
- `dev.py:~707` end-session "since last snapshot" parse: `ts.split("+")[0].split("-0")[0]` breaks for any date with "-0" (months Jan–Sep, days 01–09) → ValueError → falls back to exporting all encounters (tested in python). S3.
- Fire-and-forget `asyncio.create_task(...)` without keeping a reference: scan.py:835, :2080; syncthing.py:507, :682, :774; culinary.py:2793; ingest.py:52; enrich.py:461 (tasks can be garbage-collected).
- Docs drift: CLAUDE.md says copy-on-ingest is "migration 0021" (0021 = add_batch_state_to_scan_sessions); Alembic head 0050 (live 0054, known); "2158/2158" card/map figure stale (now 2474 cards = 2425 pins + 49 no-GPS); syncthing.py:1087 "≥80%" (live 0.70).
- index.html split proposal must account for D3-03 (app_styles.py regex-reads index.html JS).
- Markdown renderers: species.html `_renderMd`, print.html `_mdLite` (:362), lists.html `_mdLite`, lists_pdf.py `_mdlite` (:61), sharing.py `_md_inline/_md_snippet` (:406+).
- Gate implementations R1–R9 (REPORT B2) — the duplication inventory for E.
- `enrichment_sources.raw_response_json` holds HTML (C.1). `/health` 0.2.0 vs app 0.1.0 (A-10).
- Python is 3.9.6 (venv) — check PEP 604 `X | None` in annotations evaluated at runtime, `match`, `zip(strict=)`, etc. (`app_styles.py` uses `tuple[str, dict]` with `from __future__ import annotations` — fine).

## Carry-over notes for Phase C (from session 1, DB copy 20 Oct 12:24) — DONE
- `culinary_info_history.changed_by` values: pfaf_reparse 1777 · ai_approved:human 633 · human 148 · pfaf 52 · human:placeholder_clear 36 · ema 33 · multi-source 31 · human_merge 12 · normalization 4 · system_retroactive 2 · system_remediation 2 · manual_fix 1. Lock checks compare `== 'human'` exactly (culinary.py:2406-2418, enrichment.py:1050-1056); classify each value lock / non-lock in C.
- `review_status='not_applicable'`: 1 row (8196) — B1-04.
- 48 species with `edibility_status` NULL — B2-08.
- `app_settings` keys outside the registry: auto_approve_threshold, gdrive_access_token, obsidian_vault_path — A-07/A-09.
- `experience_publications` has 0 rows although walk 4 was published — check in C/D3.
- Session-1 permission note: a local GET of /api/settings (to show the DeepSeek key field is populated) was blocked by the permission classifier; A-02 stands on code + DB row. Don't retry.

Scratch DB copy (session 2): `<scratchpad>/audit.db` taken 20 Oct 2026 16:19 local via `sqlite3 .backup` (integrity_check ok).
Scratch is session-specific; a later session must take a fresh copy.
