"""
experience.py — Publish-as-experience, app side (Stage B2). Curator only on
EVERY route, GETs included: a guest / participant token gets 403 (checked via
get_identity, never by host). No publish / unpublish / push here (Stage C).

  GET   /api/experience/publications          — list
  GET   /api/experience/publications/{id}     — one
  POST  /api/experience/publications          — new draft {saved_walk_id, slug}
  PATCH /api/experience/publications/{id}     — {overrides_json?, slug?, is_default?}
  POST  /api/experience/publications/{id}/plan — export plan (no files written)
  POST  /api/experience/verify-species        — {species_id, note}: human-verify an
                                                edible/caution verdict with toxicity 'none'
  GET   /api/experience/critical              — hazards on a walk that are AI-agreed only

The plan runs scripts/experience_export/export.py --plan-json in a subprocess
rather than importing it: export.py edits sys.path and imports top-level
`gates` / `app_styles`, which must not leak into the server process, and the
API then returns exactly what the CLI prints.
"""
import asyncio
import json
import logging
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.identity import Identity, get_identity
from app.config import settings
from app.api.walk import walk_membership_for
from app.database import get_db
from app.models.experience import ExperiencePublication
from app.models.observation import Observation, is_human_confirmed
from app.models.species import (Species, SpeciesEdibilityHistory, culinary_allowed, display_common_name,
                                is_toxic_severity)
from app.models.walk import SavedWalk

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
EXPORT_SCRIPT = REPO / "scripts" / "experience_export" / "export.py"
PLAN_TIMEOUT_S = 180
# Same rule as export.py SLUG_RE (a subset of [a-z0-9-]+: no leading/trailing or
# double hyphen) so a draft can never hold a slug the export would refuse.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERIFIABLE_EDIBILITY = ("edible", "caution")


def _db_file() -> str:
    """The app's own SQLite file, so the plan reads the same DB the API does."""
    db = make_url(settings.database_url).database
    return str((REPO / db).resolve()) if not Path(db).is_absolute() else db


async def require_curator(identity: Identity = Depends(get_identity)) -> Identity:
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    return identity


router = APIRouter(prefix="/api/experience", tags=["experience"],
                   dependencies=[Depends(require_curator)])


# ---------------------------------------------------------------------------
# Publications
# ---------------------------------------------------------------------------

def _pub_out(p: ExperiencePublication) -> dict:
    return {
        "id": p.id, "saved_walk_id": p.saved_walk_id, "slug": p.slug, "is_default": bool(p.is_default),
        "overrides": json.loads(p.overrides_json) if p.overrides_json else {},
        "status": p.status,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "unpublished_at": p.unpublished_at.isoformat() if p.unpublished_at else None,
        "published_commit": p.published_commit,
        "public_species": json.loads(p.public_species_json) if p.public_species_json else None,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _check_slug(slug: str) -> str:
    slug = (slug or "").strip()
    if not SLUG_RE.match(slug):
        raise HTTPException(400, f"slug {slug!r} must be lowercase letters/digits separated by single hyphens")
    return slug


async def _load_pub(db: AsyncSession, pub_id: int) -> ExperiencePublication:
    p = await db.get(ExperiencePublication, pub_id)
    if p is None:
        raise HTTPException(404, "Publication not found")
    return p


async def _commit_and_reread(db: AsyncSession, pub_id: int) -> dict:
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(409, f"conflict: {e.orig}")
    db.expire_all()
    return _pub_out(await _load_pub(db, pub_id))


@router.get("/publications")
async def list_publications(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ExperiencePublication).order_by(ExperiencePublication.id))).scalars().all()
    return [_pub_out(p) for p in rows]


@router.get("/publications/{pub_id}")
async def get_publication(pub_id: int, db: AsyncSession = Depends(get_db)):
    return _pub_out(await _load_pub(db, pub_id))


class PublicationCreate(BaseModel):
    saved_walk_id: int
    slug: str


