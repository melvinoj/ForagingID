"""
is_ai_placeholder — the ONLY definition of "this AI draft text is a refusal /
placeholder, not content". Extend it here; never copy the marker lists into a
call site (two copies had already drifted: enrichment.py and culinary.py).

Called at every point that turns model output into a SpeciesAIDraft
(enrichment._maybe_generate_ai_drafts, enrichment._section_ai_draft,
culinary.py on-demand drafts, recipes.py regenerate) and at draft approval,
where an unedited placeholder is rejected.

Two rules, by field:

- taste_notes / recipe: a refusal phrase ANYWHERE in the text. (Existing rule,
  unchanged in behaviour for these fields apart from the added phrases.)
- medicinal_notes / medicinal_folklore: only the OPENING sentence is checked.
  The standard "No known traditional medicinal uses" / "No traditional
  medicinal uses recorded in available sources." default, and the
  "Traditional and folk use only — not medical advice." disclaimer, open
  legitimate text and pass; "Based solely on the provided source data…" or
  "I appreciate your request…" do not.

"provided source" is checked in the opening sentence for every field, and only
when that sentence also says there is nothing (no / not / cannot). Anywhere in
the text it would reject real notes that end with a caveat ("…no further detail
in the provided sources on how taste varies"); without the negation it would
reject real content that opens "Based solely on the provided source, X is
traditionally used as…".

Any other field name returns False (wikidata/fungi edibility suggestions,
whisper transcripts and system defaults are not model prose).
"""

import re
from typing import Optional

_CULINARY_FIELDS = {"taste_notes", "recipe"}
_MEDICINAL_FIELDS = {"medicinal_notes", "medicinal_folklore"}

# Refusal / non-answer phrases (lower-case).
_REFUSAL_MARKERS = (
    "not enough information",
    "not enough sourced",
    "i don't have",
    "i cannot", "i'm unable",
    "unable to provide", "cannot provide",
    "insufficient", "not able to",
    "no sourced information",
    "cannot determine",
    "i must inform you",
    "i appreciate your request",
)

# Meta-talk about the prompt's sources — a placeholder only when it opens the text.
_OPENING_ONLY_MARKERS = (
    "provided source",
    "source material provided",
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s|\n")

# An opening-only marker counts only together with a "there is nothing" word in
# the same sentence: "Based solely on the provided source data, there are no
# mentions…" is a refusal; "Based solely on the provided source, Stachys
# officinalis is traditionally used as a nervine…" is content.
_NEGATION = re.compile(r"\b(?:no|not|none|cannot)\b|n't")


def _opening(text: str) -> str:
    """First sentence (or first line), capped at 250 chars, lower-cased."""
    t = text.strip().lstrip("#*_ ").strip()
    m = _SENTENCE_END.search(t)
    return (t[:m.start()] if m else t)[:250].lower()


def is_ai_placeholder(field: str, text: Optional[str]) -> bool:
    """True when `text` for AI-drafted `field` is a refusal/placeholder."""
    if not text or not text.strip():
        return False
    opening = _opening(text)
    if any(m in opening for m in _OPENING_ONLY_MARKERS) and _NEGATION.search(opening):
        return field in _CULINARY_FIELDS or field in _MEDICINAL_FIELDS
    if field in _CULINARY_FIELDS:
        low = text.lower()
        return any(m in low for m in _REFUSAL_MARKERS)
    if field in _MEDICINAL_FIELDS:
        return any(m in opening for m in _REFUSAL_MARKERS)
    return False
