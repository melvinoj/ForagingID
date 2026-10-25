#!/usr/bin/env python3
"""
Foraging Experience — static export of one saved walk.

    ~/foragingid-venv/bin/python scripts/experience_export/export.py \
        --walk-id 4 --overrides scripts/experience_export/overrides/walk4.json --default [--plan-only]

Reads data/foragingid.db READ-ONLY (?mode=ro), never the app server. Writes
index.html + preview.html + tree.html (all data inlined as JSON, no fetch) and
photos/ re-encoded with EXIF stripped, to <out>/ for the root (--default) walk
— plus an identical copy at <out>/w/<slug>/ — or to <out>/w/<slug>/ otherwise.
Only those files are replaced; other walks under <out>/w/ are left alone.
--plan-only runs every gate and prints the plan without writing anything.
Members come only from app/services/walk_membership.compute; every publish
decision goes through gates.py. Page-wide settings: config.json; per-walk
text, slug, hidden species and "More walks": the --overrides JSON.

Reused (not forked) at build time, so the export follows the app:
  - frontend/taxonomy.html  <style> + main <script>, with anchored patches
    (each must match exactly once or the build fails) — see TREE_PATCHES.
  - app/templates/print_pdf.html  final-disclaimer text (verbatim) and the
    toxic fallback sentence (verbatim).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(REPO))
import gates  # noqa: E402
import app_styles  # noqa: E402
# Walk membership (saved stops + photos that joined by route proximity) — the
# app's own rule, imported, not re-implemented (pure Python, no DB access).
from app.services import walk_membership as wm  # noqa: E402
from app.services import walk_route  # noqa: E402
# names rule, one definition; recipe title / summary / link rules (Recipes tab)
from app.models.species import (RECIPE_TYPES, display_common_name, recipe_display_title,  # noqa: E402
                                recipe_summary_line, recipe_title_source, recipe_website_url_ok)

DB_PATH   = REPO / "data" / "foragingid.db"
DIST      = REPO / "dist"
TAXONOMY  = REPO / "frontend" / "taxonomy.html"
PRINT_PDF = REPO / "app" / "templates" / "print_pdf.html"

# Same pinned assets as the app (Leaflet SRI from frontend/index.html; d3 is the
# exact cdnjs file taxonomy.html loads, hashed 15 Oct 2026).
ASSETS = {
    "leaflet_css": ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
                    'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY='),
    "leaflet_js":  ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
                    'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo='),
    "d3_js":       ('https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js',
                    'sha384-su5kReKyYlIFrI62mbQRKXHzFobMa7BHp1cK6julLPbnYcCW9NIZKJiTODjLPeDh'),
}


class BuildError(RuntimeError):
    pass


def die(msg: str):
    raise BuildError(msg)


# ── small helpers ────────────────────────────────────────────────────────────

def first_name(raw) -> str:
    """common_names columns hold a JSON list (sometimes a plain string)."""
    if not raw:
        return ""
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return str(v[0]).strip() if v else ""
        return str(v).strip()
    except (ValueError, TypeError):
        return str(raw).split(",")[0].strip()


def en_name(sp: dict) -> str:
    """English common name — the app's own rule (app/models/species.py)."""
    return display_common_name(sp.get("preferred_common_name"), sp.get("common_names"))


def json_inline(obj) -> str:
    """JSON safe to embed inside a <script> element."""
    return (json.dumps(obj, ensure_ascii=False)
            .replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def fill(tpl: str, values: dict, name: str) -> str:
    """Fill {{KEY}} placeholders. Fails if a key the code fills is missing from
    the template (it would silently vanish) or a placeholder is left unfilled."""
    in_tpl = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", tpl))
    missing = [k for k in values if k not in in_tpl]
    if missing:
        die(f"templates/{name}: placeholders the export fills are missing from the template: {missing}")
    left = sorted(in_tpl - set(values))
    if left:
        die(f"templates/{name}: unfilled placeholders {left}")
    # One pass, so filled text is never re-scanned for placeholders.
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: values[m.group(1)], tpl)


def sri_tag(kind: str) -> str:
    url, integrity = ASSETS[kind]
    if kind.endswith("_css"):
        return f'<link rel="stylesheet" href="{url}" integrity="{integrity}" crossorigin="anonymous">'
    return f'<script src="{url}" integrity="{integrity}" crossorigin="anonymous"></script>'


# ── reused text from print_pdf.html (verbatim) ───────────────────────────────

def load_print_pdf_texts() -> dict:
    src = PRINT_PDF.read_text(encoding="utf-8")
    m = re.search(r'<div class="final-disclaimer">\s*<div class="final-disclaimer-h">(.*?)</div>\s*(.*?)\s*</div>',
                  src, re.S)
    if not m:
        die("print_pdf.html: final-disclaimer block not found — template changed?")
    paras = re.findall(r"<p>(.*?)</p>", m.group(2), re.S)
    if not paras:
        die("print_pdf.html: final-disclaimer has no <p> text")
    # The toxic fallback sentence is app.models.species.TOXIC_FALLBACK_TEXT —
    # gates.safety_texts takes it from there (batch 6), as the PDF does.
    return {"disclaimer_heading": m.group(1).strip(),
            "disclaimer_paras": [p.strip() for p in paras]}


# ── recipe teaser (approved text only — never newly written) ─────────────────

def recipe_title(rec: dict) -> str:
    """The app's one rule (app/models/species.recipe_display_title): never a
    blockquote or safety-note line."""
    return recipe_display_title(rec.get("title"), rec.get("body"))


# Sentences that only make sense after the previous one ("That quality…").
_ANAPHORIC = re.compile(r"^(this|that|these|those|it|its|it's|they|their|here|so|but|and|which)\b", re.I)
# Split on . ! ? followed by space + capital, but not after common abbreviations ("c. 6000 BC").
_SENT_SPLIT = re.compile(r"(?<!\bc\.)(?<!\bca\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bDr\.)(?<!\bSt\.)(?<=[.!?])\s+(?=[A-Z\"'‘“])")


def recipe_teaser(rec: dict, title: str, skip_patterns) -> str:
    """First self-contained sentence of the approved body: not the title, a rule,
    a byline or a sub-heading; not opening with a back-reference; and not
    matching a skip pattern (place names, medicinal wording). Text is copied
    from the approved recipe, only trimmed — never rewritten."""
    skips = [re.compile(x, re.I) for x in skip_patterns]
    body = (rec.get("body") or "").replace("\r", "")
    for para in re.split(r"\n{2,}", body):
        p = para.strip()
        if not p or p.startswith("#") or p.startswith("---"):
            continue
        plain = re.sub(r"\*+", "", p).strip()
        if not plain or plain.lower().startswith("by ") or plain.lower() == title.lower():
            continue
        if re.fullmatch(r"[^.!?]{0,90}", plain) and "—" in plain:   # "Abies grandis — Grand Fir" sub-heading
            continue
        for s in _SENT_SPLIT.split(plain.replace("\n", " ")):
            s = s.strip()
            if len(s) < 25 or _ANAPHORIC.match(s):
                continue
            if any(x.search(s) for x in skips):
                continue
            if len(s) > 190:
                s = s[:190].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
            return s
    return ""


# ── Recipes tab: every public recipe (Melvin, 25 Oct 2026) ───────────────────