@router.post("/publications")
async def create_publication(body: PublicationCreate, db: AsyncSession = Depends(get_db),
                             identity: Identity = Depends(require_curator)):
    slug = _check_slug(body.slug)
    if await db.get(SavedWalk, body.saved_walk_id) is None:
        raise HTTPException(404, f"saved walk {body.saved_walk_id} not found")
    if await db.scalar(select(ExperiencePublication.id).where(ExperiencePublication.slug == slug)):
        raise HTTPException(409, f"slug {slug!r} is already used")
    now = datetime.utcnow()
    p = ExperiencePublication(saved_walk_id=body.saved_walk_id, slug=slug, is_default=False,
                              status="draft", created_by=identity.user_id, created_at=now, updated_at=now)
    db.add(p)
    await db.flush()
    return await _commit_and_reread(db, p.id)


class PublicationPatch(BaseModel):
    overrides_json: Optional[dict] = None
    slug: Optional[str] = None
    is_default: Optional[bool] = None


@router.patch("/publications/{pub_id}")
async def patch_publication(pub_id: int, body: PublicationPatch, db: AsyncSession = Depends(get_db)):
    p = await _load_pub(db, pub_id)
    if body.slug is not None:
        slug = _check_slug(body.slug)
        if slug != p.slug:
            if p.status == "published":
                raise HTTPException(409, "cannot change the slug of a published page (its URL is public) — unpublish first")
            if await db.scalar(select(ExperiencePublication.id).where(ExperiencePublication.slug == slug)):
                raise HTTPException(409, f"slug {slug!r} is already used")
            p.slug = slug
    if body.overrides_json is not None:
        if "slug" in body.overrides_json:
            raise HTTPException(400, "slug is not an override — set it with the slug field")
        p.overrides_json = json.dumps(body.overrides_json, ensure_ascii=False)
    if body.is_default is not None:
        if body.is_default and not p.is_default:
            # One default: clear the current one first (the partial unique index
            # is the backstop if this ever races).
            for other in (await db.execute(select(ExperiencePublication).where(
                    ExperiencePublication.is_default.is_(True),
                    ExperiencePublication.id != p.id))).scalars().all():
                other.is_default = False
                other.updated_at = datetime.utcnow()
            await db.flush()
        p.is_default = body.is_default
    p.updated_at = datetime.utcnow()
    return await _commit_and_reread(db, p.id)


@router.post("/publications/{pub_id}/plan")
async def plan_publication(pub_id: int, db: AsyncSession = Depends(get_db)):
    """Runs the export plan for this publication (--plan-json: no files written)."""
    p = await _load_pub(db, pub_id)
    if p.saved_walk_id is None:
        raise HTTPException(409, "this publication's walk was deleted")
    overrides = json.loads(p.overrides_json) if p.overrides_json else {}
    overrides["slug"] = p.slug
    with tempfile.TemporaryDirectory(prefix="exp_plan_") as tmp:
        ov_path = Path(tmp) / "overrides.json"
        ov_path.write_text(json.dumps(overrides, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(EXPORT_SCRIPT), "--walk-id", str(p.saved_walk_id),
               "--overrides", str(ov_path), "--plan-json", "--db", _db_file()]
        if p.is_default:
            cmd.append("--default")
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(REPO), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=PLAN_TIMEOUT_S)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(504, f"export plan timed out after {PLAN_TIMEOUT_S}s")
    try:
        plan = json.loads(out.decode("utf-8"))
    except ValueError:
        log.error("export plan produced no JSON (rc=%s): %s", proc.returncode, err.decode("utf-8", "replace")[-2000:])
        raise HTTPException(500, "export plan failed: " + err.decode("utf-8", "replace").strip()[-500:])
    plan["returncode"] = proc.returncode
    plan["publication_id"] = p.id
    return plan


# ---------------------------------------------------------------------------
# Verify an edibility verdict (human lock) — never changes the verdict itself
# ---------------------------------------------------------------------------

class VerifySpecies(BaseModel):
    species_id: int
    note: Optional[str] = None


