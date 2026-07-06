"""
Species resources API — user-attached links, images, and PDFs.

GET    /api/species/{name}/resources        — list resources for a species
POST   /api/species/{name}/resources        — add link (JSON) or upload file (multipart)
DELETE /api/species/{name}/resources/{id}   — delete a resource (removes file from disk too)
"""
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.species import SpeciesResource

router = APIRouter(tags=["resources"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_PDF_TYPE = "application/pdf"
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


class AddLinkBody(BaseModel):
    url: str
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /api/species/{name}/resources
# ---------------------------------------------------------------------------

@router.get("/api/species/{species_name:path}/resources")
async def list_resources(species_name: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(SpeciesResource)
        .where(SpeciesResource.species_name == species_name.strip())
        .order_by(SpeciesResource.added_at.desc())
    )).scalars().all()
    return [_row_out(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /api/species/{name}/resources  — add link (JSON body)
# ---------------------------------------------------------------------------

@router.post("/api/species/{species_name:path}/resources")
async def add_resource(
    species_name: str,
    body: AddLinkBody,
    db: AsyncSession = Depends(get_db),
):
    row = SpeciesResource(
        species_name=species_name.strip(),
        resource_type="link",
        url=body.url.strip(),
        description=(body.description or "").strip() or None,
        added_at=datetime.utcnow(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _row_out(row)


# ---------------------------------------------------------------------------
# POST /api/species/{name}/resources/upload  — upload image or PDF (multipart)
# ---------------------------------------------------------------------------

@router.post("/api/species/{species_name:path}/resources/upload")
async def upload_resource(
    species_name: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    content_type = file.content_type or ""
    if content_type in _ALLOWED_IMAGE_TYPES:
        rtype = "image"
        ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    elif content_type == _ALLOWED_PDF_TYPE:
        rtype = "pdf"
        ext = "pdf"
    else:
        raise HTTPException(400, f"Unsupported file type: {content_type}. Allowed: image (jpg/png/webp/gif), PDF.")

    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large — maximum 20 MB.")

    dest_dir = settings.species_resources_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    dest_path = dest_dir / stored_name
    dest_path.write_bytes(data)

    served_url = f"/media/species-resources/{stored_name}"

    row = SpeciesResource(
        species_name=species_name.strip(),
        resource_type=rtype,
        url=served_url,
        filename=file.filename or stored_name,
        description=(description or "").strip() or None,
        added_at=datetime.utcnow(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _row_out(row)


# ---------------------------------------------------------------------------
# DELETE /api/species/{name}/resources/{id}
# ---------------------------------------------------------------------------

@router.delete("/api/species/{species_name:path}/resources/{resource_id}")
async def delete_resource(
    species_name: str,
    resource_id: int,
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(
        select(SpeciesResource)
        .where(SpeciesResource.id == resource_id)
        .where(SpeciesResource.species_name == species_name.strip())
    )
    if row is None:
        raise HTTPException(404, "Resource not found")

    # Remove file from disk if it was an upload.
    if row.resource_type in ("image", "pdf") and row.url:
        fname = row.url.split("/")[-1]
        fpath = settings.species_resources_dir / fname
        if fpath.exists():
            fpath.unlink(missing_ok=True)

    await db.delete(row)
    await db.commit()
    return {"ok": True, "id": resource_id}


def _row_out(r: SpeciesResource) -> dict:
    return {
        "id": r.id,
        "species_name": r.species_name,
        "resource_type": r.resource_type,
        "url": r.url,
        "filename": r.filename,
        "description": r.description,
        "added_at": r.added_at.isoformat() if r.added_at else None,
    }
