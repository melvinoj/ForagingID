"""
Source-link species check — the ONE rule (Melvin, 28 Oct 2026; CLOSEOUT_28oct
section 4 #2).

A culinary source link is FLAGGED when neither its title nor its URL names the
species: scientific name, display common name, or a synonym. Example: elder's
"Ground elder – Identification…" page (a different plant) and Wildman Steve
Brill's generic curriculum / day-camp / scout pages.

Flagged links are never deleted. They are hidden from printed and guest outputs
and shown to the curator with a flag (species page). Names match on a word
start ("elderberr" in "elderberries" is fine; "elder" inside "ground elder"
only matches a species whose own name is "elder"), case- and accent-blind; URL
separators (- _ + / %20 .) count as spaces.
"""
import re
import unicodedata
from typing import Iterable, List, Optional
from urllib.parse import unquote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _norm(s: Optional[str]) -> str:
    s = re.sub(r"['\u2019\u2018`]", "", unquote(s or ""))          # dryad's = dryad’s = dryads
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " " + re.sub(r"[^a-z0-9]+", " ", s).strip() + " "


def species_link_names(scientific_name: Optional[str], display_common: Optional[str],
                       synonyms: Iterable[str] = ()) -> List[str]:
    """The normalised names a link must carry (empty names dropped)."""
    out = []
    for n in [scientific_name, display_common, *synonyms]:
        k = _norm(n).strip()
        if k and k not in out:
            out.append(k)
    return out


def link_names_species(link: dict, names: List[str]) -> bool:
    """True when the link's title or URL names one of `names`."""
    text = _norm(link.get("title")) + _norm(link.get("url"))
    return any(" " + n in text for n in names)


def flag_links(links: Optional[list], names: List[str]) -> list:
    """Copies of the links, each with flagged: bool. No names → every link flagged
    (fails safe: nothing to check against)."""
    return [dict(lk, flagged=not link_names_species(lk, names)) for lk in (links or [])
            if isinstance(lk, dict)]


async def names_for_species(db: AsyncSession, sp) -> List[str]:
    from app.models.species import SpeciesSynonym, display_common_name
    import json as _json
    try:
        commons = _json.loads(sp.common_names) if sp.common_names else []
    except (TypeError, ValueError):
        commons = []
    syns = (await db.execute(
        select(SpeciesSynonym.synonym_scientific_name)
        .where(SpeciesSynonym.canonical_species_id == sp.id))).scalars().all()
    return species_link_names(sp.scientific_name,
                              display_common_name(sp.preferred_common_name, commons), syns)


async def apply_link_check(db: AsyncSession, sp, culinary_dict: Optional[dict], is_guest: bool) -> None:
    """In place on a _culinary_to_dict() output: culinary_links gain `flagged`;
    a guest never receives a flagged link."""
    if not culinary_dict or not culinary_dict.get("culinary_links"):
        return
    flagged = flag_links(culinary_dict["culinary_links"], await names_for_species(db, sp))
    culinary_dict["culinary_links"] = [lk for lk in flagged if not lk["flagged"]] if is_guest else flagged
