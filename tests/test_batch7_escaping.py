"""Batch 7 — source text renders as text on every innerHTML site found in the sweep.

Each site's template is read from the page itself (the test fails if the line
reverts), rendered in JavaScriptCore with the page's own _esc/_resc and hostile
source text, then checked two ways:
  - text: no live <script> element, and the visible text is the source text;
  - inline handler (onclick=…): the attribute is HTML-decoded the way a browser
    does it, the handler is run, and the function receives the source text intact.
"""
import html
import json
import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"

# Quotes of both kinds, markup, an ampersand, and a textarea breakout.
H = "Bad'name\" <script>alert(1)</script> & </textarea></div>"


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
    return json.loads(out.stdout.strip().splitlines()[-1])


def _fn(src, name):
    """Source of a top-level `function name(...) {...}` (brace-matched)."""
    m = re.search(r"^function %s\(" % re.escape(name), src, re.M)
    assert m, f"function {name} not found"
    i = src.index("{", m.end())
    depth = 0
    for k in range(i, len(src)):
        depth += {"{": 1, "}": -1}.get(src[k], 0)
        if depth == 0:
            return src[m.start():k + 1]
    raise AssertionError(name)


def _helpers(page):
    src = _src(page)
    if page.endswith("review.html"):
        return _fn(src, "_resc") + "\nconst _esc = _resc;\n"
    return _fn(src, "_esc") + "\n"


VARS = """
var H = %s;
var obs = { id: 1, species_primary: H, reviewer_notes: H, file_path: '/photos/' + H };
var fname = H, thumbName = H, name = H, sciName = H, t = H, url = '/thumbnails/' + H;
var sp = { scientific_name: H, id: 5 };
var p = { id: 3, species_primary: H };
var d = { field_name: 'taste_notes', id: 7 };
var item = { id: 4 };
var x = { scientific_name: H };
var e = { message: H };
""" % json.dumps(H)

# (page, setup statements copied from the page, template copied from the page,
#  check). check: ("text",) or ("call", function name, arg index, decode?)
SITES = [
    # review.html
    ("frontend/review.html", [], '<div class="sp-common">${_esc(common)}</div>', ("text",), "var common = H;"),
    ("frontend/review.html", ["const spPrimSafe   = _resc(obs.species_primary || '').replace(/'/g, \"\\\\'\");"],
     "onclick=\"itisAcceptRename('${spPrimSafe}', 'species_id')\"", ("call", "itisAcceptRename", 0), ""),
    ("frontend/review.html", ["const notesVal = _resc(obs.reviewer_notes || '');"],
     '<textarea id="notes-${obs.id}" placeholder="Add reviewer notes…" rows="2">${notesVal}</textarea>',
     ("textarea",), ""),
    ("frontend/review.html", [], '<div class="card-path" title="${_esc(obs.file_path)}">${_esc(fname)}</div>',
     ("text",), ""),
    ("frontend/review.html", [], "onclick=\"shareCardPhoto(${obs.id},'${_resc(thumbName).replace(/'/g, \"\\\\'\")}')\"",
     ("call", "shareCardPhoto", 1), ""),
    ("frontend/review.html", ["  const escName      = _resc(sp.scientific_name);",
                              "  const escArg       = escName.replace(/'/g, \"\\\\'\");"],
     "onclick=\"aiDraftToggleCollapse('${escArg}', event)\"", ("call", "aiDraftToggleCollapse", 0), ""),
    ("frontend/review.html", ["  const escName  = _resc(sciName);", "  const escArg   = escName.replace(/'/g, \"\\\\'\");"],
     "onclick=\"approveDraftField('${escArg}', '${d.field_name}', ${d.id}, false)\"",
     ("call", "approveDraftField", 0), ""),
    ("frontend/review.html", [], "onclick=\"openEnrichLightbox('${_resc(url).replace(/'/g, \"\\\\'\")}')\"",
     ("call", "openEnrichLightbox", 0, "/thumbnails/"), ""),
    ("frontend/review.html", [], "onclick=\"enrichApproveCard('${_resc(sp.scientific_name).replace(/'/g, \"\\\\'\")}', this)\"",
     ("call", "enrichApproveCard", 0), ""),
    ("frontend/review.html", ["        const spSafe = _resc(sp.scientific_name).replace(/'/g, \"\\\\'\");"],
     "onclick=\"itisAcceptRename('${spSafe}', 'enrich')\"", ("call", "itisAcceptRename", 0), ""),
    ("frontend/review.html", [], '<div style="color:#c0392b;font-size:0.85rem">Error: ${_esc(e.message)}</div>',
     ("text",), ""),
    # index.html
    ("frontend/index.html", [],
     "onclick=\"_discoverShowSpecies('${encodeURIComponent(sp.scientific_name).replace(/'/g, \"\\\\'\")}')\"",
     ("call", "_discoverShowSpecies", 0, "uri"), ""),
    ("frontend/index.html", [], "onclick=\"openRenameForm(${p.id}, '${_esc(p.species_primary).replace(/'/g, \"\\\\'\")}')\"",
     ("call", "openRenameForm", 1), ""),
    ("frontend/index.html", [], "onclick=\"enrichSpeciesFromMap('${_esc(p.species_primary).replace(/'/g, \"\\\\'\")}', ${p.id})\"",
     ("call", "enrichSpeciesFromMap", 0), ""),
    ("frontend/index.html", [], "onclick=\"_addNoteTag('${_esc(sp.scientific_name).replace(/'/g, \"\\\\'\")}')\"",
     ("call", "_addNoteTag", 0), ""),
    ("frontend/index.html", [],
     "<span class=\"np-tag\" onclick=\"_removeNoteTag('${_esc(t).replace(/'/g, \"\\\\'\")}')\" title=\"Click to remove\">${_esc(t)} ✕</span>",
     ("call", "_removeNoteTag", 0), ""),
    ("frontend/index.html", [], '<div class="find-state">❌ ${_esc(e.message)}</div>', ("text",), ""),
    # species.html
    ("frontend/species.html", [],
     "onclick=\"_selPickPhoto(event, '${_esc(name).replace(/'/g, \"\\\\'\")}', '${_esc(t.file).replace(/'/g, \"\\\\'\")}', this)\"",
     ("call", "_selPickPhoto", 1), "t = { file: H };"),
    ("frontend/species.html", [], "onclick=\"deleteResource(${item.id}, '${_esc(sciName).replace(/'/g, \"\\\\'\")}')\"",
     ("call", "deleteResource", 1), ""),
    ("frontend/species.html", [], '<div class="empty-state">Error loading profile: ${_esc(e.message)}</div>',
     ("text",), ""),
    # lists.html
    ("frontend/lists.html", [], "onclick=\"removeFromList('${_esc(String(name).replace(/'/g, \"\\\\'\"))}')\">",
     ("call", "removeFromList", 0), ""),
    ("frontend/lists.html", ["    const safe = _esc((x.scientific_name || '').replace(/'/g, \"\\\\'\"));"],
     "<div class=\"sp-lookup-item\" onclick=\"addSessionSpecies('${safe}')\">", ("call", "addSessionSpecies", 0), ""),
]


