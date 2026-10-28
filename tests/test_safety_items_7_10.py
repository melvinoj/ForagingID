"""
Safety batch items 7-10 (CLOSEOUT 28 Oct section 4 #8-#10, #21).

  7. Data Trust: the "auto-approved" figures count approved + human_corrected=0
     (mostly human ✓ approvals) scored on top_score — relabelled "approved,
     uncorrected" / "top score"; definition unchanged. The pipeline chip
     (u-stat-auto-approved) is a different stat and keeps its label.
     Obs 9536 is NOT moved: its current approval is human (19 Jul), a terminal
     decision — recorded in CHANGELOG, no DB write.
  8. Review card: "⚡ fungi detected" → "⚡ fungi suggested?" (escaped).
  9. id_notes "[iNaturalist] ..." placeholders: LmMd.stripCitations returns ''
     for text that is only dots / ellipses; enrichment never stores such text;
     the 9 rows were cleared to NULL with system:clear_placeholder history.
 10. lists.html addSessionSpecies onclick uses lmJsArg (hostile names round-trip).

Run: python tests/test_safety_items_7_10.py
"""
import html as _html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_batch15_esc_names import HOSTILE, _jsc, _src  # noqa: E402

from app.integrations.inaturalist import INatTaxonDescription  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.services.enrichment import _apply_id_notes  # noqa: E402


def test_7_data_trust_labels():
    s = _src("frontend/scan.html")
    for want in (">Approved, uncorrected</button>", "Confidence distribution — approved, uncorrected<",
                 "(&lt;75% top score, approved, uncorrected)", "All approved, uncorrected",
                 "label: 'Approved, uncorrected'", "label: 'Below 60% top score'",
                 "auto_approved:     'Confidence distribution — approved, uncorrected'"):
        assert want in s, want
    assert not re.search(r"low-confidence auto-approved|Accept all auto-approved|'Auto-approved'|Below 60% conf", s)
    assert '<div class="chip-label">Auto-approved</div>' in s       # pipeline stat untouched


def test_8_fungi_suggestion_wording():
    s = _src("frontend/review.html")
    assert "⚡ ${_esc(obs.category_suggested)} suggested?</span>" in s
    assert "${obs.category_suggested} detected" not in s


def test_9_strip_citations_hides_placeholders():
    cases = ["[iNaturalist] ...", "[iNaturalist] …", "[a] [b] . . .", "", None,
             "[iNaturalist] Leaves opposite...", "[1] Real text."]
    out = _jsc("var window = this;\n" + _src("frontend/static/js/md.js") +
               "\nprint(JSON.stringify(" + __import__("json").dumps(cases) + ".map(window.LmMd.stripCitations)));")
    assert out == ["", "", "", "", "", "Leaves opposite...", "Real text."], out


def test_9_enrichment_never_stores_a_dots_only_id_note():
    def inat(notes, desc=None):
        return INatTaxonDescription(scientific_name="X y", taxon_id=1, description=desc,
                                    identification_notes=notes, wikipedia_url=None, raw_json={})
    for junk in ("...", " … ", ". . ."):
        ci = CulinaryInfo(id=1, species_id=1, id_notes=None)
        _apply_id_notes(ci, inat(junk), None)
        assert ci.id_notes is None, (junk, ci.id_notes)
    ci = CulinaryInfo(id=1, species_id=1, id_notes=None)
    _apply_id_notes(ci, inat("Leaves opposite."), None)
    assert ci.id_notes == "[iNaturalist] Leaves opposite.", ci.id_notes


def test_10_add_session_species_round_trips_hostile_names():
    s = _src("frontend/lists.html")
    assert "onclick=\"addSessionSpecies(${lmJsArg(x.scientific_name || '')})\">" in s
    assert "replace(/'/g" not in s
    args = _jsc("var window = this;\n" + _src("frontend/static/js/esc.js") +
                "\nprint(JSON.stringify(" + __import__("json").dumps(HOSTILE) + ".map(window.lmJsArg)));")
    for raw, arg in zip(HOSTILE, args):
        attr = f'onclick="addSessionSpecies({arg})"'
        handler = _html.unescape(re.match(r'onclick="(.*)"$', attr).group(1))  # what the browser runs
        got = _jsc("var got; function addSessionSpecies(n) { got = n; }\n" + handler +
                   ";\nprint(JSON.stringify([got]));")[0]
        assert got == raw, (raw, arg, got)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
