#!/usr/bin/env python3
"""
Foraging Experience — static export of one saved walk.

    ~/foragingid-venv/bin/python scripts/experience_export/export.py

Reads data/foragingid.db READ-ONLY (?mode=ro), never the app server. Writes
dist/ (gitignored): index.html + tree.html with all data inlined as JSON (no
fetch), and photos/ re-encoded with EXIF stripped. Every publish decision goes
through gates.py.

Reused (not forked) at build time, so the export follows the app:
  - frontend/taxonomy.html  <style> + main <script>, with anchored patches
    (each must match exactly once or the build fails) — see TREE_PATCHES.
  - app/templates/print_pdf.html  final-disclaimer text (verbatim) and the
    toxic fallback sentence (verbatim).
"""
from __future__ import annotations

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
import gates  # noqa: E402
import app_styles  # noqa: E402

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
    p = (sp.get("preferred_common_name") or "").strip()
    if p and not p.startswith("["):
        return p
    return first_name(sp.get("preferred_common_name") or sp.get("common_names"))


def json_inline(obj) -> str:
    """JSON safe to embed inside a <script> element."""
    return (json.dumps(obj, ensure_ascii=False)
            .replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


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
    fb = re.search(r"preparation_warnings or '([^']+)'", src)
    if not fb:
        die("print_pdf.html: toxic fallback sentence not found")
    return {"disclaimer_heading": m.group(1).strip(),
            "disclaimer_paras": [p.strip() for p in paras],
            "toxic_fallback": fb.group(1)}


# ── recipe teaser (approved text only — never newly written) ─────────────────

def recipe_title(rec: dict) -> str:
    if (rec.get("title") or "").strip():
        return rec["title"].strip()
    for line in (rec.get("body") or "").splitlines():
        t = line.strip().strip("#").strip().strip("*").strip()
        if t:
            return t
    return ""


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
    out = (tpl.replace("{{TAXONOMY_STYLE}}", style.group(1))
              .replace("{{APP_ROOT}}", app_root_css)
              .replace("{{D3}}", sri_tag("d3_js"))
              .replace("{{DATA}}", "window.__EXPORT_TAXONOMY__ = " + json_inline(taxonomy) + ";\n"
                       "window.__EXPORT_SPECIES__ = " + json_inline(species_meta) + ";\n"
                       f"window.__EXPORT_GENUS_SLOT_DEG__ = {slot_deg:.4f};\n"
                       f"window.__EXPORT_TREE_COUNT__ = {tree_count};\n"
                       "window.__EXPORT_SKIP_CLASS_REDISTRIBUTION__ = true;\n")
              .replace("{{TAXONOMY_SCRIPT}}", script))
    return out, applied


# ── preview card (dist/preview.html — static, no JS) ─────────────────────────

def route_svg(line, stops, size=100, pad=8) -> str:
    """Small static route drawing from the saved route line (no map tiles)."""
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
    poly = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(xs, ys))
    dots = "".join(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="1.8" style="fill:var(--paper)"/>' for x, y in zip(sx, sy))
    start = f'<circle cx="{X(xs[0]):.1f}" cy="{Y(ys[0]):.1f}" r="3.2" style="fill:var(--amber)"/>' if line else ""
    return (f'<svg class="route" viewBox="0 0 {size} {size}" role="img" aria-label="Route of the walk">'
            f'<polyline points="{poly}" style="fill:none;stroke:var(--leaf)" stroke-width="2.2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dots}{start}</svg>')


def build_preview(cfg: dict, data: dict, pub: dict, app_css: str) -> tuple[str, dict]:
    recipes = data["recipes"]
    want = cfg.get("preview_recipe_ids") or []
    if want:
        chosen = [r for rid in want for r in recipes if r["recipe_id"] == rid]
        missing = [rid for rid in want if rid not in {r["recipe_id"] for r in chosen}]
        if missing:
            die(f"preview_recipe_ids not among the page's gated recipes: {missing}")
    else:
        prio = {src: i for i, src in enumerate(cfg.get("recipe_source_priority", []))}
        chosen = sorted(recipes, key=lambda r: prio.get(r["source"], len(prio)))
    chosen = chosen[:3]

    hero_sid = cfg.get("preview_hero_species_id") or (chosen[0]["species_id"] if chosen else None)
    hero = pub.get(hero_sid) if hero_sid is not None else None
    if hero is None or not hero["photo"]:
        die(f"preview hero species {hero_sid} has no photo on this walk")
    if hero["toxic"]:
        die(f"preview hero must not be a toxic species ({hero['sci']})")

    km = f"{data['walk']['distance_m'] / 1000:.1f}" if data["walk"]["distance_m"] else None
    stats = [f"<span><b>{len(pub)}</b> species</span>", f"<span><b>{len(data['walk']['stops'])}</b> stops</span>"]
    if km:
        stats.append(f"<span><b>{km}</b> km</span>")
    teasers = "".join(
        f'<li><div class="dish">{html.escape(r["dish"])}</div>'
        f'<div class="plant">{html.escape(pub[r["species_id"]]["en"] or pub[r["species_id"]]["sci"])}</div></li>'
        for r in chosen)
    tpl = (HERE / "templates" / "preview.html").read_text(encoding="utf-8")
    out = (tpl.replace("{{APP_STYLES}}", app_css)
              .replace("{{LANG}}", html.escape(cfg.get("language", "en")))
              .replace("{{TITLE}}", html.escape(cfg["title"]))
              .replace("{{WHERE}}", html.escape(cfg.get("preview_where", "")))
              .replace("{{HERO}}", f'<img src="{hero["photo"]}" alt="{html.escape(hero["en"] or hero["sci"])}">')
              .replace("{{ROUTE_SVG}}", route_svg(data["walk"]["line"], data["walk"]["stops"]))
              .replace("{{STATS}}", "".join(stats))
              .replace("{{TEASERS}}", teasers))
    return out, {"hero": f"{hero['id']} {hero['sci']}", "recipes": [f"{r['recipe_id']} {r['dish']}" for r in chosen]}


# ── main build ───────────────────────────────────────────────────────────────

def main():
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    hide = set(cfg.get("hide_obs_ids", []))
    overrides = {int(k): int(v) for k, v in (cfg.get("photo_overrides") or {}).items()}
    warnings = []

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    walk = conn.execute("SELECT * FROM saved_walks WHERE id = ?", (cfg["walk_id"],)).fetchone()
    if not walk:
        die(f"saved_walks id {cfg['walk_id']} not found")
    if walk["name"] != cfg["walk_name"]:
        die(f"saved_walks id {cfg['walk_id']} is '{walk['name']}', config says '{cfg['walk_name']}'")
    obs_ids = json.loads(walk["obs_ids_json"] or "[]")
    waypoints = json.loads(walk["waypoints_json"] or "[]")
    route = json.loads(walk["route_geojson"]) if walk["route_geojson"] else {}

    # Observations, in walk order
    q = ",".join("?" * len(obs_ids))
    rows = {r["id"]: dict(r) for r in conn.execute(
        f"SELECT id, species_id, species_primary, review_status, identification_status, file_path, photo_taken_at "
        f"FROM observations WHERE id IN ({q})", obs_ids)}
    obs_order = [rows[i] for i in obs_ids if i in rows]
    missing_obs = [i for i in obs_ids if i not in rows]
    if missing_obs:
        warnings.append(f"walk references {len(missing_obs)} missing observations: {missing_obs}")
    passing = [o for o in obs_order if gates.obs_passes(o, hide)]
    failing = [o for o in obs_order if not gates.obs_passes(o, hide)]

    # Species (rule 1)
    sp_obs = defaultdict(list)
    for o in passing:
        sp_obs[o["species_id"]].append(o)
    all_walk_species = {o["species_id"] for o in obs_order if o["species_id"] is not None}
    hidden_species = {}
    for sid in all_walk_species - set(sp_obs):
        why = sorted({f"obs {o['id']}: " + ("hidden in config" if o["id"] in hide
                      else f"{o['review_status']}/{o['identification_status']}")
                      for o in obs_order if o["species_id"] == sid})
        hidden_species[sid] = why

    species, ci_by_sp = {}, {}
    for sid in sorted(sp_obs):
        sp = dict(conn.execute("SELECT * FROM species WHERE id = ?", (sid,)).fetchone())
        ci = conn.execute("SELECT * FROM culinary_info WHERE species_id = ?", (sid,)).fetchone()
        species[sid] = sp
        ci_by_sp[sid] = dict(ci) if ci else {}

    texts = load_print_pdf_texts()

    # Fresh dist/
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "photos").mkdir(parents=True)

    # Photos: one per species — override, else first passing obs on this walk whose file exists
    photo_report, photo_paths = [], []
    for sid, olist in sp_obs.items():
        candidates = olist
        if sid in overrides:
            ov = [o for o in olist if o["id"] == overrides[sid]]
            if not ov:
                warnings.append(f"photo override species {sid} -> obs {overrides[sid]} is not a passing obs of this walk; ignored")
            candidates = ov + [o for o in olist if o["id"] != overrides[sid]]
        chosen = next((o for o in candidates if o["file_path"] and Path(o["file_path"]).is_file()), None)
        if not chosen:
            warnings.append(f"species {sid} {species[sid]['scientific_name']}: no readable photo file")
            species[sid]["_photo"] = None
            continue
        big, thumb = DIST / "photos" / f"{sid}.jpg", DIST / "photos" / f"{sid}_t.jpg"
        encode_photo(Path(chosen["file_path"]), big, cfg["photo_long_edge"], cfg["jpeg_quality"])
        encode_photo(Path(chosen["file_path"]), thumb, cfg["thumb_long_edge"], cfg["jpeg_quality"])
        photo_paths += [big, thumb]
        species[sid]["_photo"] = {"obs_id": chosen["id"]}
        photo_report.append((sid, chosen["id"]))
        # Up to N more photos of this species from THIS walk's passing observations
        # (same gate as everything else), for the Plants preview panel. Distinct files only.
        seen, extras = {chosen["file_path"]}, []
        for o in candidates:
            if len(extras) >= cfg.get("extra_photos_per_species", 3):
                break
            fp = o["file_path"]
            if o is chosen or not fp or fp in seen or not Path(fp).is_file():
                continue
            seen.add(fp)
            n = len(extras) + 1
            ex_big, ex_thumb = DIST / "photos" / f"{sid}_{n}.jpg", DIST / "photos" / f"{sid}_{n}_t.jpg"
            encode_photo(Path(fp), ex_big, cfg.get("extra_photo_long_edge", 800), cfg["jpeg_quality"])
            encode_photo(Path(fp), ex_thumb, cfg["thumb_long_edge"], cfg["jpeg_quality"])
            photo_paths += [ex_big, ex_thumb]
            extras.append({"photo": f"photos/{sid}_{n}.jpg", "thumb": f"photos/{sid}_{n}_t.jpg"})
        species[sid]["_extras"] = extras

    # Per-species public record (everything through gates)
    pub = {}
    for sid, sp in species.items():
        ci = ci_by_sp[sid]
        badge = gates.edibility_badge(sp, ci, conn, cfg)
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
            "safety": gates.safety_texts(sp, ci, conn, texts["toxic_fallback"]),
            "photo": f"photos/{sid}.jpg" if sp.get("_photo") else None,
            "thumb": f"photos/{sid}_t.jpg" if sp.get("_photo") else None,
            "n_obs": len(sp_obs[sid]),
            "extra": sp.get("_extras") or [],
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
                          "source": r["source"]}
            else:
                recipe_excluded.append((r["id"], sp["scientific_name"], "another recipe already shown for this species"))
        if picked:
            recipes_out.append(picked)

    # Stops — species from CURRENT observation IDs (stored labels can be stale)
    stops = []
    for i, wp in enumerate(waypoints):
        if wp.get("type") == "note":
            continue
        ids = wp.get("obs_ids") or ([wp["obs_id"]] if wp.get("obs_id") is not None else [])
        sids = []
        for oid in ids:
            o = rows.get(oid)
            if o and gates.obs_passes(o, hide) and o["species_id"] in pub and o["species_id"] not in sids:
                sids.append(o["species_id"])
        if not sids:
            continue
        stops.append({"n": len(stops) + 1, "lat": wp["lat"], "lng": wp["lng"], "species": sids,
                      "toxic": any(pub[s]["toxic"] for s in sids)})

    first_stop = {}
    for st in stops:
        for sid in st["species"]:
            first_stop.setdefault(sid, st["n"])
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
    (DIST / "tree.html").write_text(tree_html, encoding="utf-8")

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
        "title": cfg["title"], "intro": cfg.get("intro", ""), "cta_label": cfg.get("cta_label", "Get in touch"),
        "contact_url": cfg["contact_url"],
        "impressum_url": None if impressum_placeholder else impressum,
        "datenschutz_url": None if datenschutz_placeholder else datenschutz,
        "walk": {"name": walk["name"], "distance_m": walk["distance_m"], "duration_min": walk["duration_min"],
                 "line": line, "stops": stops},
        # Walk order: the order plants are first met along the route (Melvin, 15 Oct 2026).
        # Toxicity is shown on each plant (badge/☠), never by list position.
        "species": [pub[s] for s in sorted(pub, key=lambda s: (first_stop.get(s, len(stops) + 1), pub[s]["en"] or pub[s]["sci"]))],
        "recipes": recipes_out,
        "disclaimer": cfg.get("disclaimer_override") or {"heading": texts["disclaimer_heading"],
                                                         "paras": texts["disclaimer_paras"]},
    }
    tpl = (HERE / "templates" / "index.html").read_text(encoding="utf-8")
    page = (tpl.replace("{{TITLE}}", html.escape(cfg["title"]))
               .replace("{{LANG}}", html.escape(cfg.get("language", "en")))
               .replace("{{CANONICAL}}", f'<link rel="canonical" href="{html.escape(cfg["canonical_url"])}">'
                        if cfg.get("canonical_url") else "")
               .replace("{{LEAFLET_CSS}}", sri_tag("leaflet_css"))
               .replace("{{LEAFLET_JS}}", sri_tag("leaflet_js"))
               .replace("{{APP_STYLES}}", app_css)
               .replace("{{DATA}}", json_inline(data)))
    (DIST / "index.html").write_text(page, encoding="utf-8")
    preview_html, preview_info = build_preview(cfg, data, pub, app_css)
    (DIST / "preview.html").write_text(preview_html, encoding="utf-8")

    # Post-build checks
    meta = verify_no_metadata(photo_paths)
    out_text = page + tree_html + preview_html
    if "<script" in preview_html.lower():
        die("preview.html must stay script-free")
    if not cfg.get("show_brand", False) and "landmemory" in out_text.lower():
        die("'LandMemory' found in output while show_brand is false")
    leftovers = [m for m in ("{{", "}}") if m in page or m in tree_html.replace("${", "")]
    if "{{" in page or "{{" in tree_html or "{{" in preview_html:
        die(f"unreplaced template placeholder in output: {leftovers}")
    if meta["exiftool_gps_tags"] or meta["pil_gps_tags"]:
        die(f"GPS metadata found in output images: {meta}")
    for p in pub.values():                                  # gate cross-checks on the final data
        if p["toxic"] and p["badge"]["kind"] in ("edible", "caution"):
            die(f"toxic species with edible badge: {p['sci']}")
        if cfg.get("apiaceae_id_only") and p["apiaceae"] and p["badge"]["kind"] in ("edible", "caution"):
            die(f"Apiaceae with edible badge while apiaceae_id_only: {p['sci']}")
    for r in recipes_out:
        sp = species[r["species_id"]]
        if cfg.get("apiaceae_id_only") and gates.is_apiaceae(sp):
            die(f"recipe {r['recipe_id']} for Apiaceae while apiaceae_id_only: {sp['scientific_name']}")
        if gates.is_toxic(sp) or not gates.human_verified(sp):
            die(f"recipe {r['recipe_id']} for non-eligible species {sp['scientific_name']}")

    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())

    # Report
    print("=" * 72)
    print(f"Foraging Experience export — walk {walk['id']} '{walk['name']}'")
    print(f"Observations: {len(obs_order)} on walk, {len(passing)} pass gate, {len(failing)} fail")
    print(f"Species: {len(pub)} shown, {len(hidden_species)} hidden")
    for sid, why in hidden_species.items():
        print(f"  hidden {sid}: {why}")
    badges = Counter(p["badge"]["kind"] for p in pub.values())
    print(f"Badges: {dict(badges)}")
    for p in sorted(pub.values(), key=lambda p: p["badge"]["kind"]):
        extra = ",".join(k for k in p["safety"]) or "-"
        print(f"  {p['id']:>4} {p['sci']:<28} {p['badge']['kind']:<9} safety:{extra}")
    print(f"Tree: {sum(1 for _ in species) - len(unplaced)} placed, {len(unplaced)} not placed (no lineage): {unplaced}")
    print(f"Tree patches applied ({len(patches)}): " + "; ".join(patches))
    print(f"Recipes: {len(recipes_out)} included, {len(recipe_excluded)} excluded")
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
    print(f"Preview: hero {preview_info['hero']}; teasers {preview_info['recipes']}")
    print(f"Stops: {len(stops)} ({sum(s['toxic'] for s in stops)} with ☠)")
    n_extra = sum(len(p["extra"]) for p in pub.values())
    print(f"Images: {meta['files']} written ({len(photo_report)} species × 2 sizes + {n_extra} extra photos × 2 sizes); "
          f"GPS tags exiftool={meta['exiftool_gps_tags']} PIL={meta['pil_gps_tags']}; "
          f"files with any EXIF: {len(meta['files_with_any_exif'])} {meta['files_with_any_exif'][:5]}")
    print(f"dist size: {size/1024/1024:.2f} MB  ({DIST})")
    for w in warnings:
        print(f"WARNING: {w}")
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except (BuildError, app_styles.StyleDrift) as e:
        print(f"BUILD FAILED: {e}", file=sys.stderr)
        sys.exit(1)
