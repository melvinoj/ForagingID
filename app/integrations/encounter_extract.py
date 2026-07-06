"""
Encounter extraction — Phase 11a.4 + 12.

A lightweight Claude API call that reads an encounter transcript and surfaces
SUGGESTIONS for the user to confirm or dismiss. It never writes anything itself
and never touches species cards.

Suggestion types:
  - species       : a plant/fungus mentioned → suggest linking the encounter to a card
  - phenology     : a season/stage cue ('berries forming', 'first flowers', 'going to seed')
  - field_recipe  : a preparation/recipe sequence detected → structured Field Recipe suggestion
  - foraging_note : field awareness cue (lookalikes, "false X") — NOT a safety flag
  - safety_note   : ONLY when explicit harm language present ("toxic", "poisonous", "do not eat")
  - location      : a location cue ('by the top gate', 'north-facing slope')

Rules:
  - Requires ANTHROPIC_API_KEY (returns [] silently if absent)
  - Uses Haiku (classification-grade, cheap) by default
  - Best-effort: any failure returns [] so the encounter view never breaks
  - Species in suggestions are reconciled against the known confirmed-species index
  - "false dandelion", "not the X" → foraging_note, not safety
  - Only flag safety_note for: "toxic", "poisonous", "do not eat", "harmful", "dangerous"
"""

import json
import logging
from typing import List, Optional

log = logging.getLogger(__name__)

_EXTRACT_MODEL_DEFAULT = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """\
You read short voice-note transcripts from a forager walking in the field and \
pull out structured cues. You only extract what is genuinely present in the text \
— never infer, never invent. Return strict JSON and nothing else.\
"""

_INSTRUCTION = """\
From the transcript below, extract any of these cues. Return ONLY a JSON object of \
the form {"suggestions": [ ... ]} where each item has the appropriate structure:

TYPE: "species"
  "value": plant/fungus name as said
  "quote": short verbatim span

TYPE: "phenology"
  "value": short stage tag ("fruiting", "first flowers", "going to seed", "leafing out")
  "quote": short verbatim span

TYPE: "field_recipe"  — use ONLY when a recipe/preparation sequence is present
  (cues: "I'm making", "putting in", "cordial", "infusion", "tea", "syrup", "we're picking for", "recipe")
  "title": short auto-generated title (e.g. "Elderflower Cordial", "Wild Infusion")
  "body": the full extracted preparation text, exactly as described
  "ingredients": list of {{"name": "...", "quantity": "..."}} — preserve natural language
                 quantities exactly ("a couple of handfuls", "just a few", "lots")
  "quote": short verbatim span that triggered detection

TYPE: "foraging_note"  — for field-awareness cues (lookalikes, "false X", "be careful not to get")
  IMPORTANT: "false dandelion", "not the X", "make sure it's not the X" = foraging_note
  These are identification-awareness remarks, NOT safety warnings
  "value": the short note, e.g. "false dandelion edible but bitter — confirmed common dandelion"
  "quote": short verbatim span

TYPE: "safety_note"  — ONLY for explicit harm language
  ONLY use if transcript contains: "toxic", "poisonous", "do not eat", "harmful", "dangerous"
  "value": the safety warning
  "quote": verbatim span containing the explicit harm word

TYPE: "location"
  "value": place description ("by the top gate", "north-facing slope")
  "quote": short verbatim span

Rules:
- Only include cues actually present. If none of a type appear, omit them.
- Multiple items per type are fine.
- For field_recipe: list each ingredient separately with its quantity.
- For foraging_note: never elevate to safety_note just because a false/lookalike species is mentioned.
- If transcript contains nothing extractable, return {"suggestions": []}.

Transcript:
\"\"\"
%s
\"\"\""""

_RECIPE_CUES = frozenset([
    "cordial", "infusion", "i'm making", "we're making", "i am making",
    "putting in", "put in", "recipe", "cook", "prepare", "syrup", "jam",
    "wine", "tea", "vinegar", "i'm going to", "going to put",
    "we are picking", "picking for",
])

_SAFETY_WORDS = frozenset(["toxic", "poisonous", "do not eat", "harmful", "dangerous", "deadly"])


