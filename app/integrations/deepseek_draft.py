"""
DeepSeek — the ONE AI backend (Melvin D1, 21 Oct 2026: every AI call site uses
DeepSeek; no Anthropic, no fallback to anything else).

  ai_backend()              — the one backend choice; every AI path calls it
  ai_complete()             — one system+user completion (chat, About summary,
                              recipe regenerate, encounter extraction)
  generate_deepseek_drafts() — taste / medicinal / recipe / medicinal_folklore
                              drafts for a species (enrichment, section
                              regenerate, Regenerate)
  generate_deepseek_id_notes() — id_notes backfill

Uses the DeepSeek API (OpenAI-compatible) to generate descriptive text only.

NOTE: edibility_status is authoritative-source only (FAO, Mushroom Observer,
iNat taxonomy, established references). AI never assigns the status itself —
it may only draft descriptive text around an already-sourced, confirmed status.

API: POST https://api.deepseek.com/chat/completions
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

import aiohttp

from app.integrations.claude_draft import (
    AIDraftResult,
    _RECIPE_SYSTEM_PROMPT,
    _build_context,
    _build_safety_caveat,
    _context_to_text,
)
from app.models.species import AI_NO_CONTENT_VERDICTS

log = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"


@dataclass(frozen=True)
class AIBackend:
    api_key: str
    model: str

    @property
    def label(self) -> str:
        """Stored as species_ai_drafts.model for drafts this backend wrote."""
        return f"deepseek/{self.model}"


def ai_backend() -> AIBackend:
    """
    The one AI backend choice. Every AI path reads its key and model here and
    nowhere else. Settings come from the in-process cache: a script must call
    settings_service.load_settings_from_db() first, or the key reads as empty
    and every call is skipped (logged) — never a different backend.
    """
    from app.services.settings_service import get_setting
    key = (get_setting("deepseek_api_key") or "").strip()
    model = (get_setting("deepseek_model") or "").strip() or DEEPSEEK_DEFAULT_MODEL
    if not key:
        log.warning("[deepseek] deepseek_api_key is not set — AI calls are skipped "
                    "(scripts: load_settings_from_db() first)")
    return AIBackend(api_key=key, model=model)


async def ai_complete(subject: str, system: str, user: str, max_tokens: int, label: str) -> Optional[str]:
    """One completion on the AI backend. Returns the text, or None on any failure."""
    b = ai_backend()
    return await _call_deepseek(subject, system, user, b.api_key, b.model, max_tokens, label)

_NO_META_REFERENCE = (
    "Do not open with or refer to \"the source\", \"the source text\", \"the provided "
    "sources/material\", \"according to traditional sources\", or any similar "
    "meta-referential framing. State the traditional use or flavour directly and "
    "declaratively, as fact about the plant — not as a comment on the material you were given."
)

_TASTE_SYSTEM_PROMPT = (
    "You are a culinary expert specialising in wild and foraged foods. "
    "Write a concise tasting note (2–4 sentences) describing how this species tastes and "
    "feels in the mouth, including any variation by season, preparation, or maturity. "
    "Base your answer strictly on the provided source data — do not invent. "
    + _NO_META_REFERENCE
)

_MEDICINAL_SYSTEM_PROMPT = (
    "You are an ethnobotanist. Write a concise summary (2–4 sentences) of the traditional "
    "medicinal uses of this species. Base your answer strictly on the provided source data. "
    "Do not invent uses. If source data mentions no medicinal uses, say so plainly. "
    + _NO_META_REFERENCE + " "
    "Always end with exactly: \"Traditional and folk use only — not medical advice.\""
)

_MEDICINAL_FOLKLORE_SYSTEM_PROMPT = (
    "You are an ethnobotanist synthesising traditional medicinal folklore from raw "
    "source text scraped from Plants For A Future (PFAF). Write a short synthesis "
    "(3-6 sentences) in your own words — do not quote or closely paraphrase the "
    "source text. Base your answer strictly on the provided source data. Do not "
    "invent uses. If the source data contains no usable medicinal information, say so plainly. "
    + _NO_META_REFERENCE + " "
    "Always end with exactly: \"Traditional and folk use only — not medical advice.\""
)

_ID_NOTES_SYSTEM_PROMPT = (
    "You are a field botanist and mycologist. Write concise field identification notes "
    "(2–4 sentences) covering habitat, key distinguishing features, and lookalikes where "
    "relevant. Base your answer strictly on the provided source data."
)


async def _call_deepseek(
    scientific_name: str,
    system: str,
    user: str,
    api_key: str,
    model: str,
    max_tokens: int,
    field_label: str,
) -> Optional[str]:
    """Shared HTTP call to DeepSeek. Returns raw content string or None on any failure."""
    if not api_key:
        log.warning("[deepseek] No API key — skipping %s for %r", field_label, scientific_name)
        return None

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("[deepseek] HTTP %d for %r (%s): %s",
                              resp.status, scientific_name, field_label, body[:200])
                    return None
                data = await resp.json(content_type=None)
                text = data["choices"][0]["message"]["content"].strip()
                log.info("[deepseek] %s OK  species=%r  len=%d", field_label, scientific_name, len(text))
                return text or None
    except aiohttp.ClientConnectorError as e:
        log.error("[deepseek] Connection error for %r (%s): %s", scientific_name, field_label, e)
        return None
    except Exception as e:
        log.error("[deepseek] %s FAILED  species=%r  error=%s: %s",
                  field_label, scientific_name, type(e).__name__, e)
        return None


async def generate_deepseek_recipe(
    scientific_name: str,
    ctx_text: str,
    api_key: str,
    model: str = DEEPSEEK_DEFAULT_MODEL,
    voice_context: str = "",
) -> Optional[str]:
    """Generate a single recipe via DeepSeek. Returns None on any failure."""
    user = (
        f"Write one original recipe using {scientific_name} as the primary ingredient. "
        f"Use the following sourced information about this plant as context. "
        f"The recipe must reflect genuine knowledge of how this species tastes and "
        f"how it is prepared.\n\n{ctx_text}"
    )
    system = (voice_context + "\n\n" + _RECIPE_SYSTEM_PROMPT) if voice_context else _RECIPE_SYSTEM_PROMPT
    return await _call_deepseek(scientific_name, system, user, api_key, model, 900, "recipe")


async def generate_deepseek_taste_notes(
    scientific_name: str,
    ctx_text: str,
    api_key: str,
    model: str = DEEPSEEK_DEFAULT_MODEL,
) -> Optional[str]:
    """Generate taste notes via DeepSeek. Returns None on any failure."""
    user = (
        f"Write tasting notes for {scientific_name} as a foraged food. "
        f"Use the following sourced information as context.\n\n{ctx_text}"
    )
    return await _call_deepseek(scientific_name, _TASTE_SYSTEM_PROMPT, user, api_key, model, 400, "taste_notes")


async def generate_deepseek_medicinal_notes(
    scientific_name: str,
    ctx_text: str,
    api_key: str,
    model: str = DEEPSEEK_DEFAULT_MODEL,
) -> Optional[str]:
    """Generate medicinal notes via DeepSeek. Returns None on any failure."""
    user = (
        f"Summarise the traditional medicinal uses of {scientific_name}. "
        f"Use the following sourced information as context.\n\n{ctx_text}"
    )
    return await _call_deepseek(scientific_name, _MEDICINAL_SYSTEM_PROMPT, user, api_key, model, 400, "medicinal_notes")


async def generate_deepseek_medicinal_folklore(
    scientific_name: str,
    pfaf_text: str,
    api_key: str,
    model: str = DEEPSEEK_DEFAULT_MODEL,
) -> Optional[str]:
    """Generate a medicinal folklore synthesis via DeepSeek. Returns None on any failure."""
    user = (
        f"Write a synthesis of the traditional medicinal folklore for {scientific_name}. "
        f"Use the following PFAF source text as context.\n\n{pfaf_text}"
    )
    return await _call_deepseek(scientific_name, _MEDICINAL_FOLKLORE_SYSTEM_PROMPT, user, api_key, model, 400, "medicinal_folklore")


async def generate_deepseek_id_notes(
    scientific_name: str,
    ctx_text: str,
    api_key: str,
    model: str = DEEPSEEK_DEFAULT_MODEL,
) -> Optional[str]:
    """Generate field identification notes via DeepSeek. Returns None on any failure."""
    user = (
        f"Write field identification notes for {scientific_name}. "
        f"Use the following sourced information as context.\n\n{ctx_text}"
    )
    return await _call_deepseek(scientific_name, _ID_NOTES_SYSTEM_PROMPT, user, api_key, model, 400, "id_notes")


_DRAFT_FIELDS = ("taste_notes", "medicinal_notes", "recipe", "medicinal_folklore")


async def generate_deepseek_drafts(
    scientific_name: str,
    common_names: Optional[list] = None,
    edible_parts: Optional[str] = None,
    preparation_methods: Optional[str] = None,
    traditional_uses: Optional[str] = None,
    medicinal_folklore: Optional[str] = None,
    inat_description: Optional[str] = None,
    trompenburg_description: Optional[str] = None,
    edibility_status: Optional[str] = None,
    edibility_conditions: Optional[str] = None,
    preparation_warnings: Optional[str] = None,
    voice_context: str = "",
    synthesis_context: Optional[str] = None,
    pfaf_medicinal_text: Optional[str] = None,
    pfaf_medicinal_uses: Optional[str] = None,
    fields: Iterable[str] = _DRAFT_FIELDS,
) -> Optional[AIDraftResult]:
    """
    Draft taste_notes / medicinal_notes / recipe / medicinal_folklore on the AI
    backend — the one generator every draft path calls.

    Edibility gate (unchanged from the earlier generators):
      - AI_NO_CONTENT_VERDICTS (toxic / inedible / not_edible) → nothing (None)
      - edible / caution → every requested field; the recipe context carries
        the safety caveat (preparation warning / edibility conditions)
      - anything else (None / unknown / unclear) → medicinal fields only
    medicinal_folklore is drafted only from pfaf_medicinal_text.
    pfaf_medicinal_uses (PFAF's stored Medicinal Uses text, None on "None known")
    is added to the medicinal_notes context only — never to taste or recipe.

    Returns None when nothing was generated (gate, no context, no key, or every
    call failed) — the caller then leaves the field to the PFAF fallback.
    """
    if edibility_status in AI_NO_CONTENT_VERDICTS:
        log.info("[deepseek] suppressing ALL drafts for %r — edibility_status=%r",
                 scientific_name, edibility_status)
        return None
    fields = set(fields)
    culinary = edibility_status in ("edible", "caution")

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
    if not ctx and not pfaf_medicinal_text and not pfaf_medicinal_uses:
        log.info("[deepseek] no source context for %r — no drafts", scientific_name)
        return None
    ctx_text = _context_to_text(scientific_name, ctx)
    med_ctx = dict(ctx, pfaf_medicinal_uses=pfaf_medicinal_uses) if pfaf_medicinal_uses else ctx
    med_ctx_text = _context_to_text(scientific_name, med_ctx)
    recipe_ctx = ctx_text + _build_safety_caveat(
        generate_culinary=culinary,
        is_conditional=(edibility_status == "caution"),
        preparation_warnings=preparation_warnings,
        edibility_conditions=edibility_conditions,
    )

    b = ai_backend()

    async def _skip():
        return None

    taste, medicinal, recipe, folklore = await asyncio.gather(
        generate_deepseek_taste_notes(scientific_name, ctx_text, b.api_key, b.model)
        if culinary and "taste_notes" in fields else _skip(),
        generate_deepseek_medicinal_notes(scientific_name, med_ctx_text, b.api_key, b.model)
        if "medicinal_notes" in fields else _skip(),
        generate_deepseek_recipe(scientific_name, recipe_ctx, b.api_key, b.model, voice_context=voice_context)
        if culinary and "recipe" in fields else _skip(),
        generate_deepseek_medicinal_folklore(scientific_name, pfaf_medicinal_text, b.api_key, b.model)
        if pfaf_medicinal_text and "medicinal_folklore" in fields else _skip(),
    )
    if not (taste or medicinal or recipe or folklore):
        log.warning("[deepseek] no draft text for %r (fields=%s)", scientific_name, sorted(fields))
        return None
    return AIDraftResult(
        taste_notes=taste,
        medicinal_notes=medicinal,
        recipe=recipe,
        medicinal_folklore=folklore,
        model=b.label,
        context_used=med_ctx,
    )
