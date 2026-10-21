"""
AI draft prompts + source context — Phase 8.

Since 21 Oct 2026 (Melvin D1) every AI call site uses DeepSeek
(app/integrations/deepseek_draft.py). This module no longer calls any model:
it keeps what the DeepSeek drafter and the other AI paths share —

  - AIDraftResult      — the draft result shape
  - _RECIPE_SYSTEM_PROMPT (recipe voice); _TASTE_SYSTEM_PROMPT and
    _MEDICINAL_SYSTEM_PROMPT (shown as defaults in the prompt editor)
  - _build_context / _context_to_text — context built exclusively from
    already-stored sourced data (PFAF, Wikidata, iNaturalist, Trompenburg)
  - _build_safety_caveat — the mandatory recipe safety caveat

Rules (unchanged): drafts are never shown until approved in the review queue;
medicinal notes carry "Traditional and folk use only — not medical advice."
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class AIDraftResult:
    taste_notes: Optional[str]
    medicinal_notes: Optional[str]
    recipe: Optional[str]
    medicinal_folklore: Optional[str] = None
    model: str = ""
    context_used: dict = None  # what source texts were provided as context


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_RECIPE_SYSTEM_PROMPT = """\
You are drafting a recipe in the voice and style of Melvin Jarman — \
Sheffield-based chef, forager, and OD consultant with 28 years of professional \
cooking experience.

Cooking principles to follow:
- Flavour first, always. Texture, visual, and the feeling food gives are \
important — but flavour carries it.
- Vegetable-led without ideology — driven by quality, ethics, and context, \
not dogma.
- Foraging is structural, not decorative — wild ingredients appear because \
they carry genuine vitality, not as garnish.
- Generous with elegance — food should feel abundant and be beautifully \
presented, even at scale.
- Intuitive cooking within a framework — the recipe provides structure, \
but leaves room to improvise.
- Influences rooted in real human connections: Zanzibari, Mediterranean, \
Levantine, Mexican, Greek, East African.
- Ancient techniques (fire, fermentation, slow cooking) are always in the \
background even when not explicit.
- Vitality as a quality standard — drawn to ingredients that carry life force: \
foraged, biodynamic, organic.

Recipe format:
- Write in plain, direct, confident prose — not a list of bullet points
- Short introduction (2–3 sentences) on why this plant works in this dish
- Ingredients listed simply
- Method written as Melvin would speak it — practical, sensory, generous
- One suggestion at the end for variation or pairing
- Never preachy, never ideological, never overcomplicated\
"""

_TASTE_SYSTEM_PROMPT = """You are a practical wild food writer helping a professional forager and educator create accurate, useful tasting notes for teaching.

Write in plain, direct English. No preamble, no food writing clichés.

Cover: raw flavour, cooked flavour if different, texture, any bitterness/astringency/heat, and what the plant is comparable to that a forager or cook would recognise. Note any seasonal variation in flavour if the source data suggests it.

Two to four sentences. Never use the words 'delicate', 'subtle', 'earthy' or 'nutty' unless no other word works."""

_MEDICINAL_SYSTEM_PROMPT = """You are a careful ethnobotanical writer summarising traditional and folk uses from already-published source material. Write plainly and accurately. Never invent claims not present in the source data.

Structure the notes to cover, where the source material supports it:
- Plant part used (leaf, root, aerial parts, etc.)
- Administration route — topical or internal — and which uses belong to each. Never conflate them.
- Preparation form (infusion, decoction, poultice, oil infusion, tincture, compress, etc.)
- Body system or therapeutic application (connective tissue, respiratory, digestive, skin, etc.)
- Any safety distinctions between routes — e.g. topical use safe where internal use is cautioned

If internal use carries a known safety concern (e.g. pyrrolizidine alkaloids, oxalates, photosensitisation), state it plainly in one sentence.

Always end with exactly: "Traditional and folk use only — not medical advice."
If the source data contains no medicinal information, write exactly: "No traditional medicinal uses recorded in available sources."

