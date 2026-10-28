"""
Small fixes batch, 28 Oct 2026 (Melvin; Claude.ai defaults).

1. Source chips (CLOSEOUT_28oct section 4 #11): one chip per known source
   (PFAF under accepted name + synonym = one chip); the label comes from the
   URL's host — a Wikipedia URL stored as "iNaturalist" / "inaturalist_taxon"
   reads "Wikipedia"; a Wikipedia primary_source_url no longer reads "PFAF".
2. Bare-domain links (#12): served with https:// by the same helper; no DB write.

Plain script, no live server. Run from project root:
    python tests/test_small_fixes_28oct.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.services.source_links import host_label, normalise_url, source_chips  # noqa: E402


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ── 1. Source chips ──────────────────────────────────────────────────────────
def test_one_pfaf_chip_and_host_labels():
    # elder (107) as stored: PFAF twice, Wikipedia under "iNaturalist"
    chips = source_chips(
        "https://pfaf.org/user/Plant.aspx?LatinName=Sambucus%20nigra",
        [{"name": "PFAF", "url": "https://pfaf.org/user/Plant.aspx?LatinName=Sambucus%20nigra"},
         {"name": "iNaturalist", "url": "http://en.wikipedia.org/wiki/Sambucus_nigra"},
         {"source_name": "pfaf", "source_url": "https://pfaf.org/user/Plant.aspx?LatinName=Sambucus%20nigra"},
         {"source_name": "inaturalist_taxon", "source_url": "https://en.wikipedia.org/wiki/Sambucus_nigra"},
         {"source_name": "wikidata", "source_url": "https://www.wikidata.org/wiki/Q22701"},
         {"source_name": "trompenburg", "source_url": None}])
    assert [c["label"] for c in chips] == ["PFAF", "Wikipedia", "Wikidata"], chips
    assert chips[0]["url"].endswith("Sambucus%20nigra")


def test_pfaf_synonym_url_still_one_chip():
    chips = source_chips("https://pfaf.org/user/Plant.aspx?LatinName=Erigeron%20canadensis",
                         [{"name": "PFAF", "url": "https://pfaf.org/user/Plant.aspx?LatinName=Conyza%20canadensis"}])
    assert [c["label"] for c in chips] == ["PFAF"]
    assert "Erigeron" in chips[0]["url"]                         # primary wins


def test_wikipedia_primary_never_labelled_pfaf():
    chips = source_chips("http://en.wikipedia.org/wiki/Hieracium_maculatum",
                         [{"name": "iNaturalist", "url": "http://en.wikipedia.org/wiki/Hieracium_maculatum"}])
    assert chips == [{"label": "Wikipedia", "url": "http://en.wikipedia.org/wiki/Hieracium_maculatum"}]


def test_unknown_host_keeps_stored_name_and_real_inat_stays_inat():
    assert source_chips(None, [{"name": "TrompenburgPlants", "url": "https://www.trompenburg.nl/x"}]) == \
        [{"label": "TrompenburgPlants", "url": "https://www.trompenburg.nl/x"}]
    assert host_label("https://www.inaturalist.org/taxa/1") == "iNaturalist"
    assert host_label("https://notpfaf.org/x") is None                    # suffix needs a dot
    assert source_chips(None, []) == [] and source_chips(None, None) == []


def test_species_page_renders_server_chips_only():
    h = _read("frontend/species.html")
    body = h[h.index("function _renderSources("):h.index("function edibilityClass(")]
    assert "🔗 PFAF" not in body and "sources_json" not in body and "primary_source_url" not in body
    assert "_renderSources(ci, data.source_chips || [])" in h
    py = _read("app/api/culinary.py")
    assert '"source_chips": _chips' in py and py.count('"source_chips"') == 1


# ── 2. Bare domains ──────────────────────────────────────────────────────────
def test_bare_domain_gets_https():
    assert normalise_url("gallowaywildfoods.com") == "https://gallowaywildfoods.com"
    assert normalise_url(" nccih.nih.gov/health/herbsataglance ") == "https://nccih.nih.gov/health/herbsataglance"
    assert normalise_url("http://x.org/a") == "http://x.org/a"
    assert normalise_url("HTTPS://x.org") == "HTTPS://x.org"
    assert normalise_url(None) == "" and normalise_url("  ") == ""


def test_data_sources_serves_normalised_url_from_shared_helper():
    py = _read("app/api/data_sources.py")
    assert "from app.services.source_links import normalise_url as _normalise_url" in py
    assert re.search(r"def _normalise_url\(", py) is None                # no second copy
    assert '"url": _normalise_url(ds.url)' in py


# ── 3. Import summary adds up ────────────────────────────────────────────────
def test_p1_chips_show_duplicates_and_prefilter_rejects():
    h = _read("frontend/scan.html")
    stats = h[h.index('id="s-session-stats"'):h.index('id="s1-breakdown"')]
    for chip in ("s-sess-total", "s-sess-approved", "s-sess-review", "s-sess-failed",
                 "s-sess-rejected", "s-sess-duplicate"):
        assert stats.count(f'id="{chip}"') == 1, chip
    assert "sv(`${prefix}-sess-duplicate`, s.files_duplicate ?? null" in h
    # session 120 (28 Oct): processed 288 = 15 + 178 + 0 + 0 rejected + 95 duplicates
    assert 288 == 15 + 178 + 0 + 0 + 95
    # syncthing counts both into files_processed — the reason both chips exist
    py = _read("app/api/syncthing.py")
    assert "files_processed=1, files_duplicate=1" in py and "files_processed=1, files_rejected=1" in py


# ── 4. Background Processes: network vs render error ─────────────────────────
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        out = subprocess.run([JSC, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().split("\n")[-1])


def _bp_run(fetch_js, boot_first=False):
    """Runs settings.html's real loadBgProcesses with a stub fetch; returns the
    body HTML and what reached console.error. boot_first = call it BEFORE the
    declarations are evaluated, as settings.html's Boot block does."""
    h = _read("frontend/settings.html")
    src = h[h.index("const _BP_TYPE_LABEL = {"):h.index("// Dismiss removes a dead row")]
    call = ("var out = null; var p = loadBgProcesses(); p.then(function(){"
            " out = {html: body.innerHTML, errs: errs}; }, function(e){ out = {rejected: String(e)}; });\n")
    script = (
        "var body = {innerHTML: ''}; var errs = [];\n"
        "var document = {getElementById: function(){ return body; }};\n"
        "var console = {error: function(){ errs.push([].slice.call(arguments).map(String).join(' ')); }};\n"
        "var fetch = " + fetch_js + ";\n" +
        (call + src if boot_first else src + "\n" + call) +
        "\ndrainMicrotasks(); print(JSON.stringify(out));")
    return _jsc(script)


