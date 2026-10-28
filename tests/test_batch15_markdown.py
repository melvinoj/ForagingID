"""
Batch 15 (P4) — one Markdown dialect, and safety text that renders verbatim.

  * app/services/markdown.render_md and static/js/md.js (LmMd.render) give
    byte-identical HTML on a golden list AND on every recipe body in the live DB
    (read-only), for both heading scales (handout h3, species page h4–h6).
  * The PDF no longer drops a '#' block's later lines (recipe 125 lost its whole
    ingredient list); lists and italics render.
  * Escaping first: no raw HTML, links render as text only.
  * Curator warnings (look_alike_warnings, preparation_warnings) full of Markdown
    characters come out character-identical in visible text on every renderer:
    the in-app SafetyGate boxes (map, walk card, species page culinary block),
    the browser print / Lists printed lines, and the PDF in all three layouts.
    Nothing is swallowed as markup; no renderer passes warning text to Markdown.
  * The old renderers are gone; every page that renders recipes loads md.js.

Run from project root:  python tests/test_batch15_markdown.py
"""
import html as _html
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from app.services import markdown as md  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def _src(p):
    if p == "frontend/index.html":   # batch 16: split page, read re-inlined
        from index_source import index_source
        return index_source()
    return pathlib.Path(ROOT, p).read_text(encoding="utf-8")


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    os.unlink(f.name)
    assert out.returncode == 0 and out.stdout.strip(), out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _visible(h):
    """What a reader sees: tags removed, entities decoded."""
    return _html.unescape(re.sub(r"<[^>]+>", "", h))


SPECIES_HEADING = lambda lvl: (f"h{min(lvl + 3, 6)}", "recipe-h")  # noqa: E731

GOLDEN = [
    ("", ""),
    (None, ""),
    ("Plain text.", "<p>Plain text.</p>"),
    ("line one\nline two", "<p>line one<br>line two</p>"),
    ("## Ingredients\n- 2 cups\n- *salt* **bold**",
     "<h3>Ingredients</h3><ul><li>2 cups</li><li><em>salt</em> <strong>bold</strong></li></ul>"),
    ("### For the pickled seed keys\n1. Wash\n2. Boil",
     "<h3>For the pickled seed keys</h3><ol><li>Wash</li><li>Boil</li></ol>"),
    ("### Ingredients\n*Serves 4*", "<h3>Ingredients</h3><p><em>Serves 4</em></p>"),
    ("Intro\n\n---\n\nAfter", "<p>Intro</p><p>After</p>"),
    ("<script>alert(1)</script> & 'q' \"d\"",
     "<p>&lt;script&gt;alert(1)&lt;/script&gt; &amp; &#39;q&#39; &quot;d&quot;</p>"),
    ("See [PFAF](https://pfaf.org) for more", "<p>See PFAF for more</p>"),
    ("snake_case and 2*3*4 stay", "<p>snake_case and 2*3*4 stay</p>"),
    ("use `code` and __strong__ and _em_", "<p>use <code>code</code> and <strong>strong</strong> and <em>em</em></p>"),
    ("#hashtag is not a heading", "<p>#hashtag is not a heading</p>"),
    ("**Title**\nbody", "<p><strong>Title</strong><br>body</p>"),
    ("- a\n- b\n1. c", "<ul><li>a</li><li>b</li></ul><ol><li>c</li></ol>"),
    ("text\n- item\nmore", "<p>text</p><ul><li>item</li></ul><p>more</p>"),
    ("Grüße *ünd* Äpfel", "<p>Grüße <em>ünd</em> Äpfel</p>"),
    ("\r\n# Heading\r\n\r\nPara\r\n", "<h3>Heading</h3><p>Para</p>"),
]


def _js_render_all(inputs, species=False):
    opt = "{ heading: function (l) { return ['h' + Math.min(l + 3, 6), 'recipe-h']; } }" if species else "undefined"
    script = ("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/md.js") + "\n"
              "var inputs = " + json.dumps(inputs) + ";\n"
              "print(JSON.stringify(inputs.map(function (t) { return window.LmMd.render(t, " + opt + "); })));")
    return _jsc(script)


def test_golden_python():
    for text, want in GOLDEN:
        assert md.render_md(text) == want, (text, md.render_md(text), want)