def _normalise(s: str) -> str:
    return " ".join((s or "").lower().replace(".", " ").split())


def _match_species(value: str, species_index: List[dict]) -> Optional[dict]:
    """Return {id, scientific_name} for the best name match, or None."""
    nv = _normalise(value)
    if not nv:
        return None
    for sp in species_index:
        names = [sp.get("scientific_name") or ""] + list(sp.get("common_names") or [])
        for name in names:
            nn = _normalise(name)
            if nn and (nn == nv or nv in nn or nn in nv):
                return {"id": sp.get("id"), "scientific_name": sp.get("scientific_name")}
    return None


def _has_recipe_cue(transcript: str) -> bool:
    """Quick pre-check — does the transcript contain any recipe-type language?"""
    tl = transcript.lower()
    return any(cue in tl for cue in _RECIPE_CUES)


async def extract_suggestions(
    transcript: str,
    api_key: str,
    species_index: Optional[List[dict]] = None,
    model: str = _EXTRACT_MODEL_DEFAULT,
) -> List[dict]:
    """
    Run the extraction call. Returns a list of suggestion dicts (possibly empty).

    Suggestion shapes:
      species:       {id, type, value, quote, matched_species_id, matched_species_name, status}
      phenology:     {id, type, value, quote, status}
      field_recipe:  {id, type, title, body, ingredients, quote, status}
                     ingredients = [{name, quantity, species_id, matched_species_name}]
      foraging_note: {id, type, value, quote, status}
      safety_note:   {id, type, value, quote, status}
      location:      {id, type, value, quote, status}
    """
    transcript = (transcript or "").strip()
    if not transcript:
        return []
    if not api_key:
        log.info("[encounter_extract] no ANTHROPIC_API_KEY — skipping extraction")
        return []

    species_index = species_index or []

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
    except ImportError:
        log.error("[encounter_extract] anthropic library not installed")
        return []
    except Exception as e:
        log.error("[encounter_extract] client init failed: %s: %s", type(e).__name__, e)
        return []

    prompt = _INSTRUCTION % transcript[:4000]
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=1200,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip() if msg.content else ""
    except Exception as e:
        log.error("[encounter_extract] API call failed: %s: %s", type(e).__name__, e)
        return []

    parsed = None
    try:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(raw[start:end + 1])
    except Exception as e:
        log.warning("[encounter_extract] could not parse JSON: %s — raw=%r", e, raw[:200])
        return []

    items = (parsed or {}).get("suggestions") or []
    out: List[dict] = []
    _VALID = {"species", "phenology", "field_recipe", "foraging_note", "safety_note", "location",
              # legacy — keep old "recipe" type working for existing data
              "recipe"}

    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        stype = (item.get("type") or "").strip().lower()
        if stype not in _VALID:
            continue

        quote = (item.get("quote") or "").strip() or None

        if stype == "field_recipe":
            title = (item.get("title") or "Field Recipe").strip()
            body  = (item.get("body") or "").strip()
            raw_ings = item.get("ingredients") or []
            ingredients = []
            for ing in raw_ings:
                if not isinstance(ing, dict):
                    continue
                name = (ing.get("name") or "").strip()
                qty  = (ing.get("quantity") or "").strip()
                if not name:
                    continue
                m = _match_species(name, species_index)
                ingredients.append({
                    "name":                  name,
                    "quantity":              qty or None,
                    "species_id":            m["id"] if m else None,
                    "matched_species_name":  m["scientific_name"] if m else None,
                })
            sug = {
                "id":          f"s{i}",
                "type":        "field_recipe",
                "title":       title,
                "body":        body,
                "ingredients": ingredients,
                "quote":       quote,
                "status":      "pending",
            }
        else:
            value = (item.get("value") or "").strip()
            if not value:
                continue
            sug = {
                "id":     f"s{i}",
                "type":   stype,
                "value":  value,
                "quote":  quote,
                "status": "pending",
            }
            if stype == "species":
                m = _match_species(value, species_index)
                sug["matched_species_id"]   = m["id"] if m else None
                sug["matched_species_name"] = m["scientific_name"] if m else None

        out.append(sug)

    log.info("[encounter_extract] extracted %d suggestions (model=%r)", len(out), model)
    return out
