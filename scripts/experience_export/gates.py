"""
Publication gates for the Foraging Experience export — the ONLY place these
rules live. export.py asks these functions every question about what may be
shown; it never re-implements a rule inline (same single-source-of-truth
discipline as app/models/observation.py's predicates).

Rules (Melvin, 15 Oct 2026; tightened for Publish B1, 18 Oct 2026):
  1. Species shown = species of this walk's observations that are
     HUMAN-confirmed (is_human_confirmed — approved/manually_verified,
     identified, and a human made the decision), not in hide_obs_ids and not
     in the walk's hide_species_ids.
     1b (Melvin, 21 Oct 2026): an observation confirmed only by dual-API
     agreement (AI-agreed) also counts when the app's shared safety decision
     allows its species — severity 'none' and verdict edible / caution /
     inedible (ai_agreed_included). Every other AI-agreed species is a rule-7
     blocker: ai_agreed_included is exactly `not unconfirmed_hazard`, so an
     AI-agreed species is either shown or blocks — never silently dropped.
  2. Edible claims and recipes ONLY if edibility_verified=1 AND
     edibility_verified_by='human'. A species whose verdict is edible/caution
     but NOT human-verified, and that would otherwise get an edible label,
     FAILS the build (GateError naming it) — never silently downgraded.
  3. toxic/deadly -> warning only, never a recipe or an edible label.
     Warnings are shown whether or not the verdict is verified (fails safe).
     Toxicity that is not exactly 'none' (NULL / unrecognised) fails closed:
     no edible label, no recipe, "toxicity unknown" badge (app's severity_is_none).
  4. Apiaceae: ALWAYS look-alike / ID cards — no edible label, no recipe,
     whatever the data (was config apiaceae_id_only; now unconditional).
  5. Recipes: status='approved' only; never is_medicinal_prep.
  6. No medicinal content anywhere.
  7. A species on the route that is AI-agreed only (not shown by rule 1b) and
     toxic/deadly or of unknown toxicity is a BLOCKER: the full build fails
     (the plan still prints) until a human confirms or re-identifies it.
     Also per STOP: any AI-agreed-only member observation at a stop whose
     species is toxic/deadly/unknown blocks, even if that species is
     human-confirmed at another stop.
  8. Caution species (audit D3-01, Melvin 20 Oct 2026 — option C, B as
     fallback): the caution reason is the curator-authored
     preparation_warnings (an approved warning draft counts). With one, the
     page shows it beside the caution badge. Without one, the species still
     shows with its caution badge, but ALL its recipes are withheld.

Safety text (look-alike / preparation warnings) is published ONLY when the
current value is curator-authored: the latest history row for that field is
changed_by='human' AND its new_value equals the current value. 'ai_approved:
human' (an AI draft a human approved) is NOT human-authored.
"""
from __future__ import annotations

import sqlite3

from app.models.observation import is_human_confirmed
from app.models.observation import is_confirmed_observation
from app.models.species import (CAUTION_UNREVIEWED_LABEL, WARNING_FIELDS, handout_warnings, is_curator_authored, is_toxic_severity,
                                safety_decision, severity_is_none, species_warnings)

APPROVED_REVIEW = ("approved", "manually_verified")
APIACEAE = "Apiaceae"
# Carrot-family genera (fixed list, Melvin 19 Oct 2026). The family column is
# unreliable — 98 species hold the genus there — so a genus match alone is
# enough to make a species an ID card.
APIACEAE_GENERA = frozenset({
    "Heracleum", "Berula", "Conium", "Cicuta", "Oenanthe", "Aethusa", "Anthriscus", "Chaerophyllum",
    "Daucus", "Aegopodium", "Angelica", "Pimpinella", "Sium", "Torilis", "Carum", "Foeniculum", "Apium",
    "Pastinaca", "Smyrnium", "Myrrhis", "Sanicula", "Astrantia", "Peucedanum", "Laserpitium", "Meum",
    "Seseli", "Bupleurum", "Eryngium", "Silaum", "Selinum", "Conopodium", "Petroselinum", "Levisticum",
    "Coriandrum", "Anethum", "Scandix", "Caucalis", "Falcaria", "Trinia", "Cnidium", "Physospermum",
    "Molopospermum", "Ligusticum", "Imperatoria",
})


