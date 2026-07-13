import json as _json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.notes import MapNote
from app.api.identity import Identity, get_identity

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteCreate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    text: str = Field(..., min_length=1, max_length=5000)
    species_tags: list[str] = Field(default_factory=list)


@router.get("/geojson")
async def notes_geojson(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(MapNote).order_by(MapNote.created_at.desc()))
    ).scalars().all()
    features = []
    for n in rows:
        tags = []
        try:
            tags = _json.loads(n.species_tags or "[]")
        except Exception:
            pass
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [n.longitude, n.latitude]},
            "properties": {
                "id": n.id,
                "map_status": "note",
                "text": n.text,
                "species_tags": tags,
                "created_at": n.created_at.isoformat(),
            },
        })
    return {"type": "FeatureCollection", "features": features}


@router.post("/")
async def create_note(
    body: NoteCreate,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    note = MapNote(
        latitude=body.latitude,
        longitude=body.longitude,
        text=body.text.strip(),
        species_tags=_json.dumps(body.species_tags),
        user_id=identity.user_id,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return {
        "ok": True,
        "id": note.id,
        "latitude": note.latitude,
        "longitude": note.longitude,
        "created_at": note.created_at.isoformat(),
    }


@router.delete("/{note_id}")
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db)):
    note = await db.get(MapNote, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.commit()
    return {"ok": True}


@router.get("/by-species/{species_name}")
async def notes_by_species(species_name: str, db: AsyncSession = Depends(get_db)):
    """Field notes tagged to a given species (for species card display)."""
    rows = (
        await db.execute(select(MapNote).order_by(MapNote.created_at.desc()))
    ).scalars().all()
    results = []
    for n in rows:
        try:
            tags = _json.loads(n.species_tags or "[]")
            if species_name in tags:
                results.append({
                    "id": n.id,
                    "latitude": n.latitude,
                    "longitude": n.longitude,
                    "text": n.text,
                    "created_at": n.created_at.isoformat(),
                })
        except Exception:
            pass
    return results
