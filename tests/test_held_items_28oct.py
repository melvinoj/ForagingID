"""
Held items, 28 Oct 2026.

1. lists.html removeFromList: the × button passes the name with lmJsArg
   (decision 10, batch 15), not the old escape-then-apostrophe pattern. The
   page's own template is rendered in JavaScriptCore with hostile and real
   apostrophe names, the attribute is HTML-decoded as a browser does it, the
   handler is run, and removeFromList must receive the name intact.
2. sw.js: tokens.css and site-header.css are in APP_SHELL; cache is v20.

Static + jsc checks only — the live checks are Melvin's.
Run from project root:  python tests/test_held_items_28oct.py
"""
import html
import json
import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"

NAMES = [
    "Capsella bursa-pastoris (shepherd's purse)",
    "St John's wort",
    "lady's smock",
    "Bad'name\" <script>alert(1)</script> & </textarea></div>",
    "back\\slash \\' and   line sep",
]

TPL = "onclick=\"removeFromList(${lmJsArg(name)})\""


def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        out = subprocess.run([JSC, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().split("\n")[-1])   # not splitlines: U+2028 in a name


def test_remove_button_uses_lmjsarg_and_old_pattern_is_gone():
    src = _src("frontend/lists.html")
    assert TPL in src
    assert "removeFromList('${" not in src


def test_remove_button_round_trips_hostile_and_apostrophe_names():
    core = "var window = this;\n" + _src("frontend/static/js/esc.js") + "\nvar lmJsArg = window.lmJsArg;\n"
    for name in NAMES:
        out = _jsc(core + "var name = %s;\nprint(JSON.stringify(`<x %s>`));" % (json.dumps(name), TPL))
        assert "<script" not in out.lower(), out
        m = re.search(r'\sonclick="([^"]*)"', out)
        assert m, out
        handler = html.unescape(m.group(1))      # what the browser hands to the JS engine
        got = _jsc("var got = null; function removeFromList(n) { got = n; }\n"
                   "(function () { %s }).call({});\nprint(JSON.stringify(got));" % handler)
        assert got == name, (name, handler, got)


def test_app_shell_has_tokens_and_site_header_css_and_v20():
    sw = _src("frontend/static/sw.js")
    assert "const CACHE_VERSION  = 'foragingid-v22';" in sw
    shell = re.search(r"const APP_SHELL = \[(.*?)\n\];", sw, re.S).group(1)
    for f in ("/static/css/tokens.css", "/static/css/site-header.css"):
        assert f"'{f}'" in shell, f
        assert os.path.isfile(os.path.join(ROOT, "frontend", f.lstrip("/"))), f


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
