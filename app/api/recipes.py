"""
Recipe bank API — Phase 3.

Endpoints:
  GET    /api/recipes                             — Recipes page: every approved,
                                                     culinary-allowed recipe (25 Oct 2026)
  GET    /api/species/{name}/recipes              — list approved recipes
  POST   /api/species/{name}/recipes              — add recipe (human, review queue)
  PATCH  /api/species/{name}/recipes/{id}         — edit (review queue only)
  POST   /api/species/{name}/recipes/{id}/set-preferred
  POST   /api/species/{name}/recipes/{id}/archive — soft-delete (review queue)
  POST   /api/species/{name}/recipes/regenerate   — AI edit/regenerate draft
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.identity import Identity, get_identity
from app.database import get_db
from app.models.species import (CULINARY_ALLOWED_SQL, RECIPE_TYPES, Species, SpeciesRecipe,
                                SpeciesAIDraft, culinary_allowed,
                                display_common_name, recipe_display_title, recipe_plant_parts,
                                recipe_summary_line, recipe_title_source, recipe_website_url_ok)
from app.models.culinary import CulinaryInfo
from app.services.ai_placeholder import is_ai_placeholder

log = logging.getLogger(__name__)
router = APIRouter()

VALID_SEASONS = {"spring", "summer", "autumn", "winter", "year-round"}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RecipeCreate(BaseModel):
    body: str
    title: Optional[str] = None
    season: str = "year-round"
    is_medicinal_prep: bool = False
    is_preferred: bool = False


class RecipePatch(BaseModel):
    body: Optional[str] = None
    title: Optional[str] = None
    season: Optional[str] = None
    is_medicinal_prep: Optional[bool] = None
    is_preferred: Optional[bool] = None
    # Recipes page fields (0059). "" clears summary / recipe_type / website_url.
    summary: Optional[str] = None
    recipe_type: Optional[str] = None
    hide_from_public: Optional[bool] = None
    website_url: Optional[str] = None


class RegenerateRequest(BaseModel):
    edit_command: Optional[str] = None   # e.g. "change shoots to flowers"
    season: str = "year-round"
    recipe_id: Optional[int] = None      # if editing an existing recipe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_species(db: AsyncSession, species_name: str) -> Species:
    sp = await db.scalar(
        select(Species).where(Species.scientific_name == species_name.strip())
    )
    if sp is None:
        raise HTTPException(404, f"Species '{species_name}' not found.")
    return sp


def _recipe_dict(r: SpeciesRecipe) -> dict:
    return {
        "id":               r.id,
        "title":            r.title,
        "body":             r.body,
        "season":           r.season,
        "is_preferred":     r.is_preferred,
        "is_medicinal_prep":r.is_medicinal_prep,
        "source":           r.source,
        "status":           r.status,
        "summary":          r.summary,
        "recipe_type":      r.recipe_type,
        "hide_from_public": bool(r.hide_from_public),
        "website_url":      r.website_url,
        "created_at":       r.created_at.isoformat() if r.created_at else None,
        "updated_at":       r.updated_at.isoformat() if r.updated_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/recipes — the Recipes page (Melvin, 25 Oct 2026)
# ---------------------------------------------------------------------------

@router.get("/api/recipes")
async def all_recipes(
    q: Optional[str] = Query(None, description="Ingredient or keyword (title + recipe text)"),
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Every approved, non-medicinal recipe whose species passes the culinary
    gate (CULINARY_ALLOWED_SQL = culinary_allowed — the species page's own
    rule, so a guest sees exactly the recipes the species pages show them).
    Toxic, deadly, inedible, unknown and never-assessed species never appear.
    `safety` holds each listed species' served decision once (the page shows
    its look-alike + preparation warnings with SafetyGate.culinaryWarnings, as
    every other culinary surface does); each recipe carries the saved walks
    its species is on. No recipe body (the species page holds it).
    created_at is the approval date: a recipe row is created when its draft is
    approved (culinary.approve_ai_draft) or when the curator adds it."""
    from app.api.walk import saved_walks_by_species
    from app.services.safety_gate import safety_for_species_bulk
    stmt = (select(SpeciesRecipe, Species)
            .join(Species, Species.id == SpeciesRecipe.species_id)
            .where(SpeciesRecipe.status == "approved")
            .where(SpeciesRecipe.is_medicinal_prep.is_(False))
            .where(CULINARY_ALLOWED_SQL))
    if q and q.strip():
        pat = f"%{q.strip()}%"
        stmt = stmt.where(SpeciesRecipe.title.ilike(pat) | SpeciesRecipe.body.ilike(pat)
                          | SpeciesRecipe.summary.ilike(pat) | Species.scientific_name.ilike(pat)
                          | Species.common_names.ilike(pat) | Species.preferred_common_name.ilike(pat))
    rows = (await db.execute(stmt.order_by(SpeciesRecipe.id))).all()
    walks = await saved_walks_by_species(db)
    safety = await safety_for_species_bulk(db, [sp for _, sp in rows])
    out = []
    for r, sp in rows:
        d = safety[sp.id]
        item = {
            "id": r.id,
            "title": recipe_display_title(r.title, r.body),
            "summary": (r.summary or "").strip() or recipe_summary_line(r.title, r.body),
            "recipe_type": r.recipe_type if r.recipe_type in RECIPE_TYPES else None,
            "season": r.season,
            "parts": recipe_plant_parts(r.title, r.body),
            "approved_at": r.created_at.isoformat() if r.created_at else None,
            "website_url": r.website_url if recipe_website_url_ok(r.website_url) else None,
            "species": {"id": sp.id, "scientific_name": sp.scientific_name,
                        "common": display_common_name(sp.preferred_common_name, sp.common_names) or None,
                        "level": d["level"], "label": d["label"]},
            "walks": walks.get(sp.scientific_name, []),
        }
        if not identity.is_guest:
            item["hide_from_public"] = bool(r.hide_from_public)
            # The shown title is only a first prose sentence: the curator types one.
            item["needs_title"] = recipe_title_source(r.title, r.body) not in ("own", "heading")
        out.append(item)
    return {"count": len(out), "types": list(RECIPE_TYPES), "recipes": out,
            "safety": {str(sid): d for sid, d in safety.items()}}