def test_bp_boot_call_before_declarations_does_not_throw():
    # settings.html Boot (≈ line 1216) runs loadBgProcesses() ~1000 lines above
    # its helpers; a top-level `let` cache threw there (TDZ) on every load.
    h = _read("frontend/settings.html")
    assert h.index("loadBgProcesses();") < h.index("async function _loadBpCancellable(")
    assert "let _bpCancellable" not in h
    o = _bp_run(_ok("Promise.resolve([])"), boot_first=True)
    assert o.get("html") and "No processes running." in o["html"], o


def _ok(active_json):
    return ("function(u){ if (u.indexOf('cancellable') >= 0) return Promise.resolve({ok:true, json:function(){"
            "return Promise.resolve({cancellable_types:[]});}});"
            " return Promise.resolve({ok:true, json:function(){ return " + active_json + "; }}); }")


def test_bp_network_failure_says_could_not_reach_server():
    o = _bp_run("function(){ return Promise.reject(new TypeError('Failed to fetch')); }")
    assert "Could not reach server." in o["html"] and o["errs"] == [], o


def test_bp_render_error_is_its_own_message_and_logged():
    # a row whose getter throws while rendering = a render bug, not the network
    o = _bp_run(_ok("Promise.resolve([{get process_type(){ throw new Error('boom-render'); }}])"))
    assert "Could not reach server" not in o["html"], o
    assert "Could not display processes" in o["html"]
    assert any("boom-render" in e for e in o["errs"]), o


