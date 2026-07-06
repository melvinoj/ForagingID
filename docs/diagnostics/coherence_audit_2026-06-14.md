# ForagingID — Phases 11–13 Coherence + Whole-App Bug Scan

**Date:** 2026-06-14
**Mode:** Read-only / diagnostic. No files edited (except this report), no migrations, no DB writes, no commits. No fixes applied.
**Server:** single uvicorn on `:8001` against `data/foragingid.db` (252 MB, alembic head `0032`).
**Part A method:** verified live via a spoofed `Host` header (not a public tunnel) — see Method note. The participant-token auth path was exercised with the existing Alice token, no token minted, no encounter persisted.

**Reproduced vs inferred** is flagged on every finding. Cross-referenced `docs/diagnostics/full_audit_2026-06-13.md` (written at `0031`) but re-verified independently; divergences are called out.

---

## BLOCKER — fix before 10 Oct

### 1. Text-only encounters capture no location at all — the 13.10b "text + location" queue stores location-less rows
- **What:** The encounter capture widget only reads GPS inside `startRecording` (encounters.html:670-672). A text-only capture (the exact path 13.10b routes through the offline outbox) never calls `startRecording`, so `_lat/_lng` stay `null` and the POST omits `latitude/longitude`. The manual `detectLocation` function (encounters.html:583) is dead code — no button or `loc-coords` element is ever rendered (grep finds only the definition + a CSS class).
- **Where:** `frontend/encounters.html:670-672` (only live GPS read), `:583-598` (dead `detectLocation`), `:507/:943` (`_lat/_lng` init/reset).
- **How verified:** Reproduced statically + behaviourally — in the 13.10b browser test, `latitude/longitude` had to be injected manually; the real text path produces none. Confirmed there is no other GPS read on the page (grep).
- **Why it's a blocker:** The workshop's purpose is participants capturing located field encounters via the tokened link. As built, every text-only encounter lands with NULL coordinates.
- **Fix direction:** In `saveEncounter`, fire `GPS.getOnce()` for the text path too (or on field focus / a visible "📍 location" control). Decide whether to block save or warn when no fix is available, so absent GPS is never silent.

### 2. Outbox deletes on any 2xx without validating the body → a proxy interstitial (ngrok) could cause silent data loss — UNVERIFIED, needs the live tunnel test
- **What:** `encounter-queue.js` deletes a queued record whenever `resp.ok` is true (`flush()` → `if (resp.ok) _delete(...)`), without checking the response is the expected JSON. ngrok's free-tier browser-warning interstitial returns HTTP 200 with HTML. If an outbox POST ever hits that interstitial (before the participant clicks through, or after the skip cookie expires mid-forage), the outbox treats it as success and deletes the encounter that never reached the server.
- **Where:** `frontend/static/js/encounter-queue.js` (`flush`, the `if (resp.ok)` branch); ngrok interstitial behaviour is external.
- **How verified:** Inferred, NOT reproduced. Auth was verified via a spoofed `Host` header (no real tunnel), so the interstitial path was never exercised. Likely mitigated in practice by ngrok's click-through cookie, but that is an assumption.
- **Fix direction:** (a) Before deleting, require the 2xx body to parse as JSON containing the expected `id`/`client_uuid`; treat anything else as failure (keep queued). (b) Send `ngrok-skip-browser-warning: true` on outbox POSTs. (c) Run the real ngrok round-trip once to confirm — the single most important pre-workshop test.

---

## HIGH

