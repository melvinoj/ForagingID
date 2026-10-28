"""
Audit batch 12 + A-04 data (Melvin's decisions, 25 Oct 2026).

  C-05  An experience_publications row for walk 4 (Rümmelsbühl foray) recording
        what is actually live — every value read from the site clone
        (~/foraging-experience) and checked before anything is written:
          slug         walks.json entry whose page w/<slug>/ is walk 4's page
          published_at that entry's published_at (stored UTC, like every
                       publish) == the date of the commit below
          commit       the commit that published this content (the root walk
                       page, ed3b4d9 expected) — its page DATA equals the live
                       w/<slug>/ page's DATA except the slug key
          is_default   False unless the live root page is this walk
          public_species_json  the live page's species / recipes (same shape
                       as a publish job's snapshot) + "backfilled": true
  A-04  Move deepseek_api_key from app_settings to the gitignored .env
        (DEEPSEEK_API_KEY), then blank deepseek_api_key and gdrive_access_token
        in app_settings. The key value is never printed.

Dry run by default. --apply: snapshot through the SQLite backup API (no git
commit), write, read back by id / key.

Run:  ~/foragingid-venv/bin/python scripts/batch12_data.py [--apply]
"""
import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import ENV_FILE  # noqa: E402
from app.services import db_snapshot  # noqa: E402
from app.services.experience_publish import page_data  # noqa: E402
from app.services.settings_service import upsert_env_line  # noqa: E402

DB = ROOT / "data" / "foragingid.db"
CLONE = Path.home() / "foraging-experience"
WALK_ID = 4
EXPECT_COMMIT = "ed3b4d9"
SECRET_KEYS = ("deepseek_api_key", "gdrive_access_token")


def git(*args):
    return subprocess.run(["git", "-C", str(CLONE), *args], capture_output=True, text=True, check=True).stdout


def need(cond, msg):
    if not cond:
        sys.exit(f"STOP: {msg}")


def walk4_row(con):
    name = con.execute("SELECT name FROM saved_walks WHERE id = ?", (WALK_ID,)).fetchone()
    need(name, f"saved walk {WALK_ID} not found")
    name = name[0]
    need(not con.execute("SELECT id FROM experience_publications WHERE saved_walk_id = ?", (WALK_ID,)).fetchall(),
         f"walk {WALK_ID} already has a publication row")
    need(git("status", "--porcelain").strip() == "", "the site clone has uncommitted changes")
    walks = json.loads(git("show", "HEAD:walks.json"))
    entries = [w for w in walks["walks"] if w["title"] == name]
    need(len(entries) == 1, f"walks.json has {len(entries)} entries titled {name!r}")
    e = entries[0]
    slug = e["slug"]
    need(e["url"] == f"w/{slug}/", f"walks.json url {e['url']!r} is not w/{slug}/")
    need(not con.execute("SELECT id FROM experience_publications WHERE slug = ?", (slug,)).fetchall(),
         f"slug {slug!r} is already used by another publication")
    live = page_data(git("show", f"HEAD:w/{slug}/index.html"))
    need(live is not None and live["walk"]["name"] == name, f"w/{slug}/index.html is not walk {WALK_ID}'s page")
    need(live.get("slug") in (None, slug), f"live page slug {live.get('slug')!r}")
    # The commit that published this content: the newest commit whose page DATA
    # (root page then, w/<slug>/ now) equals the live DATA — apart from the two
    # keys the walk collection rewrote when it re-homed the page (slug, and the
    # corrected privacy link: experience_catalogue.fix_privacy_links).
    strip = lambda d: {k: v for k, v in d.items() if k not in ("slug", "datenschutz_url")}
    commit = None
    for line in git("log", "--format=%h %H %aI", "--", "index.html", f"w/{slug}/index.html").splitlines():
        short, full, when = line.split()
        for rel in ("index.html", f"w/{slug}/index.html"):
            try:
                d = page_data(git("show", f"{full}:{rel}"))
            except subprocess.CalledProcessError:
                continue
            if d is not None and strip(d) == strip(live) and rel == "index.html":
                commit = (short, full, when)
                break
        if commit:
            break
    need(commit is not None, "no commit published this content at the site root")
    need(commit[0] == EXPECT_COMMIT, f"publishing commit is {commit[0]}, expected {EXPECT_COMMIT}")
    need(commit[2] == e["published_at"], f"commit date {commit[2]} != walks.json published_at {e['published_at']}")
    published_utc = datetime.fromisoformat(e["published_at"]).astimezone(timezone.utc).replace(tzinfo=None)
    root = page_data(git("show", "HEAD:index.html"))
    is_default = bool(root) and root.get("walk", {}).get("name") == name
    need(walks.get("featured") != slug or is_default, "walks.json features this walk but the root page is not it")
    snapshot = {"is_default": is_default,
                "species": [{"id": p["id"], "scientific_name": p["sci"], "en": p["en"], "badge": p["badge"]}
                            for p in live["species"]],
                "recipes": [{"recipe_id": r["recipe_id"], "species_id": r["species_id"], "dish": r["dish"]}
                            for r in live.get("recipes", [])],
                "recipe_bank": [b["recipe_id"] for b in live.get("recipe_bank", [])],
                "backfilled": True,
                "note": f"audit C-05 (batch 12): row backfilled 25 Oct 2026 from the site clone — content "
                        f"published by {commit[0]} at the site root, re-homed to w/{slug}/ by the walk collection"}
    return {"saved_walk_id": WALK_ID, "slug": slug, "is_default": int(is_default), "overrides_json": None,
            "status": "published", "published_at": published_utc.isoformat(sep=" "),
            "published_commit": commit[1], "public_species_json": json.dumps(snapshot, ensure_ascii=False),
            "_check": {"commit": commit, "walks_json": e, "featured": walks.get("featured"),
                       "species": len(snapshot["species"]), "stops": len(live["walk"]["stops"])}}


