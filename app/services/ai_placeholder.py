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

The "no medicinal uses" claim — the ONLY definition (the retired A5 default and
the model's own "nothing found" answer, in any of its wordings, ANYWHERE in the
text: after a disclaimer, a heading or culinary text, or at the end). Since
21 Oct 2026 (Melvin D3) no automated path writes it. The refill, the approve
guard and Review's red flag all read it through pfaf_fallback; Review and the
species page get it as a server flag — no copy of the rule in JS.

  no_medicinal_uses_claim_spans()  — the sentences making the claim
  has_no_medicinal_uses_claim()    — any such sentence
  is_only_no_medicinal_uses_claim() — nothing but the claim before it
                                     (disclaimer / heading at most): the whole
                                     text is the "nothing found" answer
  strip_no_medicinal_uses_claims() — the text with only those sentences removed

A claim is "no" + an optional hedge (known / recorded / documented / specific /
explicit / detailed) or source meta-talk (information about, mention(s) of,
references to, documentation of, record of) + optional traditional / folk + 
"medicinal uses / use / applications / folklore" — or "does not
record / document / mention … ANY … medicinal uses". NOT a claim (narrower
negations, uses stated elsewhere):
  - scoped to a plant part: "no traditional medicinal uses of the root";
  - relative: "no further / additional / other / more … medicinal uses";
  - a hedge inside a though/although/but/while clause that qualifies a use just
    stated: "…with the treatment of gout, though no explicit medicinal use is
    described".
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
    # Refusal phrases only — the bare word "insufficient" is also a real use in
    # source text (PFAF: Verbena officinalis "insufficient lactation", Vinca minor
    # "insufficient blood supply"), which made real drafts read as refusals
    # (21 Oct 2026). A marker that collides with a real use is a phrase, not a word.
    "insufficient information", "insufficient data", "insufficient source",
    "insufficient detail", "insufficient context",
    "not able to",
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
    return ai_placeholder_reason(field, text) is not None


def ai_placeholder_reason(field: str, text: Optional[str]) -> Optional[str]:
    """Why is_ai_placeholder() says True — the rule and the marker it matched; None if not."""
    if not text or not text.strip():
        return None
    opening = _opening(text)
    meta = next((m for m in _OPENING_ONLY_MARKERS if m in opening), None)
    if meta and _NEGATION.search(opening) and (field in _CULINARY_FIELDS or field in _MEDICINAL_FIELDS):
        return f"opening sentence has {meta!r} with a negation"
    if field in _CULINARY_FIELDS:
        m = next((m for m in _REFUSAL_MARKERS if m in text.lower()), None)
        return f"refusal marker {m!r} in the text" if m else None
    if field in _MEDICINAL_FIELDS:
        m = next((m for m in _REFUSAL_MARKERS if m in opening), None)
        return f"refusal marker {m!r} in the opening sentence" if m else None
    return None


_TRAD = (r"(?:(?:traditional|folk|ethnobotanical|historical)"
         r"(?:\s*,?\s*(?:or\s+|and\s+)?(?:folk|traditional|ethnobotanical|historical))*\s+)?")
_NOUN = r"medicinal\s+(?:or\s+therapeutic\s+)?(?:folk\s+)?(?:uses?|applications?|folklore)\b"
_NO_USES_CLAIM = re.compile(
    r"\bno\s+"
    r"(?:(?:information|mentions?|references?|documentation|(?:explicit\s+)?record)\s+(?:about|regarding|on|of|to)\s+(?:any\s+)?)?"
    r"(?P<hedge>(?:known|recorded|documented|specific|specifically|explicit|detailed)\s+)?"
    + _TRAD + _NOUN
    # …or "does not record / document / mention … ANY (traditional) medicinal uses"
    + r"|\b(?:do|does|did)\s+not\s+(?:record|document|mention|list|contain|include|describe|attribute)\s+any\s+"
    + _TRAD + _NOUN,
    re.I,
)
_PART_SCOPED = re.compile(
    r"\s+(?:of|for|from|in)\s+(?:the\s+|its\s+)?(?:roots?|lea(?:f|ves)|flowers?|seeds?|bark|fruits?|"
    r"stems?|shoots?|sap|berr(?:y|ies)|bulbs?|tubers?|rhizomes?|buds?|gum|resin|oil|aerial\s+parts)\b", re.I)
