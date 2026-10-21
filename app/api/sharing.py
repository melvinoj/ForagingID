"""
Sharing API — ngrok tunnel management, guest-mode detection, walk export.

POST /api/sharing/start        — start ngrok tunnel (or detect existing)
POST /api/sharing/stop         — stop tunnel
GET  /api/sharing/status       — current tunnel URL + active flag
GET  /api/me                   — { is_guest, ngrok_active } for current request
POST /api/sharing/export-walk  — returns self-contained walk summary HTML

Guest detection rule:
  A request is a guest session when its Host header contains ".ngrok"
  (covers *.ngrok.io / *.ngrok.app / *.ngrok-free.app) or matches the
  stored tunnel URL's netloc exactly.

Local access (localhost / 127.0.0.1) is always treated as owner.
"""

import asyncio
import html
import ipaddress
import logging
import re
import socket
from datetime import datetime, date
from typing import Optional, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

log = logging.getLogger(__name__)

router = APIRouter(tags=["sharing"])

NGROK_BIN = "/opt/homebrew/bin/ngrok"
NGROK_LOCAL_API = "http://127.0.0.1:4040/api/tunnels"

# ---------------------------------------------------------------------------
# In-process tunnel state — single-worker local app; module-level is safe.
# ---------------------------------------------------------------------------
_ngrok_proc: Optional[asyncio.subprocess.Process] = None
_tunnel_url: Optional[str] = None
_started_at: Optional[datetime] = None


