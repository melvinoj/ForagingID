import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

import jinja2
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.identity import Identity, get_identity
from app.database import get_db
from app.services.taxonomy import normalize_taxon_key
from app.models.species import culinary_warnings, safety_decision, sentence_case_name
from app.services.safety_gate import safety_by_names

log = logging.getLogger(__name__)

os.environ.setdefault("DYLD_LIBRARY_PATH", "/opt/homebrew/lib")

router = APIRouter(prefix="/api/lists", tags=["lists"])

_PROJECT_ROOT  = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _PROJECT_ROOT / "app" / "templates"

# Audit D1-01 (21 Oct 2026): every field reaches the template from the request
# body (species[].profile, cover, seasonal_returns), so the template escapes by
# default. The only |safe outputs are _season_str and _mdlite, both built here
# from escaped text — see the comments at their use in print_pdf.html.
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
)

# Audit D1-01: the only local files WeasyPrint may read. Resolved, so neither
# ../ nor a symlink can escape them. data: URIs are also allowed; everything
# else (http/https, file:// elsewhere, any other scheme) is refused and logged.
_FETCH_ROOTS = tuple(
    p.resolve() for p in (
        _PROJECT_ROOT / "frontend" / "static",
        _PROJECT_ROOT / "media",
        _PROJECT_ROOT / "photos",
        _PROJECT_ROOT / "uploads",
    )
)


def _safe_url_fetcher(url: str):
    """WeasyPrint url_fetcher: data: URIs and files under _FETCH_ROOTS only.
    Raising makes WeasyPrint skip that resource (logged) and render the rest."""
    from weasyprint import default_url_fetcher
    parsed = urlparse(url)
    if parsed.scheme == "data":
        return default_url_fetcher(url)
    if parsed.scheme == "file" and parsed.netloc in ("", "localhost"):
        try:
            path = Path(unquote(parsed.path)).resolve()
        except (OSError, RuntimeError):
            path = None
        if path is not None and any(path.is_relative_to(root) for root in _FETCH_ROOTS):
            return default_url_fetcher(url)
    log.warning("PDF: refused to fetch %r (not a data: URI or an allowed local file)", url[:200])
    raise ValueError(f"PDF resource not allowed: {url[:200]}")


MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
NOW_MONTH = __import__('datetime').date.today().month


def _parse_months(val) -> list:
    """Accept int list, string list, or comma-separated string."""
    if not val:
        return []
    if isinstance(val, str):
        return [int(x.strip()) for x in val.split(',') if x.strip().lstrip('-').isdigit()]
    return [int(m) for m in val if str(m).strip().lstrip('-').isdigit()]


def _season_str(sp: Dict) -> str:
    phenology = sp.get('phenology') or {}
    months: set = set()
    for k in ('flower', 'fruit', 'leaf'):
        for m in _parse_months(phenology.get(k)):
            months.add(m)
    for m in _parse_months(sp.get('flower_months')):
        months.add(m)
    if not months:
        return ''
    parts = []
    for i in range(12):
        m = i + 1
        initial = MONTHS[i][0]
        if m in months:
            parts.append(f'<strong>{initial}</strong>')
        else:
            parts.append(f'<span class="off">{initial}</span>')
    return ' '.join(parts)


def _mdlite(text: str) -> str:
    if not text:
        return ''
    text = str(text).replace('\r', '')
    blocks = re.split(r'\n{2,}', text)
    out = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        h = re.match(r'^#{1,6}\s+(.*)', b)
        if h:
            heading = h.group(1).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            out.append(f'<h3>{heading}</h3>')
        else:
            content = b.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            content = content.replace('\n', '<br>')
            out.append(f'<p>{content}</p>')
    return ''.join(out)


_jinja_env.filters['mdlite'] = _mdlite


# Culinary content fields dropped for a blocked species — same list as
# SafetyGate.CULINARY_FIELDS in frontend/static/js/safety-gate.js.
CULINARY_FIELDS = frozenset({
    'edible_parts', 'preparation_methods', 'cooking_techniques', 'preservation_methods',
    'harvest_stage', 'culinary_traditions', 'flavour_profile', 'pairing_ideas', 'recipe_ideas',
    'workshop_value_score', 'taste_notes',
})


