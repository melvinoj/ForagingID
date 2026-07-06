"""
App-level settings service.

Two-layer resolution:
  1. DB table `app_settings` — human-set overrides (persisted across restarts)
  2. REGISTRY default — the .env / code default for that key

`get_setting(key)` returns the DB override if one exists, otherwise the
REGISTRY default. The result is always a typed Python value (float, int,
bool, or str depending on the key's `type` field).

Call `load_settings_from_db()` once at startup (inside lifespan). After
that every `get_setting()` call is a pure dict lookup — zero DB overhead.
`save_setting()` writes to the DB and refreshes the cache immediately so
changes take effect without a restart.

Registry structure per entry:
  key          str   — the setting key
  default      any   — value derived from .env / config / hardcoded constant
  type         str   — "float" | "int" | "bool" | "str"
  label        str   — human-readable name shown in the Settings UI
  description  str   — one-line explanation
  group        str   — UI section header
  min          opt   — minimum value (numeric only)
  max          opt   — maximum value (numeric only)
  choices      opt   — list of allowed values (str only)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import AppSetting

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry — single source of truth for every configurable setting
# ---------------------------------------------------------------------------

def _build_registry() -> List[Dict]:
    """Build the registry late so imports from config/services don't
    create circular dependencies at module load time."""

    from app.config import settings as cfg
    from app.services.prefilter import (
        PLANT_GREEN_THRESHOLD, PLANT_GREEN_THRESHOLD_GPS,
        SKIN_REJECT_THRESHOLD, WARM_REJECT_THRESHOLD,
        BLUE_REJECT_THRESHOLD, UI_RATIO_THRESHOLD,
        INDOOR_DARK_THRESHOLD, INDOOR_BRIGHT_THRESHOLD,
    )
    from app.services.enrichment import PFAF_DELAY_S, WIKIDATA_DELAY_S

    return [
        # ── Identification ────────────────────────────────────────────────
        {
            "key": "min_identification_confidence",
            "default": 0.50,
            "type": "float",
            "label": "Minimum identification confidence",
            "description": (
                "Observations whose top API result scores below this threshold are sent "
                "to review as 'no match' — species_primary is left null and the "
                "suggested name is stored separately for the reviewer. "
                "Range 10–90 %. Default 50 %."
            ),
            "group": "Identification",
            "min": 0.10,
            "max": 0.90,
        },
        {
            "key": "upload_auto_approve_threshold",
            "default": 0.80,
            "type": "float",
            "label": "Auto-approve confidence threshold (dual-API agreement)",
            "description": (
                "Both PlantNet AND iNaturalist must name the same species at or above "
                "this score for an observation to be auto-approved. Applies to all pipelines. "
                "Set to 1.0 to always send to review. "
                "Fungi are never auto-approved (single image source available)."
            ),
            "group": "Identification",
            "min": 0.0,
            "max": 1.0,
        },
        # ── Pipelines ─────────────────────────────────────────────────────
        {
            "key": "api_source_syncthing",
            "default": "both",
            "type": "str",
            "label": "API source — Syncthing pipeline",
            "description": "Which species-ID API(s) to use for Syncthing photos. 'both' enables dual-source agreement auto-approval.",
            "group": "Pipelines",
            "choices": ["plantnet", "inaturalist", "both"],
        },
        {
            "key": "api_source_file_upload",
            "default": "both",
            "type": "str",
            "label": "API source — File Upload pipeline",
            "description": "Which species-ID API(s) to use for browser-uploaded photos.",
            "group": "Pipelines",
            "choices": ["plantnet", "inaturalist", "both"],
        },
        # ── Scanning ──────────────────────────────────────────────────────
        {
            "key": "photo_library_path",
            "default": str(cfg.photo_library_path),
            "type": "str",
            "label": "Scan folder path",
            "description": "Absolute path to the folder Syncthing watches for new photos.",
            "group": "Scanning",
        },
        # ── AI / Anthropic ────────────────────────────────────────────────
        {
            "key": "enrichment_backend",
            "default": "anthropic",
            "type": "str",
            "label": "Enrichment backend",
            "description": (
                "AI backend used to generate taste notes, medicinal notes, and recipes. "
                "'ollama' uses local Mistral 7B (free, private, requires Ollama running). "
                "'anthropic' uses Claude via the Anthropic API (billed)."
            ),
            "group": "AI",
            "choices": ["anthropic", "ollama", "hybrid"],
        },
        {
            "key": "deepseek_api_key",
            "default": "",
            "type": "str",
            "label": "DeepSeek API key",
            "description": "API key for DeepSeek (hybrid backend — used for recipe generation only).",
            "group": "AI",
            "hidden": True,
        },
        {
            "key": "deepseek_model",
            "default": "deepseek-chat",
            "type": "str",
            "label": "DeepSeek model",
            "description": "DeepSeek model for recipe generation in hybrid mode.",
            "group": "AI",
            "choices": ["deepseek-chat", "deepseek-reasoner"],
        },
        {
            "key": "anthropic_model",
            "default": cfg.anthropic_model,
            "type": "str",
            "label": "Anthropic model",
            "description": "Claude model used for AI-drafted species fields (Anthropic backend only).",
            "group": "AI",
            "choices": [
                "claude-haiku-4-5-20251001",
                "claude-sonnet-4-6",
                "claude-opus-4-7",
            ],
        },
        {
            "key": "ollama_model",
            "default": "mistral",
            "type": "str",
            "label": "Ollama model",
            "description": "Ollama model name for local draft generation. Must be pulled via 'ollama pull <name>'.",
            "group": "AI",
        },
        {
            "key": "prompt_taste",
            "default": "",
            "type": "text",
            "hidden": True,
            "label": "Taste notes prompt",
            "description": "System prompt for taste notes generation. Leave blank to use the built-in default.",
            "group": "AI Prompts",
        },
        {
            "key": "prompt_medicinal",
            "default": "",
            "type": "text",
            "hidden": True,
            "label": "Medicinal notes prompt",
            "description": "System prompt for medicinal notes generation. Leave blank to use the built-in default.",
            "group": "AI Prompts",
        },
        {
            "key": "prompt_recipe",
            "default": "",
            "type": "text",
            "hidden": True,
            "label": "Recipe prompt",
            "description": "System prompt for recipe generation. Leave blank to use the built-in default.",
            "group": "AI Prompts",
        },
        # ── Enrichment ────────────────────────────────────────────────────
        {
            "key": "pfaf_delay_s",
            "default": PFAF_DELAY_S,
            "type": "float",
            "label": "PFAF request delay (seconds)",
            "description": (
                "Pause between consecutive PFAF page fetches. "
                "PFAF is a small charity — please be polite."
            ),
            "group": "Enrichment",
            "min": 0.5,
            "max": 10.0,
        },
        {
            "key": "wikidata_delay_s",
            "default": WIKIDATA_DELAY_S,
            "type": "float",
            "label": "Wikidata request delay (seconds)",
            "description": (
                "Pause between Wikidata SPARQL requests. "
                "Wikidata enforces strict rate limits — keep ≥ 1.0."
            ),
            "group": "Enrichment",
            "min": 1.0,
            "max": 10.0,
        },
        # ── Processing ────────────────────────────────────────────────────
        {
            "key": "thumbnail_size",
            "default": cfg.thumbnail_size,
            "type": "int",
            "label": "Thumbnail size (px)",
            "description": "Max width/height for generated thumbnails.",
            "group": "Processing",
            "min": 100,
            "max": 1000,
        },
        {
            "key": "batch_size",
            "default": cfg.batch_size,
            "type": "int",
            "label": "Identification batch size",
            "description": (
                "Max observations processed per identification run. "
                "Lower values reduce API burst risk."
            ),
            "group": "Processing",
            "min": 1,
            "max": 500,
        },
        # ── Cloud Sync ────────────────────────────────────────────────────
        {
            "key": "obsidian_vault_path",
            "default": "/Users/melvinjarman/Documents/Obsidian",
            "type": "str",
            "label": "Obsidian vault path",
            "description": (
                "Absolute path to your Obsidian vault. "
                "When End Session runs, writes Current State.md (overwrite) and appends to Decisions Log.md. "
                "Leave blank to skip Obsidian sync."
            ),
            "group": "Cloud Sync",
            "hidden": True,
        },
        # ── Pre-filter ────────────────────────────────────────────────────
        {
            "key": "prefilter_green_threshold",
            "default": PLANT_GREEN_THRESHOLD,
            "type": "float",
            "label": "Green threshold (no GPS)",
            "description": (
                "Minimum green-pixel fraction needed to accept a photo without GPS. "
                "Raise to be stricter; lower to pass more borderline shots."
            ),
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "key": "prefilter_green_threshold_gps",
            "default": PLANT_GREEN_THRESHOLD_GPS,
            "type": "float",
            "label": "Green threshold (with GPS)",
            "description": (
                "Minimum green-pixel fraction for photos that have GPS co-ordinates. "
                "Can be lower than the no-GPS threshold."
            ),
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "key": "prefilter_skin_threshold",
            "default": SKIN_REJECT_THRESHOLD,
            "type": "float",
            "label": "Skin-tone reject threshold",
            "description": "Photos above this fraction of skin-like pixels (with little green) are rejected.",
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "key": "prefilter_warm_threshold",
            "default": WARM_REJECT_THRESHOLD,
            "type": "float",
            "label": "Warm-colour reject threshold",
            "description": "Photos above this fraction of warm/food colours (with little green) are rejected.",
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "key": "prefilter_blue_threshold",
            "default": BLUE_REJECT_THRESHOLD,
            "type": "float",
            "label": "Sky-blue reject threshold",
            "description": "Photos above this fraction of sky-blue pixels (with little green) are rejected.",
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "key": "prefilter_pipeline2_green_threshold",
            "default": 0.35,
            "type": "float",
            "label": "Pipeline 2 (File Upload) green threshold",
            "description": (
                "Minimum green-pixel fraction to accept a browser/phone upload as a plant photo. "
                "Higher values require more green in the image before accepting as a plant photo. "
                "Set higher than the Syncthing threshold (0.22) because uploads are often "
                "indoor or close-up shots. Default 0.35."
            ),
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "key": "prefilter_indoor_dark_threshold",
            "default": INDOOR_DARK_THRESHOLD,
            "type": "float",
            "label": "Indoor dark threshold",
            "description": (
                "Near-black pixel fraction above which a photo is classified as a dark "
                "indoor scene (windowsill pots, nighttime rooms). "
                "Lower = stricter rejection. Default 0.10."
            ),
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        {
            "key": "prefilter_indoor_bright_threshold",
            "default": INDOOR_BRIGHT_THRESHOLD,
            "type": "float",
            "label": "Indoor bright threshold",
            "description": (
                "Blown-out-bright pixel fraction above which a photo is classified as "
                "an artificially lit interior (greenhouse, grow lights). "
                "Lower = stricter rejection. Default 0.10."
            ),
            "group": "Pre-filter",
            "min": 0.0,
            "max": 1.0,
        },
        # ── Sharing ───────────────────────────────────────────────────────
        {
            "key": "guest_mode_enabled",
            "default": False,
            "type": "bool",
            "label": "Workshop guest mode",
            "description": (
                "When OFF (default): ngrok connections resolve as curator — "
                "your own phone records over the tunnel with no restrictions. "
                "Turn ON only during workshops so participants get read-only guest access."
            ),
            "group": "Sharing",
            # Managed by the dedicated toggle in the Share with Guests card;
            # hidden from the generic settings renderer to avoid duplication.
            "hidden": True,
        },
        {
            "key": "guest_show_sourced_fields",
            "default": False,
            "type": "bool",
            "label": "Show unattributed reference fields to guests",
            "description": (
                "Off (default): guests never see enrichment fields that were written "
                "directly by the scraping pipeline with no audit trail (e.g. edible parts, "
                "ID notes, seasonal peak). On: those fields are also shown to guests, "
                "labelled 'Source: reference data'. Never affects unapproved AI drafts or "
                "the medicinal-notes placeholder — those stay hidden from guests regardless."
            ),
            "group": "Sharing",
        },
    ]


# Module-level registry cache (populated on first access)
_REGISTRY: Optional[List[Dict]] = None

def _get_registry() -> List[Dict]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_registry() -> List[Dict]:
    """Return the full settings registry as a list of dicts."""
    return _get_registry()


def get_default(key: str) -> Any:
    for entry in _get_registry():
        if entry["key"] == key:
            return entry["default"]
    raise KeyError(f"Unknown setting key: {key!r}")


def _cast(value: str, type_: str) -> Any:
    """Cast a stored string value to the correct Python type."""
    if type_ == "float":
        return float(value)
    if type_ == "int":
        return int(value)
    if type_ == "bool":
        return value.lower() in ("1", "true", "yes")
    return value  # str


# ---------------------------------------------------------------------------
# In-process cache — populated at startup, updated on every save
# ---------------------------------------------------------------------------

_cache: Dict[str, Any] = {}


def get_setting(key: str) -> Any:
    """
    Return the effective value for a setting key.
    Returns the DB override if set, otherwise the registry default.
    Always returns a typed Python value.
    """
    if key in _cache:
        return _cache[key]
    # Fall back to registry default (also caches it)
    try:
        default = get_default(key)
        _cache[key] = default
        return default
    except KeyError:
        raise


async def load_settings_from_db(session: AsyncSession) -> None:
    """
    Load all DB overrides into the in-process cache.
    Call once at application startup inside the lifespan handler.
    """
    global _cache
    # Seed from registry defaults first
    for entry in _get_registry():
        _cache[entry["key"]] = entry["default"]

    # Apply DB overrides
    rows = (await session.execute(select(AppSetting))).scalars().all()
    for row in rows:
        # Find the type for this key
        for entry in _get_registry():
            if entry["key"] == row.key:
                try:
                    _cache[row.key] = _cast(row.value, entry["type"])
                except (ValueError, TypeError):
                    log.warning(
                        "settings: could not cast DB value %r for key %r (%s) — using default",
                        row.value, row.key, entry["type"],
                    )
                break
    log.info("settings: loaded %d override(s) from DB", len(rows))


async def save_setting(key: str, value: Any, session: AsyncSession) -> None:
    """
    Persist a setting override and refresh the in-process cache immediately.
    Raises KeyError for unknown keys, ValueError for out-of-range/invalid values.
    """
    # Validate key exists
    entry = next((e for e in _get_registry() if e["key"] == key), None)
    if entry is None:
        raise KeyError(f"Unknown setting key: {key!r}")

    # Validate choices
    if "choices" in entry and value not in entry["choices"]:
        raise ValueError(f"Invalid value {value!r} for {key!r}. Allowed: {entry['choices']}")

    # Validate numeric range
    cast_value = _cast(str(value), entry["type"])
    if "min" in entry and cast_value < entry["min"]:
        raise ValueError(f"{key}: value {cast_value} is below minimum {entry['min']}")
    if "max" in entry and cast_value > entry["max"]:
        raise ValueError(f"{key}: value {cast_value} exceeds maximum {entry['max']}")

    # Upsert into DB
    existing = await session.get(AppSetting, key)
    if existing:
        existing.value = str(cast_value)
        existing.updated_at = datetime.utcnow()
        existing.updated_by = "human"
    else:
        session.add(AppSetting(key=key, value=str(cast_value), updated_by="human"))
    await session.commit()

    # Refresh cache immediately (no restart needed)
    _cache[key] = cast_value
    log.info("settings: saved %r = %r", key, cast_value)


async def reset_setting(key: str, session: AsyncSession) -> Any:
    """
    Delete any DB override for `key`, reverting to the registry default.
    Returns the default value.
    """
    entry = next((e for e in _get_registry() if e["key"] == key), None)
    if entry is None:
        raise KeyError(f"Unknown setting key: {key!r}")

    existing = await session.get(AppSetting, key)
    if existing:
        await session.delete(existing)
        await session.commit()

    default = entry["default"]
    _cache[key] = default
    log.info("settings: reset %r to default %r", key, default)
    return default
