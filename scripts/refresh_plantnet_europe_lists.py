#!/usr/bin/env python3
"""
Refetch PlantNet's five European regional species lists into
data/reference/plantnet_europe_species.json.

The lists drive regional demotion (app/services/regional_demotion.py): PlantNet
is queried with project "all", and candidates not listed in any European
project are re-ranked below the listed ones and flagged non_european. Scores
are never changed; nothing is hidden.

Quota: uses GET /v2/projects/{project}/species only — a catalogue endpoint.
It never calls /v2/identify, so it costs no identification quota.

Rules:
  - Writes the reference file only; never touches the database.
  - Writes atomically (temp file + rename): a failed fetch leaves the previous
    file in place rather than a partial one.
  - Every list records its source project and fetch date.

Usage:
    python scripts/refresh_plantnet_europe_lists.py            # fetch + write
    python scripts/refresh_plantnet_europe_lists.py --dry-run  # fetch, print counts, no write
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402

OUT = ROOT / "data" / "reference" / "plantnet_europe_species.json"
SPECIES_URL = "https://my-api.plantnet.org/v2/projects/{project}/species"
# WGSRPD level-2 European regions as PlantNet names them (GET /v2/projects).
PROJECTS = [
    "k-northern-europe",
    "k-middle-europe",
    "k-southwestern-europe",
    "k-southeastern-europe",
    "k-eastern-europe",
]
# Largest list is ~7.7k species; one page comfortably holds every list.
PAGE_SIZE = 20000


def fetch(project: str, api_key: str) -> list:
    r = requests.get(
        SPECIES_URL.format(project=project),
        params={"api-key": api_key, "pageSize": PAGE_SIZE},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"{project}: unexpected response shape {type(data).__name__}")
    if len(data) >= PAGE_SIZE:
        # Never silently truncate — a short list would demote real natives.
        raise RuntimeError(f"{project}: {len(data)} rows hit pageSize {PAGE_SIZE}; raise PAGE_SIZE")
    return sorted({
        (x.get("scientificNameWithoutAuthor") or "").strip()
        for x in data if (x.get("scientificNameWithoutAuthor") or "").strip()
    })


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="fetch and report; do not write")
    args = ap.parse_args()

    api_key = settings.plantnet_api_key
    if not api_key:
        print("PLANTNET_API_KEY not set", file=sys.stderr)
        return 1

    lists = []
    for project in PROJECTS:
        species = fetch(project, api_key)
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"{project:24} {len(species):6} species  (fetched {fetched_at})")
        lists.append({
            "project": project,
            "source": SPECIES_URL.format(project=project),
            "fetched_at": fetched_at,
            "species_count": len(species),
            "species": species,
        })

    if args.dry_run:
        print("dry-run: nothing written")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "description": ("PlantNet European regional species lists (WGSRPD level 2). "
                        "Used by app/services/regional_demotion.py. Regenerate with "
                        "scripts/refresh_plantnet_europe_lists.py — no identification quota."),
        "lists": lists,
    }, ensure_ascii=False, indent=1))
    tmp.replace(OUT)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
