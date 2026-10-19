"""
Publication gates for the Foraging Experience export — the ONLY place these
rules live. export.py asks these functions every question about what may be
shown; it never re-implements a rule inline (same single-source-of-truth
discipline as app/models/observation.py's predicates).

Rules (Melvin, 15 Oct 2026; tightened for Publish B1, 18 Oct 2026):
  1. Species shown = species of this walk's observations that are
     HUMAN-confirmed (is_human_confirmed — approved/manually_verified,
     identified, and a human made the decision; AI-agreed-only is excluded),
     not in hide_obs_ids and not in the walk's hide_species_ids.
  2. Edible claims and recipes ONLY if edibility_verified=1 AND
     edibility_verified_by='human'. A species whose verdict is edible/caution
     but NOT human-verified, and that would otherwise get an edible label,
     FAILS the build (GateError naming it) — never silently downgraded.
  3. toxic/deadly -> warning only, never a recipe or an edible label.
     Warnings are shown whether or not the verdict is verified (fails safe).
     Toxicity that is not exactly 'none' (NULL / unrecognised) fails closed:
     no edible label, no recipe, "toxicity unknown" badge (app's culinary_allowed).
  4. Apiaceae: ALWAYS look-alike / ID cards — no edible label, no recipe,
     whatever the data (was config apiaceae_id_only; now unconditional).
  5. Recipes: status='approved' only; never is_medicinal_prep.
  6. No medicinal content anywhere.

Safety text (look-alike / preparation warnings) is published ONLY when the
current value is curator-authored: the latest history row for that field is
changed_by='human' AND its new_value equals the current value. 'ai_approved:
human' (an AI draft a human approved) is NOT human-authored.
"""
from __future__ import annotations

import sqlite3

from app.models.observation import is_human_confirmed
from app.models.species import culinary_allowed

APPROVED_REVIEW = ("approved", "manually_verified")
TOXIC_SEVERITIES = ("toxic", "deadly")
APIACEAE = "Apiaceae"


class GateError(RuntimeError):
    """A publish rule the data cannot satisfy — the build must stop."""


# ── observations ─────────────────────────────────────────────────────────────

def obs_passes(obs: dict, hide_obs_ids: set, hide_species_ids=frozenset()) -> bool:
    """Rule 1 for a single observation."""
    return (
        obs["id"] not in hide_obs_ids
        and obs["species_id"] is not None
        and obs["species_id"] not in hide_species_ids
        and obs["review_status"] in APPROVED_REVIEW
        and obs["identification_status"] == "identified"
        and is_human_confirmed(obs)
    )


# ── species verdict ──────────────────────────────────────────────────────────

def is_toxic(sp: dict) -> bool:
    return (sp.get("edibility_status") == "toxic"
            or (sp.get("toxicity_severity") or "none") in TOXIC_SEVERITIES)


def is_deadly(sp: dict) -> bool:
    return (sp.get("toxicity_severity") or "none") == "deadly"


def is_apiaceae(sp: dict) -> bool:
    return (sp.get("family") or "") == APIACEAE


def toxicity_known_safe(sp: dict) -> bool:
    """Rule 3's fail-closed half: culinary content only when toxicity is exactly 'none'."""
    return culinary_allowed(sp.get("toxicity_severity"))


def human_verified(sp: dict) -> bool:
    """Rule 2's verification half."""
    return bool(sp.get("edibility_verified")) and sp.get("edibility_verified_by") == "human"


def human_authored(conn: sqlite3.Connection, culinary_info_id, field: str, current) -> bool:
    """True only if the CURRENT value of a culinary_info field is curator-authored."""
    if culinary_info_id is None or not (current or "").strip():
        return False
    row = conn.execute(
        """SELECT changed_by, new_value FROM culinary_info_history
            WHERE culinary_info_id = ? AND field_name = ?
            ORDER BY changed_at DESC, id DESC LIMIT 1""",
        (culinary_info_id, field),
    ).fetchone()
    return bool(row) and row[0] == "human" and (row[1] or "").strip() == (current or "").strip()


