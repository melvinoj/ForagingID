# Recon — batch 8 (guest visibility + guest notes) + Fix A + Fix B (22 Oct)

Read-only. Line numbers are from the working tree on 22 Oct, before the batch 8 build.

## 1. What a participant (guest) session can reach since batch 7

**Gate:** `app/main.py:282` `_access_middleware`. A guest device passes for **every GET** (only `/scan /review /settings /workshops` pages are redirected, main.py:256/301). Non-GET is blocked except `/api/sharing/export-walk`, `/api/encounters`, `/api/recorded-walks`, `/api/recorded-walks/audio-upload` (main.py:308-313). The access layer has no per-endpoint data rule, so every curator GET API is readable by a guest.

**Static mounts (no rule at all for guests):**
| Mount | main.py | Serves |
|---|---|---|
| `/thumbnails` | 340 | every observation thumbnail, any review status |
| `/uploads-files` | 345 | every uploaded original, any status |
| `/media/recorded-walks` | 350 | curator recorded-walk audio notes |
| `/media/encounters` | 355 | all encounter audio (curator + every participant) |
| `/media/species-resources` | 359 | curator species resources (published material) |

**JSON endpoints returning photos / encounters / notes / walks:**
| Endpoint | file:line | Filter today |
|---|---|---|
| GET /api/observations | observations.py:245 | none — any status (needs_review, rejected…) |
| GET /api/observations/{id} | observations.py:449 | none |
| GET /api/observations/{id}/photo | observations.py:738 | none — full-size original of any obs |
| GET /api/observations/{id}/edits, /stats, /label-counts, /prefilter-categories, /confirmed-no-gps, /location-review | observations.py:757/371/413/427/123/168 | none (curator data) |
| GET /api/species/{n}/profile | culinary.py:1911 | `observations.thumbnails` = **all** obs rows (culinary.py:1933-1947, 2126-2137) incl. pending/rejected |
| GET /api/species/{n}/observations | culinary.py:1871 | confirmed only ✓ |
| GET /api/map/geojson, /heat | map.py:105/272 | confirmed ✓ |
| GET /api/nearby | nearby.py:63 | confirmed ✓ |
| GET /api/timeline/positions, /at | timeline.py:212/321 | obs confirmed ✓; **/at returns every encounter's text_note + encounter photo thumbnails, all users** (timeline.py:373-412) |
| GET /api/walk/saves, /saves/{id} | walk.py:131/253 | stops from walk_membership, confirmed only (walk_membership.py:314/346) ✓ |
| GET /api/recorded-walks, /{id} | recorded_walks.py:243/270 | no user scoping (model has no user_id); thumbnails of any status; audio_note_path |
| GET /api/encounters | encounters.py:321 | participant → own only ✓; anon → [] |
| GET /api/encounters/{id} | encounters.py:482 | **none** — any encounter, transcript, audio URL |
| GET /api/encounters/field-recipes | encounters.py:290 | **none** — every user's field recipes |
| GET /api/encounters/pending-transcripts | encounters.py:274 | count over all users |
| GET /api/encounters/{id}/photo-candidates | encounters.py:374 | none — nearby obs of any status |
| GET /api/personal-lists/card/{sid} | personal_lists.py:211 | encounters of USER_ID=1 (curator), with audio_url (personal_lists.py:234-248) |
| GET /api/notes/geojson, /by-species | notes.py:21/84 | none (curator map notes; guests cannot create them, notes.py:33) |
| GET /api/species/{n}/resources | resources.py:39 | none (curator material) |
| Curator queues (/api/culinary/ai-draft-review, /api/queue/list, /api/processes/active, scan GETs, reidentify/trust/audit GETs) | various | readable by guests |

`_enc_to_dict` (encounters.py:84) lists every bound photo's thumbnail regardless of the observation's status.

## 2. Participant encounters today
- Created by `POST /api/encounters` (encounters.py:155): `user_id=identity.user_id`, `workshop_session_id=identity.workshop_session_id` (13.1). Anonymous guests refused (encounters.py:171).
- **Audio upload is possible for participants**: `audio: UploadFile` is saved to media/encounters (encounters.py:199-207). `photo_observation_ids` lets a participant bind **any** observation id (encounters.py:240-258).
- Curator = user_id 1 (identity.py:52); participants = WorkshopParticipant.id ≥ 2 (identity.py:56-59).
- No share flag on encounters (models/encounter.py:33-72).

## 3. Guest path to Lists / print / PDF
- Lists page and browser print build the output client-side from `/api/species/{n}/profile` (lists.html, print.html `_printRecipes`, `_printWarnings`).
- PDF: `POST /api/lists/pdf` (lists_pdf.py:241). **Refused for guests** by the middleware write block (main.py:308) — a guest gets "Guest mode — read-only access". The PDF is built server-side from the client profile + `safety_by_names` (lists_pdf.py:137 `_flatten_species`, template app/templates/print_pdf.html, Jinja autoescape on, lists_pdf.py:35).

## 4. Fix A — redraft-medicinal eligibility today
`_redraft_medicinal_eligible` (culinary.py, added 22 Oct): confirmed + not toxic + no pending medicinal draft. It does **not** look at the current medicinal_notes text, so approved or curator text could be drafted over. Shared predicates: `is_ai_placeholder` (ai_placeholder.py:107), `is_only_no_medicinal_uses_claim` (ai_placeholder.py:180); curator authorship `is_curator_authored` (species.py:735).

## 5. Fix B — culinary content surfaces and their warnings today
| Surface | Culinary content | Species-level warning block | Directly beside? |
|---|---|---|---|
| Species page | Culinary fields (species.html:2247), taste notes (2287), recipe bank (4714), field recipes (3389) | warnings section (2158-2201), separate section | no |
| Map pop-up | edible parts (index.html:4920) | `SafetyGate.warnings(safety)` (index.html:4913), same pop-up, immediately above | **yes** |
| Walk stop cards | none (no recipe / edible parts; index.html:6420-6446) | `SafetyGate.warnings` (6445) | n/a |
| Walk Export summary | culinary_notes + recipe (sharing.py:638-657) | look-alike + prep (sharing.py:631-637), same species block, immediately above | **yes** |
| Lists panel (in-app) | recipe snippet (lists.html:1354) | none in the panel | no |
| Lists / browser print — field guide entry | edible parts + recipe (lists.html:1983-2004, print.html:484-503) | `_printWarnings` in the same entry, immediately above (lists.html:1979, print.html:482) | **yes** |
| Lists / browser print — workshop page | Foraging notes / edible parts (lists.html:2059, print.html:548), recipe (2038/537) | Safety section at the top of the page (2028/525), other sections between | no |
| PDF recipe booklet | recipe (print_pdf.html:348-354) | look-alike + prep immediately above (345-346) | **yes** |
| PDF workshop | Foraging notes (381-386), recipe (406-410) | Safety section at top (367-375) | no |
| PDF field guide | no culinary text printed | — | n/a |
| Experience page — plant panel | recipe teaser (templates/index.html:475) | warnings in the same panel right after (460-461) | **yes** |
| Experience page — Recipes tab | recipe teaser (516) | none | no |
| Find → What can I make? | recipe cards (index.html:9603) | none | no |
| Encounter field recipes | encounters-main.js:1073 | none | no |
| Encounters personal card | recipe + taste notes (encounters-main.js:1364-1371) | none; card has no safety payload (personal_lists.py:211) | no |