def build_recipe_bank(conn: sqlite3.Connection, cfg: dict) -> tuple[list, list]:
    """(bank, excluded) — every approved recipe in the app that passes the
    export gates (gates.recipe_allowed: the same rules as this walk's own
    recipes — toxic, unknown, Apiaceae, not human-verified, withheld caution
    and medicinal preparations never get here) and is not hidden from public.
    A teaser only: dish, species names, season, type, the one-line summary
    (curator's, else the summary rule; never a line matching
    teaser_skip_patterns — then the export's own teaser rule), the curator
    warnings that travel with culinary content (Fix B) and the website link.
    Never the recipe body: no ingredients, no method. A recipe whose title is
    only a first prose sentence (recipe_title_source 'line') waits for a
    curator title and is listed as excluded."""
    skips = [re.compile(x, re.I) for x in cfg.get("teaser_skip_patterns", [])]
    rows = [dict(r) for r in conn.execute(
        "SELECT id, species_id, title, body, status, is_preferred, is_medicinal_prep, source, season, "
        "summary, recipe_type, hide_from_public, website_url, created_at FROM species_recipes "
        "WHERE status = 'approved' ORDER BY id")]
    sp_cache: dict = {}
    bank, excluded = [], []
    for r in rows:
        sid = r["species_id"]
        if sid not in sp_cache:
            sp_row = conn.execute("SELECT * FROM species WHERE id = ?", (sid,)).fetchone()
            ci_row = conn.execute("SELECT * FROM culinary_info WHERE species_id = ?", (sid,)).fetchone()
            sp_cache[sid] = (dict(sp_row) if sp_row else None, dict(ci_row) if ci_row else {})
        sp, ci = sp_cache[sid]
        if sp is None:
            excluded.append((r["id"], None, "no species row"))
            continue
        ok, why = gates.recipe_allowed(sp, ci, r, conn, cfg)
        if not ok:
            excluded.append((r["id"], sp["scientific_name"], why))
            continue
        if r["hide_from_public"]:
            excluded.append((r["id"], sp["scientific_name"], "hidden from public"))
            continue
        if recipe_title_source(r["title"], r["body"]) not in ("own", "heading"):
            excluded.append((r["id"], sp["scientific_name"], "needs a title"))
            continue
        dish = recipe_display_title(r["title"], r["body"])
        line = (r["summary"] or "").strip() or recipe_summary_line(r["title"], r["body"])
        if not line or any(x.search(line) for x in skips):
            line = recipe_teaser(r, dish, cfg.get("teaser_skip_patterns", []))
        bank.append({
            "recipe_id": r["id"], "species_id": sid, "dish": dish, "line": line,
            "season": r["season"], "type": r["recipe_type"] if r["recipe_type"] in RECIPE_TYPES else "other",
            "approved_at": str(r["created_at"] or "")[:10],
            "url": r["website_url"] if recipe_website_url_ok(r["website_url"]) else None,
            "sci": sp["scientific_name"], "en": en_name(sp), "de": first_name(sp.get("common_names_de")),
            "caution": gates.is_caution(sp), "source": r["source"],
            "warnings": gates.recipe_warnings(sp, ci, conn),
        })
    return bank, excluded


# ── photos ───────────────────────────────────────────────────────────────────

def encode_photo(src: Path, dst: Path, long_edge: int, quality: int):
    """Re-encode from pixel data only: orientation applied, then a fresh image
    with no EXIF/XMP/ICC/comment carried over. Originals are never copied."""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        im.thumbnail((long_edge, long_edge), Image.LANCZOS)
        clean = Image.new("RGB", im.size)
        clean.paste(im)
    clean.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)


def verify_no_metadata(paths) -> dict:
    """Check with exiftool (independent of PIL): GPS tags and any EXIF at all."""
    gps_total, exif_files = 0, []
    for p in paths:
        out = subprocess.run(["exiftool", "-a", "-G1", "-s", "-GPS:all", "-EXIF:all", str(p)],
                             capture_output=True, text=True, check=True).stdout
        lines = [l for l in out.splitlines() if l.strip()]
        gps_total += sum(1 for l in lines if l.startswith("[GPS]"))
        if lines:
            exif_files.append(p.name)
    pil_gps = 0
    for p in paths:
        with Image.open(p) as im:
            ex = im.getexif()
            pil_gps += len(ex.get_ifd(0x8825)) if ex else 0
    return {"files": len(paths), "exiftool_gps_tags": gps_total, "pil_gps_tags": pil_gps,
            "files_with_any_exif": exif_files}


# ── taxonomy tree (reuses frontend/taxonomy.html) ────────────────────────────

def _popup_replacement() -> str:
    return ('function openSpeciesPopup(d, e){ window.__exportSpeciesPopup(d.data.name, e); }\n'
            'function closeSpeciesPopup(){')


TREE_PATCHES = [
    # (description, regex, replacement[, expected matches=1]) — the count must be exact.
    ("inline data instead of fetch",
     r'const resp = await fetch\("/api/species/taxonomy-tree"\);\s*\n\s*if \(!resp\.ok\) throw new Error\(`HTTP \$\{resp\.status\}`\);\s*\n\s*data = await resp\.json\(\);',
     'data = window.__EXPORT_TAXONOMY__;'),
    ("baked species popup (no API, no app link)",
     r'async function openSpeciesPopup\(d, e\)\{.*?\nfunction closeSpeciesPopup\(\)\{',
     None),  # filled with _popup_replacement()
    # Two copies in taxonomy.html (arc sizing + layout(), "must match") — patched together.
    ("genus slot sized for a small tree",
     r'const GENUS_SLOT_UNIT = 0\.65 \* Math\.PI / 180;',
     'const GENUS_SLOT_UNIT = window.__EXPORT_GENUS_SLOT_DEG__ * Math.PI / 180;', 2),
    ("toxic species drawn red",
     r'function colourFor\(d\)\{\n',
     'function colourFor(d){\n  if (d.data.rank === "species" && (window.__EXPORT_SPECIES__[d.data.name] || {}).toxic) return "var(--app-toxic)";\n'),
    ("toxic ☠ on persistent species labels",
     r'\.text\(d=>d\.data\.name\.split\(" "\)\.slice\(1\)\.join\(" "\)\)',
     '.text(d=>((window.__EXPORT_SPECIES__[d.data.name]||{}).toxic ? "☠ " : "") + d.data.name.split(" ").slice(1).join(" "))'),
    ("toxic ☠ on node labels",
     r'\.text\(d=>d\.data\.rank==="species" \? d\.data\.name\.split\(" "\)\.slice\(1\)\.join\(" "\) : d\.data\.name\)',
     '.text(d=>d.data.rank==="species" ? ((window.__EXPORT_SPECIES__[d.data.name]||{}).toxic ? "☠ " : "") + d.data.name.split(" ").slice(1).join(" ") : d.data.name)'),
    ("tooltip shows common name, not 'species card'",
     r'meta = st === "none" \? "placeholder" : st === "in_review" \? "card pending review" : "species card";',
     'meta = (window.__EXPORT_SPECIES__[d.data.name] || {}).en || "";'),
    # taxonomy.html's class-tier redistribution is tuned to the app's full
    # collection and throws unless Magnoliopsida, Bryopsida, Polypodiopsida,
    # Liliopsida, Pinopsida and Florideophyceae are all present. A single walk
    # rarely has all six, so the export skips that block (layout only — the
    # general radial layout above it still positions every class node).
    ("skip full-collection class-tier redistribution",
     r'if \(gatherTrunk\) \{\n    const REDISTRIBUTE = ',
     'if (gatherTrunk && !window.__EXPORT_SKIP_CLASS_REDISTRIBUTION__) {\n    const REDISTRIBUTE = '),
    ("no empty 'Unplaced' knot",
     r'\n    drawUnplaced\(\);\n',
     '\n    if (UNPLACED.length) drawUnplaced();\n'),
    ("count badge wording",
     r'`\$\{confirmedCount\} confirmed · \$\{Object\.keys\(RAW\.Plantae\)\.length\} families · \$\{UNPLACED\.length\} unplaced`',
     '`${window.__EXPORT_TREE_COUNT__} species on this walk`'),
]


