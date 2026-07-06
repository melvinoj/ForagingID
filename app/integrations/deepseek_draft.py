"""
DeepSeek-backed AI draft generators.

Uses the DeepSeek API (OpenAI-compatible) to generate descriptive text only:
recipe, taste notes, medicinal notes, and ID notes.

NOTE: edibility_status is authoritative-source only (FAO, Mushroom Observer,
iNat taxonomy, established references). AI never assigns the status itself —
it may only draft descriptive text around an already-sourced, confirmed status.

API: POST https://api.deepseek.com/chat/completions
"""

import logging
from typing import Optional

import aiohttp

from app.integrations.claude_draft import _RECIPE_SYSTEM_PROMPT

log = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"

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
