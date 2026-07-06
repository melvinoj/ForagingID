# ANTIGRAVITY.md — ForagingID Standing Instructions

## Session Start Protocol

At the start of every session, read these files in order:
1. `CHANGELOG.md` — operational source of truth for what's built and what's outstanding
2. `CLAUDE.md` — server start command, DB path, pipeline architecture, migration conventions
3. `ForagingID_Roadmap_June2026_v23.docx` — phase context and sequencing (planning reference only)

**If CHANGELOG and roadmap conflict, CHANGELOG wins.**

The planning layer (Claude Opus in a separate claude.ai thread) is not available until Sunday. If you hit an architecture decision, a safety judgment call, or anything outside the scope defined below — stop, do the read-only diagnostic only, and log the question clearly for the planning thread.

---

## Project Paths

- **App:** `~/Library/Mobile Documents/com~apple~CloudDocs/Documents/ForagingID`
- **Venv:** `~/foragingid-venv` (outside iCloud — do not move)
- **DB:** `data/foragingid.db`
- **Start server:** `cd ~/Library/Mobile\ Documents/com\~apple\~CloudDocs/Documents/ForagingID && source ~/foragingid-venv/bin/activate && uvicorn app.main:app --reload --reload-dir app`

---

## What You Can Do Unsupervised

- **Bounded safety data writes** — Apiaceae look_alike_warnings content pass (see below)
- **Read-only diagnostics** — investigating counts, schema, file state
- **Small isolated bug fixes** — frontend or backend, no schema changes, no migration needed
- **Review queue curation support** — read-only queries to help Melvin make approval decisions

---

## What You Cannot Do Without Planning Thread Review

- Schema changes (Alembic migrations) — any new column, table, or index
- Changes to identification pipeline logic (scan.py, identification.py, enrichment.py)
- Anything touching edibility model logic
- Bulk DB operations (mass updates, deletes)
- Moving, renaming, or deleting files from `uploads/` or `snapshots/`
- Moving the project folder (do not move to `~/ForagingID` unilaterally — disk space must be freed first)
- Running enrichment pipelines without explicit instruction
- Any git operations — git is currently broken due to iCloud path, commands will hang

---

## Write Protocol — Every Time, No Exceptions

1. **DB snapshot before any write.** Always. Use the app's snapshot mechanism or copy `data/foragingid.db` to `snapshots/` with a timestamp.
2. **Read-only diagnostic first.** Confirm the current state before writing.
3. **One task at a time.** Confirm clean before the next.
4. **Read-back after every write.** Print every field — not just new_value.
5. **Never fabricate content** for any field, especially safety fields. If old_value is unknown or the field was previously empty, set `old_value=NULL`. Never invent plausible text as a placeholder.

---

## Data Model — Critical Rules

**Edibility:**
- `species.edibility_status` (edible/caution/toxic/inedible/unknown) is the only field any display or handout reads for edibility verdict
- `species.edibility_verified` is a LOCK FLAG meaning "verdict human-confirmed" — never read it as an edible/safe signal, never set it without explicit instruction
- Edibility verdicts always require manual curator confirmation — never auto-set except toxic (fails safe)
- "inedible" ≠ "toxic": inedible species may still be safe for non-culinary use

**Human lock:**
- `changed_by='human'` in `culinary_info_history` is the human-lock marker
- Enrichment pipeline guards against overwriting fields with a human history row
- Always write a `culinary_info_history` row with `changed_by='human'` when writing curator-authored content
- `old_value` must be NULL if the field was previously empty — never fabricate

**Species lookup:**
- Use `name_key` (via `normalize_taxon_key()`) for all species lookups, not `scientific_name`
- `species_resources` is string-keyed by `species_name`, not `species_id` — merges will orphan these (known issue, do not attempt merges)

**Uploads:**
- `uploads/` is the primary image store — 12,351 of 13,045 observations reference it via `file_path`
- Never bulk-delete from uploads/. Never move uploads/ without a corresponding DB path update for all affected observations.

---

## Operational State (18 June 2026)

- **DIGIERA rsync is running** — full project backup to external drive, started ~11:00, overnight. Do not interrupt, move, or delete anything while it runs.
- **Git is broken** — iCloud path causes index file timeout. Do not attempt git operations.
- **Project needs moving** to `~/ForagingID` — do NOT do this unilaterally. Requires disk space freed first (snapshots prune + orphaned uploads diagnostic).
- **Snapshots at 12GB** — regrown since June 13 prune. Do not prune without explicit instruction.
- **iCloud sync is off** — project is local but still inside iCloud container path.

---

## The Apiaceae Safety Content Pass

This is the primary unsupervised task. 16 of 17 Apiaceae species have empty `look_alike_warnings`. Chaerophyllum aureum is done (18 June). 16 remain.

**The pattern for each species:**

1. Snapshot
2. Write to `species_lookalikes`: species_id (source), lookalike_species_id (target), lookalike_name, warning_text, toxicity_level
3. Write to `culinary_info`: update `look_alike_warnings` field
4. Write to `culinary_info_history`: field='look_alike_warnings', old_value=NULL (if previously empty), new_value=warning text, changed_by='human'
5. Read-back all three rows, print every field
6. Flag any fabricated content immediately — do not proceed

**Critical rule:** Warning text content must come from Melvin verbatim. Never generate, infer, or paraphrase safety warning text. If Melvin has not provided the text for a species, do not write anything — ask.

**Conium maculatum (Hemlock):** deliberately left empty. Do not write anything to it without explicit instruction from Melvin.

**Species already done:**
- Chaerophyllum aureum ✓ (18 June 2026)

---

## Safety Doctrine

- Fails safe toward more conservative verdict — never silently overwrite human-locked verdicts
- Preparation warnings and look-alike warnings are orthogonal to edibility verdict — both must be present for hazardous species regardless of verdict
- Deadly species (Conium maculatum, Aconitum napellus, Taxus baccata, Helleborus foetidus): single safety surface, red skull display. Do not alter their safety data without explicit instruction.
- If uncertain whether a task is safe to proceed — stop and log the question.

---

## End Session Protocol

End Session is via the app button at `http://127.0.0.1:8000/settings` — never through terminal or Antigravity commands. CHANGELOG.md is written by the app, not by you. Do not edit CHANGELOG.md directly.

---

## Source of Truth Hierarchy

1. CHANGELOG.md — what's actually built (operational)
2. CLAUDE.md — how to run the app (operational)
3. ANTIGRAVITY.md (this file) — rules and scope for unsupervised work
4. ForagingID_Roadmap_June2026_v23.docx — phase context (planning reference only)
