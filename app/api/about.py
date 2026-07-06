"""
About API — editable About-page copy + guest-facing summary.

GET  /api/about                    — { full_description, snappy_summary }
                                     placeholders resolved to live counts
PUT  /api/about                    — update the single row (owner only)
POST /api/about/regenerate-summary — regenerate snappy_summary with Claude (owner only)

"Owner only" mirrors the rest of the app: ngrok guest sessions are rejected.
The global guest middleware already blocks all non-GET requests from
ngrok-tunnel guests; the explicit get_identity()-based guard here also covers
token-based workshop guests (host-only middleware can't see those).
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.identity import Identity, get_identity
from app.config import settings
from app.database import get_db
from app.models.about import AboutContent
from app.models.observation import Observation

log = logging.getLogger(__name__)

router = APIRouter(tags=["about"])

_CONFIRMED = ["approved", "manually_verified"]
_MISSING_KEY_MSG = "ANTHROPIC_API_KEY not set in environment. Add it to your .env file."
_REGEN_MODEL = "claude-sonnet-4-6"
_REGEN_SYSTEM_PROMPT = (
    "You are helping maintain the About page for ForagingID, a foraging "
    "intelligence platform. Generate a punchy, warm, 4-6 sentence summary of "
    "the following description suitable for a guest-facing landing page. Capture "
    "the core USP (getting to know individual plants not just species), the "
    "personal archive idea, the Goethean connection, and the practical outputs. "
    "Write in plain prose, no bullet points, no headers."
)


class AboutUpdate(BaseModel):
    full_description: Optional[str] = None
    snappy_summary: Optional[str] = None


def _require_owner(identity: Identity) -> None:
    if identity.is_guest:
        raise HTTPException(status_code=403, detail="Owner-only — read-only guest access")


def _anthropic_key() -> str:
    return settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")


async def _live_counts(db: AsyncSession) -> tuple[int, int]:
    """Return (confirmed_species_count, approved_observation_count)."""
    obs_count = await db.scalar(
        select(func.count())
        .select_from(Observation)
        .where(Observation.review_status.in_(_CONFIRMED))
    )
    species_count = await db.scalar(
        select(func.count(distinct(Observation.species_primary)))
        .where(Observation.review_status.in_(_CONFIRMED))
        .where(Observation.species_primary.isnot(None))
    )
    return int(species_count or 0), int(obs_count or 0)


def _resolve_placeholders(text: Optional[str], species: int, obs: int) -> Optional[str]:
    if not text:
        return text
    return text.replace("[SPECIES_COUNT]", str(species)).replace(
        "[OBSERVATION_COUNT]", str(obs)
    )


async def _get_row(db: AsyncSession) -> AboutContent:
    row = await db.get(AboutContent, 1)
    if row is None:
        # Defensive: seed migration should have created it. Create an empty row.
        row = AboutContent(id=1, full_description="", snappy_summary="")
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get("/api/about")
async def get_about(db: AsyncSession = Depends(get_db)):
    row = await _get_row(db)
    species, obs = await _live_counts(db)
    return {
        "full_description": _resolve_placeholders(row.full_description, species, obs),
        "snappy_summary": row.snappy_summary,
    }


@router.put("/api/about")
async def update_about(
    body: AboutUpdate,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    _require_owner(identity)
    row = await _get_row(db)
    if body.full_description is not None:
        row.full_description = body.full_description
    if body.snappy_summary is not None:
        row.snappy_summary = body.snappy_summary
    await db.commit()
    await db.refresh(row)
    species, obs = await _live_counts(db)
    return {
        "full_description": _resolve_placeholders(row.full_description, species, obs),
        "snappy_summary": row.snappy_summary,
    }


@router.post("/api/about/regenerate-summary")
async def regenerate_summary(
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    _require_owner(identity)

    api_key = _anthropic_key()
    if not api_key:
        raise HTTPException(status_code=400, detail=_MISSING_KEY_MSG)

    row = await _get_row(db)
    species, obs = await _live_counts(db)
    full = _resolve_placeholders(row.full_description, species, obs) or ""
    if not full.strip():
        raise HTTPException(status_code=400, detail="Full description is empty — nothing to summarise.")

    try:
        import anthropic
    except ImportError:
        raise HTTPException(status_code=500, detail="anthropic library not installed — pip install anthropic")

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model=_REGEN_MODEL,
            max_tokens=600,
            system=_REGEN_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full}],
        )
        summary = (msg.content[0].text.strip() if msg.content else "") or ""
    except Exception as e:
        log.error("[about] regenerate-summary failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=502, detail=f"Claude API error: {type(e).__name__}: {e}")

    if not summary:
        raise HTTPException(status_code=502, detail="Claude returned an empty summary.")

    row.snappy_summary = summary
    await db.commit()
    return {"snappy_summary": summary}
