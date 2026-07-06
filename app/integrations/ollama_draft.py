"""
Ollama-backed draft generator.

Mirrors the interface of claude_draft.py but calls a local Ollama instance
via plain HTTP rather than the Anthropic SDK.  Falls back to Anthropic when
the caller catches OllamaConnectionError.

API: POST http://localhost:11434/api/generate
     { "model": "mistral", "prompt": "...", "stream": false }

System prompts are imported directly from claude_draft so they stay in one
place and both backends are always in sync.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from app.integrations.claude_draft import (
    _MEDICINAL_SYSTEM_PROMPT,
    _RECIPE_SYSTEM_PROMPT,
    _TASTE_SYSTEM_PROMPT,
    _build_context,
    _build_safety_caveat,
    _context_to_text,
    _get_prompt,
)

log = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "mistral"


class OllamaConnectionError(RuntimeError):
    """Raised when the Ollama server is not reachable."""


@dataclass
class OllamaDraftResult:
    taste_notes: Optional[str]
    medicinal_notes: Optional[str]
    recipe: Optional[str]
    model: str
    context_used: dict
    medicinal_folklore: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal HTTP helper
# ---------------------------------------------------------------------------

async def _ollama_generate(system: str, user: str, model: str) -> str:
    """
    Call POST /api/generate on the local Ollama server.
    Raises OllamaConnectionError if the server is not running.
    Raises RuntimeError on non-2xx responses.
    """
    prompt = f"{system}\n\n{user}"
    payload = {"model": model, "prompt": prompt, "stream": False}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=240),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(
                        f"Ollama returned HTTP {resp.status}: {body[:200]}"
                    )
                data = await resp.json(content_type=None)
                return (data.get("response") or "").strip()
    except aiohttp.ClientConnectorError as e:
        raise OllamaConnectionError(
            f"Cannot connect to Ollama at {OLLAMA_BASE_URL} — is 'ollama serve' running? ({e})"
        ) from e


# ---------------------------------------------------------------------------
# Per-field generators
# ---------------------------------------------------------------------------

async def _generate_taste_notes(
    scientific_name: str, ctx_text: str, model: str, voice_context: str = ""
) -> Optional[str]:
    user = (
        f"Based only on the following sourced information, write 2–4 sentences "
        f"describing the flavour, texture, and eating quality of {scientific_name}. "
        f"Be practical and specific. If there is not enough information to write "
        f"accurate taste notes, say so in one short sentence.\n\n{ctx_text}"
    )
    system = (voice_context + "\n\n" + _get_prompt("prompt_taste", _TASTE_SYSTEM_PROMPT)) if voice_context else _get_prompt("prompt_taste", _TASTE_SYSTEM_PROMPT)
    try:
        text = await _ollama_generate(system, user, model)
        log.info("[ollama_draft] taste_notes OK  species=%r  len=%d", scientific_name, len(text))
        return text or None
    except OllamaConnectionError:
        raise
    except Exception as e:
        log.error("[ollama_draft] taste_notes FAILED  species=%r  error=%s: %s",
                  scientific_name, type(e).__name__, e)
        return None


async def _generate_medicinal_notes(
    scientific_name: str, ctx_text: str, model: str, voice_context: str = ""
) -> Optional[str]:
    user = (
        f"Based only on the following sourced information, write a brief summary "
        f"(3–6 sentences) of the traditional and folk medicinal uses of {scientific_name}. "
        f"Draw only from the source material provided. Start the response with: "
        f"'Traditional and folk use only — not medical advice.' "
        f"If the source data contains no medicinal information, say: "
        f"'No traditional medicinal uses recorded in available sources.'\n\n{ctx_text}"
    )
    system = (voice_context + "\n\n" + _get_prompt("prompt_medicinal", _MEDICINAL_SYSTEM_PROMPT)) if voice_context else _get_prompt("prompt_medicinal", _MEDICINAL_SYSTEM_PROMPT)
    try:
        text = await _ollama_generate(system, user, model)
        log.info("[ollama_draft] medicinal_notes OK  species=%r  len=%d", scientific_name, len(text))
        return text or None
    except OllamaConnectionError:
        raise
    except Exception as e:
        log.error("[ollama_draft] medicinal_notes FAILED  species=%r  error=%s: %s",
                  scientific_name, type(e).__name__, e)
        return None


async def _generate_recipe(
    scientific_name: str, ctx_text: str, model: str, voice_context: str = ""
) -> Optional[str]:
    user = (
        f"Write one original recipe using {scientific_name} as the primary ingredient. "
        f"Use the following sourced information about this plant as context. "
        f"The recipe must reflect genuine knowledge of how this species tastes and "
        f"how it is prepared.\n\n{ctx_text}"
    )
    system = (voice_context + "\n\n" + _get_prompt("prompt_recipe", _RECIPE_SYSTEM_PROMPT)) if voice_context else _get_prompt("prompt_recipe", _RECIPE_SYSTEM_PROMPT)
    try:
        text = await _ollama_generate(system, user, model)
        log.info("[ollama_draft] recipe OK  species=%r  len=%d", scientific_name, len(text))
        return text or None
    except OllamaConnectionError:
        raise
    except Exception as e:
        log.error("[ollama_draft] recipe FAILED  species=%r  error=%s: %s",
                  scientific_name, type(e).__name__, e)
        return None


# ---------------------------------------------------------------------------
# Public API — mirrors generate_ai_drafts() signature
# ---------------------------------------------------------------------------

async def generate_ollama_drafts(
    scientific_name: str,
    model: str = OLLAMA_DEFAULT_MODEL,
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
    pfaf_medicinal_text: Optional[str] = None,  # accepted for kwarg-parity with generate_ai_drafts;
                                                  # medicinal_folklore drafting is Anthropic-only for now
) -> Optional[OllamaDraftResult]:
    """
    Generate AI drafts via local Ollama.

    Applies the same edibility gate as generate_ai_drafts():
      - toxic / inedible / not_edible → return None (no content)
      - unknown / unclear / None      → medicinal only
      - edible / caution              → all three fields

    Raises OllamaConnectionError if Ollama is not running — the caller
    should catch this and fall back to Anthropic.
    """
    _NO_CONTENT  = ("toxic", "inedible", "not_edible")
    _UNCONFIRMED = (None, "unknown", "unclear")

    if edibility_status in _NO_CONTENT:
        log.info("[ollama_draft] suppressing ALL drafts for %r — edibility_status=%r",
                 scientific_name, edibility_status)
        return None

    generate_culinary = edibility_status in ("edible", "caution")
    is_conditional    = edibility_status == "caution"

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
    )
    if not ctx:
        log.warning("[ollama_draft] No source context for %r — skipping", scientific_name)
        return None

    ctx_text = _context_to_text(scientific_name, ctx)

    ctx_text += _build_safety_caveat(
        generate_culinary=generate_culinary,
        is_conditional=is_conditional,
        preparation_warnings=preparation_warnings,
        edibility_conditions=edibility_conditions,
    )

    import asyncio

    async def _skip():
        return None

    log.info("[ollama_draft] generating drafts for %r  model=%r  culinary=%s",
             scientific_name, model, generate_culinary)

    taste, medicinal, recipe = await asyncio.gather(
        _generate_taste_notes(scientific_name, ctx_text, model, voice_context) if generate_culinary else _skip(),
        _generate_medicinal_notes(scientific_name, ctx_text, model, voice_context),
        _generate_recipe(scientific_name, ctx_text, model, voice_context) if generate_culinary else _skip(),
    )

    if taste is None and medicinal is None and recipe is None:
        log.error("[ollama_draft] all three generations failed for %r", scientific_name)
        return None

    return OllamaDraftResult(
        taste_notes=taste,
        medicinal_notes=medicinal,
        recipe=recipe,
        model=f"ollama/{model}",
        context_used=ctx,
    )