If reference material is labelled 'synthesis only — do not reproduce', read it to inform your writing but do not quote it, closely paraphrase it, or reproduce its sentence structures. Write an original synthesis in Melvin Jarman's voice. Reference sources may be American or Scottish in tone — ignore their voice and write in Melvin's."""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(
    scientific_name: str,
    common_names: list,
    edible_parts: Optional[str],
    preparation_methods: Optional[str],
    traditional_uses: Optional[str],
    medicinal_folklore: Optional[str],
    inat_description: Optional[str],
    trompenburg_description: Optional[str],
    preparation_warnings: Optional[str] = None,
    synthesis_reference: Optional[str] = None,
) -> dict:
    """
    Assemble the source context that will be passed to the AI drafter.
    Returns a dict of non-empty context items.

    synthesis_reference — optional text fetched from SYNTHESIS_SOURCES at generation
    time. Never stored in the DB. The drafter is instructed not to reproduce it verbatim.
    """
    ctx = {}
    if common_names:
        ctx["common_names"] = ", ".join(common_names)
    if edible_parts:
        ctx["edible_parts"] = edible_parts
    if preparation_warnings:
        ctx["preparation_warnings"] = preparation_warnings
    if preparation_methods:
        ctx["preparation_methods"] = preparation_methods
    if traditional_uses:
        ctx["traditional_uses"] = traditional_uses
    if medicinal_folklore:
        ctx["medicinal_folklore"] = medicinal_folklore
    if inat_description:
        ctx["inat_description"] = inat_description[:1500]
    if trompenburg_description:
        ctx["trompenburg_description"] = trompenburg_description[:1500]
    if synthesis_reference:
        ctx["synthesis_reference"] = synthesis_reference
    return ctx


def _context_to_text(scientific_name: str, ctx: dict) -> str:
    lines = [f"Species: {scientific_name}"]
    if ctx.get("common_names"):
        lines.append(f"Common names: {ctx['common_names']}")
    if ctx.get("edible_parts"):
        lines.append(f"Edible parts (PFAF): {ctx['edible_parts']}")
    if ctx.get("preparation_warnings"):
        lines.append(f"Preparation warning (SAFETY — must be honoured): {ctx['preparation_warnings']}")
    if ctx.get("preparation_methods"):
        lines.append(f"Preparation (PFAF): {ctx['preparation_methods']}")
    if ctx.get("traditional_uses"):
        lines.append(f"Traditional uses (PFAF/Wikidata): {ctx['traditional_uses']}")
    if ctx.get("medicinal_folklore"):
        lines.append(f"Medicinal folklore (PFAF): {ctx['medicinal_folklore']}")
    if ctx.get("pfaf_medicinal_uses"):
        lines.append(f"Medicinal Uses (PFAF): {ctx['pfaf_medicinal_uses']}")
    if ctx.get("inat_description"):
        lines.append(f"Description (iNaturalist): {ctx['inat_description']}")
    if ctx.get("trompenburg_description"):
        lines.append(f"Description (Trompenburg): {ctx['trompenburg_description']}")
    if ctx.get("synthesis_reference"):
        lines.append(
            "Reference material (synthesis only — do not reproduce text, sentence "
            "structures, or phrasing):\n" + ctx["synthesis_reference"]
        )
    return "\n\n".join(lines)


def _build_safety_caveat(
    generate_culinary: bool,
    is_conditional: bool,
    preparation_warnings: Optional[str],
    edibility_conditions: Optional[str],
) -> str:
    """
    Build the mandatory recipe safety caveat appended to the generation context.

    Fires for ANY culinary-generating species (edible OR caution) that carries a
    preparation warning or per-part edibility conditions — no longer caution-gated.
    The recipe must open with the warning verbatim and may not use a part outside
    edible_parts. Returns "" when no caveat applies (so it can be string-appended).
    """
    _warn = (preparation_warnings or "").strip()
    _cond = (edibility_conditions or "").strip()
    if generate_culinary and (_warn or _cond):
        safety_lines = ["\n\nSAFETY (mandatory — overrides any source text above):"]
        if _warn:
            safety_lines.append(
                f"- This preparation warning MUST be stated verbatim at the very start of the recipe: {_warn}"
            )
        if _cond:
            safety_lines.append(
                f"- Per-part edibility conditions (state at the start and follow exactly): {_cond}"
            )
        safety_lines.append(
            "- Do NOT use, name, or suggest any plant part that is not explicitly listed in "
            "'Edible parts' above. If a part is absent from that list, treat it as unsafe and exclude it."
        )
        return "\n".join(safety_lines)
    if is_conditional:
        return (
            "\n\nNote: this species is conditionally edible — the recipe must open "
            "with a brief caution about preparation requirements before the ingredients."
        )
    return ""
