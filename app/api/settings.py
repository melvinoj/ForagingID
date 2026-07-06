"""
Settings API — GET /api/settings, PUT /api/settings/{key}, DELETE /api/settings/{key}

GET  /api/settings          → full registry with current effective values + DB override flag
PUT  /api/settings/{key}    → save override; takes effect immediately (no restart)
DELETE /api/settings/{key}  → reset to .env / code default; takes effect immediately
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sharing import is_guest_request
from app.api.identity import Identity, get_identity
from app.database import get_db
from app.models.settings import AppSetting
from app.services.settings_service import (
    get_registry,
    get_setting,
    reset_setting,
    save_setting,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: Any


class ApiKeyUpdate(BaseModel):
    api: str
    key: str


@router.get("/api-meta")
async def api_meta(request: Request):
    """Registry metadata only (no network) so the dashboard can render instantly."""
    if is_guest_request(request):
        raise HTTPException(status_code=403, detail="Owner-only")
    from app.services.api_dashboard import get_meta
    return {"apis": get_meta()}


@router.get("/api-status")
async def api_status(request: Request):
    """Live status of every external API integration, all at once (owner-only)."""
    if is_guest_request(request):
        raise HTTPException(status_code=403, detail="Owner-only")
    from app.services.api_dashboard import test_all
    return {"apis": await test_all()}


@router.get("/api-status/{api_id}")
async def api_status_one(api_id: str, request: Request):
    """Live status of a single API — used for streaming scans and per-card re-test."""
    if is_guest_request(request):
        raise HTTPException(status_code=403, detail="Owner-only")
    from app.services.api_dashboard import test_one
    try:
        return await test_one(api_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api-key")
async def save_api_key(
    body: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Save an API key/token to the correct destination (.env or DB) and apply live."""
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    from app.services.api_dashboard import set_api_key
    try:
        return await set_api_key(body.api, body.key, db)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("")
async def list_settings(db: AsyncSession = Depends(get_db)):
    """
    Return all settings from the registry, annotated with:
      - current_value: effective value (DB override if set, else default)
      - default_value: the .env / code default
      - overridden: whether a DB override is currently active
    """
    # Fetch all DB overrides in one query
    db_rows = {
        row.key: row.value
        for row in (await db.execute(select(AppSetting))).scalars().all()
    }

    result = []
    for entry in get_registry():
        key = entry["key"]
        current = get_setting(key)
        result.append({
            **entry,
            "current_value": current,
            "default_value": entry["default"],
            "overridden": key in db_rows,
            "db_raw": db_rows.get(key),
        })
    return {"settings": result}


@router.put("/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Save a setting override and apply it immediately."""
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    try:
        await save_setting(key, body.value, db)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {"key": key, "value": get_setting(key), "overridden": True}


@router.delete("/{key}")
async def reset_setting_endpoint(
    key: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Remove DB override, reverting the setting to its .env / code default."""
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    try:
        default = await reset_setting(key, db)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"key": key, "value": default, "overridden": False}


# ---------------------------------------------------------------------------
# Synthesis Sources — managed separately from the settings registry
# ---------------------------------------------------------------------------

_SYNTHESIS_SOURCES_DB_KEY = "synthesis_sources_json"


class SynthesisSourceCreate(BaseModel):
    label: str
    domain: str
    search_url: str
    note: Optional[str] = ""


async def _load_synthesis_sources(db: AsyncSession) -> list:
    """
    Return the effective SYNTHESIS_SOURCES list.
    If a DB override exists, use it. Otherwise return the module-level list.
    """
    row = await db.get(AppSetting, _SYNTHESIS_SOURCES_DB_KEY)
    if row and row.value:
        try:
            return json.loads(row.value)
        except Exception:
            pass
    from app.integrations.culinary_links import SYNTHESIS_SOURCES
    return list(SYNTHESIS_SOURCES)


async def _save_synthesis_sources(sources: list, db: AsyncSession) -> None:
    """Persist the synthesis sources list and update the in-memory module list."""
    json_val = json.dumps(sources, ensure_ascii=False)
    row = await db.get(AppSetting, _SYNTHESIS_SOURCES_DB_KEY)
    if row:
        row.value = json_val
        row.updated_at = datetime.utcnow()
        row.updated_by = "human"
    else:
        db.add(AppSetting(key=_SYNTHESIS_SOURCES_DB_KEY, value=json_val, updated_by="human"))
    await db.commit()

    # Apply immediately in-process (no restart needed)
    import app.integrations.culinary_links as _cl
    _cl.SYNTHESIS_SOURCES[:] = sources
    log.info("synthesis_sources: updated in-memory list (%d entries)", len(sources))


@router.get("/synthesis-sources")
async def get_synthesis_sources(db: AsyncSession = Depends(get_db)):
    """Return the current synthesis sources list (DB override or module default)."""
    sources = await _load_synthesis_sources(db)
    from app.integrations.culinary_links import SYNTHESIS_SOURCES as _default
    return {
        "sources": sources,
        "overridden": any(
            s["domain"] not in {d["domain"] for d in _default}
            for s in sources
        ),
    }


@router.post("/synthesis-sources")
async def add_synthesis_source(
    body: SynthesisSourceCreate,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Add a new synthesis source. URL must contain {query} placeholder."""
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    if "{query}" not in body.search_url:
        raise HTTPException(
            status_code=422,
            detail="search_url must contain the {query} placeholder (e.g. https://example.com/?s={query})",
        )
    sources = await _load_synthesis_sources(db)
    if any(s["domain"] == body.domain for s in sources):
        raise HTTPException(status_code=409, detail=f"Domain {body.domain!r} is already in the list.")
    new_entry = {
        "label": body.label.strip(),
        "domain": body.domain.strip().lower(),
        "search_url": body.search_url.strip(),
        "note": (body.note or "").strip(),
    }
    sources.append(new_entry)
    await _save_synthesis_sources(sources, db)
    return {"added": new_entry, "sources": sources}


@router.delete("/synthesis-sources/{domain:path}")
async def remove_synthesis_source(
    domain: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Remove a synthesis source by domain. Returns updated list."""
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sources = await _load_synthesis_sources(db)
    before = len(sources)
    sources = [s for s in sources if s["domain"] != domain]
    if len(sources) == before:
        raise HTTPException(status_code=404, detail=f"Domain {domain!r} not found in synthesis sources.")
    await _save_synthesis_sources(sources, db)
    return {"removed": domain, "sources": sources}