def _render(page, setup, tpl, pre):
    src = _src(page)
    for s in setup:
        assert s in src, f"{page}: setup line changed: {s}"
    assert tpl in src, f"{page}: template changed: {tpl}"
    # Wrap a bare attribute in an element so it parses like the page's markup.
    body = tpl if tpl.startswith("<") else "<x " + tpl.rstrip(">") + ">"
    script = _helpers(page) + VARS + pre + "\n" + "\n".join(setup) + "\nprint(JSON.stringify(`" + body + "`));"
    return _jsc(script)


def _assert_text(out):
    assert "<script" not in out.lower(), out
    visible = html.unescape(re.sub(r"<[^>]+>", "", out))
    assert H in visible or html.unescape(H) in visible, out


def _run_handler(out, fname, idx, decode=None):
    m = re.search(r'\son\w+="([^"]*)"', out)
    assert m, out
    handler = html.unescape(m.group(1))     # what the browser hands to the JS engine
    res = _jsc("""
var got = null; var event = { preventDefault: function () {}, stopPropagation: function () {} };
function %s() { got = Array.prototype.slice.call(arguments); }
(function () { %s }).call({});
print(JSON.stringify(got));
""" % (fname, handler))
    assert res is not None, handler
    arg = res[idx]
    if decode == "uri":
        arg = __import__("urllib.parse").parse.unquote(arg)
    elif decode:
        assert arg.startswith(decode), arg
        arg = arg[len(decode):]
    assert arg == H, (handler, arg)


def _check_site(page, setup, tpl, check, pre):
    out = _render(page, setup, tpl, pre)
    if check[0] == "text":
        _assert_text(out)
    elif check[0] == "textarea":
        inner = re.fullmatch(r"<textarea[^>]*>(.*)</textarea>", out, re.S)
        assert inner and "</textarea" not in inner.group(1).lower(), out
        assert html.unescape(inner.group(1)) == H
    else:
        assert "<script" not in out.lower(), out
        _run_handler(out, check[1], check[2], check[3] if len(check) > 3 else None)


def test_every_site_renders_source_text_as_text():
    failures = []
    for i, site in enumerate(SITES):
        try:
            _check_site(*site)
        except AssertionError as exc:
            failures.append(f"site {i} {site[0]} {site[3]}: {exc}")
    assert not failures, "\n".join(failures)


def test_print_workshop_medicinal_and_id_notes_escaped():
    """print.html workshop page: medicinal notes/folklore and ID notes (source /
    PFAF text) go into <p> elements — run the page's own statements."""
    src = _src("frontend/print.html")
    start = src.index("  const medBits = [_esc(cul.medicinal_notes), _esc(cul.medicinal_folklore),")
    end = src.index("  let fieldBlockHtml = '';", start)
    block = src[start:end]
    script = (_helpers("frontend/print.html") + "var H = %s;\n" % json.dumps(H)
              + "var cul = { medicinal_notes: H, medicinal_folklore: H, traditional_uses: H, id_notes: H,"
                " edible_parts: H, harvest_stage: H };\n"
              + "var ct = { herbal: true, id_notes: true, culinary: true, foraging: true }; var withFieldBlock = false;\n"
              + block + "\nprint(JSON.stringify(medicinalHtml + forageHtml));")
    out = _jsc(script)
    assert "<script" not in out.lower(), out
    paras = re.findall(r"<p>(.*?)</p>", out, re.S)
    assert len(paras) == 6, out
    for ptext in paras:
        assert html.unescape(re.sub(r"<[^>]+>", "", ptext)).strip().endswith(H), ptext


def test_species_page_has_no_undefined_resc():
    """species.html defines no _resc; the resources list must not call it."""
    src = _src("frontend/species.html")
    assert "function _resc" not in src
    assert "_resc(" not in src


if __name__ == "__main__":
    for _name, _f in list(globals().items()):
        if _name.startswith("test_") and callable(_f):
            _f()
            print("ok", _name)
