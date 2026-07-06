#!/usr/bin/env python3
"""
scripts/populate_phenology.py

Bulk-populates species.flower_months, fruit_months, leaf_months, peak_season
from enrichment data already stored in the DB.

Two data sources (processed in this order):

  1. enrichment_sources (source_name='pfaf')
     PFAF HTML pages contain a consistent sentence:
       "It is in flower from April to June, and the seeds ripen from July to September."
       "in leaf from April to November" / "in leaf all year"
     Yields: flower_months, fruit_months, leaf_months (month CSV, e.g. "4,5,6")

  2. culinary_info.seasonal_peak
     Free-text harvest-peak label, e.g. "Spring, Summer" / "May, July, Autumn"
     Copied verbatim to species.peak_season.

Rules:
  - NULL-safe: a field is only written if it is currently NULL on the species row.
    Manually curated values are never overwritten.
  - Each species gets at most one PFAF extraction (most recent fetch by id).
  - "in leaf all year" → leaf_months = "1,2,3,4,5,6,7,8,9,10,11,12"

Usage:
  python scripts/populate_phenology.py           # dry run (default)
  python scripts/populate_phenology.py --live    # write changes to DB
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Month name → integer map (full names only; PFAF always uses full names)
# ---------------------------------------------------------------------------

MONTH_NAMES: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# ---------------------------------------------------------------------------
# PFAF regex patterns (applied to HTML-stripped text)
# ---------------------------------------------------------------------------

# "in flower from April to June"  or  "in flower in July"
FLOWER_PAT = re.compile(
    r"\bin flower\s+(?:in|from)\s+([A-Za-z]+)(?:\s+to\s+([A-Za-z]+))?",
    re.IGNORECASE,
)

# "seeds ripen from July to September"  or  "seeds ripen in October"
# Also catches "seed ripen" and "seeds mature"
FRUIT_PAT = re.compile(
    r"\bseeds?\s+(?:ripen|mature)s?\s+(?:in|from)\s+([A-Za-z]+)(?:\s+to\s+([A-Za-z]+))?",
    re.IGNORECASE,
)

# "in leaf from April to November"  or  "in leaf all year"
LEAF_PAT = re.compile(
    r"\bin leaf\s+(all\s+year|(?:from|in)\s+([A-Za-z]+)(?:\s+to\s+([A-Za-z]+))?)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _months_range(m1: str, m2: Optional[str]) -> List[int]:
    """
    Convert a month-name range to a sorted list of month integers.
    Handles Dec-Feb wrap-around.
    Returns [] if m1 is not a recognised month name.
    """
    n1 = MONTH_NAMES.get(m1.lower())
    if n1 is None:
        return []
    if not m2:
        return [n1]
    n2 = MONTH_NAMES.get(m2.lower())
    if n2 is None:
        return [n1]
    if n1 <= n2:
        return list(range(n1, n2 + 1))
    # Wrap-around (e.g. November → February)
    return list(range(n1, 13)) + list(range(1, n2 + 1))


def _to_csv(months: List[int]) -> Optional[str]:
    if not months:
        return None
    return ",".join(str(m) for m in sorted(set(months)))


def _month_label(csv: Optional[str]) -> str:
    """Human-readable label for a months CSV string."""
    if not csv:
        return ""
    LABELS = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }
    try:
        return " · ".join(LABELS[int(m)] for m in csv.split(","))
    except Exception:
        return csv


def extract_pfaf_phenology(html: str) -> Dict[str, Optional[str]]:
    """
    Parse PFAF HTML and return a dict with keys:
      flower_months, fruit_months, leaf_months  (CSV strings or None)
    """
    # Strip HTML tags
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", plain)

    result: Dict[str, Optional[str]] = {
        "flower_months": None,
        "fruit_months": None,
        "leaf_months": None,
    }

    fm = FLOWER_PAT.search(plain)
    if fm:
        months = _months_range(fm.group(1), fm.group(2))
        result["flower_months"] = _to_csv(months)

    fr = FRUIT_PAT.search(plain)
    if fr:
        months = _months_range(fr.group(1), fr.group(2))
        result["fruit_months"] = _to_csv(months)

    lf = LEAF_PAT.search(plain)
    if lf:
        if re.match(r"all\s+year", lf.group(1), re.IGNORECASE):
            result["leaf_months"] = "1,2,3,4,5,6,7,8,9,10,11,12"
        else:
            months = _months_range(lf.group(2), lf.group(3))
            result["leaf_months"] = _to_csv(months)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(live: bool) -> None:
    mode = "LIVE" if live else "DRY-RUN"
    print(f"\n{'='*60}")
    print(f"populate_phenology.py  [{mode}]")
    print(f"{'='*60}\n")

    async with AsyncSessionLocal() as db:

        # ------------------------------------------------------------------
        # 1. Load current species phenology state
        # ------------------------------------------------------------------
        rows = (await db.execute(text(
            "SELECT id, scientific_name, flower_months, fruit_months, leaf_months, peak_season "
            "FROM species ORDER BY scientific_name"
        ))).fetchall()

        # Index by id for quick lookup
        species: dict[int, dict] = {
            r[0]: {
                "id": r[0],
                "name": r[1],
                "flower_months": r[2],
                "fruit_months": r[3],
                "leaf_months": r[4],
                "peak_season": r[5],
                # Pending updates (populated below)
                "_new_flower": None,
                "_new_fruit": None,
                "_new_leaf": None,
                "_new_peak": None,
                "_sources": [],
            }
            for r in rows
        }

        # ------------------------------------------------------------------
        # 2. Pass 1 — PFAF HTML extraction
        # ------------------------------------------------------------------
        print("Pass 1: PFAF HTML extraction (flower / fruit / leaf months)")
        print("-" * 60)

        pfaf_rows = (await db.execute(text(
            """
            SELECT e.species_id, e.raw_response_json
            FROM enrichment_sources e
            WHERE e.source_name = 'pfaf'
              AND e.id = (
                  SELECT MAX(e2.id) FROM enrichment_sources e2
                  WHERE e2.species_id = e.species_id AND e2.source_name = 'pfaf'
              )
              AND length(e.raw_response_json) > 200
            ORDER BY e.species_id
            """
        ))).fetchall()

        pfaf_total = pfaf_new_flower = pfaf_new_fruit = pfaf_new_leaf = 0

        for species_id, html in pfaf_rows:
            sp = species.get(species_id)
            if not sp:
                continue  # orphaned enrichment row

            pfaf_total += 1
            extracted = extract_pfaf_phenology(html)

            # Only propose updates for currently-NULL fields
            if sp["flower_months"] is None and extracted["flower_months"]:
                sp["_new_flower"] = extracted["flower_months"]
                sp["_sources"].append("pfaf→flower")
                pfaf_new_flower += 1

            if sp["fruit_months"] is None and extracted["fruit_months"]:
                sp["_new_fruit"] = extracted["fruit_months"]
                sp["_sources"].append("pfaf→fruit")
                pfaf_new_fruit += 1

            if sp["leaf_months"] is None and extracted["leaf_months"]:
                sp["_new_leaf"] = extracted["leaf_months"]
                sp["_sources"].append("pfaf→leaf")
                pfaf_new_leaf += 1

        print(f"  PFAF rows processed : {pfaf_total}")
        print(f"  New flower_months   : {pfaf_new_flower}")
        print(f"  New fruit_months    : {pfaf_new_fruit}")
        print(f"  New leaf_months     : {pfaf_new_leaf}")

        # ------------------------------------------------------------------
        # 3. Pass 2 — culinary_info.seasonal_peak → peak_season
        # ------------------------------------------------------------------
        print()
        print("Pass 2: culinary_info.seasonal_peak → peak_season")
        print("-" * 60)

        peak_rows = (await db.execute(text(
            """
            SELECT ci.species_id, ci.seasonal_peak
            FROM culinary_info ci
            WHERE ci.seasonal_peak IS NOT NULL AND ci.seasonal_peak != ''
            ORDER BY ci.species_id
            """
        ))).fetchall()

        peak_new = 0

        for species_id, seasonal_peak in peak_rows:
            sp = species.get(species_id)
            if not sp:
                continue
            if sp["peak_season"] is None:
                sp["_new_peak"] = seasonal_peak.strip()
                sp["_sources"].append("culinary→peak")
                peak_new += 1

        print(f"  culinary_info rows  : {len(peak_rows)}")
        print(f"  New peak_season     : {peak_new}")

        # ------------------------------------------------------------------
        # 4. Collect all species that will be updated
        # ------------------------------------------------------------------
        updates = [
            sp for sp in species.values()
            if sp["_new_flower"] or sp["_new_fruit"] or sp["_new_leaf"] or sp["_new_peak"]
        ]

        print()
        print(f"Species with at least one new field: {len(updates)}")
        print()

        # ------------------------------------------------------------------
        # 5. Print per-species report
        # ------------------------------------------------------------------
        print(f"{'Species':<38} {'flower':<15} {'fruit':<15} {'leaf':<15} {'peak_season'}")
        print("-" * 110)

        for sp in sorted(updates, key=lambda x: x["name"]):
            fl  = sp["_new_flower"] or "(keep NULL)"
            fr  = sp["_new_fruit"]  or "(keep NULL)"
            lf  = sp["_new_leaf"]   or "(keep NULL)"
            pk  = (sp["_new_peak"][:40] + "…") if sp["_new_peak"] and len(sp["_new_peak"]) > 40 else (sp["_new_peak"] or "(keep NULL)")
            print(
                f"  {sp['name']:<36} {_month_label(sp['_new_flower']) or '—':<15} "
                f"{_month_label(sp['_new_fruit']) or '—':<15} "
                f"{_month_label(sp['_new_leaf']) or '—':<15} "
                f"{pk}"
            )

        # ------------------------------------------------------------------
        # 6. Write (live only)
        # ------------------------------------------------------------------
        if not live:
            print()
            print(f"[DRY-RUN] No changes written. Re-run with --live to apply.")
            return

        print()
        print("Writing to database…")

        written_flower = written_fruit = written_leaf = written_peak = 0

        for sp in updates:
            sp_id = sp["id"]

            if sp["_new_flower"]:
                await db.execute(
                    text("UPDATE species SET flower_months = :v WHERE id = :id AND flower_months IS NULL"),
                    {"v": sp["_new_flower"], "id": sp_id},
                )
                written_flower += 1

            if sp["_new_fruit"]:
                await db.execute(
                    text("UPDATE species SET fruit_months = :v WHERE id = :id AND fruit_months IS NULL"),
                    {"v": sp["_new_fruit"], "id": sp_id},
                )
                written_fruit += 1

            if sp["_new_leaf"]:
                await db.execute(
                    text("UPDATE species SET leaf_months = :v WHERE id = :id AND leaf_months IS NULL"),
                    {"v": sp["_new_leaf"], "id": sp_id},
                )
                written_leaf += 1

            if sp["_new_peak"]:
                await db.execute(
                    text("UPDATE species SET peak_season = :v WHERE id = :id AND peak_season IS NULL"),
                    {"v": sp["_new_peak"], "id": sp_id},
                )
                written_peak += 1

        await db.commit()

        print()
        print("Done. Fields written to DB:")
        print(f"  flower_months : {written_flower}")
        print(f"  fruit_months  : {written_fruit}")
        print(f"  leaf_months   : {written_leaf}")
        print(f"  peak_season   : {written_peak}")
        print(f"  species touched: {len(updates)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-populate species phenology from PFAF + culinary_info data."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Write changes to the database. Without this flag the script is a dry-run.",
    )
    args = parser.parse_args()
    asyncio.run(run(live=args.live))


if __name__ == "__main__":
    main()