# recipe_allowed() reason for rule 8 — export.py matches on it for the plan.
CAUTION_WITHHELD = "caution species without an approved warning — recipes withheld"


class GateError(RuntimeError):
    """A publish rule the data cannot satisfy — the build must stop."""


# ── observations ─────────────────────────────────────────────────────────────

def obs_passes(obs: dict, hide_obs_ids: set, hide_species_ids=frozenset(), sp=None) -> bool:
    """Rule 1 (+ 1b) for a single observation. sp = its species row; without it
    an AI-agreed observation fails closed (not shown)."""
    return (
        obs["id"] not in hide_obs_ids
        and obs["species_id"] is not None
        and obs["species_id"] not in hide_species_ids
        and obs["review_status"] in APPROVED_REVIEW
        and obs["identification_status"] == "identified"
        and (is_human_confirmed(obs)
             or (is_confirmed_observation(obs) and sp is not None and ai_agreed_included(sp)))
    )


# ── species verdict ──────────────────────────────────────────────────────────

def is_toxic(sp: dict) -> bool:
    return sp.get("edibility_status") == "toxic" or is_toxic_severity(sp.get("toxicity_severity"))


def is_deadly(sp: dict) -> bool:
    return (sp.get("toxicity_severity") or "none") == "deadly"


def _first_word(name) -> str:
    return (name or "").strip().split(" ")[0]


def is_apiaceae(sp: dict) -> bool:
    """Any of: family Apiaceae, genus in APIACEAE_GENERA, or the scientific
    name's first word in APIACEAE_GENERA. Any match = ID card only (rule 4)."""
    return ((sp.get("family") or "") == APIACEAE
            or (sp.get("genus") or "") in APIACEAE_GENERA
            or _first_word(sp.get("scientific_name")) in APIACEAE_GENERA)


def taxonomy_warnings(sp: dict) -> list:
    """Data-quality notes for --plan-only (warnings, never failures)."""
    out = []
    fam, genus = sp.get("family"), sp.get("genus")
    if not fam or not fam.endswith("aceae"):
        out.append(f"family {fam!r} is not a family name")
    first = _first_word(sp.get("scientific_name"))
    if genus and first and genus != first:
        out.append(f"genus {genus!r} disagrees with scientific name {sp.get('scientific_name')!r}")
    return out


def ai_agreed_included(sp) -> bool:
    """Rule 1b (Melvin, 21 Oct 2026): may an AI-agreed-only species be shown?
    The app's shared safety decision (safety_decision) — level 'none' or
    'caution', i.e. severity exactly 'none' and a verdict that is neither toxic
    nor unassessed (edible / caution / inedible) — and not toxic by this file's
    rule 3 either. sp=None fails closed."""
    if sp is None or is_toxic(sp):
        return False
    return safety_decision(sp.get("toxicity_severity"), sp.get("edibility_status"))["level"] in ("none", "caution")


def unconfirmed_hazard(sp) -> bool:
    """Rule 7 (B2, 19 Oct 2026): an AI-agreed-only species on the route that is
    toxic/deadly OR of unknown toxicity blocks the full build — it is left off
    the page, so its stop would carry no ☠. sp=None (observation not linked to
    a species row) is unknown, so it blocks too (fails closed). Exactly the
    complement of ai_agreed_included (rule 1b): an AI-agreed species is shown
    or it blocks. (Since 1b this also blocks a severity-'none' species whose
    verdict is unassessed — none exist on 21 Oct 2026.)"""
    return not ai_agreed_included(sp)


def obs_unconfirmed_hazard(obs: dict, sp) -> bool:
    """Rule 7, per stop (B2 follow-up, 19 Oct 2026): this member observation is
    AI-agreed only AND its species is a hazard (unconfirmed_hazard). Blocks even
    when the same species is human-confirmed at another stop — the page would
    show ☠ there but not at this stop."""
    return not is_human_confirmed(obs) and unconfirmed_hazard(sp)


