"""
Batch 15 (P15 + P5) — one escaper, safe inline-handler arguments, one names rule.

  * static/js/esc.js lmEsc: the 5-char table, null/undefined → '', 0 → '0';
    identical to app/services/markdown.esc.
  * lmJsArg round-trips hostile strings: decode the attribute the way the HTML
    parser does, evaluate it as JS, and get the original string back (the old
    '${_esc(x).replace(/'/g, "\\'")}' pattern breaks on an apostrophe once the
    escaper is 5-char).
  * No page or module keeps its own escape logic: every helper is a one-line
    delegate to window.lmEsc, and every page that escapes loads esc.js before
    any other script. No _esc(…).replace(/'/g, "\\'") handler argument is left.
  * spPickCommon (JS) == display_common_name (Python) on every shape; the server
    picks (find, personal_lists, seasonal_returns, edibility, lists_pdf) go
    through display_common_name — the PDF honours preferred_common_name.

Run from project root:  python tests/test_batch15_esc_names.py
"""
import html as _html
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.models.species import display_common_name  # noqa: E402
from app.services.markdown import esc as py_esc  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def _src(p):
    if p == "frontend/index.html":   # batch 16: split page, read re-inlined
        from index_source import index_source
        return index_source()
    return pathlib.Path(ROOT, p).read_text(encoding="utf-8")


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    os.unlink(f.name)
    assert out.returncode == 0 and out.stdout.strip(), out.stderr
    return json.loads(out.stdout.strip().split("\n")[-1])


HOSTILE = ["O'Brien", 'a"b', "</script><b>x</b>", "back\\slash", "line sep", "&amp; already",
           "${x} `tick`", "", "Ünïcödé — St John's wort", "'); alert(1); ('"]


def test_lmesc_table_and_python_twin():
    cases = HOSTILE + [None, 0, 12.5, False]
    js = _jsc("var window = this;\n" + _src("frontend/static/js/esc.js") +
              "\nprint(JSON.stringify(" + json.dumps(cases) + ".map(window.lmEsc)));")
    assert js[cases.index(None)] == "" and js[cases.index(0)] == "0"
    assert js[0] == "O&#39;Brien" and js[1] == "a&quot;b" and js[2].startswith("&lt;/script&gt;")
    py = [py_esc(c) if not isinstance(c, bool) else py_esc(str(c).lower()) for c in cases]
    assert js == py, (js, py)


def test_lmjsarg_round_trips_through_the_attribute():
    script = ("var window = this;\n" + _src("frontend/static/js/esc.js") +
              "\nprint(JSON.stringify(" + json.dumps(HOSTILE) + ".map(window.lmJsArg)));")
    args = _jsc(script)
    for raw, arg in zip(HOSTILE, args):
        assert "'" not in arg and '"' not in arg and "<" not in arg, arg      # attribute-safe either quoting
        decoded = _html.unescape(arg)                                       # what the handler's JS sees
        back = _jsc("print(JSON.stringify([" + decoded + "]));")[0]
        assert back == raw, (raw, arg, back)


ESCAPING_PAGES = ("about", "encounters", "index", "lists", "print", "recipes", "review", "scan", "seasons",
                  "settings", "sightings", "species", "workshops")
MODULES = ("md.js", "species-names.js", "safety-gate.js", "guest-notes.js", "hazard-ack.js", "walk-publish.js",
           "dry-run.js", "job-status-widget.js", "reidentify.js", "seasonal-returns.js", "encounters-main.js")


def test_every_escaping_page_loads_esc_js_first():
    for pg in ESCAPING_PAGES:
        s = _src(f"frontend/{pg}.html")
        first = re.search(r"<script\b[^>]*>", s).group(0)
        assert first == '<script src="/static/js/esc.js">', (pg, first)
    # a module that calls lmEsc is never loaded by a page without esc.js
    for f in pathlib.Path(ROOT, "frontend").glob("*.html"):
        s = f.read_text(encoding="utf-8")
        if any(f"/static/js/{m}" in s for m in MODULES) or "site-header.js" in s:
            assert '<script src="/static/js/esc.js"></script>' in s, f.name


def test_no_local_escape_logic_left():
    files = list(pathlib.Path(ROOT, "frontend").glob("*.html")) + list(pathlib.Path(ROOT, "frontend/static/js").rglob("*.js"))   # rglob: static/js/index/* (batch 16)
    for f in files:
        if f.name == "esc.js":
            continue
        s = f.read_text(encoding="utf-8")
        assert not re.search(r"replace\(/&/g", s), f.name
        assert not re.search(r"replace\(/\[&<>\"']/g", s), f.name
        # escape-THEN-replace (the 4-char-only pattern); replace-then-escape is safe
        assert not re.search(r"(_esc|_resc)\((?:[^()]|\([^()]*\))*\)\.replace\(/'/g", s), f.name
    delegates = [("frontend/index.html", "_esc"), ("frontend/index.html", "_escHtml"), ("frontend/review.html", "_resc"),
                 ("frontend/species.html", "_esc"), ("frontend/lists.html", "_esc"), ("frontend/print.html", "_esc"),
                 ("frontend/scan.html", "_esc"), ("frontend/scan.html", "_escHtml"), ("frontend/settings.html", "_esc"),
                 ("frontend/static/js/safety-gate.js", "_h"), ("frontend/static/js/species-names.js", "esc"),
                 ("frontend/static/js/md.js", "esc"), ("frontend/static/js/encounters-main.js", "_esc")]
    for p, name in delegates:
        assert re.search(r"function " + name + r"\((\w+)\) \{ return window\.lmEsc\(\1\); \}", _src(p)), (p, name)
    # the recording IIFE's shadowing copy is gone (it resolves to the page's _esc)
    assert len(re.findall(r"function _esc\(", _src("frontend/index.html"))) == 1