### 3. Token lifetime vs forage + 403 wedge compound, with no in-field recovery
- **What:** Guest token TTL is 7 days default / 90 max (`workshop_tokens.py:32-33`, `expires = utcnow()+timedelta(days=days)` at :111). A forage is hours, so mid-forage expiry only happens if a token is minted ≥7 days ahead (or with a short custom TTL). But when a send returns 403, the outbox is oldest-first stop-on-failure: it marks the item failed and breaks, wedging the entire queue behind it. There is no in-field refresh path — once a participant's token lapses, nothing syncs for the rest of the day.
- **Where:** TTL `app/api/workshop_tokens.py:110-111`; wedge behaviour `encounter-queue.js` (`flush` reduce-chain returns stop on non-2xx). 403 reproduced: expired token POST over ngrok host → `403 "Token required"` (no row written, 13→13).
- **How verified:** Reproduced (403 + no-write) read-only; wedge behaviour confirmed from the 13.10b code.
- **A3/A4 answered explicitly:** 403 → whole queue wedges behind the first failure (intended "don't drop data"), and the chip does surface it ("N failed — will retry" once `attempts > 3`; "N queued" before that) — not silent. A 422 / any permanent 4xx behaves identically: there is no eviction or skip path, so one poison record stalls everything behind it indefinitely.
- **Fix direction:** Mint tokens day-of with TTL ≥ forage; surface an explicit "token expired — re-open your link" state in the chip on repeated 403; consider a bounded skip/park for poison non-auth 4xx so a 422 can't block the rest.

### 4. P1/P2 can produce duplicate observations — dedup is check-then-insert with no DB constraint, and the mutex doesn't cover the browser-upload path
- **What:** `ix_observations_file_hash` is non-unique (schema confirmed: `unique=0`); dedup is `SELECT ... WHERE file_hash == sha` in a separate session, then insert (scan.py:264, scan.py:2058). `file_path` is unique but P1 and P2 write different uuid-prefixed filenames for the same source, so it doesn't catch source-level dupes. The cross-pipeline mutex (`pipeline_lock.py`) is held only by P1 syncthing (syncthing.py:462) and P2 archive-scan (scan.py:1976) — not by the browser upload path: `process_delta` (scan.py:1740) only arms a session; ingest happens via `POST /api/scan` (`scan_image`, scan.py:180), which takes no lock. P1's auto-scan loop runs unattended every 60 s (syncthing.py:302-319). `busy_timeout=10s`+WAL (database.py:17-18,54-55) prevent most "database is locked" crashes but do nothing for the logical race.
- **Where:** schema (`pragma_index_list('observations')`), scan.py:264 / 2058 / 1740 / 180 / 1976, syncthing.py:462, `app/services/pipeline_lock.py`.
- **How verified:** Inferred from schema + code, not reproduced (would need concurrent P1 + browser upload on overlapping sources).
- **Fix direction:** Add a UNIQUE constraint/index on `file_hash` (then catch `IntegrityError` like the encounters idempotency path) and/or extend the pipeline mutex to wrap `scan_image`/the process-delta upload flow.

### 5. Geotagged count dropped 11,481 → 10,543 since this morning (total unchanged) — possible silent coordinate loss
- **What:** This morning's audit reported 11,481 geotagged (lat AND lng); the direct query now returns 10,543 (`lat`, `lng`, and `both` all equal 10,543) with total still 13,045. Either ~938 observations lost coordinates since then (real data loss) or the two audits defined the metric differently.
- **Where:** `observations` table; cross-reference `docs/diagnostics/full_audit_2026-06-13.md:106`.
- **How verified:** Both numbers are direct SELECTs but from different runs; the 11,481 figure could not be reproduced and loss-vs-definition cannot be told apart read-only. Flagging, not asserting.
- **Fix direction:** Diff the two by id to see if specific rows lost coords; if so, hunt the writer that nulls lat/lng (no fill-when-empty path should — finding 9 — so this would be a real bug).

---

## MEDIUM

### 6. Encounter recorder reuses a stale GPS fix for ≤60 s (the Zurich bug class, in the encounter path)
- **What:** `GPS.getOnce()` returns a cached fix if younger than 60 s (`gps.js:14,39-42`). Two audio encounters recorded within a minute while walking get the same coordinates — the exact reused-reading class the Zurich batch-upload fix addressed, still present in the encounter recorder.
- **Where:** `gps.js:14,39-42`; consumed at `encounters.html:671-672`.
- **How verified:** Inferred from code (cache window), not reproduced.
- **Fix direction:** For capture, pass `maximumAge: 0` / bypass the cache, or stamp+display the fix age and re-detect.