def toxicity_known_safe(sp: dict) -> bool:
    """Rule 3's fail-closed half: toxicity assessed as exactly 'none' (the app's
    severity_is_none). Severity only, on purpose: it picks the "Toxicity unknown"
    badge and rule 7's blocker. Edible claims and recipes also need the verdict
    (may_claim_edible: human-verified edible/caution), which is stricter than the
    app's culinary_allowed()."""
    return severity_is_none(sp.get("toxicity_severity"))


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
    return bool(row) and is_curator_authored(row[0], row[1], current)


def is_caution(sp: dict) -> bool:
    return sp.get("edibility_status") == "caution"


def caution_warning(sp: dict, ci: dict, conn: sqlite3.Connection):
    """Rule 8: the curator-authored caution reason (preparation_warnings), or
    None. Toxic species are rule 3's (their warning is the toxic one)."""
    if not is_caution(sp) or is_toxic(sp):
        return None
    prep = species_warnings(_latest_rows(conn, ci))["preparation"]     # the app's one warnings rule
    return prep["text"] if prep and prep["reviewed"] else None


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
            if caution_warning(sp, ci, conn) is None:          # rule 8 (batch 6: same label as every handout)
                return {"kind": "caution", "text": CAUTION_UNREVIEWED_LABEL}
            return {"kind": "caution", "text": "Edible with caution"}
        return {"kind": "edible", "text": "Edible"}
    return {"kind": "none", "text": "For identification"}


def _latest_rows(conn: sqlite3.Connection, ci: dict) -> dict:
    """{column: (current, latest_changed_by, latest_new_value)} — species_warnings() input."""
    out = {}
    for col in WARNING_FIELDS.values():
        row = conn.execute(
            """SELECT changed_by, new_value FROM culinary_info_history
                WHERE culinary_info_id = ? AND field_name = ?
                ORDER BY changed_at DESC, id DESC LIMIT 1""",
            (ci.get("id"), col),
        ).fetchone() if ci.get("id") is not None else None
        out[col] = (ci.get(col), row[0] if row else None, row[1] if row else None)
    return out


def safety_texts(sp: dict, ci: dict, conn: sqlite3.Connection) -> dict:
    """The app's handout_warnings() (batch 6, one definition for every outgoing
    surface): curator-authored warnings only; toxic species always get a
    warning (TOXIC_FALLBACK_TEXT when none is curator-authored). Keys: toxic /
    caution / preparation (the preparation warning, by verdict) + look_alike."""
    level = "toxic" if is_toxic(sp) else safety_decision(sp.get("toxicity_severity"), sp.get("edibility_status"))["level"]
    hw = handout_warnings(level, species_warnings(_latest_rows(conn, ci)))
    out = {}
    if hw["look_alike"]:
        out["look_alike"] = hw["look_alike"]
    if is_toxic(sp):
        out["toxic"] = hw["preparation"]
    elif hw["preparation"]:
        out["caution" if is_caution(sp) else "preparation"] = hw["preparation"]   # caution = rule 8's reason
    return out


# ── repeat lines (species already shown at an earlier stop) ──────────────────

# Badges a compact "Also here" line must keep — every safety signal: ☠ deadly /
# toxic, ⚠ toxicity unknown, caution, and the Apiaceae look-alike warning.
# Edible / inedible / none carry no warning, so the compact line drops them.
REPEAT_BADGE_KINDS = ("deadly", "toxic", "unknown", "caution", "apiaceae")


def repeat_line_badge(badge: dict):
    """The badge for a repeat line (same dict edibility_badge() made), or None."""
    return badge if badge["kind"] in REPEAT_BADGE_KINDS else None


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
    # Rule 8 = the app's outgoing-surface rule (safety_decision's
    # handout_culinary_allowed, batch 6) — one predicate for every handout.
    d = safety_decision(sp.get("toxicity_severity"), sp.get("edibility_status"), caution_warning(sp, ci, conn))
    if d["level"] == "caution" and not d["handout_culinary_allowed"]:
        return False, CAUTION_WITHHELD                       # rule 8
    return True, ""
