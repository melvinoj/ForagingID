"""
Headless smoke pass — EVIDENCE ONLY, never "verified" (CLAUDE.md, Melvin 28 Oct 2026).

Loads each given page on a SCRATCH server and reports console errors, page
exceptions, failed requests and HTTP >= 400 responses. It never touches the
live server (:8000) or data/foragingid.db (read once, read-only, through the
SQLite backup API).

Scratch layout (outside the repo, so the live uvicorn reload never sees it):
  ~/ForagingID_scratch/tree/   APFS copy-on-write clone (cp -c) of the project
                               minus .git, .env, snapshots/, logs/, live DB files.
                               app/ frontend/ scripts/ migrations/ are re-cloned
                               every run so the scratch runs the current code.
  ~/ForagingID_scratch/tree/data/foragingid.db   fresh backup-API copy per run
  ~/ForagingID_scratch/home/   throwaway HOME (no publish repo, no PhoneForaging)

Server: 127.0.0.1:8001, no --reload, FORAGINGID_ENV_FILE= (no .env), every API
key empty, DATABASE_URL pointing at the scratch DB. photo_library_path is set
to a missing folder IN THE SCRATCH DB ONLY so the syncthing loop ingests nothing.
The server is started and stopped by this script.

Run:  ~/foragingid-venv/bin/python scripts/dev/smoke_pass.py /lists.html /print.html
      --guest  also loads each page as a LAN guest (X-Forwarded-For), not curator
      --keep   leave the 8001 server running afterwards (prints its PID)
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LIVE = Path(__file__).resolve().parents[2]
SCRATCH = Path.home() / "ForagingID_scratch"
TREE = SCRATCH / "tree"
HOME = SCRATCH / "home"
PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"

CODE_DIRS = ["app", "frontend", "scripts", "migrations"]
SKIP_TOP = {".git", ".env", "snapshots", "logs", ".claude", "dist", "exports", "Obsidian"}
KEY_VARS = ["PLANTNET_API_KEY", "INATURALIST_APP_ID", "INATURALIST_APP_SECRET",
            "INATURALIST_API_TOKEN", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
            "GDRIVE_ACCESS_TOKEN", "OPENAI_API_KEY", "ORS_API_KEY",
            "THUNDERFOREST_API_KEY"]


def _clone(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        shutil.rmtree(dst) if dst.is_dir() and not dst.is_symlink() else dst.unlink()
    subprocess.run(["cp", "-cR", str(src), str(dst)], check=True)


def build_scratch() -> None:
    assert SCRATCH in TREE.parents and LIVE not in TREE.parents and TREE != LIVE
    TREE.mkdir(parents=True, exist_ok=True)
    HOME.mkdir(parents=True, exist_ok=True)
    for entry in LIVE.iterdir():
        name = entry.name
        if name in SKIP_TOP or name.startswith(".env"):
            continue
        if name == "data":
            (TREE / "data").mkdir(exist_ok=True)
            for d in entry.iterdir():
                if d.name.startswith("foragingid") or d.name.startswith("._") or d.suffix in (".db", ".sqlite"):
                    continue
                if not (TREE / "data" / d.name).exists():
                    _clone(d, TREE / "data" / d.name)
            continue
        if name in CODE_DIRS or entry.is_file() or not (TREE / name).exists():
            _clone(entry, TREE / name)
    for leftover in TREE.glob(".env*"):
        leftover.unlink()
    (TREE / "logs").mkdir(exist_ok=True)

    db = TREE / "data" / "foragingid.db"
    for side in (db, db.with_name("foragingid.db-wal"), db.with_name("foragingid.db-shm")):
        if side.exists():
            side.unlink()
    src = sqlite3.connect(f"file:{LIVE / 'data' / 'foragingid.db'}?mode=ro", uri=True)
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    src.close()
    assert dst.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    dst.execute("UPDATE app_settings SET value=? WHERE key='photo_library_path'",
                (str(SCRATCH / "no_such_folder"),))
    dst.commit()
    dst.close()


def start_server() -> subprocess.Popen:
    try:
        urllib.request.urlopen(f"{BASE}/api/processes/active", timeout=2)
        sys.exit(f"something is already listening on {PORT} — stop it first")
    except OSError:
        pass
    env = {k: v for k, v in os.environ.items() if k not in KEY_VARS}
    env.update({k: "" for k in KEY_VARS})
    env.update({
        "HOME": str(HOME),
        "FORAGINGID_ENV_FILE": "",
        "DATABASE_URL": f"sqlite+aiosqlite:///{TREE / 'data' / 'foragingid.db'}",
    })
    py = Path.home() / "foragingid-venv" / "bin" / "python"
    log = open(SCRATCH / "server_8001.log", "w")
    proc = subprocess.Popen(
        [str(py), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=TREE, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        if proc.poll() is not None:
            sys.exit(f"scratch server exited — see {SCRATCH / 'server_8001.log'}")
        try:
            urllib.request.urlopen(f"{BASE}/api/processes/active", timeout=2)
            return proc
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    sys.exit("scratch server did not come up in 60 s")


def load_pages(pages, guest: bool):
    from playwright.sync_api import sync_playwright
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for path in pages:
            headers = {"X-Forwarded-For": "192.168.1.77"} if guest else {}
            ctx = browser.new_context(extra_http_headers=headers, service_workers="block")
            page = ctx.new_page()
            r = {"page": path, "as": "guest" if guest else "curator",
                 "console_errors": [], "page_errors": [], "failed": [], "http_errors": []}
            page.on("console", lambda m, r=r: m.type == "error" and r["console_errors"].append(m.text[:300]))
            page.on("pageerror", lambda e, r=r: r["page_errors"].append(str(e)[:300]))
            page.on("requestfailed", lambda q, r=r: r["failed"].append(f"{q.url[:160]} {q.failure}"))
            page.on("response", lambda s, r=r: s.status >= 400 and r["http_errors"].append(f"{s.status} {s.url[:160]}"))
            try:
                page.goto(BASE + path, wait_until="load", timeout=45000)
            except Exception as exc:  # timeout on a page that keeps polling is reported, not fatal
                r["page_errors"].append(f"goto: {str(exc)[:200]}")
            page.wait_for_timeout(3000)  # polling pages never reach networkidle
            ctx.close()
            results.append(r)
        browser.close()
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--guest", action="store_true")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    build_scratch()
    proc = start_server()
    try:
        res = load_pages(a.pages, False)
        if a.guest:
            res += load_pages(a.pages, True)
    finally:
        if a.keep:
            print(f"scratch server left running, PID {proc.pid}")
        else:
            proc.terminate()
            proc.wait(timeout=15)
    print(json.dumps(res, indent=1))
    bad = sum(len(r["console_errors"]) + len(r["page_errors"]) + len(r["http_errors"]) for r in res)
    print(f"smoke: {len(res)} page loads, {bad} errors (evidence only, not verification)")


if __name__ == "__main__":
    main()