def test_bp_unreadable_body_is_its_own_message_and_logged():
    o = _bp_run(_ok("Promise.reject(new SyntaxError('bad json'))"))
    assert "unreadable process list" in o["html"] and "Could not reach server" not in o["html"]
    assert any("bad json" in e for e in o["errs"]), o
    o = _bp_run(_ok("Promise.resolve({detail: 'x'})"))
    assert "unreadable process list" in o["html"], o


def test_bp_empty_and_normal_rows_unchanged():
    assert "No processes running." in _bp_run(_ok("Promise.resolve([])"))["html"]
    o = _bp_run(_ok("Promise.resolve([{process_id:1, process_type:'p1_syncthing', progress_total:4,"
                    " progress_current:2, heartbeat_age_s:5, status:'running', is_stalled:false}])"))
    assert "2 of 4" in o["html"] and "running" in o["html"] and o["errs"] == [], o


# ── 5. Guest scene pin wording ───────────────────────────────────────────────
def test_scene_no_description_line_is_curator_only():
    js = _read("frontend/static/js/index/detail-card.js")
    line = [l for l in js.split("\n") if "No description added yet" in l]
    assert len(line) == 1 and "data-guest-hide" in line[0], line
    assert "edit in review queue" in line[0]                             # curator wording unchanged
    assert "body.guest-mode [data-guest-hide]" in _read("frontend/static/js/guest-mode.js")


# ── 6. No stats request for guests ───────────────────────────────────────────
def test_review_badge_only_in_owner_branch():
    js = _read("frontend/static/js/site-header.js")
    ident = js[js.index("function _initIdentity()"):js.index("function _initEncountersBadge()")]
    guest_branch = ident[ident.index("if (d.is_guest) {"):ident.index("} else {")]
    owner_branch = ident[ident.index("} else {"):]
    assert "_initReviewBadge()" not in guest_branch and "_initReviewBadge();" in owner_branch
    assert js.count("_initReviewBadge();") == 1                          # no unconditional boot call
    assert js.count("/api/observations/stats") == 1


# ── 7. Medicinal-prep search serves recipe_season ────────────────────────────
def test_medicinal_search_serves_recipe_season():
    import asyncio
    from datetime import datetime
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    import app.main  # noqa: F401
    from app.api.find import find_medicinal
    from app.database import Base
    from app.models.species import Species, SpeciesRecipe, recipe_season
    from app.services.taxonomy import normalize_taxon_key

    async def go():
        path = os.path.join(tempfile.mkdtemp(prefix="sf28_"), "t.db")
        Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
        eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
        S = async_sessionmaker(eng, expire_on_commit=False)
        async with S() as s:
            s.add(Species(id=1, scientific_name="Sambucus nigra", name_key=normalize_taxon_key("Sambucus nigra"),
                          edibility_status="caution", toxicity_severity="none", kingdom="Plantae"))
            # stored autumn, ai_generated, title says Spring → served spring (title word wins)
            s.add(SpeciesRecipe(id=10, species_id=1, title="Spring Elderflower Tea", body="A tea for colds.",
                                season="autumn", source="ai_generated", status="approved",
                                is_medicinal_prep=True, created_at=datetime(2026, 10, 1)))
            await s.commit()
        async with S() as s:
            d = await find_medicinal(q="tea", db=s)
        await eng.dispose()
        return d

    d = asyncio.run(go())
    prep = d["results"][0]["preparations"][0]
    assert prep["season"] == recipe_season("autumn", "ai_generated", "Spring Elderflower Tea", "A tea for colds.")
    assert prep["season"] == "spring", prep


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(exc)[:400])
    print("failures:", fails)
    sys.exit(1 if fails else 0)
