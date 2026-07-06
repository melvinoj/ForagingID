
---

## 01 June 2026 — Session 2 (11a.2–11a.3 + fixes + Data Sources)

### Completed
- 11a.1 UI Addendum — native MediaRecorder recorder, dandelion-leaf waveform visualiser (AnalyserNode→leaf serrations), Wake Lock toggle (default on), upload fallback (mp3/m4a/wav/ogg); both paths write audio_path; no schema change. STATUS: COMPLETE — 01 June 2026
- 11a.2 — inline species/enrichment editing removed (display read-only); admin-only "Send to review" on species card = single canonical write path → enrichment review queue; CulinaryInfo.review_requested + migration 0011; scientific-name rename form retained (taxonomic, not enrichment). STATUS: COMPLETE — 01 June 2026
- Data Sources registry — Settings card under API Dashboard; data_sources table (migration 0012); GET/POST/PATCH/DELETE + reachability test; 24 sources seeded (10 original + 14 added via direct SQLite insert). No scraping logic — registry + reachability only. STATUS: COMPLETE — 01 June 2026
- Prompt A review queue fixes — Review Queue→Species ID rename; lookup/Second Opinion candidate auto-updates species name before Approve; Google Lens uploadbyurl via /api/observations/{id}/photo (works over ngrok); enrichment edit+approve fixed (ai_approved_fields_json) + per-card Repopulate; null medicinal_notes auto-fill "No known traditional medicinal uses" + 19-species backfill; edibility status persists + Unknown edibility queue (217) + Rescan; Location Review map invalidateSize fix. STATUS: COMPLETE — 01 June 2026
- Prompt B Data Trust audit — one real bug found (send-to-review read d.updated not d.queued); fixed; Accept button + /api/trust/accept-species (auto-approved → manually_verified, human_corrected); Database Overview consolidated into Data Trust collapsible Section E, separate tab removed; no dead UI, no removals. STATUS: COMPLETE — 01 June 2026
- 11a.3 — My Season standing personal list (personal_lists + personal_list_species, migration 0013, server-side); personal card read-only join (GET /api/personal-lists/card/{id}); "Your encounters" panel on species card + filterable My Season view; Stage 1 prompt "What do you actually see?" (prompt_stage=1, other 3 stages deferred); browser-print stub; /api/species/ id field fix. STATUS: COMPLETE — 01 June 2026

### Notes / corrections
- Hardening pass + old Prompt B (Pipeline 2 tweaks) were already COMPLETE in CHANGELOG (29 + 31 May) but still showed OUTSTANDING in roadmap v11 — corrected in v12.
- Data Sources: 14 new sources added via direct SQLite insert (no Code session). Natural Medicines seeded as paused (paywalled). PubMed Central flagged reference-only.
- Scraping is per-source future work; registry is the foundation only.

### Outstanding (carry to next thread)
- Roadmap v12 — produce via surgical docx edit in new thread with real binary attached (changeset prepared)
- Browser verification pass — your time
- 11a.4: Whisper transcription + Claude extraction layer — STATUS: OUTSTANDING
- 11b: Seasonal return notifications — STATUS: OUTSTANDING (next build)
- PWA install on Pixel — deferred to Sheffield
- Google Drive token refresh — only red API
- 9 failed_identification records, 56 re-queued auto-approve, obs 8366 — manual review
- Bulk archive uploads — needs good wifi

### Next Code session opener
Continue on ForagingID. Browser verification first, then next prompt is 11a.4 or 11b.