def test_golden_js_matches_python():
    inputs = [t for t, _ in GOLDEN]
    got = _js_render_all(inputs)
    for (text, want), g in zip(GOLDEN, got):
        assert g == want, (text, g, want)


def _recipe_bodies():
    db = pathlib.Path(ROOT, "data/foragingid.db")
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = [r[0] for r in con.execute("SELECT body FROM species_recipes WHERE body IS NOT NULL")]
        rows += [r[0] for r in con.execute(
            "SELECT field_recipes FROM encounters WHERE field_recipes IS NOT NULL")]
    finally:
        con.close()
    out = []
    for r in rows:
        try:
            v = json.loads(r)
            out.append(v.get("body") if isinstance(v, dict) else r)
        except (ValueError, TypeError):
            out.append(r)
    return [x for x in out if x]


def test_parity_on_every_live_recipe_both_heading_scales():
    bodies = _recipe_bodies()
    assert len(bodies) > 100, len(bodies)
    py = [md.render_md(b) for b in bodies]
    js = _js_render_all(bodies)
    bad = [i for i, (a, b) in enumerate(zip(py, js)) if a != b]
    assert not bad, (len(bad), bodies[bad[0]][:200], py[bad[0]][:300], js[bad[0]][:300])
    py_s = [md.render_md(b, SPECIES_HEADING) for b in bodies]
    js_s = _js_render_all(bodies, species=True)
    bad = [i for i, (a, b) in enumerate(zip(py_s, js_s)) if a != b]
    assert not bad, (len(bad), bodies[bad[0]][:200])


def test_species_heading_scale():
    assert md.render_md("# a\n## b\n### c\n#### d", SPECIES_HEADING) == (
        '<h4 class="recipe-h">a</h4><h5 class="recipe-h">b</h5><h6 class="recipe-h">c</h6>'
        '<h6 class="recipe-h">d</h6>')


def test_pdf_keeps_every_line_of_a_heading_block():
    import app.api.lists_pdf as lp
    out = lp._mdlite("### For the pickled seed keys\n- 200 g ash keys\n- 300 ml cider vinegar\n\nMethod text.")
    assert "200 g ash keys" in out and "300 ml cider vinegar" in out and "Method text." in out
    assert out.startswith("<h3>For the pickled seed keys</h3><ul>"), out
    assert lp._jinja_env.filters["mdlite"] is lp._mdlite


def test_snippet_same_dialect_title_dedupe_and_limit():
    s = md.md_snippet("# Nettle soup\n\n## Ingredients\n- nettles\n- *stock*\n\nSimmer.", "Nettle soup")
    assert "Nettle soup" not in s                                   # repeated title dropped
    assert "<ul style=" in s and "<em>stock</em>" in s and "Simmer." in s
    long = "\n\n".join(["Para %d " % i + "x" * 200 for i in range(10)])
    assert md.md_snippet(long, "t").endswith("<p style='margin:4px 0 0'>…</p>")
    assert "<script>" not in md.md_snippet("<script>x</script>", "t")


def test_strip_citations_twins():
    cases = ["Leaves [1] are [PFAF 2] toothed.", None, "", "  [x]  "]
    py = [md.strip_citations(c) for c in cases]
    js = _jsc("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/md.js") +
              "\nprint(JSON.stringify(" + json.dumps(cases) + ".map(window.LmMd.stripCitations)));")
    assert py == js == ["Leaves are toothed.", "", "", ""], (py, js)


def test_old_renderers_gone_and_pages_load_md_js():
    for p, gone in (("frontend/print.html", "function _mdLite("), ("frontend/lists.html", "function _mdLite("),
                    ("app/api/sharing.py", "def _md_inline("), ("app/api/sharing.py", "_MD_LIST")):
        assert gone not in _src(p), (p, gone)
    sp = _src("frontend/species.html")
    assert "return LmMd.render(raw, { heading:" in sp
    for p in ("frontend/print.html", "frontend/lists.html", "frontend/species.html", "frontend/encounters.html"):
        assert '<script src="/static/js/md.js"></script>' in _src(p), p
    for p in ("frontend/print.html", "frontend/lists.html"):
        assert "replace(/\\[[^\\]]*\\]\\s*/g" not in _src(p), p
    assert "strip_citations(id_notes_raw)" in _src("app/api/lists_pdf.py")


