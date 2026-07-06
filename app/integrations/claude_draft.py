"""
AI draft generator — Phase 8.

Uses the Anthropic Claude API to generate three draft fields per species:
  1. taste_notes    — practical flavour and texture description
  2. medicinal_notes — summarised from sourced folk/traditional data (with disclaimer)
  3. recipe          — original recipe in Melvin Jarman's voice (exact system prompt)

Rules:
  - Requires ANTHROPIC_API_KEY in settings (returns None silently if absent)
  - Drafts are NEVER shown to users until explicitly approved in the review queue
  - All AI-generated content is clearly labelled with the generating model
  - Medicinal notes always include the disclaimer: "Traditional and folk use only —
    not medical advice."
  - Context passed to Claude is built exclusively from already-stored sourced data
    (PFAF, Wikidata, iNaturalist, Trompenburg) — never hallucinated
  - Returns None on any failure so enrichment run is never blocked
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

_MEDICINAL_FOLKLORE_SYSTEM_PROMPT = """You are synthesising traditional medicinal folklore for a wild-food forager's species card, based on raw source text scraped from Plants For A Future (PFAF).

Read the source text and write an original synthesis in Melvin Jarman's voice — do not quote it, closely paraphrase it, or reproduce its sentence structures. This is a distinct field from medicinal_notes: it is folklore/historical-use framing, not a clinical-style summary.

Cover, where the source material supports it: plant part used, preparation form, and the traditional application it was known for.