def build_tree_html(species_meta: dict, taxonomy: dict, slot_deg: float, app_root_css: str) -> tuple[str, list]:
    src = TAXONOMY.read_text(encoding="utf-8")
    style = re.search(r"<style>(.*?)</style>", src, re.S)
    scripts = re.findall(r"<script>(.*?)</script>", src, re.S)
    if not style or len(scripts) != 1:
        die(f"taxonomy.html: expected 1 <style> and 1 inline <script>, found style={bool(style)} scripts={len(scripts)}")
    script = scripts[0]
    applied = []
    for desc, pattern, repl, *rest in TREE_PATCHES:
        expected = rest[0] if rest else 1
        n = len(re.findall(pattern, script, re.S))
        if n != expected:
            die(f"taxonomy.html patch '{desc}': anchor matched {n} times (expected {expected}) — taxonomy.html changed")
        script = re.sub(pattern, (repl if repl is not None else _popup_replacement()).replace("\\", "\\\\"),
                        script, count=expected, flags=re.S)
        applied.append(desc)
    # Published copy drops full-line // comments (internal notes, API paths);
    # code lines are untouched.
    script = re.sub(r"(?m)^[ \t]*//.*\n", "", script)
    for banned in ("fetch(", "/api/", "/thumbnails", "/species?s=", "/static/"):
        if banned in script:
            die(f"tree script still contains '{banned}' after patching")
    # Render on load: the iframe is only created when the Plants tab opens, so the
    # window already has its real size (the layout reads window.innerWidth/Height).

    tree_count = sum(len(sp) for orders in taxonomy["RAW"]["Plantae"].values() for fams in orders.values()
                     for gens in fams.values() for sp in gens.values()) + \
                 sum(len(sp) for orders in taxonomy["FUNGI"].values() for fams in orders.values()
                     for gens in fams.values() for sp in gens.values())
    tpl = (HERE / "templates" / "tree.html").read_text(encoding="utf-8")
    # TAXONOMY_SCRIPT last: the app's script may itself contain "{{" (template
    # literals), so the unfilled check runs on the template before it goes in.
    out = fill(tpl.replace("{{TAXONOMY_SCRIPT}}", "\x00TAXONOMY_SCRIPT\x00"), {
        "TAXONOMY_STYLE": style.group(1),
        "APP_ROOT": app_root_css,
        "D3": sri_tag("d3_js"),
        "DATA": "window.__EXPORT_TAXONOMY__ = " + json_inline(taxonomy) + ";\n"
                "window.__EXPORT_SPECIES__ = " + json_inline(species_meta) + ";\n"
                f"window.__EXPORT_GENUS_SLOT_DEG__ = {slot_deg:.4f};\n"
                f"window.__EXPORT_TREE_COUNT__ = {tree_count};\n"
                "window.__EXPORT_SKIP_CLASS_REDISTRIBUTION__ = true;\n",
    }, "tree.html")
    if out.count("\x00TAXONOMY_SCRIPT\x00") != 1:
        die("templates/tree.html: {{TAXONOMY_SCRIPT}} must appear exactly once")
    out = out.replace("\x00TAXONOMY_SCRIPT\x00", script)
    return out, applied


# ── preview card (preview.html — static, no JS) ──────────────────────────────

def _split_ranges(n: int, ranges: list) -> list:
    """[(a, b, dashed)] covering vertices 0..n-1 — solid between the dashed ranges."""
    out, at = [], 0
    for a, b in ranges:
        if a > at:
            out.append((at, a, False))
        out.append((a, b, True))
        at = b
    if at < n - 1:
        out.append((at, n - 1, False))
    return out