def _flatten_species(name: str, profile: Optional[Dict], base_by_name: Dict,
                     safety: Optional[Dict] = None) -> Dict:
    """Merge base species record + profile into a flat dict for the template.
    safety = the server's safety_decision() for this species (B2-09: the
    client's severity / culinary text is never trusted). Missing → fails closed.
    The PDF is an outgoing surface (batch 6): the handout half of the decision
    gates culinary content, and the warnings come from the server's
    handout_warnings (curator-authored, toxic fallback included), never from
    the payload."""
    if safety is None:
        safety = safety_decision(None, None)
    allowed = bool(safety.get('handout_culinary_allowed'))
    hw = safety.get('handout_warnings') or {}
    base = base_by_name.get(name) or {}
    sp   = (profile or {}).get('species') or base
    cul  = (profile or {}).get('culinary') or {}
    # Print rule = D5 (Melvin B, 21 Oct 2026): a field holding PFAF fallback text
    # never prints, as on the public experience page. pfaf_fallback_fields is the
    # shared is_pfaf_fallback() predicate, served by /api/species/{name}/profile.
    withheld = set((profile or {}).get('pfaf_fallback_fields') or [])
    cul = {k: v for k, v in cul.items() if k not in withheld}
    if not allowed:
        # Safety gate: no edible parts / harvest / taste / recipe for toxic,
        # deadly or unknown-toxicity species — dropped here, not just in the template.
        cul = {k: v for k, v in cul.items() if k not in CULINARY_FIELDS}
    recipes = ((profile or {}).get('recipes') or []) if allowed else []
    key_recipe = next((r for r in recipes if r.get('is_preferred')), recipes[0] if recipes else None)

    common_names = sp.get('common_names') or base.get('common_names') or []
    parts_bits = []
    if cul.get('edible_parts'):  parts_bits.append(cul['edible_parts'])
    if cul.get('harvest_stage'): parts_bits.append(cul['harvest_stage'])

    id_notes_raw = (cul.get('id_notes') or '').strip()
    id_notes = re.sub(r'\[[^\]]*\]\s*', '', id_notes_raw).strip()

    return {
        'scientific_name': name,
        'common_name':    sentence_case_name(common_names[0]) if common_names else '',   # names: sentence case
        'edibility_status': sp.get('edibility_status') or '',
        'culinary_allowed': allowed,
        'safety_level':    safety.get('level') or 'unknown',
        'safety_label':    safety.get('handout_label', safety.get('label')) or '',
        'safety_warning':  safety.get('warning') or '',
        'id_notes':        id_notes,
        'look_alike':      (hw.get('look_alike') or '').strip(),
        'preparation_warnings': (hw.get('preparation') or '').strip(),
        'edible_parts':    cul.get('edible_parts') or '',
        'harvest_stage':   cul.get('harvest_stage') or '',
        'medicinal_notes': cul.get('medicinal_notes') or '',
        'medicinal_clinical_tags': json.loads(cul.get('medicinal_clinical') or '[]'),
        'parts_text':      ' · '.join(parts_bits),
        'recipe_title':    key_recipe['title'] if key_recipe else '',
        'recipe_body':     key_recipe['body']  if key_recipe else '',
        # Cautionary text printed with culinary content (Fix B, 22 Oct 2026):
        # look-alike + preparation, curator text only, uncut. [] = nothing added.
        'culinary_warnings': culinary_warnings(safety, handout=True) if allowed else [],
        'season_str':      _season_str(sp),
        'phenology':       sp.get('phenology') or {},
    }


# ── Request / response models ────────────────────────────────────────────────

class SpeciesData(BaseModel):
    scientific_name: str
    profile: Optional[Dict[str, Any]] = None

class CoverData(BaseModel):
    event:    Optional[str] = ''
    date:     Optional[str] = ''
    location: Optional[str] = ''
    intro:    Optional[str] = ''

class ContentToggles(BaseModel):
    id_notes: bool = True
    foraging: bool = True
    culinary: bool = True
    recipes:  bool = True
    season:   bool = True
    herbal:   bool = True
    photos:   bool = True
    map:      bool = True

# margins param → concrete @page margin string + goethean column width
_MARGIN_MAP = {
    #          page_margin     workshop_margin  goe_width  goe_pad
    'narrow': ('5mm 3mm',      '5mm 3mm',        150,       154),
    'normal': ('10mm 8mm',     '10mm 8mm',        150,       154),
    'wide':   ('18mm 14mm',    '20mm 14mm',       150,       154),
}


class PdfRequest(BaseModel):
    species:    List[SpeciesData]
    base_species: Optional[List[Dict[str, Any]]] = None
    style:      Optional[str] = 'botanical'    # botanical | herbalist | goethean
    layout:     Optional[str] = 'field_guide'  # field_guide | recipe_booklet | workshop
    cover:      Optional[CoverData] = None
    toggles:    Optional[ContentToggles] = None
    margins:    Optional[str] = 'normal'        # narrow | normal | wide
    seasonal_returns: Optional[List[Dict[str, Any]]] = None


