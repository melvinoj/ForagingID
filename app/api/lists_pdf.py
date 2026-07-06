import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2
from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

log = logging.getLogger(__name__)

os.environ.setdefault("DYLD_LIBRARY_PATH", "/opt/homebrew/lib")

router = APIRouter(prefix="/api/lists", tags=["lists"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "app" / "templates"

# Jinja2 env — autoescape off (we control all inputs server-side)
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=False,
)

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
            out.append(f'<h3>{h.group(1)}</h3>')
        else:
            content = b.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            content = content.replace('\n', '<br>')
            out.append(f'<p>{content}</p>')
    return ''.join(out)


_jinja_env.filters['mdlite'] = _mdlite


def _flatten_species(name: str, profile: Optional[Dict], base_by_name: Dict) -> Dict:
    """Merge base species record + profile into a flat dict for the template."""
    base = base_by_name.get(name) or {}
    sp   = (profile or {}).get('species') or base
    cul  = (profile or {}).get('culinary') or {}
    recipes = (profile or {}).get('recipes') or []
    key_recipe = next((r for r in recipes if r.get('is_preferred')), recipes[0] if recipes else None)

    common_names = sp.get('common_names') or base.get('common_names') or []
    parts_bits = []
    if cul.get('edible_parts'):  parts_bits.append(cul['edible_parts'])
    if cul.get('harvest_stage'): parts_bits.append(cul['harvest_stage'])

    id_notes_raw = (cul.get('id_notes') or '').strip()
    id_notes = re.sub(r'\[[^\]]*\]\s*', '', id_notes_raw).strip()

    return {
        'scientific_name': name,
        'common_name':    common_names[0] if common_names else '',
        'edibility_status': sp.get('edibility_status') or '',
        'toxicity_severity': sp.get('toxicity_severity') or 'none',
        'id_notes':        id_notes,
        'look_alike':      (cul.get('look_alike_warnings') or '').strip(),
        'preparation_warnings': (cul.get('preparation_warnings') or '').strip(),
        'edible_parts':    cul.get('edible_parts') or '',
        'harvest_stage':   cul.get('harvest_stage') or '',
        'medicinal_notes': cul.get('medicinal_notes') or '',
        'medicinal_clinical_tags': json.loads(cul.get('medicinal_clinical') or '[]'),
        'parts_text':      ' · '.join(parts_bits),
        'recipe_title':    key_recipe['title'] if key_recipe else '',
        'recipe_body':     key_recipe['body']  if key_recipe else '',
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


@router.post("/pdf")
def generate_pdf(body: PdfRequest):
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
        _flatten_species(s.scientific_name, s.profile, base_by_name)
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

    _frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    _base_url = f"file://{_frontend_dir}/"
    log.info("WeasyPrint base_url=%s", _base_url)
    try:
        from weasyprint import HTML as WeasyprintHTML
    except Exception as exc:
        log.warning("WeasyPrint import failed: %s", exc)
        return JSONResponse(status_code=503, content={"detail": f"WeasyPrint unavailable: {exc}. Check DYLD_LIBRARY_PATH."})
    try:
        pdf_bytes = WeasyprintHTML(string=html, base_url=_base_url).write_pdf()
    except Exception as exc:
        log.exception("WeasyPrint failed")
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="foragingid-list.pdf"'},
    )