### 7. Scan-session counters are incoherent → P2 counts and "Fix 5" are untrustworthy
- **What:** The single P2 session (id 31) shows `files_received=2899` but `files_duplicate=23682`, `files_new=0`, `files_processed=475` — duplicate ~8× files received. `process_delta` resets some outcome counters on re-arm (scan.py:1835) but `files_duplicate` accumulates across re-runs into the same row. Almost certainly the root of the recurring "Fix 5 total/geotagged count" instability.
- **Where:** `scan_sessions` id 31; scan.py:1835 (partial reset), scan.py:2065 (dup increment).
- **How verified:** Reproduced (read-only query of durable session state).
- **117 anomaly:** Could not reproduce the exact "117" figure. Durable evidence shows P2's last archive run created 0 new observations (everything deduped) with `files_failed=0/files_rejected=0` — i.e. P2 is not silently erroring; it's finding everything already ingested. "117" is likely a stale partial figure from an earlier run. P2 is not starved in the archive path (it would SKIP wholesale if P1 held the mutex, not partially — scan.py:1977-1987).
- **Fix direction:** Reset all per-session counters on re-arm; define one canonical geotagged/total query and use it everywhere.

### 8. `GET /api/observations/{id}/gbif-check` commits + makes an outbound call — guest-reachable, bypasses the write-guard model
- **What:** A GET handler writes `obs.gbif_occurrence_json` and calls GBIF (reidentify.py:897-952). The guest middleware only blocks non-GET methods, so a tunnel guest can trigger this write + outbound request. Data written is benign (a public GBIF count), but it's a mutating-GET anti-pattern outside the guard model.
- **Where:** `app/api/reidentify.py:897-952`.
- **How verified:** Reproduced statically (AST scan flagged it as the only GET that commits; confirmed by reading).
- **Fix direction:** Make it POST (curator-guarded) or split the persistence out of the GET.

### 9. Auth is host-based, not token-based — any non-ngrok exposure = curator with no token
- **What:** 149/152 write endpoints have no per-route guard; they rely entirely on the middleware, which only restricts when `is_guest_request` sees `.ngrok` in the Host (sharing.py:48-61). On any other host you are curator, full write, no token — including the LAN URL surfaced by `/api/sharing/lan-url` (sharing.py:225-235), a custom/vanity domain, or a different tunnel. B3/coordinate paths are safe within this (PATCH coordinates is curator-only + audited; recorded-walks now has its own `is_guest→403` guard at recorded_walks.py:148,358 — note this fixes the prior audit's Top-Risk-2).
- **Where:** `app/main.py:188-216`, `app/api/sharing.py:48-61,225-235`.
- **How verified:** Reproduced read-only (token resolution behaviour over spoofed hosts).
- **Fix direction:** Treat the host check as defence-in-depth only; require a token for writes regardless of host, or never expose on a non-ngrok host.

### 10. iNaturalist token expired → dual-API auto-approve can never fire (silent quality degrade)
- **What:** On 401 iNat falls through to an empty candidate list (inaturalist.py:42,160-161). The pipeline keeps working on PlantNet only, but `_identify_scanned`'s auto-approve requires dual-API agreement — so with iNat down, everything routes to needs_review. Degrades cleanly (no crash) but silently changes routing.
- **How verified:** Inferred from code + the standing "iNat token expired" ops note. Not re-validated live.
- **Fix direction:** Refresh the token; surface iNat-down as a visible banner, not just a boot log.

### 11. `alembic check` is broken — schema drift can't be auto-detected
- **What:** `alembic check` raises `NoReferencedTableError: guest_tokens.workshop_session_id → foraging_sessions`. Alembic's env.py metadata doesn't register the `foraging_sessions` model, so autogenerate/check can't resolve the FK. Runtime is fine (server boots; `create_all` via main.py's noqa imports is complete), so this is a tooling gap, not a live breakage. The migration chain itself is linear 0007→0032, single head (verified). No `v21` migration gap; the "v20→v22 roadmap" is a docs-versioning question and the roadmap is still pending v20 (no v21/v22 references found).
- **Where:** `migrations/env.py` metadata; FK at `guest_tokens`/migration 0031; target table from 0024.
- **How verified:** Reproduced (`alembic check` output).
- **Fix direction:** Import the `ForagingSession` model into env.py's target metadata.

