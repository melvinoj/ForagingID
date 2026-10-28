"""
Batch 17 tidy (28 Oct 2026) — the pieces Code can check without a browser.

  * /api/species/ carries one thumbnail per species: the best CONFIRMED photo
    (candidates[0] is its own species → highest score), never a needs_review or
    rejected photo; NULL when the species has no confirmed thumbnail.
  * scan.html loadPrefilterThreshold reads {settings:[…]} (it called .find on the
    object and the empty catch hid it).
  * Lists: the Lookalike warnings / Edibility conditions rows offer no checkbox,
    and the warnings stay ungated in print.
  * Settings device list refreshes itself (poll while a link is unused, stops
    after 10 minutes, refresh on visibilitychange).
  * pwa.js shows a reload prompt on controllerchange (only when a controller
    existed at load) and never reloads by itself.
  * One APP_VERSION, one HTTP_USER_AGENT; no "ForagingID/" User-Agent left.
  * The access-log filter drops 2xx/304 polls only; errors and other paths log.
  * [TIMING] lines print only with LOG_TIMING.
  * Dead code stays gone (scratch page route, git-banner.js, current_phase.md).

Run from project root:  python tests/test_batch17_tidy.py
"""
import json
import logging
import os
import pathlib
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_enrichment_safety import Env, _run  # noqa: E402
from test_enrichment_scope_and_recipe_warnings import _add  # noqa: E402

import app.api.culinary as culinary_api  # noqa: E402
import app.config as config  # noqa: E402
import app.main as main  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import Species  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402


def _src(p):
    return pathlib.Path(ROOT, p).read_text(encoding="utf-8")


def _fn(src, name):
    """The body of `function name(` up to the next top-level function."""
    i = src.index(f"function {name}(")
    j = src.find("\nfunction ", i + 1)
    k = src.find("\nasync function ", i + 1)
    ends = [x for x in (j, k) if x != -1]
    return src[i:min(ends) if ends else len(src)]


# ── 17-B3 thumbnail on /api/species/ ─────────────────────────────────────────

def _cands(name, score):
    return json.dumps([{"scientific_name": name, "score": score}])


def test_species_list_thumbnail_is_best_confirmed_photo():
    env = Env()
    try:
        a, b, c = "Testia alpha", "Testia beta", "Testia gamma"
        _add(env, [
            Species(id=50, scientific_name=a, name_key=normalize_taxon_key(a), edibility_status="edible"),
            Species(id=51, scientific_name=b, name_key=normalize_taxon_key(b), edibility_status="caution"),
            Species(id=52, scientific_name=c, name_key=normalize_taxon_key(c), edibility_status="edible"),
            # a: low-score confirmed, high-score confirmed, higher-score but needs_review
            Observation(id=5001, file_path="/x/b17_1.jpg", thumbnail_path="/t/a_low.jpg", species_primary=a,
                        species_candidates_json=_cands(a, 0.2), review_status="approved",
                        identification_status="identified"),
            Observation(id=5002, file_path="/x/b17_2.jpg", thumbnail_path="/t/a_best.jpg", species_primary=a,
                        species_candidates_json=_cands(a, 0.9), review_status="manually_verified",
                        identification_status="identified"),
            Observation(id=5003, file_path="/x/b17_3.jpg", thumbnail_path="/t/a_review.jpg", species_primary=a,
                        species_candidates_json=_cands(a, 0.99), review_status="needs_review",
                        identification_status="identified"),
            # b: candidates[0] names ANOTHER species → its score does not count
            Observation(id=5004, file_path="/x/b17_4.jpg", thumbnail_path="/t/b_other.jpg", species_primary=b,
                        species_candidates_json=_cands("Testia delta", 0.95), review_status="approved",
                        identification_status="identified"),
            Observation(id=5005, file_path="/x/b17_5.jpg", thumbnail_path="/t/b_own.jpg", species_primary=b,
                        species_candidates_json=_cands(b, 0.3), review_status="approved",
                        identification_status="identified"),
            # c: confirmed but no thumbnail file → NULL; plus a rejected one with a thumb
            Observation(id=5006, file_path="/x/b17_6.jpg", thumbnail_path=None, species_primary=c,
                        review_status="approved", identification_status="identified"),
            Observation(id=5007, file_path="/x/b17_7.jpg", thumbnail_path="/t/c_rej.jpg", species_primary=c,
                        review_status="rejected", identification_status="identified"),
        ])

        async def go():
            async with env.S() as s:
                return await culinary_api.list_species(db=s)
        rows = {r["scientific_name"]: r for r in _run(go())}
        assert rows[a]["thumbnail"] == "a_best.jpg", rows[a]["thumbnail"]
        assert rows[b]["thumbnail"] == "b_own.jpg", rows[b]["thumbnail"]
        assert rows[c]["thumbnail"] is None, rows[c]["thumbnail"]
        assert all("thumbnail" in r for r in rows.values())
    finally:
        env.close()


def test_species_page_uses_list_thumbnail_and_keeps_map_fallback():
    sp = _src("frontend/species.html")
    f = _fn(sp, "_spThumbFile")
    assert "_spListThumb(name)" in f
    load = _fn(sp, "loadSpeciesList")
    assert "!_spListHasThumbs()" in load and load.index("allSpecies = await r.json()") < load.index("_loadSpThumbs()")
    assert "!_spListHasThumbs()" in _fn(sp, "setSpeciesView")