async def stop_ngrok_subprocess() -> None:
    """
    Stop the ngrok process THIS server started (Settings → Start sharing), if
    any: terminate, wait up to 3 s, then kill. Never touches an ngrok started
    outside the app — stop_sharing() adds the `pkill -x ngrok` for that.

    Called by stop_sharing() and by the app lifespan on every graceful shutdown
    (main.py). Before 15 Oct 2026 shutdown did not stop it: a stop that does
    not signal the whole process group — `kill -INT <pid>`, or a --reload
    worker restart — left the tunnel up while the app reported "not sharing".
    """
    global _ngrok_proc
    if _ngrok_proc:
        try:
            _ngrok_proc.terminate()
            await asyncio.wait_for(_ngrok_proc.wait(), timeout=3.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                _ngrok_proc.kill()
            except Exception:
                pass
        _ngrok_proc = None


# ---------------------------------------------------------------------------
# Guest detection — imported by main.py middleware
# ---------------------------------------------------------------------------
def _host_only(request: Request) -> str:
    """Lowercased Host header with any port stripped (handles IPv6 ``[::1]:8001``)."""
    host = (request.headers.get("host", "") or "").split(",")[0].strip().lower()
    if host.startswith("["):
        end = host.find("]")
        return host[1:end] if end != -1 else host
    if ":" in host:
        return host.rsplit(":", 1)[0]
    return host


def _guest_mode_enabled() -> bool:
    """Read guest_mode_enabled from the settings cache (zero-overhead dict lookup)."""
    from app.services.settings_service import get_setting
    return bool(get_setting("guest_mode_enabled"))


def classify_host(request: Request) -> str:
    """
    Three-tier host classification for access control:

      'curator' — loopback / private-LAN IP / ``localhost`` / ``*.local`` (the owner's
                  own devices — full access, always).
      'guest'   — the ngrok tunnel host WHEN guest_mode_enabled=True.
                  When guest_mode_enabled=False (default), the ngrok host also
                  resolves as 'curator' so the owner's phone is unrestricted.
      'denied'  — anything else (an unrecognised public host) → blocked outright.
                  The 'denied' tier is NEVER affected by guest_mode_enabled — a host
                  that is neither private-LAN nor the known tunnel is always rejected.

    guest_mode_enabled (default OFF) is the master switch: flip it ON only when
    running a workshop so participants get read-only guest access via the tunnel.
    """
    host = _host_only(request)
    if not host:
        return "denied"
    # ngrok tunnel: tier depends on the guest-mode master switch.
    # OFF (default) → curator so the owner's phone records over the tunnel freely.
    # ON → guest for workshop participants.
    if ".ngrok" in host:
        return "guest" if _guest_mode_enabled() else "curator"
    if _tunnel_url:
        try:
            from urllib.parse import urlparse
            ngrok_host = urlparse(_tunnel_url).netloc.lower().rsplit(":", 1)[0]
            if host == ngrok_host:
                return "guest" if _guest_mode_enabled() else "curator"
        except Exception:
            pass
    # Owner's own devices: localhost, mDNS *.local (LAN-only), loopback / private IPs.
    if host == "localhost" or host.endswith(".local"):
        return "curator"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_private:
            return "curator"
    except ValueError:
        pass
    return "denied"


def is_guest_request(request: Request) -> bool:
    """Return True when the request originates from the ngrok tunnel (guest tier)."""
    return classify_host(request) == "guest"


# ---------------------------------------------------------------------------
# Helper: read the public HTTPS URL from the ngrok local API
# ---------------------------------------------------------------------------
async def _read_ngrok_url() -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(NGROK_LOCAL_API)
            if r.status_code == 200:
                for t in r.json().get("tunnels", []):
                    url = t.get("public_url", "")
                    if url.startswith("https://"):
                        return url
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# POST /api/sharing/start
# ---------------------------------------------------------------------------
@router.post("/api/sharing/start")
async def start_sharing(request: Request):
    global _ngrok_proc, _tunnel_url, _started_at

    # Forward the tunnel to the port the curator actually reached the app on, so the
    # share link / QR never points at a stale port (the old hardcoded 8000 broke when
    # the server runs on 8001).
    port = request.url.port
    if not port:
        host = request.headers.get("host", "")
        if ":" in host:
            try:
                port = int(host.rsplit(":", 1)[1])
            except ValueError:
                port = None
    port = str(port or 8000)

    # Step 1: Kill our tracked process (if any).
    if _ngrok_proc:
        try:
            _ngrok_proc.terminate()
            await asyncio.wait_for(_ngrok_proc.wait(), timeout=3.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                _ngrok_proc.kill()
            except Exception:
                pass
        _ngrok_proc = None

    # Step 2: Kill any externally-started ngrok (e.g. manually launched tunnel
    # that left a stale URL in the local API).
    try:
        kill_proc = await asyncio.create_subprocess_exec(
            "pkill", "-x", "ngrok",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(kill_proc.wait(), timeout=3.0)
    except Exception:
        pass  # pkill not found or no ngrok to kill — fine

    _tunnel_url = None
    _started_at = None

    # Step 3: Wait for the local API to go dark (up to 3 s) so the old
    # tunnel registration is fully cleared before we start a new one.
    for _ in range(6):
        await asyncio.sleep(0.5)
        if not await _read_ngrok_url():
            break

    # Step 4: Launch a fresh ngrok subprocess.
    try:
        _ngrok_proc = await asyncio.create_subprocess_exec(
            NGROK_BIN, "http", port,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=f"ngrok not found at {NGROK_BIN}",
        )

    # Step 5: Poll ngrok local API until the HTTPS tunnel appears (up to 10 s).
    for _ in range(20):
        await asyncio.sleep(0.5)
        url = await _read_ngrok_url()
        if url:
            _tunnel_url = url
            _started_at = datetime.utcnow()
            log.info("ngrok tunnel started: %s", _tunnel_url)
            return {"url": _tunnel_url, "status": "started"}

    # Timeout — clean up.
    if _ngrok_proc:
        _ngrok_proc.terminate()
        _ngrok_proc = None
    raise HTTPException(
        status_code=500,
        detail="ngrok tunnel did not start within 10 s. Check your auth token.",
    )


# ---------------------------------------------------------------------------
# POST /api/sharing/stop
# ---------------------------------------------------------------------------
@router.post("/api/sharing/stop")
async def stop_sharing():
    global _ngrok_proc, _tunnel_url, _started_at
    await stop_ngrok_subprocess()
    # Also kill any externally-started ngrok so the local API goes dark
    # and GET /api/sharing/status returns active=false immediately.
    try:
        kill_proc = await asyncio.create_subprocess_exec(
            "pkill", "-x", "ngrok",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(kill_proc.wait(), timeout=3.0)
    except Exception:
        pass
    _tunnel_url = None
    _started_at = None
    return {"status": "stopped"}


# ---------------------------------------------------------------------------
# GET /api/sharing/status
# ---------------------------------------------------------------------------
@router.get("/api/sharing/status")
async def sharing_status():
    global _ngrok_proc, _tunnel_url, _started_at

    # Process died without us noticing?
    if _ngrok_proc is not None and _ngrok_proc.returncode is not None:
        _ngrok_proc = None
        _tunnel_url = None
        _started_at = None

    # Also detect externally-started ngrok instances.
    if not _tunnel_url:
        detected = await _read_ngrok_url()
        if detected:
            _tunnel_url = detected
            _started_at = _started_at or datetime.utcnow()

    return {
        "active": _tunnel_url is not None,
        "url": _tunnel_url,
        "started_at": _started_at.isoformat() if _started_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/me
# ---------------------------------------------------------------------------
@router.get("/api/me")
async def me(request: Request):
    guest = is_guest_request(request)
    resp = {
        "is_guest": guest,
        "ngrok_active": _tunnel_url is not None,
    }
    # Owner-only: last iNaturalist call status so the UI can warn when an expired
    # token is silently routing every scan to needs_review (not exposed to guests).
    if not guest:
        from app.integrations.inaturalist import last_inat_status
        resp["inat"] = last_inat_status()
    return resp


@router.get("/api/sharing/lan-url")
async def lan_url():
    """Return the LAN IP and URL for local network sharing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return {"url": f"http://{ip}:8000", "ip": ip}
    except Exception:
        return {"url": None, "ip": None}


# ---------------------------------------------------------------------------
# Walk export models
# ---------------------------------------------------------------------------
class WalkSpecies(BaseModel):
    species_scientific: str
    species_common: Optional[str] = None
    all_common: Optional[List[str]] = None
    edibility: Optional[str] = None
    # Safety gate label — overwritten server-side by apply_walk_safety() from the
    # DB (B2-09); whatever the client sends here or in the culinary fields is
    # not trusted.
    toxicity_warning: Optional[str] = None
    safety_warning: Optional[str] = None       # approved caution warning (server-set)
    culinary_notes: Optional[str] = None
    recipe_title: Optional[str] = None
    recipe_body: Optional[str] = None
    recipe_season: Optional[str] = None
    is_medicinal_prep: Optional[bool] = None


class WalkStop(BaseModel):
    num: int
    label: Optional[str] = None               # saved-walk stop label ("7", "7a"); shown instead of num
    dist_from_prev: Optional[float] = None   # metres
    note_text: Optional[str] = None           # field-note stop (no species)
    species: List[WalkSpecies] = []           # species FIRST listed at this stop (full block)
    also_here: List["WalkRepeat"] = []        # species already listed at an earlier stop (compact line)


class WalkRepeat(BaseModel):
    species_scientific: str
    species_common: Optional[str] = None       # names rule: "Common (Latin)" on the compact line
    first_label: str                           # label of the stop where its full block is
    toxicity_warning: Optional[str] = None     # toxic guard label, kept on the compact line


WalkStop.model_rebuild()


class WalkExportRequest(BaseModel):
    stops: List[WalkStop]
    total_distance_m: Optional[float] = None
    season: Optional[str] = None
    title: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /api/sharing/export-walk
# ---------------------------------------------------------------------------
@router.post("/api/sharing/export-walk", response_class=HTMLResponse)
async def export_walk(body: WalkExportRequest, db: AsyncSession = Depends(get_db)):
    """Return a self-contained, printable HTML walk summary. No DB reads beyond
    the safety gate, no DB writes."""
    from app.services.safety_gate import safety_by_names
    names = [sp.species_scientific for st in body.stops for sp in st.species] + \
            [r.species_scientific for st in body.stops for r in st.also_here]
    apply_walk_safety(body, await safety_by_names(db, names))
    return HTMLResponse(content=_build_walk_html(body), status_code=200)


def apply_walk_safety(body: "WalkExportRequest", safety: dict) -> None:
    """B2-09: re-apply the safety gate server-side (app.models.species.
    safety_decision, looked up by name). Blocked species lose their culinary
    notes, recipe and edibility badge and get the label; caution species get
    "⚠ caution" and the approved warning. A name with no decision fails closed."""
    from app.models.species import safety_decision
    unknown = safety_decision(None, None)
    for st in body.stops:
        for sp in st.species:
            d = safety.get(sp.species_scientific) or unknown
            sp.toxicity_warning = d["label"] or None
            sp.safety_warning = d["warning"]
            # Verdict badge from the DB, never the client; a ☠ / ⚠ label replaces it.
            sp.edibility = None if (d["label"] and not d["culinary_allowed"]) else d.get("verdict")
            if not d["culinary_allowed"]:
                sp.culinary_notes = None
                sp.recipe_title = sp.recipe_body = sp.recipe_season = None
                sp.is_medicinal_prep = None
        for r in st.also_here:
            d = safety.get(r.species_scientific) or unknown
            r.toxicity_warning = d["label"] or None


# ---------------------------------------------------------------------------
# HTML builder helpers
# ---------------------------------------------------------------------------
_SEASON_ICON = {
    "spring": "🌱", "summer": "☀️", "autumn": "🍂",
    "winter": "❄️", "year-round": "🔄",
}
_EDIB_COLORS = {
    "edible":   ("#d1f5da", "#166534"),
    "medicinal": ("#e0e7ff", "#3730a3"),
    "toxic":    ("#fee2e2", "#991b1b"),
    "inedible": ("#fee2e2", "#991b1b"),
}


def _h(s: Optional[str]) -> str:
    return html.escape(str(s)) if s else ""


def _fmt_dist(m: Optional[float]) -> str:
    if not m:
        return ""
    return f"{round(m)}m" if m < 1000 else f"{m / 1000:.1f}km"


_MD_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _md_inline(text: str) -> str:
    """Escape, then **bold** / *italic* / _italic_ / `code`. Escaping first means
    recipe text can never inject HTML."""
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"__(.+?)__", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def _md_snippet(body: str, title: str, limit: int = 700) -> str:
    """Recipe Markdown → small safe HTML: headings, paragraphs, bullet/numbered
    lists, bold/italic. A leading heading that repeats the recipe title is
    dropped (the title is already shown). Whole blocks are kept up to ~limit
    characters, then '…'."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", (body or "").replace("\r", "")) if b.strip()]
    title_norm = re.sub(r"[#*_\s]+", " ", title or "").strip().lower()
    out, used = [], 0
    for i, b in enumerate(blocks):
        if re.fullmatch(r"[-*_]{3,}", b):
            continue                                            # horizontal rule
        m = re.match(r"^(#{1,6})\s+(.*)$", b.split("\n", 1)[0])
        if i <= 1 and not out and re.sub(r"[#*_\s]+", " ", b).strip().lower() == title_norm:
            continue                                            # "**Title**" / "# Title" alone
        if m and i == 0 and re.sub(r"[#*_\s]+", " ", m.group(2)).strip().lower() == title_norm:
            rest = b.split("\n", 1)[1].strip() if "\n" in b else ""
            if not rest:
                continue
            b, m = rest, re.match(r"^(#{1,6})\s+(.*)$", rest.split("\n", 1)[0])
        if used and used + len(b) > limit:
            out.append("<p style='margin:4px 0 0'>…</p>")
            break
        used += len(b)
        lines = b.split("\n")
        if m and len(lines) == 1:
            out.append(f"<div style='font-weight:600;color:#2d5016;margin:6px 0 2px'>{_md_inline(m.group(2))}</div>")
        elif all(_MD_LIST.match(l) for l in lines):
            tag = "ol" if re.match(r"^\s*\d", lines[0]) else "ul"
            items = "".join(f"<li>{_md_inline(_MD_LIST.sub('', l))}</li>" for l in lines)
            out.append(f"<{tag} style='margin:4px 0 4px 18px;padding:0'>{items}</{tag}>")
        else:
            if m:                                               # heading line + text below it
                out.append(f"<div style='font-weight:600;color:#2d5016;margin:6px 0 2px'>{_md_inline(m.group(2))}</div>")
                lines = lines[1:]
            out.append(f"<p style='margin:4px 0'>{_md_inline(' '.join(l.strip() for l in lines))}</p>")
    return "".join(out)


def _toxicity_warning_colors(label: str) -> tuple:
    """(background, text) for a toxicity warning badge — the ONE rule for the
    full species block and the "Also here" repeat line: red for ☠ (toxic /
    deadly), amber for the rest ("⚠ toxicity unknown"). Before 21 Oct 2026 the
    repeat line was always red (audit D2-01)."""
    return ("#dc2626", "#fff") if "☠" in (label or "") else ("#fef3c7", "#92400e")


def _walk_species_html(s: WalkSpecies, first: bool) -> str:
    """One species section inside a stop card. Content is gated server-side by
    apply_walk_safety() first; a toxicity_warning replaces the edibility badge."""
    bg, fg = _EDIB_COLORS.get((s.edibility or "").lower(), ("#f3f3f3", "#555"))
    edib_badge = (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'font-size:0.7rem;font-weight:600;background:{bg};color:{fg}">{_h(s.edibility)}</span>'
    ) if s.edibility else ""
    if s.toxicity_warning:
        t_bg, t_fg = _toxicity_warning_colors(s.toxicity_warning)
        edib_badge = (
            f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
            f'font-size:0.7rem;font-weight:700;background:{t_bg};color:{t_fg}">'
            f'{_h(s.toxicity_warning)}</span>'
        )

    common_main = s.species_common or (s.all_common[0] if s.all_common else None)
    extra_common = s.all_common[1:] if (s.all_common and len(s.all_common) > 1) else []

    culinary_html = ""
    if s.safety_warning:
        culinary_html += (
            f'<div style="font-size:0.77rem;color:#92400e;background:#fffbeb;border-left:3px solid #f59e0b;'
            f'padding:3px 8px;margin-top:4px">⚠ Caution: {_h(s.safety_warning)}</div>'
        )
    if s.culinary_notes:
        note = s.culinary_notes[:130]
        if len(s.culinary_notes) > 130:
            note += "…"
        culinary_html += (
            f'<div style="font-size:0.77rem;color:#666;margin-top:4px">{_h(note)}</div>'
        )

    recipe_html = ""
    if s.recipe_title or s.recipe_body:
        r_icon = _SEASON_ICON.get(s.recipe_season or "", "💡")
        r_label = ("Preparation" if s.is_medicinal_prep else None) or s.recipe_title or "Recipe"
        recipe_html = (
            f'<div style="background:#f8faf4;border-left:3px solid #7a9e50;'
            f'padding:8px 12px;margin-top:8px;border-radius:0 6px 6px 0">'
            f'<div style="font-size:0.78rem;font-weight:600;color:#2d5016;margin-bottom:4px">'
            f'{r_icon} {_h(r_label)}</div>'
            f'<div class="recipe-md" style="font-size:0.75rem;color:#555;line-height:1.55">'
            f'{_md_snippet(s.recipe_body or "", s.recipe_title or "")}</div></div>'
        )

    sep = "" if first else "border-top:1px dashed #e3ead7;margin-top:10px;padding-top:10px;"
    return (
        f'<div class="walk-sp" style="{sep}">'
        f'<div style="font-style:italic;font-size:0.92rem;font-weight:600;color:#1a2e0a">'
        f'{_h(s.species_scientific)}</div>'
        + (f'<div style="font-size:0.97rem;font-weight:600;color:#2d5016;margin-bottom:3px">'
           f'{_h(common_main)}</div>' if common_main else "")
        + (f'<div style="font-size:0.75rem;color:#999;margin-bottom:3px">'
           f'{_h(" · ".join(extra_common))}</div>' if extra_common else "")
        + f'<div style="margin:5px 0">{edib_badge}</div>'
        + culinary_html
        + recipe_html
        + "</div>"
    )


def _build_walk_html(body: WalkExportRequest) -> str:
    # Saved walks send their name; an unsaved route gets a dated default.
    title = body.title or f"Walk — {date.today().strftime('%d %b %Y')}"
    n_stops = len(body.stops)
    n_species = len({sp.species_scientific for s in body.stops for sp in s.species}
                    | {r.species_scientific for s in body.stops for r in s.also_here})
    season_icon = _SEASON_ICON.get(body.season or "", "")
    total_str = _fmt_dist(body.total_distance_m)

    stops_html = ""
    for s in body.stops:
        dist_html = (
            f'<span style="font-size:0.7rem;color:#bbb;margin-left:auto">'
            f'{_fmt_dist(s.dist_from_prev)}</span>'
        ) if s.dist_from_prev else ""

        species_html = ""
        for k, sp in enumerate(s.species):
            species_html += _walk_species_html(sp, first=(k == 0))
        if s.note_text is not None:
            species_html += (
                f'<div style="font-size:0.8rem;color:#92400e;font-weight:600">📝 Field note</div>'
                f'<div style="font-size:0.77rem;color:#555;margin-top:3px;white-space:pre-wrap">'
                f'{_h(s.note_text[:400])}</div>'
            )

        if s.also_here:
            parts = []
            for r in s.also_here:
                w_bg, w_fg = _toxicity_warning_colors(r.toxicity_warning)
                warn = (f' <span style="font-size:0.66rem;font-weight:700;padding:0 5px;border-radius:4px;'
                        f'background:{w_bg};color:{w_fg}">{_h(r.toxicity_warning)}</span>'
                        if r.toxicity_warning else "")
                name = (f'{_h(r.species_common)} (<em>{_h(r.species_scientific)}</em>)' if r.species_common
                        else f'<em>{_h(r.species_scientific)}</em>')             # names rule
                parts.append(f'{name}{warn} (see stop {_h(r.first_label)})')
            species_html += (
                f'<div style="font-size:0.75rem;color:#666;margin-top:{8 if s.species else 2}px">'
                f'Also here: {", ".join(parts)}</div>'
            )

        n_here = len(s.species) + len(s.also_here)
        stops_html += (
            f'<div style="background:white;border:1px solid #e0e8d0;border-radius:8px;'
            f'padding:14px 16px;margin-bottom:12px;page-break-inside:avoid">'
            f'<div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:6px">'
            f'<span style="min-width:22px;height:22px;border-radius:11px;padding:0 4px;box-sizing:border-box;'
            f'background:#2d5016;color:white;font-size:0.68rem;font-weight:700;'
            f'display:inline-flex;align-items:center;justify-content:center;flex-shrink:0">'
            f'{_h(s.label) if s.label else s.num}</span>'
            + (f'<span style="font-size:0.75rem;color:#556040;font-weight:600">{n_here} species here</span>'
               if n_here > 1 else "")
            + f'{dist_html}</div>'
            + species_html
            + "</div>"
        )

    season_stat = (
        f'<span class="stat">{season_icon} {_h(body.season.capitalize())}</span>'
        if body.season else ""
    )
    dist_stat = f'<span class="stat">~{total_str}</span>' if total_str else ""

    return (
        f"<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        f"  <meta charset='UTF-8'>\n"
        f"  <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n"
        f"  <title>{_h(title)}</title>\n"
        f"  <style>\n"
        f"    * {{box-sizing:border-box;margin:0;padding:0;}}\n"
        f"    body {{font-family:system-ui,-apple-system,sans-serif;"
        f"background:#f4f6f0;color:#222;padding:20px 16px 60px;"
        f"max-width:680px;margin:0 auto;}}\n"
        f"    @media print {{body{{background:white;padding:10mm;}} .no-print{{display:none!important;}}}}\n"
        f"    h1 {{font-size:1.25rem;font-weight:700;color:#2d5016;margin-bottom:4px;}}\n"
        f"    .meta {{font-size:0.8rem;color:#888;margin-bottom:20px;}}\n"
        f"    .stat {{display:inline-block;background:#e8f0dc;color:#2d5016;"
        f"border-radius:4px;padding:3px 8px;font-size:0.75rem;font-weight:600;margin-right:6px;}}\n"
        f"    .print-btn {{display:inline-block;margin-bottom:16px;padding:7px 18px;"
        f"background:#2d5016;color:white;border:none;border-radius:6px;"
        f"font-size:0.82rem;cursor:pointer;}}\n"
        f"    .footer {{margin-top:24px;font-size:0.72rem;color:#aaa;"
        f"border-top:1px solid #e0e8d0;padding-top:12px;text-align:center;}}\n"
        f"  </style>\n</head>\n<body>\n"
        f"  <h1>🥾 {_h(title)}</h1>\n"
        f"  <div class='meta'>"
        f"{season_stat}"
        f"<span class='stat'>{n_stops} stop{'s' if n_stops != 1 else ''}</span>"
        f"<span class='stat'>{n_species} species</span>"
        f"{dist_stat}</div>\n"
        f"  <button class='print-btn no-print' onclick='window.print()'>🖨 Print / Save as PDF</button>\n"
        f"  {stops_html}\n"
        f"  <div class='footer'>Generated by LandMemory · "
        f"{date.today().strftime('%d %b %Y')}</div>\n"
        f"</body>\n</html>"
    )
