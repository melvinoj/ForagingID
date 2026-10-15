"""
App look for the Foraging Experience export — copied from the app's own
stylesheets AT BUILD TIME, never hand-copied, so the export follows the app.

Same discipline as export.py's TREE_PATCHES: every extraction is anchored and
must match exactly once (or the exact count given); if the app's CSS/JS drifts,
the build fails loudly instead of silently shipping stale or missing styles.
The app's full stylesheets are NOT linked — only the rules listed below.

Sources
  frontend/static/css/tokens.css  — the :root design tokens (verbatim)
  frontend/species.html            — dark page shell (#2a3330), species cards, headings
  frontend/lists.html              — deep shell colour (#1e2b28)
  frontend/index.html              — walk-panel stop cards / recipe strip (CSS), and
                                     the walk-panel edibility badge colours (inline in
                                     renderWalkPanel(), so read from the JS)
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOKENS_CSS = REPO / "frontend" / "static" / "css" / "tokens.css"
SPECIES_HTML = REPO / "frontend" / "species.html"
LISTS_HTML = REPO / "frontend" / "lists.html"
INDEX_HTML = REPO / "frontend" / "index.html"

TOKEN_NAMES = ("--ink", "--ground", "--paper", "--moss", "--moss-light", "--leaf", "--leaf-pale",
               "--hairline", "--damson", "--amber", "--water", "--alert",
               "--font-display", "--font-ui", "--touch-min")

# (source file, selector) — the rule is copied verbatim.
RULES = [
    (INDEX_HTML,   ".walk-stop-card"),
    (INDEX_HTML,   ".walk-stop-num"),
    (INDEX_HTML,   ".walk-stop-species"),
    (INDEX_HTML,   ".walk-stop-common"),
    (INDEX_HTML,   ".walk-stop-meta"),
    (INDEX_HTML,   ".walk-stop-recipe"),
    (INDEX_HTML,   ".walk-stop-recipe strong"),
    (INDEX_HTML,   ".walk-header h3"),
    (INDEX_HTML,   ".walk-header .walk-sub"),
    (SPECIES_HTML, ".species-card"),
    (SPECIES_HTML, ".species-card .common"),
    (SPECIES_HTML, ".species-card .sci-name"),
    (SPECIES_HTML, ".species-card .common-de"),
    (SPECIES_HTML, ".species-card .family"),
    (SPECIES_HTML, ".species-card .warn-badge"),
    (SPECIES_HTML, ".species-card .toxic-badge"),
    (SPECIES_HTML, "#list-view h2"),
    (SPECIES_HTML, "#list-view .subtitle"),
]


class StyleDrift(RuntimeError):
    pass


def _one(pattern: str, text: str, what: str, flags=0) -> re.Match:
    ms = list(re.finditer(pattern, text, flags))
    if len(ms) != 1:
        raise StyleDrift(f"{what}: anchor matched {len(ms)} times (expected 1) — app styles changed")
    return ms[0]


def _rule(src: Path, selector: str) -> str:
    text = src.read_text(encoding="utf-8")
    # Top-level rules only (4-space indent inside <style>); copies nested in
    # @media blocks sit deeper and are deliberately not matched.
    m = _one(r"(?m)^    " + re.escape(selector) + r"[ \t]*\{[^}]*\}", text, f"{src.name} '{selector}'")
    return m.group(0).strip()


def _body_colours(src: Path) -> dict:
    text = src.read_text(encoding="utf-8")
    m = _one(r"(?m)^[ \t]*body \{ font-family: [^;]+; background: (#[0-9a-fA-F]{6}); color: (#[0-9a-fA-F]{6});",
             text, f"{src.name} body rule")
    return {"background": m.group(1), "color": m.group(2)}


def _walk_badges() -> dict:
    """renderWalkPanel()'s inline badge colours (toxic + per-status)."""
    js = INDEX_HTML.read_text(encoding="utf-8")
    tox = _one(r"background:(#[0-9a-fA-F]{6});color:(#[0-9a-fA-F]{3,6})\">☠ \$\{_sev === 'deadly'", js,
               "index.html walk toxic badge")
    statuses = r"\$\{edib==='edible'\?'(#\w+)':edib==='toxic'\?'(#\w+)':edib==='inedible'\?'(#\w+)':edib==='medicinal'\?'(#\w+)':'(#\w+)'\}"
    bg = _one(r"background:" + statuses, js, "index.html walk badge backgrounds")
    fg = _one(r"color:" + statuses, js, "index.html walk badge colours")
    shape = _one(r"<span style=\"font-size:(0\.\d+rem);padding:(\d+px \d+px);border-radius:(\d+px);font-weight:700;", js,
                 "index.html walk badge shape")
    return {
        "toxic":    (tox.group(1), tox.group(2)),
        "edible":   (bg.group(1), fg.group(1)),
        "inedible": (bg.group(3), fg.group(3)),
        "default":  (bg.group(5), fg.group(5)),
        "shape":    {"font_size": shape.group(1), "padding": shape.group(2), "radius": shape.group(3)},
    }