async def participant_notes_by_name(db: AsyncSession, identity, names) -> Dict[str, List[str]]:
    """Batch 8: {requested name: [note text]} — the participant's OWN text notes
    for those species (looked up by name_key), oldest first. {} for the curator
    and anonymous guests: curator handouts are unchanged."""
    if not identity.is_guest or identity.is_anonymous_guest or identity.user_id is None:
        return {}
    from app.models.encounter import Encounter
    from app.models.species import Species
    keys = {normalize_taxon_key(n): n for n in names if n}
    rows = (await db.execute(
        select(Species.name_key, Encounter.text_note)
        .join(Species, Encounter.species_id == Species.id)
        .where(Encounter.user_id == identity.user_id)            # their own — never another participant's
        .where(Encounter.text_note.is_not(None))
        .where(Species.name_key.in_(list(keys)))
        .order_by(Encounter.encounter_date, Encounter.id))).all()
    out: Dict[str, List[str]] = {}
    for key, txt in rows:
        if (txt or "").strip():
            out.setdefault(keys[key], []).append(txt.strip())
    return out


@router.post("/pdf")
async def generate_pdf(body: PdfRequest, db: AsyncSession = Depends(get_db),
                       identity: Identity = Depends(get_identity)):
    # B2-09: the safety decision comes from the DB by name, never from the payload.
    names = [s.scientific_name for s in body.species]
    safety = await safety_by_names(db, names)
    my_notes = await participant_notes_by_name(db, identity, names)
    return await run_in_threadpool(render_pdf, body, safety, my_notes)


def render_pdf(body: PdfRequest, safety: Dict[str, Dict], my_notes: Optional[Dict[str, List[str]]] = None) -> Response:
    style   = body.style   if body.style   in ('botanical', 'herbalist', 'goethean')           else 'botanical'
    layout  = body.layout  if body.layout  in ('field_guide', 'recipe_booklet', 'workshop')    else 'field_guide'
    margins = body.margins if body.margins in _MARGIN_MAP                                       else 'normal'
    cover   = (body.cover or CoverData()).model_dump()
    ct      = (body.toggles or ContentToggles()).model_dump()

    log.info("PDF request — style=%r layout=%r margins=%r species_count=%d",
             style, layout, margins, len(body.species))

    page_margin, ws_margin, goe_width, goe_pad = _MARGIN_MAP[margins]
    if layout == 'workshop':
        page_margin = ws_margin

    base_by_name: Dict[str, Dict] = {}
    for s in (body.base_species or []):
        base_by_name[s['scientific_name']] = s

    flat_species = [
        dict(_flatten_species(s.scientific_name, s.profile, base_by_name, safety.get(s.scientific_name)),
             my_notes=(my_notes or {}).get(s.scientific_name, []))
        for s in body.species
    ]

    # Format seasonal-return dates for the template (Python 3.9 safe)
    sr_items = []
    for item in (body.seasonal_returns or []):
        sr = dict(item)
        raw = sr.get('last_seen') or ''
        if raw:
            try:
                from datetime import date as _date
                d = _date.fromisoformat(raw[:10])
                sr['last_seen_fmt'] = f"{d.day} {MONTHS[d.month - 1]} {d.year}"
            except Exception:
                sr['last_seen_fmt'] = raw[:10]
        else:
            sr['last_seen_fmt'] = ''
        sr_items.append(sr)

    try:
        tmpl = _jinja_env.get_template('print_pdf.html')
        html = tmpl.render(
            style=style,
            layout=layout,
            cover=cover,
            species=flat_species,
            ct=ct,
            page_margin=page_margin,
            goe_width=goe_width,
            goe_pad=goe_pad,
            seasonal_returns=sr_items,
        )
        log.info("Template rendered OK — style=%r html_len=%d", style, len(html))
        # Confirm style string landed in the rendered HTML
        style_check = f'style == \'{style}\'' if False else style
        log.info("Style marker presence: border-wrap=%s goe-left=%s",
                 'border-wrap' in html, 'goe-left' in html)
    except Exception as exc:
        log.exception("Template render failed")
        return JSONResponse(status_code=500, content={"detail": f"Template error: {exc}"})

    _frontend_dir = _PROJECT_ROOT / "frontend"
    _base_url = f"file://{_frontend_dir}/"
    log.info("WeasyPrint base_url=%s", _base_url)
    try:
        from weasyprint import HTML as WeasyprintHTML
    except Exception as exc:
        log.warning("WeasyPrint import failed: %s", exc)
        return JSONResponse(status_code=503, content={"detail": f"WeasyPrint unavailable: {exc}. Check DYLD_LIBRARY_PATH."})
    try:
        pdf_bytes = WeasyprintHTML(
            string=html, base_url=_base_url, url_fetcher=_safe_url_fetcher,
        ).write_pdf()
    except Exception as exc:
        log.exception("WeasyPrint failed")
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="landmemory-list.pdf"'},
    )
