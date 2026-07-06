"""
API Dashboard service — standardised status + key management for every external
API integration (iNaturalist, PlantNet, Mushroom Observer, PFAF, OpenRouteService,
DeepSeek, Anthropic).

Provides:
  - API_REGISTRY: metadata + step-by-step "how to get a token" instructions
  - test_all(): concurrent live status check for every API (green / amber / red)
  - decode_jwt_expiry(): iNaturalist JWT expiry detection (cause #1)
  - set_api_key(): safe upsert into .env (or DB for DeepSeek) + live config update

Status semantics:
  green   — configured and a live probe succeeded
  amber   — reachable/working but needs attention (e.g. iNat token < 4h to expiry,
            or a key-less service we can only reach, or a probe timed out)
  red     — missing/invalid/expired key, or a definitive auth failure
  na      — no token required (informational reachability only)
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

log = logging.getLogger("foragingid.api_dashboard")

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
_PROBE_TIMEOUT = 6.0
INAT_EXPIRY_WARN_SECONDS = 4 * 3600   # warn when < 4h remain (cause #1)


# ── Registry ────────────────────────────────────────────────────────────────
# env_key:  the .env variable name (None for key-less or DB-stored services)
# db_key:   for services whose secret lives in the DB settings table (Drive)
# how_to:   ordered step strings; may contain URLs and commands to paste
API_REGISTRY = [
    {
        "id": "inaturalist",
        "name": "iNaturalist",
        "env_key": "INATURALIST_API_TOKEN",
        "needs_key": True,
        "token_url": "https://www.inaturalist.org/users/api_token",
        "how_to": [
            "Open https://www.inaturalist.org/users/api_token (log in to iNaturalist first).",
            "Copy the entire token string shown (a long JWT, starts with 'eyJ').",
            "Paste it in the box above and click Save.",
            "Note: iNaturalist tokens expire ~24h after issue. When the status turns "
            "amber or red, return to that URL and paste a fresh token.",
        ],
    },
    {
        "id": "plantnet",
        "name": "PlantNet",
        "env_key": "PLANTNET_API_KEY",
        "needs_key": True,
        "token_url": "https://my.plantnet.org/account/settings",
        "how_to": [
            "Create a free account at https://my.plantnet.org/",
            "Go to https://my.plantnet.org/account/settings and find your API key.",
            "Copy the key and paste it above, then click Save.",
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "needs_key": True,
        "token_url": "https://console.anthropic.com/settings/keys",
        "how_to": [
            "Open https://console.anthropic.com/settings/keys (log in).",
            "Click 'Create Key', name it, and copy the value (starts with 'sk-ant-').",
            "Paste it above and click Save. Used for AI-drafted species fields.",
        ],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek (Recipes)",
        "env_key": None,
        "db_key": "deepseek_api_key",
        "needs_key": True,
        "token_url": "https://platform.deepseek.com/api_keys",
        "how_to": [
            "Sign up at https://platform.deepseek.com/",
            "Go to API Keys and create a new key.",
            "Top up a small amount ($5 covers hundreds of recipe generations).",
            "Paste the key above and click Save.",
            "Used for recipe generation in hybrid backend mode.",
        ],
    },
    {
        "id": "openai",
        "name": "OpenAI (Whisper)",
        "env_key": "OPENAI_API_KEY",
        "needs_key": True,
        "token_url": "https://platform.openai.com/api-keys",
        "how_to": [
            "Open https://platform.openai.com/api-keys (log in).",
            "Click 'Create new secret key', copy the value (starts with 'sk-').",
            "Paste it above and click Save. Used for encounter audio transcription "
            "(Whisper, ~£0.006/min).",
        ],
    },
    {
        "id": "ors",
        "name": "OpenRouteService",
        "env_key": "ORS_API_KEY",
        "needs_key": True,
        "token_url": "https://openrouteservice.org/dev/#/signup",
        "how_to": [
            "Sign up at https://openrouteservice.org/dev/#/signup",
            "In the dashboard, request a token on the free 'standard' plan.",
            "Copy the token and paste it above, then click Save. Used for Walk routes.",
        ],
    },
    {
        "id": "thunderforest",
        "name": "Thunderforest (Map tiles)",
        "env_key": "THUNDERFOREST_API_KEY",
        "needs_key": True,
        "token_url": "https://www.thunderforest.com/my/apikeys",
        "how_to": [
            "Create a free account at https://www.thunderforest.com/",
            "In your dashboard, go to https://www.thunderforest.com/my/apikeys",
            "Create a new API key (free tier includes Outdoors tiles).",
            "Copy the key and paste it above, then click Save.",
            "The Outdoors layer will appear in the map layer switcher automatically.",
        ],
    },
    {
        "id": "mushroom_observer",
        "name": "Mushroom Observer",
        "env_key": None,
        "needs_key": False,
        "token_url": "https://mushroomobserver.org/",
        "how_to": [
            "No token required — Mushroom Observer's public API is used for fungi links.",
            "This card shows reachability only.",
        ],
    },
    {
        "id": "pfaf",
        "name": "PFAF (Plants For A Future)",
        "env_key": None,
        "needs_key": False,
        "token_url": "https://pfaf.org/",
        "how_to": [
            "No token required — PFAF data is fetched directly from pfaf.org.",
            "This card shows reachability only.",
        ],
    },
]

_REGISTRY_BY_ID = {a["id"]: a for a in API_REGISTRY}


# ── JWT expiry (iNaturalist, cause #1) ───────────────────────────────────────
def decode_jwt_expiry(token: str) -> Optional[int]:
    """Return the JWT 'exp' (unix seconds) or None if not a decodable JWT."""
    if not token or token.count(".") != 2:
        return None
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)            # pad base64
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = data.get("exp")
        return int(exp) if exp else None
    except Exception:
        return None


def _inat_token_status(token: str) -> dict:
    """JWT-based status hint for iNaturalist before any network call."""
    info = {"jwt_expiry": None, "expires_in_seconds": None, "expiring_soon": False}
    if not token:
        return info
    exp = decode_jwt_expiry(token)
    if exp is None:
        return info
    remaining = exp - int(time.time())
    info["jwt_expiry"] = exp
    info["expires_in_seconds"] = remaining
    info["expiring_soon"] = 0 < remaining < INAT_EXPIRY_WARN_SECONDS
    return info


# ── Live probes ──────────────────────────────────────────────────────────────
# Each probe returns {"state": <STATE>, "error": str|None, ...extra}.
# STATE vocabulary: live | expired | invalid | unreachable | not_configured
STATES = {"live", "expired", "invalid", "unreachable", "not_configured"}

# Map each state to a dashboard dot colour.
STATE_COLOR = {
    "live": "green",
    "expired": "red",
    "invalid": "red",
    "unreachable": "amber",
    "not_configured": "na",
}
# States that count as "healthy" in the summary banner.
HEALTHY_STATES = {"live"}


async def _probe_inaturalist(client: httpx.AsyncClient) -> dict:
    token = settings.inaturalist_api_token
    extra = _inat_token_status(token)
    if not token:
        return {"state": "not_configured", "error": "No token configured", **extra}
    exp = extra["expires_in_seconds"]
    if exp is not None and exp <= 0:
        return {"state": "expired", "error": "Token expired — refresh required", **extra}
    # Live authenticated call in addition to the JWT decode.
    r = await client.get(
        "https://api.inaturalist.org/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code == 200:
        err = "Token valid but expires within 4h — refresh soon" if extra["expiring_soon"] else None
        return {"state": "live", "error": err, **extra}
    if r.status_code == 401:
        # JWT decoded fine but server rejects it → treat as expired/invalid.
        return {"state": "expired" if exp is not None else "invalid",
                "error": "401 Unauthorized — token expired or invalid", **extra}
    return {"state": "unreachable", "error": f"Unexpected HTTP {r.status_code}", **extra}


async def _probe_plantnet(client: httpx.AsyncClient) -> dict:
    key = settings.plantnet_api_key
    if not key:
        return {"state": "not_configured", "error": "No API key configured"}
    # No image → a valid key yields 400 (bad request); an invalid key yields 401/403.
    r = await client.get(f"https://my-api.plantnet.org/v2/identify/all?api-key={key}")
    if r.status_code in (400, 200):
        return {"state": "live", "error": None}
    if r.status_code in (401, 403):
        return {"state": "invalid", "error": f"{r.status_code} — API key rejected"}
    return {"state": "unreachable", "error": f"Unexpected HTTP {r.status_code}"}


async def _probe_anthropic(client: httpx.AsyncClient) -> dict:
    key = settings.anthropic_api_key
    if not key:
        return {"state": "not_configured", "error": "No API key configured"}
    r = await client.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    if r.status_code == 200:
        return {"state": "live", "error": None}
    if r.status_code in (401, 403):
        return {"state": "invalid", "error": f"{r.status_code} — API key rejected"}
    return {"state": "unreachable", "error": f"Unexpected HTTP {r.status_code}"}


async def _probe_openai(client: httpx.AsyncClient) -> dict:
    key = settings.openai_api_key
    if not key:
        return {"state": "not_configured", "error": "No API key configured"}
    r = await client.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    if r.status_code == 200:
        return {"state": "live", "error": None}
    if r.status_code in (401, 403):
        return {"state": "invalid", "error": f"{r.status_code} — API key rejected"}
    return {"state": "unreachable", "error": f"Unexpected HTTP {r.status_code}"}


async def _probe_ors(client: httpx.AsyncClient) -> dict:
    key = settings.ors_api_key
    if not key:
        return {"state": "not_configured", "error": "No API key configured"}
    # No coords → valid key yields a 4xx params error; bad key yields 403.
    r = await client.get(
        "https://api.openrouteservice.org/v2/directions/foot-walking",
        headers={"Authorization": key},
    )
    if r.status_code in (401, 403):
        return {"state": "invalid", "error": f"{r.status_code} — API key rejected"}
    return {"state": "live", "error": None}


async def _probe_thunderforest(client: httpx.AsyncClient) -> dict:
    key = settings.thunderforest_api_key
    if not key:
        return {"state": "not_configured", "error": "No API key configured"}
    # Fetch a single tile; valid key returns 200, invalid key returns 401/403.
    r = await client.get(
        f"https://tile.thunderforest.com/outdoors/10/511/340.png?apikey={key}"
    )
    if r.status_code == 200:
        return {"state": "live", "error": None}
    if r.status_code in (401, 403):
        return {"state": "invalid", "error": f"{r.status_code} — API key rejected"}
    return {"state": "unreachable", "error": f"Unexpected HTTP {r.status_code}"}


async def _probe_mushroom_observer(client: httpx.AsyncClient) -> dict:
    # Key-less public API — reachability only.
    r = await client.get("https://mushroomobserver.org/api2/observations",
                         params={"format": "json", "detail": "none", "number": 1})
    if r.status_code < 500:
        return {"state": "live", "error": None}
    return {"state": "unreachable", "error": f"HTTP {r.status_code}"}


async def _probe_pfaf(client: httpx.AsyncClient) -> dict:
    # Key-less scraped site — reachability only.
    r = await client.get("https://pfaf.org/user/Default.aspx")
    if r.status_code < 500:
        return {"state": "live", "error": None}
    return {"state": "unreachable", "error": f"HTTP {r.status_code}"}


async def _probe_itis(client: httpx.AsyncClient) -> dict:
    # Key-less public JSON API — probe with a minimal name search.
    r = await client.get(
        "https://www.itis.gov/ITISWebService/jsonservice/searchByScientificName",
        params={"srchKey": "Taraxacum officinale"},
    )
    if r.status_code == 200:
        try:
            data = r.json()
            if "scientificNames" in data:
                return {"state": "live", "error": None}
        except Exception:
            pass
    return {"state": "unreachable", "error": f"HTTP {r.status_code}"}


async def _probe_deepseek(client: httpx.AsyncClient) -> dict:
    from app.services.settings_service import get_setting
    key = (get_setting("deepseek_api_key") or "").strip()
    if not key:
        return {"state": "not_configured", "error": "No API key configured"}
    r = await client.get(
        "https://api.deepseek.com/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    if r.status_code == 200:
        return {"state": "live", "error": None}
    if r.status_code in (401, 403):
        return {"state": "invalid", "error": f"{r.status_code} — API key rejected"}
    return {"state": "unreachable", "error": f"Unexpected HTTP {r.status_code}"}


_PROBES = {
    "inaturalist": _probe_inaturalist,
    "deepseek": _probe_deepseek,
    "plantnet": _probe_plantnet,
    "anthropic": _probe_anthropic,
    "openai": _probe_openai,
    "ors": _probe_ors,
    "thunderforest": _probe_thunderforest,
    "mushroom_observer": _probe_mushroom_observer,
    "pfaf": _probe_pfaf,
    "itis": _probe_itis,
}


def _has_key(api: dict) -> bool:
    if api.get("env_key"):
        return bool(getattr(settings, api["env_key"].lower(), "") or "")
    if api.get("db_key"):
        from app.services.settings_service import get_setting
        return bool((get_setting(api["db_key"]) or "").strip())
    return False


def get_meta() -> list[dict]:
    """Registry metadata only — no network. Lets the UI render cards instantly."""
    return [{
        "id": a["id"],
        "name": a["name"],
        "needs_key": a["needs_key"],
        "has_key": _has_key(a),
        "token_url": a.get("token_url"),
        "how_to": a["how_to"],
    } for a in API_REGISTRY]


async def test_one(api_id: str) -> dict:
    """Run a single API's live probe with timing. Used for streaming + per-card re-test."""
    api = _REGISTRY_BY_ID.get(api_id)
    if not api:
        raise KeyError(f"Unknown API: {api_id}")
    probe = _PROBES.get(api_id)
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT, follow_redirects=True) as client:
            res = await probe(client) if probe else {"state": "live", "error": None}
    except httpx.TimeoutException:
        res = {"state": "unreachable", "error": f"Timed out after {_PROBE_TIMEOUT:.0f}s"}
    except Exception as e:
        res = {"state": "unreachable", "error": f"{type(e).__name__}: {e}"}
    response_ms = int((time.monotonic() - started) * 1000)
    state = res.get("state", "unreachable")
    return {
        "id": api["id"],
        "name": api["name"],
        "needs_key": api["needs_key"],
        "has_key": _has_key(api),
        "token_url": api.get("token_url"),
        "how_to": api["how_to"],
        "tested_at": int(time.time()),
        "response_ms": response_ms,
        "color": STATE_COLOR.get(state, "amber"),
        "healthy": state in HEALTHY_STATES,
        **res,
    }


