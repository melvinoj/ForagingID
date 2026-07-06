"""
POST /api/species/{name}/chat — single-turn species chat.

Loads the species context (same source data as enrichment drafts) and
passes it + the user's message to the active AI backend.  No history
persistence — each call is fully stateless.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.culinary import CulinaryInfo
from app.models.species import EnrichmentSource, Species
from app.integrations.claude_draft import _build_context, _context_to_text

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


async def _get_species_or_404(db: AsyncSession, name: str) -> Species:
    sp = await db.scalar(select(Species).where(Species.scientific_name == name))
    if not sp:
        raise HTTPException(404, f"Species {name!r} not found")
    return sp


@router.post("/api/species/{species_name:path}/chat")
async def species_chat(
    species_name: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Single-turn chat grounded in the species' stored source data.

    Context is built from culinary_info + raw iNat/Trompenburg descriptions
    — the same inputs used by enrichment draft generation.
    """
    from app.services.settings_service import get_setting as _gs

    sp = await _get_species_or_404(db, species_name)
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))

    # Load common names
    import json
    common_names: list = []
    try:
        names = json.loads(sp.common_names or "[]")
        if isinstance(names, list):
            common_names = names
    except Exception:
        pass

    # Pull iNat / Trompenburg descriptions from stored raw sources
    inat_desc: Optional[str] = None
    trompen_desc: Optional[str] = None
    try:
        raw_rows = (await db.execute(
            select(EnrichmentSource)
            .where(EnrichmentSource.species_id == sp.id)
            .where(EnrichmentSource.source_name.in_(["inaturalist", "trompenburg"]))
        )).scalars().all()
        for row in raw_rows:
            if not row.raw_data:
                continue
            d = json.loads(row.raw_data) if isinstance(row.raw_data, str) else row.raw_data
            if not isinstance(d, dict):
                continue
            if row.source_name == "inaturalist":
                inat_desc = d.get("description")
            elif row.source_name == "trompenburg":
                trompen_desc = d.get("description")
    except Exception as e:
        log.warning("[chat] failed to load raw sources for %r: %s", species_name, e)

    # Build context — same helper used by enrichment drafts
    # Suppress culinary fields for toxic/deadly species so the AI
    # cannot surface cooking/preparation advice for dangerous plants.
    _is_toxic = (sp.toxicity_severity or 'none') in ('deadly', 'toxic')
    ctx = _build_context(
        scientific_name=sp.scientific_name,
        common_names=common_names,
        edible_parts=None if _is_toxic else (ci.edible_parts if ci else None),
        preparation_methods=None if _is_toxic else (ci.preparation_methods if ci else None),
        traditional_uses=ci.traditional_uses if ci else None,
        medicinal_folklore=ci.medicinal_folklore if ci else None,
        inat_description=inat_desc,
        trompenburg_description=trompen_desc,
    )

    if not ctx:
        # No source data at all — answer from species name only
        ctx_text = f"Species: {sp.scientific_name}"
        log.info("[chat] no source context for %r — answering from name only", species_name)
    else:
        ctx_text = _context_to_text(sp.scientific_name, ctx)

    try:
        from app.services.voice_library import load_voice_context as _load_voice
        _voice = _load_voice()
    except Exception:
        _voice = ""

    _toxic_guard = (
        f"IMPORTANT: {sp.scientific_name} is classified as {sp.toxicity_severity}. "
        f"Do not provide culinary advice, recipes, preparation methods, or any guidance "
        f"that could encourage consumption. If asked about eating or cooking this species, "
        f"clearly state it is not safe.\n\n"
    ) if _is_toxic else ""
    _base_prompt = (
        f"You are a forager and wild food assistant for {sp.scientific_name}. "
        f"Answer questions based only on the following sourced data. "
        f"Do not invent information not present in the source. "
        f"Write in plain, direct English — no preamble, no clichés.\n\n"
        f"{_toxic_guard}"
        f"Source data:\n{ctx_text}"
    )
    system_prompt = (_voice + "\n\n" + _base_prompt) if _voice else _base_prompt

    backend = _gs("enrichment_backend")
    response_text: Optional[str] = None

    # ── Ollama path ────────────────────────────────────────────────────────────
    if backend == "ollama":
        try:
            from app.integrations.ollama_draft import OllamaConnectionError, _ollama_generate
            model = _gs("ollama_model") or "mistral"
            response_text = await _ollama_generate(system_prompt, body.message, model)
            log.info("[chat] ollama OK  species=%r  model=%r  len=%d",
                     species_name, model, len(response_text or ""))
        except Exception as _e:
            _is_conn_err = False
            try:
                from app.integrations.ollama_draft import OllamaConnectionError
                _is_conn_err = isinstance(_e, OllamaConnectionError)
            except ImportError:
                pass
            if _is_conn_err:
                log.warning("[chat] Ollama unreachable for %r — falling back to Anthropic: %s",
                            species_name, _e)
            else:
                log.error("[chat] Ollama error for %r (%s: %s) — falling back to Anthropic",
                          species_name, type(_e).__name__, _e)
            backend = "anthropic"

    # ── Anthropic path (primary or fallback) ──────────────────────────────────
    if backend == "anthropic" and response_text is None:
        from app.config import settings as _cfg
        if not _cfg.anthropic_api_key:
            raise HTTPException(503, "No AI backend available — Anthropic API key not set")
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=_cfg.anthropic_api_key)
            model = _gs("anthropic_model")
            msg = await client.messages.create(
                model=model,
                max_tokens=400,
                system=system_prompt,
                messages=[{"role": "user", "content": body.message}],
            )
            response_text = msg.content[0].text.strip() if msg.content else ""
            log.info("[chat] anthropic OK  species=%r  model=%r  len=%d",
                     species_name, model, len(response_text or ""))
        except Exception as e:
            log.error("[chat] Anthropic failed for %r: %s: %s", species_name, type(e).__name__, e)
            raise HTTPException(502, f"AI backend error: {e}")

    return {"response": response_text or ""}