def route_svg(line, stops, straight_ranges=(), size=100, pad=8) -> str:
    """Small static route drawing from the saved route line (no map tiles).
    straight_ranges (no mapped footpath / ORS detour) are drawn dashed, as in the app."""
    pts = [(c[0], c[1]) for c in (line or [])] or [(st["lng"], st["lat"]) for st in stops]
    if not pts:
        return ""
    import math
    lat0 = sum(p[1] for p in pts) / len(pts)
    kx = math.cos(math.radians(lat0))                       # equirectangular, true aspect at this latitude
    xs = [p[0] * kx for p in pts]; ys = [p[1] for p in pts]
    sx = [st["lng"] * kx for st in stops]; sy = [st["lat"] for st in stops]
    minx, maxx = min(xs + sx), max(xs + sx); miny, maxy = min(ys + sy), max(ys + sy)
    span = max(maxx - minx, maxy - miny) or 1e-9
    sc = (size - 2 * pad) / span
    ox = pad + ((size - 2 * pad) - (maxx - minx) * sc) / 2
    oy = pad + ((size - 2 * pad) - (maxy - miny) * sc) / 2
    X = lambda x: ox + (x - minx) * sc
    Y = lambda y: oy + (maxy - y) * sc                      # north up
    xy = [f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(xs, ys)]
    style = 'style="fill:none;stroke:var(--leaf)" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"'
    if line and straight_ranges:
        polys = "".join(f'<polyline points="{" ".join(xy[a:b + 1])}" {style}'
                        + (' stroke-dasharray="3 3"' if dashed else "") + "/>"
                        for a, b, dashed in _split_ranges(len(xy), straight_ranges))
    else:
        polys = f'<polyline points="{" ".join(xy)}" {style}/>'
    dots = "".join(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="1.8" style="fill:var(--paper)"/>' for x, y in zip(sx, sy))
    start = f'<circle cx="{X(xs[0]):.1f}" cy="{Y(ys[0]):.1f}" r="3.2" style="fill:var(--amber)"/>' if line else ""
    return (f'<svg class="route" viewBox="0 0 {size} {size}" role="img" aria-label="Route of the walk">'
            f'{polys}{dots}{start}</svg>')


def preview_choice(cfg: dict, data: dict, pub: dict) -> tuple[list, dict]:
    """(teaser recipes, hero) for preview.html — always THIS walk's own data
    (Melvin, 22 Oct 2026: no fixed config values; the card is never filled from
    another walk). Teasers: this walk's gated recipes, first 3 by
    recipe_source_priority. Hero: the first teaser plant that is not toxic and
    has a photo on this walk, else the first such plant in walk order. Either
    missing → the build fails."""
    prio = {src: i for i, src in enumerate(cfg.get("recipe_source_priority", []))}
    chosen = sorted(data["recipes"], key=lambda r: prio.get(r["source"], len(prio)))[:3]
    if not chosen:
        die("preview.html: this walk has no gated recipes for the card's teasers "
            "(the card is never filled from another walk)")

    def ok(p):
        return p is not None and p["photo"] and not p["toxic"]
    hero = next((pub.get(r["species_id"]) for r in chosen if ok(pub.get(r["species_id"]))), None)
    if hero is None:
        hero = next((p for p in data["species"] if ok(p)), None)
    if hero is None:
        die("preview.html: no non-toxic species with a photo on this walk for the card's hero "
            "(the card is never filled from another walk)")
    return chosen, hero


def build_preview(cfg: dict, ov: dict, data: dict, pub: dict, app_css: str) -> tuple[str, dict]:
    chosen, hero = preview_choice(cfg, data, pub)

    km = f"{data['walk']['distance_m'] / 1000:.1f}" if data["walk"]["distance_m"] else None
    stats = [f"<span><b>{len(pub)}</b> species</span>", f"<span><b>{len(data['walk']['stops'])}</b> stops</span>"]
    if km:
        stats.append(f"<span><b>{km}</b> km</span>")
    teasers = "".join(
        f'<li><div class="dish">{html.escape(r["dish"])}</div>'
        f'<div class="plant">{html.escape(pub[r["species_id"]]["en"] or pub[r["species_id"]]["sci"])}</div></li>'
        for r in chosen)
    more = ov["more_walks"]
    more_html = ""
    if more:
        more_html = ('<div class="more-walks">More walks: ' + " · ".join(
            f'<a href="{html.escape(m["url"])}" target="_top">{html.escape(m["title"])}</a>' for m in more) + "</div>")
    tpl = (HERE / "templates" / "preview.html").read_text(encoding="utf-8")
    out = fill(tpl, {
        "APP_STYLES": app_css,
        "LANG": html.escape(cfg.get("language", "en")),
        "TITLE": html.escape(ov["title_en"]),
        "WHERE": html.escape(ov["where_en"]),
        "CARD_CLASS": "card has-more" if more else "card",
        "HERO": f'<img src="{hero["photo"]}" alt="{html.escape(hero["en"] or hero["sci"])}">',
        "ROUTE_SVG": route_svg(data["walk"]["line"], data["walk"]["stops"], data["walk"]["straight_ranges"]),
        "STATS": "".join(stats),
        "TEASERS": teasers,
        "MORE_WALKS": more_html,
    }, "preview.html")
    return out, {"hero": f"{hero['id']} {hero['sci']}", "recipes": [f"{r['recipe_id']} {r['dish']}" for r in chosen],
                 "more_walks": [m["title"] for m in more]}


# ── CLI + per-walk overrides ─────────────────────────────────────────────────

OVERRIDE_TEXT_KEYS = ("title_en", "title_de", "intro_en", "intro_de", "where_en", "where_de")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Files a build owns in its page directory — the only things it ever deletes there.
OWNED_FILES = ("index.html", "preview.html", "tree.html")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Foraging Experience — static export of one saved walk.")
    ap.add_argument("--walk-id", type=int, required=True, help="saved_walks.id to export")
    ap.add_argument("--overrides", type=Path, help="per-walk JSON: slug, titles/intros/where (en/de), "
                    "hide_species_ids, more_walks")
    ap.add_argument("--out", type=Path, default=REPO / "dist", help="output root (default dist/)")
    ap.add_argument("--plan-only", action="store_true", help="print the plan; write no files")
    ap.add_argument("--db", type=Path, default=DB_PATH,
                    help="SQLite database, opened read-only (default data/foragingid.db; the API passes the app's own)")
    ap.add_argument("--plan-json", action="store_true",
                    help="like --plan-only, but the plan is JSON on stdout (app/api/experience.py reads it)")
    ap.add_argument("--default", action="store_true", dest="is_default",
                    help="this walk is the root walk: <out>/index.html (+ a copy at <out>/w/<slug>/)")
    args = ap.parse_args(argv)
    args.plan_only = args.plan_only or args.plan_json
    return args


def load_overrides(path, walk) -> dict:
    """Per-walk overrides. All optional except slug (when a file is given).
    Missing German text stays empty — never machine-translated."""
    raw = {}
    if path is not None:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            die(f"overrides {path}: {e}")
        if not isinstance(raw, dict):
            die(f"overrides {path}: top level must be an object")
        allowed = {"slug", "hide_species_ids", "more_walks", *OVERRIDE_TEXT_KEYS}
        unknown = sorted(k for k in raw if k not in allowed and not k.startswith("_"))
        if unknown:
            die(f"overrides {path}: unknown keys {unknown} (allowed: {sorted(allowed)})")
        if "slug" not in raw:
            die(f"overrides {path}: 'slug' is required")
    slug = raw.get("slug", f"walk-{walk['id']}")
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        die(f"overrides: slug {slug!r} must be lowercase letters/digits separated by single hyphens")
    ov = {"slug": slug}
    for k in OVERRIDE_TEXT_KEYS:
        v = raw.get(k, "")
        if not isinstance(v, str):
            die(f"overrides: {k} must be a string")
        ov[k] = v.strip()
    if not ov["title_en"]:
        ov["title_en"] = walk["name"]
    hide = raw.get("hide_species_ids", [])
    if not isinstance(hide, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in hide):
        die("overrides: hide_species_ids must be a list of species ids (integers)")
    ov["hide_species_ids"] = set(hide)
    more = raw.get("more_walks", [])
    if not isinstance(more, list):
        die("overrides: more_walks must be a list of {title, url}")
    ov["more_walks"] = []
    for m in more:
        if not (isinstance(m, dict) and isinstance(m.get("title"), str) and isinstance(m.get("url"), str)
                and m["title"].strip() and m["url"].strip()):
            die(f"overrides: more_walks entry {m!r} needs a non-empty title and url")
        url = m["url"].strip()
        if ":" in url.split("/")[0] and not url.lower().startswith(("https://", "http://")):
            die(f"overrides: more_walks url {url!r} — only http(s) or relative links")
        ov["more_walks"].append({"title": m["title"].strip(), "url": url})
    return ov


def saved_straight_ranges(route: dict, line) -> tuple:
    """Dashed vertex ranges of the saved line — walk_route.straight_ranges, the
    app's own reading rule (straight_ranges, or legacy straight_from). Invalid
    entries are drawn solid, as the app does; that is reported as a warning."""
    meta = route.get("foragingid") or {}
    raw = meta.get("straight_ranges", meta.get("straight_from"))
    if raw is None or not line:
        return [], None
    ranges = walk_route.straight_ranges(meta, len(line))
    if not ranges:
        return [], f"route straight legs {raw!r} are out of range for a {len(line)}-vertex line — drawn solid, as the app does"
    return ranges, None


# ── main build ───────────────────────────────────────────────────────────────

# Filled as main() runs so a --plan-json BuildError can still report what was
# known (walk, blockers) — see __main__.
_PARTIAL: dict = {}


def main(argv=None):
    args = parse_args(argv)
    _PARTIAL.clear()
    _PARTIAL["plan_json"] = args.plan_json
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    hide = set(cfg.get("hide_obs_ids", []))
    overrides = {int(k): int(v) for k, v in (cfg.get("photo_overrides") or {}).items()}
    warnings = []

    conn = sqlite3.connect(f"file:{Path(args.db).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    walk = conn.execute("SELECT * FROM saved_walks WHERE id = ?", (args.walk_id,)).fetchone()
    if not walk:
        die(f"saved_walks id {args.walk_id} not found")
    _PARTIAL["walk"] = {"id": walk["id"], "name": walk["name"]}
    ov = load_overrides(args.overrides, walk)
    hide_sp = ov["hide_species_ids"]
    route = json.loads(walk["route_geojson"]) if walk["route_geojson"] else {}

    out_root = args.out.resolve()
    page_dir = out_root if args.is_default else out_root / "w" / ov["slug"]
    mirror_dir = out_root / "w" / ov["slug"] if args.is_default else None
    site = cfg["site_url"].rstrip("/") + "/"
    canonical = site if args.is_default else f"{site}w/{ov['slug']}/"

    # Membership, exactly as the app computes it (walk_membership.compute) and
    # ONLY from it: saved stops + confirmed photos within the walk's buffer taken
    # since save / accepted from review, minus removed ones; species resolved from
    # the CURRENT observation rows (stale saved labels never used). Stop labels
    # ("7", "7a") as in the app.
    obs_cols = ("id, species_id, species_primary, review_status, identification_status, file_path, "
                "photo_taken_at, latitude, longitude, gps_accuracy_m, reviewed_at")
    saved_ids = sorted(wm.saved_obs_ids(dict(walk)))
    q = ",".join("?" * len(saved_ids))
    saved_rows = {r["id"]: dict(r) for r in conn.execute(
        f"SELECT {obs_cols} FROM observations WHERE id IN ({q})", saved_ids)} if saved_ids else {}
    bb = wm.search_bbox(dict(walk))
    nearby_rows = [dict(r) for r in conn.execute(
        f"SELECT {obs_cols} FROM observations WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
        bb)] if bb else []
    # Hand-added photos (accepted_obs_json) can lie outside the bbox — loaded by id.
    extra = sorted(wm.accepted_ids(dict(walk)) - set(saved_rows) - {r["id"] for r in nearby_rows})
    if extra:
        nearby_rows += [dict(r) for r in conn.execute(
            f"SELECT {obs_cols} FROM observations WHERE id IN ({','.join('?' * len(extra))})", extra)]
    membership = wm.compute(dict(walk), saved_rows, nearby_rows)
    mem_stops = membership["stops"]
    rows = dict(saved_rows)
    rows.update({r["id"]: r for r in nearby_rows if r["id"] not in rows})

    # Member observations, in walk order (the confirmed ones compute() put on a stop)
    obs_ids = list(dict.fromkeys(oid for st in mem_stops for sp in st["species"] for oid in sp["obs_ids"]))
    obs_order = [rows[i] for i in obs_ids if i in rows]
    missing_obs = [i for i in obs_ids if i not in rows]
    if missing_obs:
        warnings.append(f"membership references {len(missing_obs)} observations not loaded: {missing_obs}")
    sp_cache = {}
    def _species_row(sid):
        if sid not in sp_cache:
            r = conn.execute("SELECT * FROM species WHERE id = ?", (sid,)).fetchone() if sid is not None else None
            sp_cache[sid] = dict(r) if r else None
        return sp_cache[sid]
    # Rule 1 + 1b: the gate also needs the species row (AI-agreed harmless species are shown).
    passing = [o for o in obs_order if gates.obs_passes(o, hide, hide_sp, _species_row(o["species_id"]))]
    failing = [o for o in obs_order if not gates.obs_passes(o, hide, hide_sp, _species_row(o["species_id"]))]

    # Species (rule 1: human-confirmed members only)
    sp_obs = defaultdict(list)
    for o in passing:
        sp_obs[o["species_id"]].append(o)
    mem_species = {}                    # species_id -> {name, human, stops}
    for st in mem_stops:
        for sp in st["species"]:
            e = mem_species.setdefault(sp["species_id"], {"name": sp["name"], "human": False, "stops": []})
            e["human"] = e["human"] or sp["human"]
            if st["label"] not in e["stops"]:
                e["stops"].append(st["label"])
    ai_agreed = {sid: e for sid, e in mem_species.items() if not e["human"]}
    hidden_species = {}
    for sid in set(mem_species) - set(sp_obs):
        if sid in ai_agreed:
            continue                    # reported in its own section
        why = sorted({f"obs {o['id']}: " + ("hide_species_ids" if sid in hide_sp
                      else "hidden in config" if o["id"] in hide
                      else f"{o['review_status']}/{o['identification_status']}")
                      for o in obs_order if o["species_id"] == sid})
        hidden_species[sid] = why
    # Rule 7: an AI-agreed-only species that is toxic/deadly/unknown is on the
    # route but not on the page (no ☠ at its stop) → BLOCKER. The plan still
    # prints; the full build writes nothing and fails.
    blockers, ai_agreed_out = [], []
    for sid, e in sorted(ai_agreed.items(), key=lambda kv: kv[1]["name"] or ""):
        row = conn.execute("SELECT * FROM species WHERE id = ?", (sid,)).fetchone() if sid is not None else None
        sp_ai = dict(row) if row else None
        hazard = gates.unconfirmed_hazard(sp_ai)
        ai_agreed_out.append({
            "species_id": sid, "name": e["name"], "stops": e["stops"],
            "edibility_status": sp_ai.get("edibility_status") if sp_ai else None,
            "toxicity_severity": sp_ai.get("toxicity_severity") if sp_ai else None,
            "blocker": hazard,
            "included": sid in sp_obs,      # rule 1b: shown (harmless, not hidden)
        })
        if hazard:
            where = ("stop " if len(e["stops"]) == 1 else "stops ") + ", ".join(e["stops"])
            blockers.append(f"hazard on route not human-confirmed: {e['name']} {where}")
    # Rule 7 per stop: the per-species check above misses a toxic species that is
    # human-confirmed at one stop (so it IS on the page) but only AI-agreed at
    # another — that stop would carry no ☠. Checked per member observation.
    for st_m in mem_stops:
        for sp_m in st_m["species"]:
            bad = [oid for oid in sp_m["obs_ids"]
                   if oid not in rows     # not loaded → cannot show it is safe → blocks
                   or gates.obs_unconfirmed_hazard(rows[oid], _species_row(rows[oid]["species_id"]))]
            if bad:
                blockers.append(f"hazard at stop {st_m['label']} not human-confirmed: {sp_m['name']} "
                                f"(obs {', '.join(str(b) for b in bad)})")
    _PARTIAL["blockers"] = blockers
    # Per member observation that no human has confirmed (Stage C publish panel:
    # one row per photo with a "Confirm species" button). hazard is the per-stop
    # rule 7 test above (gates.obs_unconfirmed_hazard), so the panel's list and
    # the blockers can never disagree; shown is rule 1/1b (gates.obs_passes).
    ai_agreed_obs = []
    for st_m in mem_stops:
        for sp_m in st_m["species"]:
            for oid in sp_m["obs_ids"]:
                o = rows.get(oid)
                if o is not None and gates.is_human_confirmed(o):
                    continue
                sp_row = _species_row(o["species_id"]) if o is not None else None
                ai_agreed_obs.append({
                    "obs_id": oid, "species_id": o["species_id"] if o else None, "name": sp_m["name"],
                    "stop": st_m["label"],
                    "toxicity_severity": sp_row.get("toxicity_severity") if sp_row else None,
                    "hazard": o is None or gates.obs_unconfirmed_hazard(o, sp_row),
                    "shown": o is not None and gates.obs_passes(o, hide, hide_sp, sp_row),
                })

    unknown_hide = sorted(hide_sp - set(mem_species))
    if unknown_hide:
        warnings.append(f"hide_species_ids not on this walk (no effect): {unknown_hide}")

    species, ci_by_sp = {}, {}
    for sid in sorted(sp_obs):
        sp = dict(conn.execute("SELECT * FROM species WHERE id = ?", (sid,)).fetchone())
        ci = conn.execute("SELECT * FROM culinary_info WHERE species_id = ?", (sid,)).fetchone()
        species[sid] = sp
        ci_by_sp[sid] = dict(ci) if ci else {}
        for note in gates.taxonomy_warnings(sp):
            warnings.append(f"taxonomy: species {sid} {sp['scientific_name']}: {note}")

    texts = load_print_pdf_texts()

    # Photos (planned): one per species — override, else first passing obs on this
    # walk whose file exists; plus up to N more distinct files for the preview panel.
    photo_plan = {}                     # sid -> {"main": obs, "extras": [obs, ...]}
    for sid, olist in sp_obs.items():
        candidates = olist
        if sid in overrides:
            ovr = [o for o in olist if o["id"] == overrides[sid]]
            if not ovr:
                warnings.append(f"photo override species {sid} -> obs {overrides[sid]} is not a passing obs of this walk; ignored")
            candidates = ovr + [o for o in olist if o["id"] != overrides[sid]]
        chosen = next((o for o in candidates if o["file_path"] and Path(o["file_path"]).is_file()), None)
        if not chosen:
            warnings.append(f"species {sid} {species[sid]['scientific_name']}: no readable photo file")
            continue
        seen, extras = {chosen["file_path"]}, []
        for o in candidates:
            if len(extras) >= cfg.get("extra_photos_per_species", 3):
                break
            fp = o["file_path"]
            if o is chosen or not fp or fp in seen or not Path(fp).is_file():
                continue
            seen.add(fp)
            extras.append(o)
        photo_plan[sid] = {"main": chosen, "extras": extras}

    # Per-species public record (everything through gates). GateError (e.g. an
    # unverified 'edible' that would get an edible label) stops the build here.
    pub = {}
    for sid, sp in species.items():
        ci = ci_by_sp[sid]
        badge = gates.edibility_badge(sp, ci, conn, cfg)
        pp = photo_plan.get(sid)
        pub[sid] = {
            "id": sid,
            "sci": sp["scientific_name"],
            "en": en_name(sp),
            "de": first_name(sp.get("common_names_de")),
            "family": sp.get("family") or "",
            "kingdom": sp.get("kingdom") or "",
            "toxic": gates.is_toxic(sp),
            "deadly": gates.is_deadly(sp),
            "apiaceae": gates.is_apiaceae(sp),
            "badge": badge,
            "safety": gates.safety_texts(sp, ci, conn),
            "photo": f"photos/{sid}.jpg" if pp else None,
            "thumb": f"photos/{sid}_t.jpg" if pp else None,
            "n_obs": len(sp_obs[sid]),
            "extra": [{"photo": f"photos/{sid}_{n}.jpg", "thumb": f"photos/{sid}_{n}_t.jpg"}
                      for n in range(1, len(pp["extras"]) + 1)] if pp else [],
            # Months this species was photographed on THIS walk (from passing obs).
            "months": sorted({int(str(o["photo_taken_at"])[5:7]) for o in sp_obs[sid]
                              if o.get("photo_taken_at") and str(o["photo_taken_at"])[5:7].isdigit()}),
        }

    # Recipes — one teaser per species. Order: config recipe_source_priority
    # (human-authored sources first), then preferred, then oldest. The same dish
    # is never shown twice (one menu item can be stored against several species).
    prio = {src: i for i, src in enumerate(cfg.get("recipe_source_priority", []))}
    recipes_out, recipe_excluded, dishes_shown = [], [], set()
    for sid, sp in species.items():
        recs = [dict(r) for r in conn.execute(
            "SELECT id, title, body, status, is_preferred, is_medicinal_prep, source FROM species_recipes "
            "WHERE species_id = ?", (sid,))]
        recs.sort(key=lambda r: (prio.get(r["source"], len(prio)), -int(bool(r["is_preferred"])), r["id"]))
        picked = None
        for r in recs:
            ok, why = gates.recipe_allowed(sp, ci_by_sp[sid], r, conn, cfg)
            if not ok:
                recipe_excluded.append((r["id"], sp["scientific_name"], why))
                continue
            if picked is None:
                title = recipe_title(r)
                teaser = recipe_teaser(r, title, cfg.get("teaser_skip_patterns", []))
                if not title or not teaser:
                    recipe_excluded.append((r["id"], sp["scientific_name"], "no usable title/teaser line"))
                    continue
                if title.lower() in dishes_shown:
                    recipe_excluded.append((r["id"], sp["scientific_name"], "same dish already shown for another species"))
                    continue
                dishes_shown.add(title.lower())
                picked = {"recipe_id": r["id"], "species_id": sid, "dish": title, "line": teaser,
                          "source": r["source"],
                          # look-alike + prep beside the recipe (Fix B, 22 Oct 2026): curator text, uncut
                          "warnings": gates.recipe_warnings(sp, ci_by_sp[sid], conn)}
            else:
                recipe_excluded.append((r["id"], sp["scientific_name"], "another recipe already shown for this species"))
        if picked:
            recipes_out.append(picked)

    recipe_bank, recipe_bank_excluded = build_recipe_bank(conn, cfg)

    # Rule 8 (D3-01) per caution species: approved warning shown, recipes kept
    # or withheld. A caution species that is not human-verified never gets here
    # (edibility_badge raised GateError above — that is a block, not a withhold).
    caution_report = []
    for sid, sp in species.items():
        if not gates.is_caution(sp):
            continue
        caution_report.append({
            "species_id": sid, "scientific_name": sp["scientific_name"], "badge": pub[sid]["badge"]["kind"],
            "approved_warning": gates.caution_warning_shown(pub[sid]["safety"]),
            "recipes_kept": [r["recipe_id"] for r in recipes_out if r["species_id"] == sid],
            "recipes_withheld": [rid for rid, name, why in recipe_excluded
                                 if name == sp["scientific_name"] and why == gates.CAUTION_WITHHELD],
        })

    # Stops — from the computed membership. "n" is the app's stop label ("7",
    # "7a") so the page matches the walk panel and printed sheet. A stop whose
    # confirmed species are all hidden or AI-agreed-only stays as a numbered
    # point with no species; a stop with no confirmed species at all is skipped.
    stops, emptied_stops = [], []
    for st_m in mem_stops:
        if st_m["is_note"] or not st_m["species"]:
            continue
        sids = []
        for sp_m in st_m["species"]:
            for oid in sp_m["obs_ids"]:
                o = rows.get(oid)
                if o and gates.obs_passes(o, hide, hide_sp, _species_row(o["species_id"])) \
                        and o["species_id"] in pub and o["species_id"] not in sids:
                    sids.append(o["species_id"])
        if not sids:
            emptied_stops.append(st_m["label"])
        stops.append({"n": st_m["label"], "lat": st_m["lat"], "lng": st_m["lng"], "species": sids,
                      "toxic": any(pub[s]["toxic"] for s in sids)})

    first_stop = {}                      # species id → position of the first stop it appears at
    for pos, st in enumerate(stops):
        for sid in st["species"]:
            first_stop.setdefault(sid, pos)
    # Repeats: full species card only at the first stop in walk order; later
    # stops get a compact "Also here … — see stop N" line that keeps the safety
    # badge (gates.repeat_line_badge). Mirrors _walkRepeatSplit in
    # frontend/index.html — not shared: this static page cannot load the app's
    # JS, and the gate cross-checks below run here in Python. st["species"]
    # still lists EVERY species at the stop (☠ flag, hidden check, blockers).
    for st in stops:
        st["repeat"] = {}
        for sid in st["species"]:
            first_label = stops[first_stop[sid]]["n"]
            if first_label != st["n"]:
                st["repeat"][str(sid)] = {"first": first_label, "badge": gates.repeat_line_badge(pub[sid]["badge"])}
    missing_from_stops = [pub[s]["sci"] for s in pub if s not in first_stop]
    if missing_from_stops:
        warnings.append(f"species not on any stop (listed last): {missing_from_stops}")

    line = None
    for f in route.get("features") or []:
        if (f.get("geometry") or {}).get("type") == "LineString":
            line = f["geometry"]["coordinates"]
            break
    if not line:
        warnings.append("walk has no saved route geometry — only stops are drawn")
    straight_ranges, sf_warn = saved_straight_ranges(route, line)
    if sf_warn:
        warnings.append(sf_warn)
    # The line AS SHOWN in the app (walk_route.shown_line): the circular /
    # point-to-point view of the stored line, with the distance/time for that
    # shape. Same function the app's walk API uses, so the page matches the panel.
    walk_dist, walk_dur, loop_view = walk["distance_m"], walk["duration_min"], None
    if line:
        sh = walk_route.shown_line([w for w in json.loads(walk["waypoints_json"] or "[]") if isinstance(w, dict)],
                                   route, walk["distance_m"], walk["duration_min"])
        line, straight_ranges = sh["coordinates"], sh["straight_ranges"]
        walk_dist, walk_dur = sh["distance_m"], sh["duration_min"]
        loop_view = ("circular" if sh["circular"] else "point-to-point") + (
            "" if sh["line_closed"] == sh["circular"] else
            (" (saved line cut at the last stop)" if sh["line_closed"] else " (dashed straight leg back to stop 1 added)"))

    # Taxonomy (mirrors app/api/taxonomy.py placement rule)
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    fungi = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    unplaced = []
    for sid, sp in species.items():
        k = (sp.get("kingdom") or "").lower()
        ok = (sp.get("gbif_match_type") == "EXACT" and all(sp.get(c) for c in ("phylum", "class_", "order_", "family", "genus"))
              and k in ("plantae", "fungi"))
        if not ok:
            unplaced.append(sp["scientific_name"])
            continue
        tgt = raw if k == "plantae" else fungi
        tgt[sp["class_"]][sp["order_"]][sp["family"]][sp["genus"]].append(sp["scientific_name"])
    flat = lambda n: {c: {o: {f: dict(g) for f, g in fs.items()} for o, fs in os_.items()} for c, os_ in n.items()}
    taxonomy = {"RAW": {"Plantae": flat(raw)}, "FUNGI": flat(fungi), "UNPLACED": [],
                "OBS_STATE": {species[s]["scientific_name"]: "confirmed" for s in species}}
    units = sum(max(1, len(v)) for os_ in raw.values() for fs in os_.values() for gs in fs.values() for v in gs.values())
    slot_deg = min(8.0, 200.0 / max(units, 1))     # plant fan ≈ 200° (app: 0.65° × ~460 species ≈ 298°)

    species_meta = {p["sci"]: {"id": p["id"], "en": p["en"], "de": p["de"], "toxic": p["toxic"],
                               "badge": p["badge"], "thumb": p["thumb"]} for p in pub.values()}
    app_css, style_report = app_styles.load()
    tree_html, patches = build_tree_html(species_meta, taxonomy, slot_deg, style_report["root_css"])

    # Page
    impressum = cfg.get("impressum_url") or ""
    impressum_placeholder = (not impressum) or impressum.startswith("TODO")
    if impressum_placeholder:
        warnings.append("impressum_url is a PLACEHOLDER — footer shows 'Impressum (link to follow)'. Do not publish until set.")
    datenschutz = cfg.get("datenschutz_url") or ""
    datenschutz_placeholder = (not datenschutz) or datenschutz.startswith("TODO")
    if datenschutz_placeholder:
        warnings.append("datenschutz_url is a PLACEHOLDER — footer shows 'Datenschutz (link to follow)'. Do not publish until set.")
    data = {
        # Which publication this page is (Stage C: unpublish reads it back from the
        # site to know whether the front page belongs to this walk). Not shown.
        "slug": ov["slug"],
        "title": ov["title_en"], "title_de": ov["title_de"],
        "intro": ov["intro_en"], "intro_de": ov["intro_de"],
        "where": ov["where_en"], "where_de": ov["where_de"],
        "cta_label": cfg.get("cta_label", "Get in touch"),
        "contact_url": cfg["contact_url"],
        "impressum_url": None if impressum_placeholder else impressum,
        "datenschutz_url": None if datenschutz_placeholder else datenschutz,
        # distance/duration: the saved walk's own figures (the walk panel's), never a stop sum.
        "walk": {"name": walk["name"], "distance_m": walk_dist, "duration_min": walk_dur,
                 "line": line, "straight_ranges": straight_ranges, "stops": stops},
        # Walk order: the order plants are first met along the route (Melvin, 15 Oct 2026).
        # Toxicity is shown on each plant (badge/☠), never by list position.
        "species": [pub[s] for s in sorted(pub, key=lambda s: (first_stop.get(s, len(stops) + 1), pub[s]["en"] or pub[s]["sci"]))],
        "recipes": recipes_out,
        # Recipes tab (25 Oct 2026): every public recipe, teaser only (build_recipe_bank).
        "recipe_bank": recipe_bank,
        "disclaimer": cfg.get("disclaimer_override") or {"heading": texts["disclaimer_heading"],
                                                         "paras": texts["disclaimer_paras"]},
    }
    tpl = (HERE / "templates" / "index.html").read_text(encoding="utf-8")
    page = fill(tpl, {
        "TITLE": html.escape(ov["title_en"]),
        "LANG": html.escape(cfg.get("language", "en")),
        "CANONICAL": f'<link rel="canonical" href="{html.escape(canonical)}">',
        "LEAFLET_CSS": sri_tag("leaflet_css"),
        "LEAFLET_JS": sri_tag("leaflet_js"),
        "APP_STYLES": app_css,
        "DATA": json_inline(data),
    }, "index.html")
    preview_html, preview_info = build_preview(cfg, ov, data, pub, app_css)

    # Pre-write checks (run in --plan-only too)
    out_text = page + tree_html + preview_html
    if "<script" in preview_html.lower():
        die("preview.html must stay script-free")
    if not cfg.get("show_brand", False) and "landmemory" in out_text.lower():
        die("'LandMemory' found in output while show_brand is false")
    for p in pub.values():                                  # gate cross-checks on the final data
        if (p["toxic"] or p["apiaceae"]) and p["badge"]["kind"] in ("edible", "caution"):
            die(f"toxic/Apiaceae species with edible badge: {p['sci']}")
        if p["badge"]["kind"] in ("edible", "caution") and not gates.human_verified(species[p["id"]]):
            die(f"edible badge on a species not human-verified: {p['sci']}")
    for r in recipes_out:
        sp = species[r["species_id"]]
        if gates.is_apiaceae(sp):
            die(f"recipe {r['recipe_id']} for Apiaceae: {sp['scientific_name']}")
        if gates.is_toxic(sp) or not gates.toxicity_known_safe(sp) or not gates.human_verified(sp):
            die(f"recipe {r['recipe_id']} for non-eligible species {sp['scientific_name']}")
        if gates.is_caution(sp) and not gates.caution_warning_shown(pub[r["species_id"]]["safety"]):
            die(f"recipe {r['recipe_id']} for caution species without an approved warning: {sp['scientific_name']}")
    for sid in hide_sp:
        if sid in pub or any(sid in st["species"] for st in stops) or any(r["species_id"] == sid for r in recipes_out):
            die(f"hidden species {sid} still present in the output")
    # Recipes tab: the same gate cross-checks, re-asked of the final list, and no recipe text.
    bodies = {r["id"]: r["body"] for r in map(dict, conn.execute(
        "SELECT id, body FROM species_recipes WHERE id IN (%s)" % ",".join("?" * len(recipe_bank)),
        [b["recipe_id"] for b in recipe_bank]))} if recipe_bank else {}
    # Curator warnings are shown in full by design (Fix B) and a recipe body may
    # repeat them, so the leak check reads every bank field except "warnings".
    bank_json = json.dumps([{k: v for k, v in b.items() if k != "warnings"} for b in recipe_bank],
                           ensure_ascii=False)
    for b in recipe_bank:
        sp = dict(conn.execute("SELECT * FROM species WHERE id = ?", (b["species_id"],)).fetchone())
        if gates.is_apiaceae(sp) or gates.is_toxic(sp) or not gates.toxicity_known_safe(sp) \
                or not gates.human_verified(sp):
            die(f"Recipes tab: recipe {b['recipe_id']} for non-eligible species {sp['scientific_name']}")
        if b["recipe_id"] in set(cfg.get("exclude_recipe_ids", [])):
            die(f"Recipes tab: excluded recipe {b['recipe_id']} present")
        if set(b) & {"body", "ingredients", "method"}:
            die(f"Recipes tab: recipe {b['recipe_id']} carries recipe text fields")
        # No ingredients or method: a sample from the middle of every long body
        # paragraph (the one-line teaser cannot hold it) must not be in the tab's data.
        for para in re.split(r"\n\s*\n", bodies.get(b["recipe_id"]) or ""):
            para = para.strip()
            if len(para) < 150:
                continue
            mid = para[len(para) // 2: len(para) // 2 + 60]
            if mid not in b["line"] and mid in bank_json:
                die(f"Recipes tab: recipe {b['recipe_id']} body text found in the page data")
    for st in stops:                                        # a repeat line never drops a safety badge
        for k, rp in st["repeat"].items():
            if pub[int(k)]["badge"]["kind"] in gates.REPEAT_BADGE_KINDS and rp["badge"] != pub[int(k)]["badge"]:
                die(f"repeat line for {pub[int(k)]['sci']} at stop {st['n']} lost its {pub[int(k)]['badge']['kind']} badge")

    # ── write (skipped by --plan-only / --plan-json, and when a blocker stands) ──
    meta, size = None, 0
    if not args.plan_only and not blockers:
        page_dir.mkdir(parents=True, exist_ok=True)
        for name in OWNED_FILES:
            (page_dir / name).unlink(missing_ok=True)
        if (page_dir / "photos").exists():
            shutil.rmtree(page_dir / "photos")
        (page_dir / "photos").mkdir()
        photo_paths = []
        for sid, pp in photo_plan.items():
            src = Path(pp["main"]["file_path"])
            big, thumb = page_dir / "photos" / f"{sid}.jpg", page_dir / "photos" / f"{sid}_t.jpg"
            encode_photo(src, big, cfg["photo_long_edge"], cfg["jpeg_quality"])
            encode_photo(src, thumb, cfg["thumb_long_edge"], cfg["jpeg_quality"])
            photo_paths += [big, thumb]
            for n, o in enumerate(pp["extras"], 1):
                ex_big, ex_thumb = page_dir / "photos" / f"{sid}_{n}.jpg", page_dir / "photos" / f"{sid}_{n}_t.jpg"
                encode_photo(Path(o["file_path"]), ex_big, cfg.get("extra_photo_long_edge", 800), cfg["jpeg_quality"])
                encode_photo(Path(o["file_path"]), ex_thumb, cfg["thumb_long_edge"], cfg["jpeg_quality"])
                photo_paths += [ex_big, ex_thumb]
        (page_dir / "tree.html").write_text(tree_html, encoding="utf-8")
        (page_dir / "index.html").write_text(page, encoding="utf-8")
        (page_dir / "preview.html").write_text(preview_html, encoding="utf-8")
        meta = verify_no_metadata(photo_paths)
        if meta["exiftool_gps_tags"] or meta["pil_gps_tags"]:
            die(f"GPS metadata found in output images: {meta}")
        if mirror_dir is not None:
            # Root walk also served at /w/<slug>/; its canonical points to the root
            # (the same canonical the root page carries), so the copy is identical.
            if mirror_dir.exists():
                shutil.rmtree(mirror_dir)
            mirror_dir.mkdir(parents=True)
            for name in OWNED_FILES:
                shutil.copy2(page_dir / name, mirror_dir / name)
            shutil.copytree(page_dir / "photos", mirror_dir / "photos")
        size = sum(f.stat().st_size for d in filter(None, (page_dir, mirror_dir))
                   for f in [*(d / n for n in OWNED_FILES), *(d / "photos").rglob("*")] if f.is_file())

    n_main = len(photo_plan); n_extra = sum(len(pp["extras"]) for pp in photo_plan.values())
    if args.plan_json:
        # Same content as the text report below, structured. stdout is ONLY this JSON.
        plan = {
            "ok": True,
            "buildable": not blockers,
            "walk": {"id": walk["id"], "name": walk["name"], "title_en": ov["title_en"], "title_de": ov["title_de"],
                     "slug": ov["slug"], "is_default": args.is_default, "canonical": canonical,
                     "writes": str(page_dir), "mirror": str(mirror_dir) if mirror_dir else None},
            "distance": {"distance_m": walk_dist, "duration_min": walk_dur, "loop_view": loop_view,
                         "route_vertices": len(line or []), "straight_ranges": straight_ranges},
            "observations": {"member": len(obs_order), "pass": len(passing), "fail": len(failing)},
            "stops": [{"label": st["n"], "species_ids": st["species"], "toxic": st["toxic"],
                       "repeats": {k: {"first": v["first"], "badge": v["badge"]["kind"] if v["badge"] else None}
                                   for k, v in st["repeat"].items()}} for st in stops],
            "emptied_stops": emptied_stops,
            "public_species": [{
                "id": p["id"], "scientific_name": p["sci"], "en": p["en"], "badge": p["badge"]["kind"],
                "edibility_status": species[p["id"]].get("edibility_status"),
                "toxicity_severity": species[p["id"]].get("toxicity_severity"),
                "edibility_verified": bool(species[p["id"]].get("edibility_verified")),
                "verified_by": species[p["id"]].get("edibility_verified_by"),
                "apiaceae": p["apiaceae"], "safety": sorted(p["safety"]),
            } for p in data["species"]],
            "caution": caution_report,
            "ai_agreed_excluded": ai_agreed_out,
            "ai_agreed_obs": ai_agreed_obs,
            "hidden": [{"species_id": sid, "why": why} for sid, why in hidden_species.items()],
            "recipes": {"included": [{"recipe_id": r["recipe_id"], "species_id": r["species_id"], "dish": r["dish"],
                                      "source": r["source"]} for r in recipes_out],
                        "excluded": [{"recipe_id": rid, "species": name, "why": why}
                                     for rid, name, why in recipe_excluded]},
            # Recipes tab (25 Oct 2026): the full public list, for review before publishing.
            "recipe_bank": {"count": len(recipe_bank),
                            "list": [{"recipe_id": b["recipe_id"], "species_id": b["species_id"],
                                      "dish": b["dish"], "sci": b["sci"], "en": b["en"], "season": b["season"],
                                      "type": b["type"], "approved_at": b["approved_at"], "caution": b["caution"],
                                      "url": b["url"]} for b in recipe_bank],
                            "excluded": [{"recipe_id": rid, "species": name, "why": why}
                                         for rid, name, why in recipe_bank_excluded]},
            "tree": {"placed": len(species) - len(unplaced), "unplaced": unplaced},
            "images_planned": 2 * (n_main + n_extra),
            "warnings": warnings,
            "blockers": blockers,
            "failures": [{"obs_id": o["id"], "species_id": o["species_id"], "species": o["species_primary"],
                          "review_status": o["review_status"], "identification_status": o["identification_status"],
                          "human_confirmed": gates.is_human_confirmed(o)} for o in failing],
        }
        print(json.dumps(plan, ensure_ascii=False, default=str))
        return

    # Report
    print("=" * 72)
    print(f"Foraging Experience export — walk {walk['id']} '{walk['name']}'"
          + ("  [PLAN ONLY — no files written]" if args.plan_only else ""))
    print(f"Title: {ov['title_en']}" + (f"  |  DE: {ov['title_de']}" if ov["title_de"] else "  |  DE: (none)"))
    print(f"Slug: {ov['slug']}  default(root): {args.is_default}")
    print(f"Writes: {page_dir}/" + (f"  + copy {mirror_dir}/" if mirror_dir else "") + f"  canonical → {canonical}")
    print(f"Route: {len(line or [])} vertices; {loop_view or 'no line'}; distance {walk_dist} m / {walk_dur} min "
          f"(saved walk {walk['distance_m']} m / {walk['duration_min']} min); "
          + (f"dashed vertex ranges {straight_ranges} (straight legs)" if straight_ranges else "all solid"))
    print(f"Observations: {len(obs_order)} member, {len(passing)} pass gate, {len(failing)} fail")
    print(f"Species: {len(pub)} shown, {len(hidden_species)} hidden, {len(ai_agreed)} AI-agreed only")
    for sid, why in hidden_species.items():
        print(f"  hidden {sid}: {why}")
    print("AI-agreed only (rule 1b: harmless ones are shown; hazards block):" + ("" if ai_agreed else " none"))
    for a in ai_agreed_out:
        print(f"  {a['species_id'] if a['species_id'] is not None else '?':>4} {a['name']:<28} "
              f"stops {', '.join(a['stops'])}  toxicity {a['toxicity_severity']}"
              + ("  ← BLOCKER" if a["blocker"] else "  → shown" if a["included"] else "  (hidden)"))
    badges = Counter(p["badge"]["kind"] for p in pub.values())
    print(f"Badges: {dict(badges)}")
    for p in sorted(pub.values(), key=lambda p: p["badge"]["kind"]):
        extra = ",".join(k for k in p["safety"]) or "-"
        print(f"  {p['id']:>4} {p['sci']:<28} {p['badge']['kind']:<9} safety:{extra}")
    n_warned = sum(c["approved_warning"] for c in caution_report)
    print(f"Caution species: {len(caution_report)} — {n_warned} with an approved warning, "
          f"{len(caution_report) - n_warned} without (their recipes are withheld)")
    for c in caution_report:
        state = "warning ✓" if c["approved_warning"] else "no approved warning"
        recs = "; ".join(filter(None, (f"recipes kept {c['recipes_kept']}" if c["recipes_kept"] else "",
                                       f"recipes WITHHELD {c['recipes_withheld']}" if c["recipes_withheld"] else "")))
        print(f"  {c['species_id']:>4} {c['scientific_name']:<28} {c['badge']:<9} {state:<20} {recs or 'no eligible recipes'}")
    print(f"Tree: {sum(1 for _ in species) - len(unplaced)} placed, {len(unplaced)} not placed (no lineage): {unplaced}")
    print(f"Tree patches applied ({len(patches)}): " + "; ".join(patches))
    print(f"Recipes: {len(recipes_out)} included, {len(recipe_excluded)} excluded")
    print(f"Recipes tab: {len(recipe_bank)} public recipes, {len(recipe_bank_excluded)} not public")
    for r in recipes_out:
        print(f"  + {r['recipe_id']:>4} {species[r['species_id']]['scientific_name']:<26} [{r['source']}] {r['dish']}")
        print(f"         \"{r['line']}\"")
    for rid, name, why in recipe_excluded:
        print(f"  - {rid:>4} {name:<26} {why}")
    print("Disclaimer: " + ("config disclaimer_override (web wording)" if cfg.get("disclaimer_override")
                              else "print_pdf.html verbatim"))
    print(f"App styles: {len(style_report['tokens'])} tokens, {len(style_report['rules'])} rules copied, "
          f"shell {style_report['shell']['background']}/{style_report['deep']['background']}, "
          f"badges toxic {style_report['badges']['toxic'][0]} edible {style_report['badges']['edible'][0]} "
          f"inedible {style_report['badges']['inedible'][0]}")
    print(f"Preview: hero {preview_info['hero']}; teasers {preview_info['recipes']}; "
          f"more walks {preview_info['more_walks'] or '(none — line hidden)'}")
    print(f"Stops: {len(stops)} ({sum(s['toxic'] for s in stops)} with ☠): "
          + ", ".join(s["n"] + ("☠" if s["toxic"] else "") for s in stops))
    if emptied_stops:
        print(f"  numbered points with no species shown (hidden / AI-agreed only): {emptied_stops}")
    if meta:
        print(f"Images: {meta['files']} written ({n_main} species × 2 sizes + {n_extra} extra photos × 2 sizes); "
              f"GPS tags exiftool={meta['exiftool_gps_tags']} PIL={meta['pil_gps_tags']}; "
              f"files with any EXIF: {len(meta['files_with_any_exif'])} {meta['files_with_any_exif'][:5]}")
        print(f"output size: {size/1024/1024:.2f} MB")
    else:
        print(f"Images (planned): {n_main} species × 2 sizes + {n_extra} extra photos × 2 sizes = {2 * (n_main + n_extra)} files")
    for w in warnings:
        print(f"WARNING: {w}")
    for b in blockers:
        print(f"BLOCKER: {b}")
    print("=" * 72)
    if blockers and not args.plan_only:
        die(f"{len(blockers)} blocker(s), nothing written: " + "; ".join(blockers))


if __name__ == "__main__":
    try:
        main()
    except (BuildError, gates.GateError, app_styles.StyleDrift) as e:
        if _PARTIAL.get("plan_json"):
            # The plan could not be completed; stdout stays JSON for the API.
            print(json.dumps({"ok": False, "buildable": False, "build_error": str(e),
                              "walk": _PARTIAL.get("walk"), "blockers": _PARTIAL.get("blockers", [])},
                             ensure_ascii=False, default=str))
        print(f"BUILD FAILED: {e}", file=sys.stderr)
        sys.exit(1)