_CONCESSIVE_BEFORE = re.compile(r"[,;]\s*(?:though|although|but|while)\s+$", re.I)
_NARROW_HEDGES = {"explicit", "specific", "specifically", "detailed"}

# A sentence: up to . ! ? (not after e.g./i.e./etc./cf./spp./var./subsp.) or a line end.
_SENT = re.compile(r"(?:[^.!?\n]|(?<=\be\.g)\.|(?<=\bi\.e)\.|(?<=\betc)\.|(?<=\bcf)\.|(?<=\bspp)\.|"
                   r"(?<=\bvar)\.|(?<=\bsubsp)\.)+(?:[.!?]+|(?=\n)|$)")
# What may precede a whole-text claim: the medicinal disclaimer, headings, rules, quotes, markup.
_PREAMBLE = re.compile(
    r"(?:\s|#[^\n]*\n|-{3,}|[*_'\"“”>()]|traditional\s+and\s+folk\s+use\s+only\s*[—–-]\s*not\s+medical\s+advice\.?)*",
    re.I)


def _is_claim(sentence: str, m) -> bool:
    if _PART_SCOPED.match(sentence[m.end():]):
        return False
    hedge = (m.groupdict().get("hedge") or "").strip().lower()
    if hedge in _NARROW_HEDGES and _CONCESSIVE_BEFORE.search(sentence[:m.start()]):
        return False
    return True


def no_medicinal_uses_claim_spans(text: Optional[str]) -> list:
    """(start, end) of every sentence in `text` that claims there are no medicinal uses."""
    spans = []
    for sm in _SENT.finditer(text or ""):
        sentence = sm.group(0)
        if any(_is_claim(sentence, m) for m in _NO_USES_CLAIM.finditer(sentence)):
            spans.append((sm.start(), sm.end()))
    return spans


def has_no_medicinal_uses_claim(text: Optional[str]) -> bool:
    return bool(no_medicinal_uses_claim_spans(text))


def is_only_no_medicinal_uses_claim(text: Optional[str]) -> bool:
    """The claim comes first — only a disclaimer / heading before it."""
    spans = no_medicinal_uses_claim_spans(text)
    if not spans:
        return False
    before = text[:spans[0][0]]
    return _PREAMBLE.fullmatch(before) is not None


def medicinal_notes_redraftable(text: Optional[str]) -> bool:
    """medicinal_notes a re-draft may replace (Fix A, 22 Oct 2026): empty, an AI
    placeholder / refusal, or only a "no medicinal uses" claim. Real text —
    approved or curator-written — is never drafted over (the caller also checks
    curator authorship and pending drafts)."""
    return not (text or "").strip() or is_ai_placeholder("medicinal_notes", text) \
        or is_only_no_medicinal_uses_claim(text)


def _join_at_cut(out: str, chunk: str) -> str:
    """Append `chunk` after a cut, collapsing the blank lines the cut left behind."""
    if out:
        while out.endswith("\n\n") and chunk.startswith("\n"):
            chunk = chunk[1:]
    return out + chunk


def strip_no_medicinal_uses_claims(text: Optional[str]) -> Optional[str]:
    """
    `text` with only the claim sentences removed; everything else verbatim.
    A removed sentence takes its own leading separator with it, and its **bold**
    / *italic* markers only when they wrap exactly that sentence. Blank lines
    left at a cut collapse to one; nothing else is touched.
    """
    spans = no_medicinal_uses_claim_spans(text)
    if not spans:
        return text
    out, pos = "", 0
    for start, end in spans:
        core = text[start:end].lstrip()
        starts_line = len(core) == end - start          # no separator of its own before it
        if core.startswith("**") and text[end:end + 2] == "**":
            end += 2
        elif core.startswith("*") and not core.startswith("**") and text[end:end + 1] == "*":
            end += 1
        if starts_line:                                 # take the next sentence's leading spaces instead
            while end < len(text) and text[end] in " \t":
                end += 1
        out = _join_at_cut(out, text[pos:start])
        pos = end
    out = _join_at_cut(out, text[pos:])
    if spans[0][0] == 0 or not text[:spans[0][0]].strip():
        out = out.lstrip()
    if pos >= len(text.rstrip()):
        out = out.rstrip()
    return out if out.strip() else None
