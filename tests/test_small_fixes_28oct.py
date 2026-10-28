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
import os
import re
import sys

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
    assert '"source_chips": chips' in py


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