# ── 17-B4 scan.html ──────────────────────────────────────────────────────────

def test_prefilter_threshold_reads_settings_list():
    f = _fn(_src("frontend/scan.html"), "loadPrefilterThreshold")
    assert "(list.settings || []).find(" in f
    assert not re.search(r"\blist\.find\(", f)


# ── 17-B1 Lists ──────────────────────────────────────────────────────────────

def test_lists_fixed_rows_have_no_checkbox_and_warnings_stay_ungated():
    ls = _src("frontend/lists.html")
    assert "FIXED_SECTION_TEXT = { lookalikes: 'Always printed', conditions: 'Not printed' }" in ls
    f = _fn(ls, "toggleExpandFill")
    assert f.index("FIXED_SECTION_TEXT[key]") < f.index('<input type="checkbox"')
    assert "prefs.lookalikes" not in ls
    assert "_printWarnings(prof, 'div', 'fg-lookalike')" in ls


# ── 17-B5 device list ────────────────────────────────────────────────────────

def test_device_list_refreshes_itself():
    st = _src("frontend/settings.html")
    load = _fn(st, "loadDevices")
    assert "_syncDevicePoll(rows.some(function (d) { return d.is_active && !d.claimed_at; }))" in load
    poll = _fn(st, "_syncDevicePoll")
    assert "10 * 60 * 1000" in poll and "clearInterval(_devicePollTimer)" in poll
    assert "document.visibilityState === 'visible'" in poll
    assert re.search(r"addEventListener\('visibilitychange'[^)]*\)\s*\{\s*\n\s*if \(document.visibilityState === 'visible'\) loadDevices\(\);", st)


# ── 17-B2 reload prompt ──────────────────────────────────────────────────────

def test_pwa_reload_prompt_never_auto_reloads():
    js = _src("frontend/static/js/pwa.js")
    assert "addEventListener('controllerchange'" in js
    assert "var hadController = !!navigator.serviceWorker.controller;" in js
    assert "if (hadController) showReloadBar();" in js
    # the only reload is the button's own click handler
    assert js.count("location.reload(") == 1
    assert "btn.onclick = function () { window.location.reload(); };" in js
    assert "reg.update()" in js
    for page in ("encounters.html", "workshops.html", "index.html", "species.html"):
        assert '<script src="/static/js/pwa.js"></script>' in _src(f"frontend/{page}"), page


# ── A-10 / UA ────────────────────────────────────────────────────────────────

def test_one_version_and_one_user_agent():
    assert config.APP_VERSION == "0.2.0"
    assert main.app.version == config.APP_VERSION
    assert config.HTTP_USER_AGENT == "LandMemory/0.2 (+https://melvinjarman.co.uk)"
    out = subprocess.run(["git", "grep", "-n", "-E", r"User-Agent\"?\s*[:=]\s*\"|_UA\s*=\s*\"", "--", "app", "scripts"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    assert out.strip() == "", out
    out = subprocess.run(["git", "grep", "-n", "ForagingID/[0-9]", "--", "app", "scripts"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    assert out.strip() == "", out


# ── E-12 logs ────────────────────────────────────────────────────────────────

def _rec(path, status):
    return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                             ("127.0.0.1:1", "GET", path, "1.1", status), None)


def test_quiet_poll_filter():
    f = main._QuietPollFilter()
    assert not f.filter(_rec("/api/processes/active", 200))
    assert not f.filter(_rec("/api/queue/list?x=1", 200))
    assert not f.filter(_rec("/health", 304))
    assert f.filter(_rec("/api/processes/active", 500))       # errors still log
    assert f.filter(_rec("/health", 404))
    assert f.filter(_rec("/api/me", 200))                     # other paths log
    assert any(isinstance(x, main._QuietPollFilter) for x in logging.getLogger("uvicorn.access").filters)


def test_timing_prints_only_with_flag():
    for p in ("app/main.py", "app/database.py"):
        s = _src(p)
        assert 'print(f"[TIMING]' not in s, p
        assert "log_timing(f\"[TIMING]" in s, p
    src = _src("app/config.py")
    assert 'LOG_TIMING = os.environ.get("LOG_TIMING", "").strip() not in ("", "0")' in src


def test_launcher_keeps_ten_logs():
    s = _src("START_ForagingID.command")
    i = s.index("ls -t logs/server_*.log 2>/dev/null | tail -n +10")
    assert i < s.index('LOG="logs/server_$(date')


# ── E-07 / E-09 ──────────────────────────────────────────────────────────────

def test_dead_code_stays_gone():
    for p in ("frontend/scratch-filename-test.html", "frontend/static/js/git-banner.js", "docs/current_phase.md"):
        assert not pathlib.Path(ROOT, p).exists(), p
    assert "scratch-filename-test" not in _src("app/main.py")
    assert "_update_current_phase_doc" not in _src("app/api/dev.py")
    req = _src("requirements.txt")
    for dep in ("geopy", "piexif", "aiofiles"):
        assert dep not in req, dep
    assert "Current head: `0059_recipe_page_fields`." in _src("CLAUDE.md")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
