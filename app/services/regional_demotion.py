"""
regional_demotion.py — re-rank PlantNet candidates so European species come first.

PlantNet is queried with project "all" (world flora; it takes no coordinates),
so a European photo regularly gets another continent's look-alike near the top
(A/B of 19 Oct 2026: ~1.5 non-European names per top 5; Crataegus monogyna #6
and Larix decidua #10 behind them). A regional project fixes that but drops
garden exotics that are not on its list (Helianthus silphioides, Fuchsia
magellanica, Platanus × hispanica). This module keeps `all` and demotes instead:

  * stable partition — European-listed candidates first, then the rest, each
    group keeping PlantNet's own order;
  * scores are NEVER altered;
  * every demoted candidate is flagged non_european=True and stays in the list
    (the UI labels it "not native to Europe — planted?"); nothing is hidden;
  * PlantNet's raw rank is kept on each candidate (raw_rank) for audit.

"European" = listed in any of PlantNet's five European regional projects
(data/reference/plantnet_europe_species.json, refreshed by
scripts/refresh_plantnet_europe_lists.py). Names are matched via
normalize_taxon_key / collapse_autonym. Never demoted:
  * hybrids (any name with × or a bare "x" token) — garden/forestry hybrids are
    often absent from the lists but are not exotic look-alikes;
  * infraspecific names whose parent species (genus + epithet) is listed;
  * genus-only or otherwise unparseable names — there is no basis to judge.

If the reference file is missing or unreadable, nothing is demoted (logged
once). Ranking-only: this module decides order and a flag, never a verdict,
threshold, status or edibility.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import FrozenSet, List, Optional, Sequence

from app.services.taxonomy import collapse_autonym, normalize_taxon_key

log = logging.getLogger(__name__)

REFERENCE_PATH = (Path(__file__).resolve().parent.parent.parent
                  / "data" / "reference" / "plantnet_europe_species.json")

NON_EUROPEAN_LABEL = "not native to Europe — planted?"


def _key(name: str) -> str:
    return normalize_taxon_key(collapse_autonym(name or ""))


@lru_cache(maxsize=1)
def european_keys() -> Optional[FrozenSet[str]]:
    """Normalized keys of every species in the five European lists, or None if unavailable."""
    try:
        data = json.loads(REFERENCE_PATH.read_text())
        keys = frozenset(
            _key(n) for lst in data["lists"] for n in lst["species"] if n
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("[regional-demotion] reference list unavailable (%s) — demotion disabled", exc)
        return None
    if not keys:
        log.warning("[regional-demotion] reference list is empty — demotion disabled")
        return None
    return keys


def _is_hybrid(name: str) -> bool:
    return "×" in name or any(t.lower() == "x" for t in name.split())


def is_non_european(name: str, keys: Optional[FrozenSet[str]] = None) -> bool:
    """True only when the name is a species-level name absent from every European list."""
    keys = european_keys() if keys is None else keys
    if not keys or not name or _is_hybrid(name):
        return False
    key = _key(name)
    tokens = key.split()
    if len(tokens) < 2:
        return False                      # genus-only / unparseable: no basis to judge
    if key in keys:
        return False
    if len(tokens) > 2 and " ".join(tokens[:2]) in keys:
        return False                      # infraspecific, parent species listed
    return True


def demote_candidates(candidates: Sequence, keys: Optional[FrozenSet[str]] = None) -> List:
    """
    Stable re-rank of PlantNet candidates (objects with .scientific_name and .rank).

    Mutates each candidate in place: raw_rank = PlantNet's rank, rank = new
    1-based position, non_european = flag. Returns the re-ordered list.
    Scores are untouched. Idempotent: an already-demoted list keeps its raw_rank.
    """
    keys = european_keys() if keys is None else keys
    ordered = sorted(candidates, key=lambda c: (getattr(c, "raw_rank", None) or c.rank))
    for c in ordered:
        if getattr(c, "raw_rank", None) is None:
            c.raw_rank = c.rank
        c.non_european = is_non_european(c.scientific_name, keys)
    result = ([c for c in ordered if not c.non_european]
              + [c for c in ordered if c.non_european])
    for i, c in enumerate(result, start=1):
        c.rank = i
    return result


def raw_order(candidates: Sequence) -> List:
    """The same candidates back in PlantNet's raw order (for decisions that must ignore demotion)."""
    return sorted(candidates, key=lambda c: (getattr(c, "raw_rank", None) or c.rank))


def display_slots(candidates: Sequence, n: int) -> List:
    """
    Candidates to show in an N-slot UI list: the demoted top N, plus any
    candidate that was in PlantNet's raw top N but was pushed out by demotion.
    Guarantees demotion never hides a candidate the raw list would have shown.
    """
    shown = list(candidates[:n])
    seen = {id(c) for c in shown}
    for c in raw_order(candidates)[:n]:
        if id(c) not in seen:
            shown.append(c)
            seen.add(id(c))
    return shown
