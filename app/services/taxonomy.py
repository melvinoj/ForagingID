"""
taxonomy.py — pure, deterministic helpers for taxon name normalization.

normalize_taxon_key() produces a collision-resistant lookup key for a
scientific name. It collapses typographic variants that should be considered
the same taxon (autonym trinomials, hybrid × markers) while leaving
inter-genus synonyms visibly different — so Trametes ≠ Polyporus.

No DB access. No side effects. Safe to call from any context.
"""

import re
import unicodedata

# Rank abbreviations that appear as token[2] in trinomials but are NOT
# autonyms — never drop the following token when one of these is token[2].
_RANK_ABBREVS = frozenset({
    "subsp", "ssp", "var", "f", "forma", "cv",
    "nothosubsp", "nothovar",
})

_WS = re.compile(r"\s+")


def normalize_taxon_key(name: str) -> str:
    """
    Return a normalized lookup key for a scientific taxon name.

    Steps (applied in order):
      a. Strip outer whitespace; lowercase; collapse internal whitespace runs
         to a single space.
      b. Remove every U+00D7 (×) character.
      c. Split into tokens; drop tokens that equal exactly "x" (the ASCII
         hybrid marker used when × is unavailable). Token-equality only —
         never strips "x" from within a word (taxus, larix, buxus survive).
      d. Re-collapse whitespace (handled implicitly by join after split).
      e. Autonym collapse: if exactly 3 tokens remain AND token[2] == token[1]
         AND token[1] is not a rank abbreviation, drop token[2].
      f. Return single-space-joined tokens.

    Examples:
      "Taxus baccata"           -> "taxus baccata"   (x inside word: safe)
      "Larix decidua decidua"   -> "larix decidua"   (autonym collapsed)
      "Geranium × oxonianum"    -> "geranium oxonianum"
      "Geranium oxonianum"      -> "geranium oxonianum"
      "Polyporus versicolor"    -> "polyporus versicolor"  (≠ trametes)
    """
    if not name:
        return ""

    # (a) strip / lowercase / collapse whitespace
    key = _WS.sub(" ", name.strip().lower())

    # (b) remove × (U+00D7)
    key = key.replace("×", "")

    # (c) split and drop bare "x" tokens
    tokens = [t for t in key.split() if t != "x"]

    # (d) implicit — join collapses any gaps left by step (b)/(c)

    # (e) autonym collapse
    if (
        len(tokens) == 3
        and tokens[2] == tokens[1]
        and tokens[1] not in _RANK_ABBREVS
    ):
        tokens = tokens[:2]

    # (f) join
    return " ".join(tokens)


def collapse_autonym(name: str) -> str:
    """
    Collapse a trailing autonym token from a trinomial display name,
    preserving original case.

    "Larix decidua decidua" → "Larix decidua"   (autonym collapsed)
    "Geranium × oxonianum"  → unchanged          (× token, not autonym)
    "Taxus baccata"         → unchanged          (binomial)
    "Daucus carota subsp. sativus" → unchanged   (real infraspecific, 4 tokens)

    Rule: exactly 3 whitespace-separated tokens AND token[2].lower() ==
    token[1].lower() AND token[1] is not a rank abbreviation → drop token[2].
    """
    if not name:
        return name
    tokens = _WS.sub(" ", name.strip()).split()
    if (
        len(tokens) == 3
        and tokens[2].lower() == tokens[1].lower()
        and tokens[1].lower() not in _RANK_ABBREVS
    ):
        return f"{tokens[0]} {tokens[1]}"
    return name