def secret_plan(con):
    rows = {k: v for k, v in con.execute(
        f"SELECT key, value FROM app_settings WHERE key IN ({','.join('?' * len(SECRET_KEYS))})", SECRET_KEYS)}
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    need(ENV_FILE is not None and ENV_FILE == ROOT / ".env", f"this process's .env is {ENV_FILE}, not the project's")
    need(subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", ".env"]).returncode == 0,
         ".env is not gitignored")

    con = sqlite3.connect(DB)
    row = walk4_row(con)
    chk = row.pop("_check")
    print("C-05 walk 4 publication row (verified against the clone):")
    for k, v in row.items():
        shown = f"{chk['species']} species snapshot" if k == "public_species_json" else v
        print(f"  {k:<20} {shown}")
    print(f"  checks: commit {chk['commit'][0]} {chk['commit'][2]}; walks.json published_at {chk['walks_json']['published_at']}; "
          f"featured {chk['featured']!r}; {chk['stops']} stops")
    secrets = secret_plan(con)
    ds = (secrets.get("deepseek_api_key") or "").strip()
    print("A-04:")
    print(f"  deepseek_api_key in app_settings: {'set, ' + str(len(ds)) + ' chars' if ds else 'empty'} → .env DEEPSEEK_API_KEY, then blanked")
    print(f"  gdrive_access_token in app_settings: {'set' if (secrets.get('gdrive_access_token') or '').strip() else 'empty'} → blanked (not moved)")
    env_text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    have = [l.split("=", 1)[1] for l in env_text.splitlines() if l.startswith("DEEPSEEK_API_KEY=")]
    print(f"  .env DEEPSEEK_API_KEY now: {'present' if have and have[0] else 'absent'}")
    if not a.apply:
        print("Dry run — nothing written.")
        return
    con.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap = ROOT / "snapshots" / f"db_{ts}.sqlite"
    info = db_snapshot.backup_to_file(DB, snap)
    print(f"Snapshot: {snap.name} quick_check={info['quick_check']}")

    # A-04 step 1: .env first, so the key is never only in a blanked DB row.
    if ds:
        if have and have[0] and have[0] != ds:
            sys.exit("STOP: .env already holds a different DEEPSEEK_API_KEY — nothing changed")
        upsert_env_line(ENV_FILE, "DEEPSEEK_API_KEY", ds)
        back = [l.split("=", 1)[1] for l in ENV_FILE.read_text(encoding="utf-8").splitlines()
                if l.startswith("DEEPSEEK_API_KEY=")]
        need(back == [ds], ".env read-back does not hold the key")
        print(f"  .env read-back: DEEPSEEK_API_KEY present, {len(back[0])} chars, matches the DB value")

    con = sqlite3.connect(DB, timeout=30)
    con.execute("BEGIN IMMEDIATE")
    now = datetime.utcnow().isoformat(sep=" ")
    cur = con.execute("INSERT INTO experience_publications (saved_walk_id, slug, is_default, overrides_json, status, "
                      "published_at, published_commit, public_species_json, created_at, updated_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (row["saved_walk_id"], row["slug"], row["is_default"], row["overrides_json"], row["status"],
                       row["published_at"], row["published_commit"], row["public_species_json"], now, now))
    pub_id = cur.lastrowid
    for k in SECRET_KEYS:
        con.execute("UPDATE app_settings SET value = '', updated_at = ?, updated_by = 'audit A-04' WHERE key = ?",
                    (now, k))
    con.commit()

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    got = con.execute("SELECT id, saved_walk_id, slug, is_default, overrides_json, status, published_at, "
                      "published_commit, length(public_species_json) FROM experience_publications WHERE id = ?",
                      (pub_id,)).fetchone()
    print(f"Read-back experience_publications {got}")
    ok = (got[1:8] == (row["saved_walk_id"], row["slug"], row["is_default"], row["overrides_json"], row["status"],
                       row["published_at"], row["published_commit"]))
    for k in SECRET_KEYS:
        v = con.execute("SELECT key, value, updated_by, updated_at FROM app_settings WHERE key = ?", (k,)).fetchone()
        print(f"Read-back app_settings {v[0]}: value {'EMPTY' if v[1] == '' else 'NOT EMPTY'}, updated_by {v[2]}, {v[3]}")
        ok = ok and v[1] == ""
    print("Read-back:", "ok" if ok else "MISMATCH")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