async def test_all() -> list[dict]:
    """Run every API's live probe concurrently (used by the batch endpoint)."""
    import asyncio
    return await asyncio.gather(*[test_one(a["id"]) for a in API_REGISTRY])


# ── Key management ────────────────────────────────────────────────────────────
def _upsert_env(env_key: str, value: str) -> None:
    """Insert or replace a KEY=value line in .env (creates the file if absent)."""
    lines: list[str] = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
    prefix = f"{env_key}="
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[i] = f"{env_key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{env_key}={value}")
    _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def set_api_key(api_id: str, key: str, db) -> dict:
    """
    Save an API key/token to the correct destination and apply it live.
    .env-backed APIs update the .env file + the in-memory settings object.
    DeepSeek (DB-backed) routes through the existing settings table.
    """
    api = _REGISTRY_BY_ID.get(api_id)
    if not api:
        raise KeyError(f"Unknown API: {api_id}")
    if not api["needs_key"]:
        raise ValueError(f"{api['name']} does not use a key")
    key = (key or "").strip()
    if not key:
        raise ValueError("Empty key")

    if api.get("db_key"):
        # DB-stored secret (e.g. DeepSeek) — reuse the settings service.
        from app.services.settings_service import save_setting
        await save_setting(api["db_key"], key, db)
        return {"id": api_id, "saved": True, "destination": "db"}

    env_key = api["env_key"]
    _upsert_env(env_key, key)
    # Apply immediately so integrations pick it up without a restart.
    setattr(settings, env_key.lower(), key)
    log.info("API key updated for %s (%s)", api_id, env_key)
    return {"id": api_id, "saved": True, "destination": "env"}