---

## LOW

- **12. C2 job queue:** `recover_stale_jobs()` (queue_api.py:142-172) marks orphaned `running`→`interrupted` at startup, and `_is_stale` surfaces stragglers at read-time without writing (queue_api.py:61-92). So no phantom-running and no auto-duplicate on restart. Not verified: pause/resume/cancel idempotency and whether a re-run of an `interrupted` job double-writes (depends on each handler's idempotency — enrichment skips already-populated, others not traced). Inferred.
- **13. B5 AI backend:** `deepseek_draft.py`/`ollama_draft.py` catch ConnectionError/HTTP/Exception, log, and return empty (deepseek_draft.py:82-93) — a down local model leaves the field blank, doesn't raise into the job queue. Not verified: the ollama timeout value and every caller; prior audit also notes these two backends may have no live caller. Inferred.
- **14. C5 leaks:** SSE generators have `finally` cleanup (scan.py:1945,2241,2275,2343); map endpoint is set-based, no N+1 (per prior audit, consistent). `/api/me` per page-load is overhead, not a leak. Low at single-user/workshop scale.
- **15. dismiss-stays-dismissed:** `POST /seasonal-returns/dismiss` writes a `NotificationDismissal` (notifications.py:62-79) and looks correct, but `notification_dismissals` is empty (0 rows) and the read-side filter was not traced. Inconclusive — could not confirm fixed; needs a live dismiss→reload test.
- **16. C3 single-instance:** Confirmed one uvicorn (reloader PID 73299 + worker 79029 sharing the socket — normal `--reload`), one DB (`data/foragingid.db`), nothing on `:8000`. Two 0-byte decoy DBs in repo root (`foragingid.db`, `foraging_id.db`) are unused but could confuse tooling — worth deleting. No split-brain; `0032` is on the correct DB.
- **17. foray model (C4):** `foraging_sessions` is 0 rows, no UI, `encounters.workshop_session_id` all NULL — Phase 13.2 is stubbed/forward-wired, not in use. Consequence: even a valid participant capture scopes `workshop_session_id=NULL` today (confirmed via Alice's token).

---

## Method note / what I could NOT verify
- **Part A token round-trip:** auth + scoping reproduced read-only by spoofing the ngrok `Host` header (`is_guest_request` keys only on Host), reusing the existing Alice token (id 1). Result: token → `user_id=2`, listing scoped to her row only; invalid/expired → anonymous `[]`; no-token/expired POST → `403`, no row written. A participant encounter was deliberately not persisted and no token was minted (honouring "don't write to the DB"); no public tunnel was started — so the ngrok interstitial path (finding 2) and real network/flaky-cellular behaviour are unverified.
- **Not reproduced (inferred only):** findings 4 (concurrent dupes), 6 (60s reuse), 13 (AI callers/timeout), 12 (job idempotency), and the loss-vs-definition question in 5.

## The three things most worth doing before 10 Oct
1. **Make the text path capture location** (finding 1) — otherwise the workshop's queued encounters have no coordinates. Highest workshop impact.
2. **Run the real ngrok round-trip once** and harden the outbox to validate the 2xx body before deleting (finding 2) + send `ngrok-skip-browser-warning` — closes the only plausible silent-data-loss vector.
3. **Token lifecycle for the field** (finding 3): mint day-of with TTL ≥ forage, and give the chip an explicit "expired — re-open your link" recovery state so an expired token can't silently wedge a participant's whole queue.

---

*End of report. No changes were made to the application, database, or git state during this audit; only this file was written.*
