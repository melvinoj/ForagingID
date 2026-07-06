"""
Data Sources registry API (Phase 11a).

Registry + reachability only — NO scraping logic. Scraping is per-source in
future prompts.

  GET    /api/data-sources           — list all
  POST   /api/data-sources           — add a new source
  PATCH  /api/data-sources/{id}       — update status / notes (and other fields)
  DELETE /api/data-sources/{id}       — remove a source
  POST   /api/data-sources/{id}/test  — HEAD/GET reachability probe (8s timeout)
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.data_source import DataSource

log = logging.getLogger(__name__)

# Consistent with the 8s fail-fast timeout used by the external API clients.
REQUEST_TIMEOUT_S = 8

router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])

_VALID_DATA_TYPES = {"culinary", "id_notes", "medicinal", "phenology", "folklore"}
_VALID_SCOPE = {"plants", "fungi", "both"}
_VALID_STATUS = {"active", "paused", "reference-only"}


# ---------------------------------------------------------------------------
# Pydantic
# ---------------------------------------------------------------------------

class DataSourceCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=300)
    url: str = Field(..., min_length=3, max_length=1000)
    data_types: List[str] = Field(default_factory=list)
    species_scope: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None


class DataSourceUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=300)
    url: Optional[str] = Field(None, max_length=1000)
    data_types: Optional[List[str]] = None
    species_scope: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_types(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return [str(x) for x in v] if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def _clean_types(types: List[str]) -> List[str]:
    # Keep only known types, de-duplicated, order-preserving.
    seen, out = set(), []
    for t in types or []:
        t = (t or "").strip()
        if t in _VALID_DATA_TYPES and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _normalise_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _to_dict(ds: DataSource) -> dict:
    return {
        "id": ds.id,
        "label": ds.label,
        "url": ds.url,
        "data_types": _parse_types(ds.data_types),
        "species_scope": ds.species_scope,
        "region": ds.region,
        "status": ds.status,
        "notes": ds.notes,
        "last_tested": ds.last_tested.isoformat() if ds.last_tested else None,
        "last_test_status": ds.last_test_status,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }


async def _get_or_404(db: AsyncSession, source_id: int) -> DataSource:
    ds = await db.scalar(select(DataSource).where(DataSource.id == source_id))
    if not ds:
        raise HTTPException(404, detail="Data source not found")
    return ds


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_data_sources(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(DataSource).order_by(DataSource.label.asc()))
    return {"data_sources": [_to_dict(ds) for ds in rows.scalars().all()]}


@router.post("")
async def create_data_source(body: DataSourceCreate, db: AsyncSession = Depends(get_db)):
    url = _normalise_url(body.url)
    if not url:
        raise HTTPException(422, detail="A URL is required")

    if body.species_scope and body.species_scope not in _VALID_SCOPE:
        raise HTTPException(422, detail=f"species_scope must be one of {sorted(_VALID_SCOPE)}")

    existing = await db.scalar(select(DataSource).where(DataSource.url == url))
    if existing:
        raise HTTPException(409, detail="A source with this URL already exists")

    ds = DataSource(
        label=body.label.strip(),
        url=url,
        data_types=json.dumps(_clean_types(body.data_types)),
        species_scope=body.species_scope or None,
        region=(body.region or None),
        status="active",
        notes=(body.notes or "").strip() or None,
        last_test_status="untested",
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return _to_dict(ds)


@router.patch("/{source_id}")
async def update_data_source(source_id: int, body: DataSourceUpdate, db: AsyncSession = Depends(get_db)):
    ds = await _get_or_404(db, source_id)

    if body.label is not None:
        ds.label = body.label.strip()
    if body.url is not None:
        new_url = _normalise_url(body.url)
        if new_url and new_url != ds.url:
            clash = await db.scalar(select(DataSource).where(DataSource.url == new_url))
            if clash:
                raise HTTPException(409, detail="A source with this URL already exists")
            ds.url = new_url
    if body.data_types is not None:
        ds.data_types = json.dumps(_clean_types(body.data_types))
    if body.species_scope is not None:
        if body.species_scope and body.species_scope not in _VALID_SCOPE:
            raise HTTPException(422, detail=f"species_scope must be one of {sorted(_VALID_SCOPE)}")
        ds.species_scope = body.species_scope or None
    if body.region is not None:
        ds.region = body.region or None
    if body.status is not None:
        if body.status not in _VALID_STATUS:
            raise HTTPException(422, detail=f"status must be one of {sorted(_VALID_STATUS)}")
        ds.status = body.status
    if body.notes is not None:
        ds.notes = body.notes.strip() or None

    await db.commit()
    await db.refresh(ds)
    return _to_dict(ds)


@router.delete("/{source_id}")
async def delete_data_source(source_id: int, db: AsyncSession = Depends(get_db)):
    ds = await _get_or_404(db, source_id)
    await db.delete(ds)
    await db.commit()
    return {"ok": True, "id": source_id}


@router.post("/{source_id}/test")
async def test_data_source(source_id: int, db: AsyncSession = Depends(get_db)):
    """
    Reachability probe only — HEAD first, fall back to GET if HEAD is rejected.
    Updates last_tested + last_test_status (ok / unreachable). 8s timeout.
    """
    ds = await _get_or_404(db, source_id)

    status = "unreachable"
    http_status: Optional[int] = None
    detail: Optional[str] = None

    headers = {"User-Agent": "ForagingID-DataSourceRegistry/1.0"}
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S, follow_redirects=True, headers=headers
        ) as client:
            try:
                resp = await client.head(ds.url)
                # Some servers don't support HEAD — retry with GET.
                if resp.status_code in (403, 405, 501) or resp.status_code >= 500:
                    resp = await client.get(ds.url)
            except httpx.HTTPError:
                resp = await client.get(ds.url)

            http_status = resp.status_code
            status = "ok" if resp.status_code < 400 else "unreachable"
            if status == "unreachable":
                detail = f"HTTP {resp.status_code}"
    except httpx.TimeoutException:
        detail = f"Timed out after {REQUEST_TIMEOUT_S}s"
    except httpx.HTTPError as e:
        detail = str(e) or e.__class__.__name__
    except Exception as e:  # noqa: BLE001 — never let a probe 500 the endpoint
        detail = str(e) or e.__class__.__name__

    ds.last_tested = datetime.utcnow()
    ds.last_test_status = status
    await db.commit()
    await db.refresh(ds)

    log.info("Tested data source %s (%s): %s", ds.label, ds.url, status)
    return {
        "ok": True,
        "id": ds.id,
        "last_test_status": status,
        "http_status": http_status,
        "detail": detail,
        "last_tested": ds.last_tested.isoformat(),
    }
