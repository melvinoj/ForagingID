"""
Batch 16 — frontend/index.html split into static/css/index.css and nine
static/js/index/*.js files (28 Oct 2026, verbatim moves).

Guards the split's wiring; the behaviour checks are Melvin's (CHANGELOG
Browser checks).
Run from project root:  python tests/test_batch16_index_split.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from index_source import FRONTEND, INDEX_HTML, index_parts, index_source  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORDER = ["map-core", "pins-filters", "detail-card", "walk-build", "walk-panel",
         "walk-saved", "walk-alerts", "recording", "search-notes-find"]


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _app_shell():
    sw = _read(os.path.join(FRONTEND, "static", "sw.js"))
    m = re.search(r"const APP_SHELL = \[(.*?)\n\];", sw, re.S)
    return set(re.findall(r"(?m)^\s*'(/[^']*)',", m.group(1)))


def test_page_loads_the_css_and_the_nine_files_in_order():
    parts = [p for p, _f in index_parts()]
    assert parts == ["/static/css/index.css"] + [f"/static/js/index/{n}.js" for n in ORDER], parts
    for _p, f in index_parts():
        assert os.path.isfile(f) and os.path.getsize(f) > 0, f


def test_no_inline_style_or_script_body_left():
    html = _read(INDEX_HTML)
    assert "<style" not in html
    assert not re.search(r"<script>(?!</script>)", html), "an inline <script> body is back in index.html"


def test_split_scripts_sit_between_the_page_libraries_and_the_tail_scripts():
    html = _read(INDEX_HTML)
    srcs = re.findall(r'<script src="([^"]+)"', html)
    i0 = srcs.index("/static/js/index/map-core.js")
    assert srcs[i0 - 1] == "/static/js/walk-publish.js"
    assert srcs[i0 + len(ORDER)] == "/static/js/lightbox.js"
    assert srcs.index("/static/js/esc.js") == 0


def test_every_local_index_asset_is_in_app_shell():
    shell = _app_shell()
    html = _read(INDEX_HTML)
    local = [s for s in re.findall(r'<script src="(/static/[^"]+)"', html)]
    local += [h for h in re.findall(r'<link rel="stylesheet" href="(/static/css/index\.css)"', html)]
    missing = [s for s in local if s not in shell]
    assert not missing, missing


def test_re_inlined_page_has_one_script_and_one_style_block():
    src = index_source()
    assert src.count("  <style>\n") == 1 and src.count("  </style>\n") == 1
    assert src.count("<script>\n") == 1


def test_note_pin_zoom_handler_is_registered_after_its_function():
    # Prep commit 0cf780e: the only synchronous cross-file forward reference.
    js = _read(os.path.join(FRONTEND, "static", "js", "index", "search-notes-find.js"))
    assert js.index("function _rescaleNotePins()") < js.index("map.on('zoomend', _rescaleNotePins);")
    core = _read(os.path.join(FRONTEND, "static", "js", "index", "map-core.js"))
    assert "_rescaleNotePins" not in core


def test_export_styles_read_the_split_files():
    sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))
    import app_styles
    css, _report = app_styles.load()
    assert ".walk-stop-card" in css


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
