# Recon — Stage C publish panel (22 Oct 2026)

Read-only. Nothing pushed. The only network command run was `git ls-remote`.

## 1. How the export is built today

- `scripts/experience_export/export.py` reads the DB read-only (`:515` `?mode=ro`) and writes `index.html`, `preview.html`, `tree.html` (`OWNED_FILES`, `:417`) plus `photos/`.
- Where the files go (`:527–528`):
  - A default walk is written to `<out>/`, plus an identical copy at `<out>/w/<slug>/`.
  - Any other walk is written to `<out>/w/<slug>/` only.
  - Only those files are replaced (`:899–931`); other walks under `w/` are left alone.
- Checks inside the export:
  - **Photos:** each one is re-encoded from pixel data (`encode_photo`, `:188`). `verify_no_metadata` (`:200`) runs exiftool and PIL, but the build only fails on **GPS** tags (`:921–923`). A file with other EXIF is only reported (`files_with_any_exif`).
  - **Placeholders:** a missing or `TODO` Impressum/Datenschutz URL is only a **warning** (`:833–838`, "Do not publish until set"). It does not block the build.
  - **Unfilled `{{X}}`:** `fill()` dies on these (`:102–113`).
  - **Gate cross-checks:** `:874–895`.
  - **Rule 7 blockers:** per species (`:597–611`) and per stop (`:615–622`). With any blocker, the full build writes nothing and dies (`:1042`).
- `--plan-json` (`:937–976`) writes no files and prints JSON:
  - `buildable`, `walk{slug, is_default, canonical, writes, mirror}`, `distance`, `observations`, `stops`;
  - `public_species[{id, scientific_name, en, badge, …}]`;
  - `caution[{…, recipes_withheld}]`;
  - `ai_agreed_excluded[{species_id, name, stops, toxicity_severity, blocker, included}]`;
  - `recipes{included, excluded}`, `images_planned`, `warnings`, `blockers`.
  - On a BuildError it prints `{"ok": false, "build_error", "blockers"}` (`:1050`).
- `POST /api/experience/publications/{id}/plan` (`app/api/experience.py:185`) runs `--plan-json` in a subprocess (`:196`) with the publication's `overrides_json` plus its slug, and adds `--default` when `is_default` is set.
- AI-agreed per observation: the plan lists AI-agreed **species** (`ai_agreed_excluded`) but not their observation ids. Observation ids appear only inside the per-stop blocker strings. The existing "Confirm species" path is `PATCH /api/observations/{id}/review?status=manually_verified` (`frontend/review.html:2263`, `critConfirm`).
- **The live page cannot be found in the page text.** `index.html` holds the fallback text `<span class="placeholder">Impressum (link to follow)</span>` as template code, even when the link is set. The real signal is `window.DATA.impressum_url` / `datenschutz_url` being null (template `:233`, `window.DATA = {{DATA}};`).

## 2. The foraging-experience clone and push credentials

- Path `/Users/melvinjarman/foraging-experience`, branch `main`, tracking `origin/main`, clean, HEAD `ed3b4d9` ("Rümmelsbühl foray: republish walk 4 …").
- Remote: `https://github.com/melvinoj/foraging-experience.git` (HTTPS, not SSH).
- Credential helper: `osxkeychain`, set both in `/opt/homebrew/etc/gitconfig` and in `~/.gitconfig`. git is `/opt/homebrew/bin/git` 2.54.0; the helper is in `/opt/homebrew/opt/git/libexec/git-core/`.
- Keychain: the login keychain holds an internet password for `github.com`, protocol `htps`, account `melvinoj`. Only the attributes were read, never the secret.
- **ls-remote test:** `GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/usr/bin/false git ls-remote origin` → `ed3b4d9… refs/heads/main`, rc 0, 0.65 s. It also succeeds with `-c credential.helper=` (no credentials at all), so **the repo is public and ls-remote proves read access only, not push.**
- **Evidence that a push from uvicorn authenticates:**
  - End Session runs `git push origin main` from inside the uvicorn process (`app/api/dev.py:723`).
  - ForagingID's `origin/main` is `731da51`, the 17:26 End Session commit. That is the same github.com host, the same HTTPS remote and the same keychain helper.
  - uvicorn is started by `START_ForagingID.command` in Terminal, as Melvin's user with the login keychain unlocked.
- **Remaining unknown:** if the stored token is a fine-grained PAT scoped to the ForagingID repo only, a push to foraging-experience would be refused. The publish job therefore checks the login first with `git push --dry-run` (an authenticated receive-pack request that sends nothing). I did not run that here (ls-remote only, as asked).
- **The site has no `w/` folder.** The last republish copied the root files only, so `w/ruemmelsbuehl/` (the default walk's mirror) has never been live.

## 3. experience_publications

- Columns (`migrations/versions/0054_experience_publications.py`): `id`, `saved_walk_id` (FK, ON DELETE SET NULL), `slug` (unique), `is_default`, `overrides_json`, `status` (draft/published/unpublished), `published_at`, `unpublished_at`, `published_commit`, `public_species_json`, `created_by`, `created_at`, `updated_at`.
- Default rule: at most one `is_default=1` (partial unique index). `PATCH` clears the old default first (`experience.py:170–181`).
- The slug cannot change while published (`experience.py:162`).
- Deleting a walk is refused (409) while published; drafts are deleted with it, and unpublished rows stay as history (`app/api/walk.py:725–748`).
- **The table is empty today.** Walk 4 went live through the CLI with `scripts/experience_export/overrides/walk4.json` (slug `ruemmelsbuehl`, title "Foraging Experience — Gresgen", intro, where). None of that is in the DB. A publication created without it gets title = walk name and an empty intro (`export.py:455–466`). The panel's create step therefore offers to copy an overrides file.
- What "unpublish" can mean with these files:
  - Remove `w/<slug>/`.
  - If it was the default, also remove the root `index.html`, `preview.html`, `tree.html` and `photos/`, leaving the site root with no page (404) until another walk is published as the default.
  - One commit plus a normal push. Git history and other people's caches keep the old page.