Always end with exactly: "Traditional and folk use only — not medical advice."
If the source text contains no usable medicinal information, write exactly: "No traditional medicinal folklore recorded in available sources."
"""


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
    Assemble the source context that will be passed to Claude.
    Returns a dict of non-empty context items.

    synthesis_reference — optional text fetched from SYNTHESIS_SOURCES at generation
    time. Never stored in the DB. Claude is instructed not to reproduce it verbatim.
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


# ---------------------------------------------------------------------------
# Draft generators
# ---------------------------------------------------------------------------

def _get_prompt(key: str, default: str) -> str:
    """Get a prompt from app_settings, falling back to the hardcoded default if blank."""
    try:
        from app.services.settings_service import get_setting
        val = get_setting(key)
        return val.strip() if val and val.strip() else default
    except Exception:
        return default


async def _generate_taste_notes(
    client, model: str, scientific_name: str, ctx_text: str, voice_context: str = ""
) -> Optional[str]:
    prompt = (
        f"Based only on the following sourced information, write 2–4 sentences "
        f"describing the flavour, texture, and eating quality of {scientific_name}. "
        f"Be practical and specific. If there is not enough information to write "
        f"accurate taste notes, say so in one short sentence.\n\n{ctx_text}"
    )
    system = (voice_context + "\n\n" + _get_prompt("prompt_taste", _TASTE_SYSTEM_PROMPT)) if voice_context else _get_prompt("prompt_taste", _TASTE_SYSTEM_PROMPT)
    log.info(
        "[claude_draft] taste_notes request  model=%r  species=%r  prompt_len=%d",
        model, scientific_name, len(prompt),
    )
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        log.info(
            "[claude_draft] taste_notes response  stop_reason=%r  content_blocks=%d",
            msg.stop_reason, len(msg.content),
        )
        text = msg.content[0].text.strip() if msg.content else None
        if text:
            log.info("[claude_draft] taste_notes OK  len=%d  preview=%r", len(text), text[:80])
        else:
            log.warning("[claude_draft] taste_notes returned empty content block")
        return text or None
    except Exception as e:
        log.error(
            "[claude_draft] taste_notes FAILED  model=%r  species=%r  error=%s: %s",
            model, scientific_name, type(e).__name__, e,
        )
        return None


async def _generate_medicinal_notes(
    client, model: str, scientific_name: str, ctx_text: str, voice_context: str = ""
) -> Optional[str]:
    prompt = (
        f"Based only on the following sourced information, write a structured summary "
        f"(4–8 sentences) of the traditional and folk medicinal uses of {scientific_name}. "
        f"Distinguish topical from internal uses. Note preparation form and plant part where known. "
        f"Flag any safety distinction between routes. "
        f"Draw only from the source material provided.\n\n{ctx_text}"
    )
    system = (voice_context + "\n\n" + _get_prompt("prompt_medicinal", _MEDICINAL_SYSTEM_PROMPT)) if voice_context else _get_prompt("prompt_medicinal", _MEDICINAL_SYSTEM_PROMPT)
    log.info(
        "[claude_draft] medicinal_notes request  model=%r  species=%r  prompt_len=%d",
        model, scientific_name, len(prompt),
    )
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        log.info(
            "[claude_draft] medicinal_notes response  stop_reason=%r  content_blocks=%d",
            msg.stop_reason, len(msg.content),
        )
        text = msg.content[0].text.strip() if msg.content else None
        if text:
            log.info("[claude_draft] medicinal_notes OK  len=%d  preview=%r", len(text), text[:80])
        else:
            log.warning("[claude_draft] medicinal_notes returned empty content block")
        return text or None
    except Exception as e:
        log.error(
            "[claude_draft] medicinal_notes FAILED  model=%r  species=%r  error=%s: %s",
            model, scientific_name, type(e).__name__, e,
        )
        return None


async def _generate_medicinal_folklore(
    client, model: str, scientific_name: str, pfaf_text: str, voice_context: str = ""
) -> Optional[str]:
    prompt = (
        f"Based only on the following PFAF source text, write a short synthesis "
        f"(3–6 sentences) of the traditional medicinal folklore for {scientific_name}. "
        f"Do not quote or closely paraphrase the source text — write an original "
        f"synthesis in your own words.\n\nPFAF source text:\n{pfaf_text}"
    )
    system = (voice_context + "\n\n" + _get_prompt("prompt_medicinal_folklore", _MEDICINAL_FOLKLORE_SYSTEM_PROMPT)) if voice_context else _get_prompt("prompt_medicinal_folklore", _MEDICINAL_FOLKLORE_SYSTEM_PROMPT)
    log.info(
        "[claude_draft] medicinal_folklore request  model=%r  species=%r  prompt_len=%d",
        model, scientific_name, len(prompt),
    )
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=500,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        log.info(
            "[claude_draft] medicinal_folklore response  stop_reason=%r  content_blocks=%d",
            msg.stop_reason, len(msg.content),
        )
        text = msg.content[0].text.strip() if msg.content else None
        if text:
            log.info("[claude_draft] medicinal_folklore OK  len=%d  preview=%r", len(text), text[:80])
        else:
            log.warning("[claude_draft] medicinal_folklore returned empty content block")
        return text or None
    except Exception as e:
        log.error(
            "[claude_draft] medicinal_folklore FAILED  model=%r  species=%r  error=%s: %s",
            model, scientific_name, type(e).__name__, e,
        )
        return None


async def _generate_recipe(
    client, model: str, scientific_name: str, ctx_text: str, voice_context: str = ""
) -> Optional[str]:
    prompt = (
        f"Write one original recipe using {scientific_name} as the primary ingredient. "
        f"Use the following sourced information about this plant as context. "
        f"The recipe must reflect genuine knowledge of how this species tastes and "
        f"how it is prepared.\n\n{ctx_text}"
    )
    system = (voice_context + "\n\n" + _get_prompt("prompt_recipe", _RECIPE_SYSTEM_PROMPT)) if voice_context else _get_prompt("prompt_recipe", _RECIPE_SYSTEM_PROMPT)
    log.info(
        "[claude_draft] recipe request  model=%r  species=%r  prompt_len=%d",
        model, scientific_name, len(prompt),
    )
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=900,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        log.info(
            "[claude_draft] recipe response  stop_reason=%r  content_blocks=%d",
            msg.stop_reason, len(msg.content),
        )
        text = msg.content[0].text.strip() if msg.content else None
        if text:
            log.info("[claude_draft] recipe OK  len=%d  preview=%r", len(text), text[:80])
        else:
            log.warning("[claude_draft] recipe returned empty content block")
        return text or None
    except Exception as e:
        log.error(
            "[claude_draft] recipe FAILED  model=%r  species=%r  error=%s: %s",
            model, scientific_name, type(e).__name__, e,
        )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_ai_drafts(
    scientific_name: str,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
    common_names: Optional[list] = None,
    edible_parts: Optional[str] = None,
    preparation_methods: Optional[str] = None,
    traditional_uses: Optional[str] = None,
    medicinal_folklore: Optional[str] = None,
    inat_description: Optional[str] = None,
    trompenburg_description: Optional[str] = None,
    edibility_status: Optional[str] = None,
    edibility_conditions: Optional[str] = None,  # human-set conditions text for caution species
    preparation_warnings: Optional[str] = None,  # safety warning text (e.g. "must cook / toxic raw")
    voice_context: str = "",
    synthesis_context: Optional[str] = None,     # synthesis-only reference text; never stored
    pfaf_medicinal_text: Optional[str] = None,   # this session's raw PFAF Medicinal Uses scrape —
                                                   # source material for the medicinal_folklore draft
                                                   # field only; distinct from `medicinal_folklore`
                                                   # above (ci.medicinal_folklore context input)
) -> Optional[AIDraftResult]:
    """
    Generate AI drafts for taste_notes, medicinal_notes, and recipe.

    Gate rules — edibility_status controls which fields are generated:
      - "edible"               → all three fields generated, no caveat
      - "caution"              → all three fields generated; recipe prompt includes
                                 edibility_conditions text as a mandatory caveat.
                                 (Maps to "conditionally edible" in the UI.)
      - "toxic" / "inedible" / "not_edible"
                               → nothing generated (return None). Safety-critical.
      - None / "unknown" / "unclear"
                               → medicinal_notes only; recipe and taste_notes suppressed
                                 until a human confirms edibility.
      - any other value        → medicinal_notes only (conservative fallback)

    Returns AIDraftResult or None if:
      - api_key is empty (silently skip)
      - edibility_status blocks all generation
      - All three generations fail
      - The anthropic library is not installed
    """
    # ── Edibility gate ────────────────────────────────────────────────────────
    # Nothing generated for toxic/inedible — safety-critical, no exceptions.
    _NO_CONTENT = ("toxic", "inedible", "not_edible")
    # Culinary fields (recipe + taste_notes) suppressed when edibility is unconfirmed.
    # "caution" is the DB value for "conditionally edible" and IS confirmed — recipes
    # are permitted but must carry the conditions caveat (see recipe prompt below).
    _UNCONFIRMED = (None, "unknown", "unclear")

    if edibility_status in _NO_CONTENT:
        log.info(
            "[claude_draft] suppressing ALL drafts for %r — edibility_status=%r",
            scientific_name, edibility_status,
        )
        return None

    generate_culinary = edibility_status in ("edible", "caution")
    is_conditional    = edibility_status == "caution"

    if not generate_culinary:
        log.info(
            "[claude_draft] suppressing recipe/taste_notes for %r — edibility_status=%r (medicinal only)",
            scientific_name, edibility_status,
        )
    if not api_key:
        log.warning(
            "[claude_draft] generate_ai_drafts called with empty api_key for %r — skipping",
            scientific_name,
        )
        return None

    log.info(
        "[claude_draft] generate_ai_drafts START  species=%r  model=%r  api_key_prefix=%r",
        scientific_name, model, api_key[:12] + "...",
    )

    try:
        import anthropic  # lazy import — optional dependency
        client = anthropic.AsyncAnthropic(api_key=api_key)
        log.info("[claude_draft] Anthropic client created OK  sdk_version=%s",
                 getattr(anthropic, "__version__", "unknown"))
    except ImportError:
        log.error("[claude_draft] anthropic library not installed — pip install anthropic")
        return None
    except Exception as e:
        log.error("[claude_draft] Failed to init Anthropic client: %s: %s", type(e).__name__, e)
        return None

    ctx = _build_context(
        scientific_name=scientific_name,
        common_names=common_names or [],
        edible_parts=edible_parts,
        preparation_methods=preparation_methods,
        traditional_uses=traditional_uses,
        medicinal_folklore=medicinal_folklore,
        inat_description=inat_description,
        trompenburg_description=trompenburg_description,
        preparation_warnings=preparation_warnings,
        synthesis_reference=synthesis_context,
    )

    if not ctx:
        log.warning(
            "[claude_draft] No source context available for %r — skipping AI draft generation",
            scientific_name,
        )
        return None

    log.info(
        "[claude_draft] Context built for %r: keys=%s  total_chars=%d",
        scientific_name,
        list(ctx.keys()),
        sum(len(str(v)) for v in ctx.values()),
    )

    ctx_text = _context_to_text(scientific_name, ctx)

    ctx_text += _build_safety_caveat(
        generate_culinary=generate_culinary,
        is_conditional=is_conditional,
        preparation_warnings=preparation_warnings,
        edibility_conditions=edibility_conditions,
    )

    # Run generations concurrently — culinary fields suppressed for unconfirmed species
    import asyncio

    async def _skip():
        return None

    log.info(
        "[claude_draft] Launching API calls for %r — culinary=%s  conditional=%s",
        scientific_name, generate_culinary, is_conditional,
    )
    taste, medicinal, recipe, folklore = await asyncio.gather(
        _generate_taste_notes(client, model, scientific_name, ctx_text, voice_context) if generate_culinary else _skip(),
        _generate_medicinal_notes(client, model, scientific_name, ctx_text, voice_context),
        _generate_recipe(client, model, scientific_name, ctx_text, voice_context) if generate_culinary else _skip(),
        _generate_medicinal_folklore(client, model, scientific_name, pfaf_medicinal_text, voice_context) if pfaf_medicinal_text else _skip(),
        return_exceptions=False,
    )

    log.info(
        "[claude_draft] All calls complete for %r: taste=%s  medicinal=%s  recipe=%s  folklore=%s",
        scientific_name,
        "OK" if taste else "NONE",
        "OK" if medicinal else "NONE",
        "OK" if recipe else "NONE",
        "OK" if folklore else "NONE",
    )

    # If everything failed, return None
    if taste is None and medicinal is None and recipe is None and folklore is None:
        log.error(
            "[claude_draft] ALL generations failed for %r — returning None",
            scientific_name,
        )
        return None

    return AIDraftResult(
        taste_notes=taste,
        medicinal_notes=medicinal,
        medicinal_folklore=folklore,
        recipe=recipe,
        model=model,
        context_used=ctx,
    )