def may_claim_edible(sp: dict, ci: dict, conn: sqlite3.Connection, cfg: dict) -> bool:
    """May the page call this species edible (or edible-with-caution)?"""
    if is_apiaceae(sp):
        return False                                   # rule 4
    if is_toxic(sp) or not toxicity_known_safe(sp):
        return False                                   # rule 3
    if sp.get("edibility_status") not in ("edible", "caution"):
        return False
    if not human_verified(sp):
        return False                                   # rule 2
    return True


def edibility_badge(sp: dict, ci: dict, conn: sqlite3.Connection, cfg: dict) -> dict:
    """{kind, text} for the species badge. Never an edible label for toxic.
    Raises GateError for an edible/caution verdict that is not human-verified
    (rule 2) — the curator verifies it or hides the species; no downgrade."""
    if is_toxic(sp):
        if is_deadly(sp):
            return {"kind": "deadly", "text": "☠ Deadly — do not touch or eat"}
        return {"kind": "toxic", "text": "☠ Toxic — do not eat"}
    if not toxicity_known_safe(sp):
        return {"kind": "unknown", "text": "⚠ Toxicity unknown — do not eat"}
    if is_apiaceae(sp):
        return {"kind": "apiaceae", "text": "Carrot family — deadly look-alikes"}
    if sp.get("edibility_status") == "inedible":
        return {"kind": "inedible", "text": "Not for eating"}
    if sp.get("edibility_status") in ("edible", "caution") and not human_verified(sp):
        raise GateError(
            f"species {sp['id']} {sp['scientific_name']} is '{sp['edibility_status']}' but not human-verified "
            f"(edibility_verified={sp.get('edibility_verified')!r}, edibility_verified_by={sp.get('edibility_verified_by')!r}) "
            f"— it would show an edible label. Verify it in the app, or add {sp['id']} to this walk's hide_species_ids.")
    if may_claim_edible(sp, ci, conn, cfg):
        if sp["edibility_status"] == "caution":
            return {"kind": "caution", "text": "Edible with caution"}
        return {"kind": "edible", "text": "Edible"}
    return {"kind": "none", "text": "For identification"}


def safety_texts(sp: dict, ci: dict, conn: sqlite3.Connection, toxic_fallback: str) -> dict:
    """Curator-authored warnings only; toxic species always get a warning."""
    out = {}
    if human_authored(conn, ci.get("id"), "look_alike_warnings", ci.get("look_alike_warnings")):
        out["look_alike"] = ci["look_alike_warnings"].strip()
    if is_toxic(sp):
        if human_authored(conn, ci.get("id"), "preparation_warnings", ci.get("preparation_warnings")):
            out["toxic"] = ci["preparation_warnings"].strip()
        else:
            out["toxic"] = toxic_fallback
    return out


# ── recipes ──────────────────────────────────────────────────────────────────

def recipe_allowed(sp: dict, ci: dict, recipe: dict, conn: sqlite3.Connection, cfg: dict):
    """(allowed: bool, reason: str). Reason is reported for every exclusion."""
    if recipe["status"] != "approved":
        return False, f"status {recipe['status']}"
    if recipe["is_medicinal_prep"]:
        return False, "medicinal preparation"
    if recipe["id"] in set(cfg.get("exclude_recipe_ids", [])):
        return False, "excluded in config"
    if sp["id"] in set(cfg.get("exclude_recipe_species_ids", [])):
        return False, "species excluded in config"
    if recipe["source"] not in set(cfg.get("recipe_sources_allowed", [])):
        return False, f"source not allowed ({recipe['source']})"
    if is_toxic(sp):
        return False, "toxic species"
    if not toxicity_known_safe(sp):
        return False, f"toxicity unknown ({sp.get('toxicity_severity')!r}) — fails closed"
    if is_apiaceae(sp):
        return False, "Apiaceae — ID card only"
    if not may_claim_edible(sp, ci, conn, cfg):
        return False, "no edible claim (not human-verified edible/caution)"
    return True, ""
