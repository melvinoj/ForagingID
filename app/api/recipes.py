"""
Recipe bank API — Phase 3.

Endpoints:
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

from app.database import get_db
from app.models.species import Species, SpeciesRecipe, SpeciesAIDraft
from app.models.culinary import CulinaryInfo

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
        "created_at":       r.created_at.isoformat() if r.created_at else None,
        "updated_at":       r.updated_at.isoformat() if r.updated_at else None,
    }


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

    # Enforce edibility rules: blank for toxic/unknown species
    edib = (sp.edibility_status or "").lower()
    if edib in ("toxic", "inedible", "not_edible"):
        # Return empty recipe bank for toxic species (no auto-delete)
        return {"species": sp.scientific_name, "edibility_blocked": True, "recipes": []}
    if edib in ("unknown", "unclear", "") and sp.edibility_status is None:
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
):
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
        recipe.title = body.title
    if body.season is not None:
        recipe.season = body.season if body.season in VALID_SEASONS else recipe.season
    if body.is_medicinal_prep is not None:
        recipe.is_medicinal_prep = body.is_medicinal_prep
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
    db: AsyncSession = Depends(get_db),
):
    """
    Regenerate (or edit) a recipe using Claude with Melvin's cooking style prompt.
    Creates a new species_ai_drafts entry with status='pending' — shows in review queue.
    Returns the new draft immediately (not yet approved).
    """
    from app.config import settings as _settings
    from app.services.settings_service import get_setting
    sp = await _get_species(db, species_name)

    api_key = _settings.anthropic_api_key or ""
    model_id = get_setting("anthropic_model")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured.")

    # Enforce edibility: don't regenerate for toxic species
    edib = (sp.edibility_status or "").lower()
    if edib in ("toxic", "inedible", "not_edible"):
        raise HTTPException(400, f"Recipe generation is blocked for {edib} species.")

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

    # Call Claude
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model=model_id,
            max_tokens=900,
            system=_RECIPE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        new_text = msg.content[0].text.strip() if msg.content else None
    except ImportError:
        raise HTTPException(503, "anthropic library not installed.")
    except Exception as exc:
        log.error("[recipes] regenerate failed for %r: %s", species_name, exc)
        raise HTTPException(500, f"Generation failed: {exc}")

    if not new_text:
        raise HTTPException(500, "Claude returned empty response.")

    # Save as pending AI draft
    draft = SpeciesAIDraft(
        species_id=sp.id,
        field_name="recipe",
        draft_text=new_text,
        status="pending",
        model="claude-haiku-4-5-20251001",
        generation_context_json=json.dumps({
            "edit_command": body.edit_command,
            "season":       body.season,
            "source_recipe_id": body.recipe_id,
        }),
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    return {
        "ok":       True,
        "draft_id": draft.id,
        "season":   body.season,
        "preview":  new_text[:200] + ("…" if len(new_text) > 200 else ""),
        "draft_text": new_text,
    }