def load() -> tuple[str, dict]:
    """Returns (css, report). css = tokens + copied rules + badge classes."""
    tokens_src = TOKENS_CSS.read_text(encoding="utf-8")
    root = _one(r":root \{[^}]*\}", tokens_src, "tokens.css :root").group(0)
    missing = [t for t in TOKEN_NAMES if re.search(re.escape(t) + r"\s*:", root) is None]
    if missing:
        raise StyleDrift(f"tokens.css missing tokens: {missing}")
    tokens = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", root))

    shell = _body_colours(SPECIES_HTML)
    deep = _body_colours(LISTS_HTML)
    rules = [(f"{src.name}", sel, _rule(src, sel)) for src, sel in RULES]
    b = _walk_badges()

    h2_rule = next(r for _s, sel, r in rules if sel == "#list-view h2")
    heading = _one(r"color:\s*(#[0-9a-fA-F]{6})", h2_rule, "#list-view h2 color").group(1)
    warn_rule = next(r for _s, sel, r in rules if sel == ".species-card .warn-badge")
    warn_bg = _one(r"background:\s*(#[0-9a-fA-F]{6})", warn_rule, ".warn-badge background").group(1)
    warn_fg = _one(r"[^-]color:\s*(#[0-9a-fA-F]{6})", warn_rule, ".warn-badge color").group(1)
    num_rule = next(r for _s, sel, r in rules if sel == ".walk-stop-num")
    forest = _one(r"background:\s*(#[0-9a-fA-F]{6})", num_rule, ".walk-stop-num background").group(1)
    sh = b["shape"]
    badge_css = f"""
/* Edibility badges — colours read from index.html renderWalkPanel() at build time */
.badge {{ display:inline-block; font-size:{sh['font_size']}; padding:{sh['padding']}; border-radius:{sh['radius']};
  font-weight:600; background:{b['default'][0]}; color:{b['default'][1]}; }}
.badge.toxic, .badge.deadly {{ background:{b['toxic'][0]}; color:{b['toxic'][1]}; font-weight:700; }}
.badge.edible   {{ background:{b['edible'][0]}; color:{b['edible'][1]}; }}
.badge.inedible {{ background:{b['inedible'][0]}; color:{b['inedible'][1]}; }}
/* Apiaceae ID card: species.html .warn-badge colours */
.badge.apiaceae {{ background:{warn_bg}; color:{warn_fg}; font-weight:700; }}
/* caution: the walk panel has no caution colour — use the app's --amber token */
.badge.caution  {{ background:var(--amber); color:var(--ink); }}
"""
    root_css = ("/* ── frontend/static/css/tokens.css :root (verbatim) ── */\n" + root + "\n"
           + f"/* ── app shell colours: species.html body {shell}, lists.html body {deep} ── */\n"
           + f":root {{ --app-shell:{shell['background']}; --app-shell-deep:{deep['background']}; --app-text:{shell['color']};"
           + f" --app-toxic:{b['toxic'][0]}; --app-forest:{forest}; --app-heading:{heading}; }}\n")
    css = (root_css
           + "\n".join(f"/* {src} */\n{r}" for src, _sel, r in rules) + "\n" + badge_css)
    report = {"tokens": tokens, "shell": shell, "deep": deep, "badges": b, "forest": forest, "heading": heading,
              "root_css": root_css,
              "rules": [f"{src} {sel}" for src, sel, _ in rules]}
    return css, report