# ---------------------------------------------------------------------------
# GET /api/species/{name}/recipes
# ---------------------------------------------------------------------------

@router.get("/api/species/{species_name:path}/recipes")
async def list_recipes(
    species_name: str,
    season: Optional[str] = None,
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    List all approved (and optionally archived) recipes for a species.
    Ordered: preferred first, then by season match, then by created_at.
    """
    sp = await _get_species(db, species_name)

    stmt = select(SpeciesRecipe).where(SpeciesRecipe.species_id == sp.id)
    if not include_archived:
        stmt = stmt.where(SpeciesRecipe.status == "approved")
    stmt = stmt.order_by(
        SpeciesRecipe.is_preferred.desc(),
        SpeciesRecipe.created_at.desc(),
    )
    rows = (await db.execute(stmt)).scalars().all()

    # Culinary guard — one rule (safety_decision via culinary_allowed): recipes
    # only for an edible/caution verdict with severity 'none'. Blank otherwise
    # (no auto-delete).
    if not culinary_allowed(sp.toxicity_severity, sp.edibility_status):
        return {"species": sp.scientific_name, "edibility_blocked": True, "recipes": []}

    return {
        "species":          sp.scientific_name,
        "edibility_status": sp.edibility_status,
        "edibility_blocked":False,
        "recipes":          [_recipe_dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# POST /api/species/{name}/recipes  — add human recipe
# ---------------------------------------------------------------------------

@router.post("/api/species/{species_name:path}/recipes", status_code=201)
async def add_recipe(
    species_name: str,
    body: RecipeCreate,
    db: AsyncSession = Depends(get_db),
):
    sp = await _get_species(db, species_name)
    season = body.season if body.season in VALID_SEASONS else "year-round"

    # If marking preferred, clear previous preferred flag
    if body.is_preferred:
        prev = await db.scalars(
            select(SpeciesRecipe)
            .where(SpeciesRecipe.species_id == sp.id)
            .where(SpeciesRecipe.is_preferred == True)  # noqa: E712
        )
        for r in prev.all():
            r.is_preferred = False

    new_recipe = SpeciesRecipe(
        species_id=sp.id,
        title=body.title,
        body=body.body,
        season=season,
        is_preferred=body.is_preferred,
        is_medicinal_prep=body.is_medicinal_prep,
        source="human",
        status="approved",
    )
    db.add(new_recipe)
    await db.commit()
    await db.refresh(new_recipe)
    return _recipe_dict(new_recipe)


# ---------------------------------------------------------------------------
# PATCH /api/species/{name}/recipes/{recipe_id}
# ---------------------------------------------------------------------------

@router.patch("/api/species/{species_name:path}/recipes/{recipe_id}")
async def edit_recipe(
    species_name: str,
    recipe_id: int,
    body: RecipePatch,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    # Validate before anything changes.
    if body.recipe_type not in (None, "") and body.recipe_type not in RECIPE_TYPES:
        raise HTTPException(400, f"recipe_type must be one of {list(RECIPE_TYPES)}")
    if body.website_url not in (None, "") and not recipe_website_url_ok(body.website_url):
        raise HTTPException(400, "website_url must be an https link on melvinjarman.co.uk")
    if body.title is not None and len(body.title.strip()) > 200:
        raise HTTPException(400, "title is at most 200 characters")
    sp = await _get_species(db, species_name)
    recipe = await db.scalar(
        select(SpeciesRecipe)
        .where(SpeciesRecipe.id == recipe_id)
        .where(SpeciesRecipe.species_id == sp.id)
    )
    if recipe is None:
        raise HTTPException(404, "Recipe not found.")

    if body.body is not None:
        recipe.body = body.body
    if body.title is not None:
        recipe.title = body.title.strip() or None
    if body.season is not None:
        recipe.season = body.season if body.season in VALID_SEASONS else recipe.season
    if body.is_medicinal_prep is not None:
        recipe.is_medicinal_prep = body.is_medicinal_prep
    if body.summary is not None:
        recipe.summary = body.summary.strip() or None
    if body.recipe_type is not None:
        recipe.recipe_type = body.recipe_type or None
    if body.hide_from_public is not None:
        recipe.hide_from_public = bool(body.hide_from_public)
    if body.website_url is not None:
        recipe.website_url = body.website_url.strip() or None
    if body.is_preferred is not None:
        if body.is_preferred:
            # Clear previous preferred
            prev = await db.scalars(
                select(SpeciesRecipe)
                .where(SpeciesRecipe.species_id == sp.id)
                .where(SpeciesRecipe.is_preferred == True)  # noqa: E712
            )
            for r in prev.all():
                r.is_preferred = False
        recipe.is_preferred = body.is_preferred
    recipe.updated_at = datetime.utcnow()

    await db.commit()
    return _recipe_dict(recipe)


# ---------------------------------------------------------------------------
# POST /api/species/{name}/recipes/{id}/set-preferred
# ---------------------------------------------------------------------------

@router.post("/api/species/{species_name:path}/recipes/{recipe_id}/set-preferred")
async def set_preferred_recipe(
    species_name: str,
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
):
    sp = await _get_species(db, species_name)
    # Clear all preferred flags for this species
    all_recs = await db.scalars(
        select(SpeciesRecipe).where(SpeciesRecipe.species_id == sp.id)
    )
    for r in all_recs.all():
        r.is_preferred = (r.id == recipe_id)
    await db.commit()
    return {"ok": True, "preferred_recipe_id": recipe_id}


# ---------------------------------------------------------------------------
# POST /api/species/{name}/recipes/{id}/archive  — soft-delete
# ---------------------------------------------------------------------------

@router.post("/api/species/{species_name:path}/recipes/{recipe_id}/archive")
async def archive_recipe(
    species_name: str,
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
):
    sp = await _get_species(db, species_name)
    recipe = await db.scalar(
        select(SpeciesRecipe)
        .where(SpeciesRecipe.id == recipe_id)
        .where(SpeciesRecipe.species_id == sp.id)
    )
    if recipe is None:
        raise HTTPException(404, "Recipe not found.")
    recipe.status = "archived"
    recipe.updated_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "archived_id": recipe_id}


# ---------------------------------------------------------------------------
# POST /api/species/{name}/recipes/regenerate  — AI edit/regenerate
# ---------------------------------------------------------------------------

@router.post("/api/species/{species_name:path}/recipes/regenerate")
async def regenerate_recipe(
    species_name: str,
    body: RegenerateRequest,
    dry_run: bool = Query(False, description="show what it would create; write nothing"),
    db: AsyncSession = Depends(get_db),
):
    """
    Regenerate (or edit) a recipe on the AI backend (DeepSeek) with Melvin's cooking style prompt.
    Creates a new species_ai_drafts entry with status='pending' — shows in review queue
    BESIDE any pending recipe draft (kept one wins when Melvin approves it).
    Saved through the shared pre-save check (draft_gate); a refused recipe is 422.
    Returns the new draft immediately (not yet approved).
    """
    from app.integrations.deepseek_draft import ai_backend, ai_complete
    sp = await _get_species(db, species_name)

    backend = ai_backend()
    if not backend.api_key:
        raise HTTPException(503, "DeepSeek API key not configured.")

    # Enforce edibility: don't regenerate for toxic species
    from app.models.species import AI_NO_CONTENT_VERDICTS
    edib = (sp.edibility_status or "").lower()
    if edib in AI_NO_CONTENT_VERDICTS:
        raise HTTPException(400, f"Recipe generation is blocked for {edib} species.")
    if dry_run:
        from app.services.enrichment_plan import plan
        out = await plan(db, [sp.scientific_name], sources=False, regenerate=True, only_field="recipe")
        out["drafts_may_create"] = {"recipe": 1}
        return out

    # Get source recipe (from existing recipe or culinary_info)
    existing_body: Optional[str] = None
    if body.recipe_id:
        existing_recipe = await db.scalar(
            select(SpeciesRecipe)
            .where(SpeciesRecipe.id == body.recipe_id)
            .where(SpeciesRecipe.species_id == sp.id)
        )
        if existing_recipe:
            existing_body = existing_recipe.body

    # Get culinary context
    ci = await db.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
    )

    # Build prompt
    from app.integrations.claude_draft import _RECIPE_SYSTEM_PROMPT, _build_context, _context_to_text
    import json as _json

    common_names: list = []
    if sp.common_names:
        try:
            common_names = _json.loads(sp.common_names) or []
        except Exception:
            pass

    ctx = _build_context(
        scientific_name=species_name,
        common_names=common_names,
        edible_parts=ci.edible_parts if ci else None,
        preparation_methods=ci.preparation_methods if ci else None,
        traditional_uses=ci.traditional_uses if ci else None,
        medicinal_folklore=None,
        inat_description=None,
        trompenburg_description=None,
    )
    ctx_text = _context_to_text(species_name, ctx)

    # Build user prompt
    season_label = body.season.capitalize() if body.season != "year-round" else None
    if existing_body and body.edit_command:
        user_prompt = (
            f"Edit the following recipe for {species_name}. "
            f"Apply this change: {body.edit_command}\n\n"
            f"Original recipe:\n{existing_body}\n\n"
            f"Species context:\n{ctx_text}"
        )
        if season_label:
            user_prompt += f"\n\nTailor the recipe for {season_label}."
    elif existing_body:
        user_prompt = (
            f"Rewrite this recipe for {species_name} in Melvin Jarman's voice.\n\n"
            f"Original:\n{existing_body}\n\n"
            f"Species context:\n{ctx_text}"
        )
        if season_label:
            user_prompt += f"\n\nTailor for {season_label}."
    else:
        user_prompt = (
            f"Write one original recipe using {species_name} as the primary ingredient. "
            f"Use the following sourced information about this plant as context. "
            f"The recipe must reflect genuine knowledge of how this species tastes and how it is prepared."
            f"\n\n{ctx_text}"
        )
        if season_label:
            user_prompt += f"\n\nTailor for {season_label}."

    # The one AI backend (DeepSeek — Melvin D1, 21 Oct 2026)
    new_text = await ai_complete(species_name, _RECIPE_SYSTEM_PROMPT, user_prompt,
                                 max_tokens=900, label="recipe_regenerate")

    if not new_text:
        raise HTTPException(502, "The AI backend (DeepSeek) returned no recipe — nothing saved.")
    if is_ai_placeholder("recipe", new_text):
        raise HTTPException(422, "The AI returned a placeholder/refusal, not a recipe — nothing saved.")

    # Save as pending AI draft — through the shared pre-save check
    from app.services.draft_gate import check_ai_draft, save_ai_draft
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    draft = save_ai_draft(db, sp, ci, "recipe", new_text, model=backend.label,
                          context_json=json.dumps({
            "edit_command": body.edit_command,
            "season":       body.season,
            "source_recipe_id": body.recipe_id,
        }))
    if draft is None:
        raise HTTPException(422, f"Recipe not saved — {check_ai_draft('recipe', new_text, sp, ci).reason}")
    await db.commit()
    await db.refresh(draft)

    return {
        "ok":       True,
        "draft_id": draft.id,
        "season":   body.season,
        "preview":  draft.draft_text[:200] + ("…" if len(draft.draft_text) > 200 else ""),
        "draft_text": draft.draft_text,
    }