@router.post("/verify-species")
async def verify_species(body: VerifySpecies, db: AsyncSession = Depends(get_db)):
    sp = await db.get(Species, body.species_id)
    if sp is None:
        raise HTTPException(404, f"species {body.species_id} not found")
    if sp.edibility_status not in VERIFIABLE_EDIBILITY:
        raise HTTPException(400, f"{sp.scientific_name}: edibility_status is {sp.edibility_status!r} — "
                                 f"only {list(VERIFIABLE_EDIBILITY)} can be verified here")
    if not culinary_allowed(sp.toxicity_severity):
        raise HTTPException(400, f"{sp.scientific_name}: toxicity_severity is {sp.toxicity_severity!r} — "
                                 f"only 'none' can be verified here")
    if sp.edibility_verified and sp.edibility_verified_by == "human":
        raise HTTPException(400, f"{sp.scientific_name} is already human-verified")

    note = (body.note or "").strip() or None
    old_verified, old_by = sp.edibility_verified, sp.edibility_verified_by
    sp.edibility_verified = True
    sp.edibility_verified_by = "human"
    now = datetime.utcnow()
    db.add(SpeciesEdibilityHistory(species_id=sp.id, field="edibility_verified",
                                   old_value=None if old_verified is None else str(int(bool(old_verified))),
                                   new_value="1", changed_at=now, changed_by="human", note=note))
    db.add(SpeciesEdibilityHistory(species_id=sp.id, field="edibility_verified_by",
                                   old_value=old_by, new_value="human", changed_at=now,
                                   changed_by="human", note=note))
    await db.commit()

    # Re-read by id — the write is only reported once it is seen in the row.
    db.expire_all()
    row = await db.get(Species, body.species_id)
    if not (row.edibility_verified and row.edibility_verified_by == "human"):
        raise HTTPException(500, f"write did not persist: edibility_verified={row.edibility_verified!r}, "
                                 f"edibility_verified_by={row.edibility_verified_by!r}")
    hist = (await db.execute(select(SpeciesEdibilityHistory).where(
        SpeciesEdibilityHistory.species_id == row.id, SpeciesEdibilityHistory.changed_at == now
    ).order_by(SpeciesEdibilityHistory.id))).scalars().all()
    return {
        "ok": True,
        "species": {"id": row.id, "scientific_name": row.scientific_name,
                    "edibility_status": row.edibility_status, "toxicity_severity": row.toxicity_severity,
                    "edibility_verified": bool(row.edibility_verified),
                    "edibility_verified_by": row.edibility_verified_by},
        "history": [{"id": h.id, "field": h.field, "old_value": h.old_value, "new_value": h.new_value,
                     "changed_by": h.changed_by, "note": h.note} for h in hist],
    }


# ---------------------------------------------------------------------------
# Critical hazards — computed at read time; no stored flag, no status change
# ---------------------------------------------------------------------------

@router.get("/critical")
async def critical_hazards(db: AsyncSession = Depends(get_db)):
    """Walk members (walk_membership, as the walk panel and export compute them)
    whose observation is AI-agreed only (confirmed, not is_human_confirmed) and
    whose species is toxic/deadly (is_toxic_severity). Unknown toxicity is not
    listed here — it is an export blocker only. review_status is never changed,
    so the map pin stays visible."""
    walks = (await db.execute(select(SavedWalk).order_by(SavedWalk.id))).scalars().all()
    placements = []                       # (walk, stop label, obs_id)
    for w in walks:
        mem = await walk_membership_for(db, w)
        for st in mem["stops"]:
            for sp in st["species"]:
                # sp["human"] is any-of across the species' obs — check each obs instead.
                for oid in sp["obs_ids"]:
                    placements.append((w, st["label"], oid))
    ids = sorted({oid for _, _, oid in placements})
    rows = {}
    if ids:
        res = await db.execute(select(Observation, Species)
                               .outerjoin(Species, Species.id == Observation.species_id)
                               .where(Observation.id.in_(ids)))
        rows = {o.id: (o, s) for o, s in res.all()}
    items = []
    for w, label, oid in placements:
        o, s = rows.get(oid, (None, None))
        if o is None or s is None or is_human_confirmed(o) or not is_toxic_severity(s.toxicity_severity):
            continue
        thumb = Path(o.thumbnail_path).name if o.thumbnail_path else None
        items.append({
            "obs_id": o.id, "species": o.species_primary, "species_id": s.id,
            "common": display_common_name(s.preferred_common_name, s.common_names) or None,
            "severity": s.toxicity_severity, "walk_id": w.id, "walk_name": w.name, "stop": label,
            "thumbnail": f"/thumbnails/{thumb}" if thumb else None,
            "review_status": o.review_status,
        })
    items.sort(key=lambda i: (0 if i["severity"] == "deadly" else 1, i["walk_id"], i["obs_id"]))
    return {"count": len({i["obs_id"] for i in items}), "items": items}