# ── safety text renders verbatim ─────────────────────────────────────────────

LOOK_H = ("# Not a heading — *Conium* looks like **parsley**; _never_ eat __any__ part. "
          "2*3*4, snake_case, `x`, [1](u), <b>bold?</b> & 50% ~ ---")
PREP_H = ("- not a list: boil *twice* (__no__ shortcuts) #1 rule; 1. still text * stars * "
          "_under_ <script>alert(1)</script> &amp; 'quotes\"")


def _hostile_decisions():
    import test_batch6_warnings as b6
    saved = (dict(b6.PREP), dict(b6.LOOK))
    try:
        for sid in (2, 4, 6):            # toxic Hedera, caution Sambucus, edible Allium — all curator rows
            b6.PREP[sid] = PREP_H + f" [{sid}]"
            b6.LOOK[sid] = LOOK_H + f" [{sid}]"
        d = b6._run(b6._decisions())
        return b6, d, {b6.SPECIES[i][1]: (PREP_H + f" [{sid}]", LOOK_H + f" [{sid}]")
                       for i, sid in ((0, 2), (1, 4), (2, 6))}
    finally:
        b6.PREP.clear(); b6.PREP.update(saved[0])
        b6.LOOK.clear(); b6.LOOK.update(saved[1])


def test_warnings_verbatim_in_app_print_and_pdf():
    b6, d, texts = _hostile_decisions()
    # served decisions carry the stored text unchanged
    for name, (prep, look) in texts.items():
        assert d[name]["warnings"]["preparation"]["text"] == prep, name
        assert d[name]["warnings"]["look_alike"]["text"] == look, name
    # JS: in-app boxes (SafetyGate.warnings / culinaryWarnings) and the printed
    # lines browser print + Lists use (handoutWarningsHtml / culinaryWarnings handout)
    script = ("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/safety-gate.js") + "\n"
              "var d = " + json.dumps({n: d[n] for n in texts}) + ";\nvar out = {};\n"
              "Object.keys(d).forEach(function (n) { var s = d[n]; out[n] = {\n"
              "  app: window.SafetyGate.warnings(s),\n"
              "  app_folded: window.SafetyGate.warnings(s, {collapse: 'all'}),\n"
              "  culinary: window.SafetyGate.culinaryWarnings(s),\n"
              "  print_lines: window.SafetyGate.handoutWarningsHtml(s, 'div', 'fg-lookalike'),\n"
              "  print_culinary: window.SafetyGate.culinaryWarnings(s, {handout: true}) }; });\n"
              "print(JSON.stringify(out));")
    js = _jsc(script)
    for name, (prep, look) in texts.items():
        for surface, h in js[name].items():
            v = _visible(h)
            assert prep in v, (name, surface, v[:400])
            assert look in v, (name, surface, v[:400])
            assert "<script>" not in h and "<b>bold?</b>" not in h, (name, surface)
    # PDF, every layout
    for layout in ("field_guide", "recipe_booklet", "workshop"):
        pages = b6._pdf_html(layout, d)
        for name, (prep, look) in texts.items():
            v = _visible(b6._species_block(pages[name]))
            assert prep in v, (layout, name, v[:600])
            assert look in v, (layout, name, v[:600])


def test_no_renderer_passes_warning_text_to_markdown():
    pat = re.compile(r"(LmMd\.render|render_md|md_snippet|mdlite|_renderMd)\b[^\n]*(look_alike|preparation_warn|warnings)"
                     r"|(look_alike|preparation_warn)[^\n]*(LmMd\.render|render_md|md_snippet|\|\s*mdlite|_renderMd\()")
    for p in ("app/templates/print_pdf.html", "app/api/lists_pdf.py", "app/api/sharing.py", "frontend/print.html",
              "frontend/lists.html", "frontend/species.html", "frontend/index.html",
              "frontend/static/js/encounters-main.js", "frontend/static/js/safety-gate.js"):
        hits = [l for l in _src(p).splitlines() if pat.search(l) and not l.strip().startswith(("//", "#", "{#", "*"))]
        assert not hits, (p, hits)
    # the species page safety block escapes the served text (no Markdown)
    assert "<br><span data-field-key=\"${key}\" data-field-orig=\"${_esc(raw)}\">${_esc(w.text)}</span>" in \
        _src("frontend/species.html")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