def test_onclick_args_use_lmjsarg():
    idx = _src("frontend/index.html")
    for call in ("openRenameForm(${p.id}, ${lmJsArg(p.species_primary)})",
                 "enrichSpeciesFromMap(${lmJsArg(p.species_primary)}, ${p.id})",
                 "_addNoteTag(${lmJsArg(sp.scientific_name)})", "_removeNoteTag(${lmJsArg(t)})"):
        assert call in idx, call
    rv = _src("frontend/review.html")
    assert "const escArg       = lmJsArg(sp.scientific_name);" in rv and "aiDraftToggleCollapse(${escArg}, event)" in rv
    assert "'${escArg}'" not in rv and "'${sciArg}'" not in rv and "'${comArg}'" not in rv
    assert "openEnrichLightbox(${photoUrl})" in rv
    assert "pdApprove(${lmJsArg(sciName)}," in _src("frontend/species.html")
    ws = _src("frontend/workshops.html")
    assert "const safeName = lmJsArg(p.name);" in ws and "'${safeName}'" not in ws


NAME_CASES = [
    ("Wild garlic", '["ramsons"]'), (None, '["disc mayweed", "pineapple weed"]'), ("", ["st John's wort"]),
    ('["bear garlic"]', None), (None, None), ("  ", '["x"]'), (None, "nettle, stinging nettle"),
    (None, "[]"), (None, []), ("ägir", None), (None, '"single"'),
]


def test_sppickcommon_matches_display_common_name():
    js = _jsc("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/species-names.js") +
              "\nprint(JSON.stringify(" + json.dumps(NAME_CASES) + ".map(function (c) { return window.spPickCommon(c[0], c[1]); })));")
    py = [display_common_name(p, c) for p, c in NAME_CASES]
    assert js == py, list(zip(NAME_CASES, js, py))


def test_server_picks_use_the_one_rule():
    for p in ("app/api/find.py", "app/api/personal_lists.py", "app/services/seasonal_returns.py", "app/api/edibility.py"):
        s = _src(p)
        assert "display_common_name(" in s, p
        assert "_first_common_name" not in s, p
    assert _src("app/api/find.py").count("display_common_name(r.preferred_common_name, r.common_names) or None") == 3
    import app.api.lists_pdf as lp
    row = lp._flatten_species("Allium ursinum", {"species": {"preferred_common_name": "wild garlic",
                                                             "common_names": ["ramsons"]}, "culinary": {}}, {})
    assert row["common_name"] == "Wild garlic", row["common_name"]          # was "Ramsons" (P5)
    row = lp._flatten_species("Allium ursinum", None, {"Allium ursinum": {"common_names": ["ramsons"]}})
    assert row["common_name"] == "Ramsons", row["common_name"]
    assert "display_common_name(sp.get('preferred_common_name') or base.get('preferred_common_name'), common_names)" \
        in _src("app/api/lists_pdf.py")


def test_js_pick_sites_use_sppickcommon():
    idx = _src("frontend/index.html")
    assert "common_names[0]" not in re.sub(r"\.toLowerCase\(\)\.includes|//.*", "", idx.replace(
        "((sp.common_names && sp.common_names[0]) || '').toLowerCase()", "")), "index still picks common_names[0]"
    ls = _src("frontend/lists.html")
    assert ls.count("spPickCommon(") >= 5
    em = _src("frontend/static/js/encounters-main.js")
    assert "spNameText(sp.scientific_name, spPickCommon(sp.preferred_common_name, sp.common_names))" in em
    for pg in ("encounters", "seasons"):
        assert '<script src="/static/js/species-names.js"></script>' in _src(f"frontend/{pg}.html"), pg



def test_one_service_worker_bump_for_the_final_pass():
    sw = _src("frontend/static/sw.js")
    assert "const CACHE_VERSION  = 'foragingid-v22';" in sw
    assert "const SPECIES_CACHE  = 'foragingid-species-4';" in sw          # /api/species/ thumbnails (17-B3)
    shell = sw[sw.index("const APP_SHELL = ["):sw.index("];", sw.index("const APP_SHELL = ["))]
    for f in ("/static/js/esc.js", "/static/js/md.js", "/static/js/species-names.js", "/static/js/safety-gate.js"):
        assert f"'{f}'" in shell, f
    assert shell.index("'/static/js/esc.js'") < shell.index("'/static/js/safety-gate.js'")

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
