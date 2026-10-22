"""
Tests for the experience-export gates — caution rule 8 (audit D3-01, fix pass
batch 1, 20 Oct 2026) and the curator-authored predicate it rests on — plus the
classifier of scripts/import_warning_review_drafts.py.

Rule 8: a caution species' recipes are published only when its
preparation_warnings is curator-authored (latest history row changed_by='human'
AND equal to the current text — an approved warning draft writes exactly that).
Without one the species keeps its caution badge but every recipe is withheld.

Run from project root:  python -m pytest tests/test_experience_gates.py -v
Or standalone:          python tests/test_experience_gates.py
"""

import os
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gates  # noqa: E402
from app.models.species import is_curator_authored  # noqa: E402
from import_warning_review_drafts import MARKER, classify  # noqa: E402

WARNING = "Contains a photosensitising compound; avoid in strong sunlight."
CFG = {"recipe_sources_allowed": ["ai_generated", "human"], "exclude_recipe_ids": [], "exclude_recipe_species_ids": []}


def _conn(history=()):
    """In-memory DB with only the table human_authored() reads. history rows:
    (culinary_info_id, field, changed_by, new_value, changed_at)."""
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE culinary_info_history (id INTEGER PRIMARY KEY, culinary_info_id INTEGER,
                 field_name TEXT, old_value TEXT, new_value TEXT, changed_at TEXT, changed_by TEXT)""")
    for ciid, field, by, new, at in history:
        c.execute("INSERT INTO culinary_info_history (culinary_info_id, field_name, changed_by, new_value, changed_at)"
                  " VALUES (?, ?, ?, ?, ?)", (ciid, field, by, new, at))
    return c


def _sp(status="caution", severity="none", verified=True, sci="Hypericum perforatum", family="Hypericaceae"):
    return {"id": 229, "scientific_name": sci, "family": family, "genus": sci.split()[0],
            "edibility_status": status, "toxicity_severity": severity,
            "edibility_verified": 1 if verified else 0, "edibility_verified_by": "human" if verified else None}


def _ci(pw=WARNING):
    return {"id": 7, "preparation_warnings": pw, "look_alike_warnings": None}


def _recipe(rid=1):
    return {"id": rid, "status": "approved", "is_medicinal_prep": 0, "source": "ai_generated"}


HUMAN_ROW = [(7, "preparation_warnings", "human", WARNING, "2026-10-20 19:00:00.000000")]


# ── curator-authored predicate ───────────────────────────────────────────────

def test_curator_authored_requires_human_and_equal_text():
    assert is_curator_authored("human", WARNING, WARNING)
    assert is_curator_authored("human", WARNING + "  ", "  " + WARNING)       # whitespace-trimmed
    assert not is_curator_authored("ai_approved:human", WARNING, WARNING)     # AI draft approval ≠ curator
    assert not is_curator_authored("pfaf_reparse", WARNING, WARNING)
    assert not is_curator_authored("human", MARKER, WARNING)                  # E-14 marker row
    assert not is_curator_authored("human", WARNING, WARNING + " (edited)")   # field changed since
    assert not is_curator_authored("human", "", "")                           # empty is never authored
    assert not is_curator_authored(None, None, WARNING)


# ── rule 8: caution with an approved warning ─────────────────────────────────

def test_caution_with_approved_warning_keeps_recipes_and_shows_it():
    conn = _conn(HUMAN_ROW)
    assert gates.caution_warning(_sp(), _ci(), conn) == WARNING
    assert gates.recipe_allowed(_sp(), _ci(), _recipe(), conn, CFG) == (True, "")
    assert gates.safety_texts(_sp(), _ci(), conn)["caution"] == WARNING
    assert gates.edibility_badge(_sp(), _ci(), conn, CFG)["kind"] == "caution"


# ── rule 8: caution without an approved warning (B fallback) ─────────────────

def test_caution_with_pfaf_text_only_withholds_recipes_keeps_badge():
    conn = _conn([(7, "preparation_warnings", "pfaf_reparse", WARNING, "2026-06-11 07:00:00")])
    assert gates.caution_warning(_sp(), _ci(), conn) is None
    assert gates.recipe_allowed(_sp(), _ci(), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)
    assert "caution" not in gates.safety_texts(_sp(), _ci(), conn)
    assert gates.edibility_badge(_sp(), _ci(), conn, CFG)["kind"] == "caution"   # species still shown


def test_caution_with_no_history_withholds():
    conn = _conn()
    assert gates.recipe_allowed(_sp(), _ci(), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)


def test_caution_with_empty_field_withholds():
    conn = _conn([(7, "preparation_warnings", "human", "", "2026-10-20 19:00:00")])
    assert gates.recipe_allowed(_sp(), _ci(pw=None), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)


def test_caution_with_e14_marker_row_withholds():
    conn = _conn([(7, "preparation_warnings", "human", MARKER, "2026-06-24 19:26:42")])
    assert gates.recipe_allowed(_sp(), _ci(), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)


def test_caution_with_ai_approved_warning_withholds():
    conn = _conn([(7, "preparation_warnings", "ai_approved:human", WARNING, "2026-10-20 19:00:00")])
    assert gates.recipe_allowed(_sp(), _ci(), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)


def test_caution_warning_edited_after_approval_withholds():
    # A later non-human write over the approved text: the current text is no longer curator-authored.
    conn = _conn(HUMAN_ROW + [(7, "preparation_warnings", "pfaf_reparse", "Other text.", "2026-10-21 08:00:00")])
    assert gates.recipe_allowed(_sp(), _ci(pw="Other text."), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)


def test_latest_human_row_wins_over_older_rows():
    conn = _conn([(7, "preparation_warnings", "human", MARKER, "2026-06-24 19:26:42")] + HUMAN_ROW)
    assert gates.recipe_allowed(_sp(), _ci(), _recipe(), conn, CFG) == (True, "")


def test_other_species_warning_row_does_not_count():
    conn = _conn([(8, "preparation_warnings", "human", WARNING, "2026-10-20 19:00:00")])   # ci 8, not 7
    assert gates.recipe_allowed(_sp(), _ci(), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)


# ── rule 8 leaves the other rules alone ──────────────────────────────────────

def test_edible_species_needs_no_warning():
    conn = _conn()
    assert gates.recipe_allowed(_sp(status="edible"), _ci(pw=None), _recipe(), conn, CFG) == (True, "")
    assert "caution" not in gates.safety_texts(_sp(status="edible"), _ci(pw=None), conn)


def test_toxic_species_gets_toxic_warning_not_caution():
    conn = _conn(HUMAN_ROW)
    sp = _sp(status="caution", severity="toxic")
    out = gates.safety_texts(sp, _ci(), conn)
    assert out.get("toxic") == WARNING and "caution" not in out
    assert gates.recipe_allowed(sp, _ci(), _recipe(), conn, CFG)[0] is False


def test_unverified_caution_still_blocks_the_build():
    conn = _conn(HUMAN_ROW)
    try:
        gates.edibility_badge(_sp(verified=False), _ci(), conn, CFG)
    except gates.GateError:
        return
    raise AssertionError("unverified caution species must raise GateError (rule 2)")


def test_apiaceae_caution_keeps_id_card_and_shows_approved_warning():
    conn = _conn(HUMAN_ROW)
    sp = _sp(sci="Pimpinella major", family="Apiaceae")
    assert gates.edibility_badge(sp, _ci(), conn, CFG)["kind"] == "apiaceae"
    assert gates.recipe_allowed(sp, _ci(), _recipe(), conn, CFG) == (False, "Apiaceae — ID card only")
    assert gates.safety_texts(sp, _ci(), conn)["caution"] == WARNING


# ── import classifier (scripts/import_warning_review_drafts.py) ─────────────

def test_classify_pfaf_warning():
    assert classify(None, [], WARNING) == ("pfaf", WARNING, "PFAF Known Hazards")
    assert classify(WARNING, [], WARNING) == ("pfaf", WARNING, "PFAF Known Hazards")   # field = PFAF


def test_classify_field_text_that_differs_from_pfaf_is_queued_as_shown():
    """21 Oct 2026 (Frangula alnus): the shown text is queued, never PFAF's."""
    assert classify("old text", [], WARNING) == (
        "unknown_origin", "old text", "text in the field differs from PFAF — field text queued")


def test_classify_pfaf_none_known_is_no_data():
    assert classify("None known", [("pfaf_reparse", "None known")], "None Known")[0] is None
    assert classify(None, [], None)[2] == "no warning text anywhere"


def test_classify_unknown_origin_copies_field_verbatim():
    assert classify("The leaves are used in salads.", [], None) == (
        "unknown_origin", "The leaves are used in salads.", "text in the field, origin unknown")


def test_classify_pfaf_reparsed_field_with_history_still_queued():
    """A field PFAF wrote (machine history row) and PFAF agrees with → queued."""
    assert classify(WARNING, [("pfaf_reparse", WARNING)], WARNING)[0] == "pfaf"


def test_classify_machine_text_with_history_not_queued():
    assert classify("Some text.", [("pfaf_reparse", "Some text.")], None)[0] is None


def test_classify_curator_authored_skipped():
    assert classify(WARNING, [("human", WARNING)], "PFAF text")[0] is None


def test_classify_marker_row_queues_confirmation_of_current_text():
    assert classify(WARNING, [("human", MARKER)], "PFAF text") == (
        "marker_confirm", WARNING, "E-14 marker row — confirm the text is yours")


def test_classify_other_human_row_left_alone():
    assert classify(WARNING, [("pfaf_reparse", WARNING), ("human", "Older own text.")], "PFAF text")[0] is None


# ── rule 1b (Melvin, 21 Oct 2026): AI-agreed harmless species are shown ──────

def _obs(human=False, status="approved"):
    return {"id": 1, "species_id": 193, "species_primary": "Stellaria graminea", "review_status": status,
            "identification_status": "identified", "reviewed_at": "2026-10-21" if human else None}


def test_rule_1b_ai_agreed_harmless_included_hazard_blocks():
    stellaria = _sp(status="edible", sci="Stellaria graminea", family="Caryophyllaceae")
    ai = _obs(human=False)
    for verdict in ("edible", "caution", "inedible"):                    # harmless → shown
        sp = _sp(status=verdict, sci="Stellaria graminea", family="Caryophyllaceae")
        assert gates.ai_agreed_included(sp) and not gates.unconfirmed_hazard(sp), verdict
    assert gates.obs_passes(ai, set(), frozenset(), stellaria)
    assert not gates.obs_passes(ai, set(), frozenset())                  # no species row → fails closed
    assert not gates.obs_passes(ai, {1}, frozenset(), stellaria)         # hide_obs_ids still wins
    assert not gates.obs_passes(ai, set(), {193}, stellaria)             # hide_species_ids still wins
    assert not gates.obs_passes(_obs(status="needs_review"), set(), frozenset(), stellaria)
    # rule 7 unchanged: toxic / deadly / unknown AI-agreed species block and are not shown
    for status, sev in (("toxic", "toxic"), ("toxic", "deadly"), ("edible", "unknown"), ("unknown", "unknown"),
                        ("caution", "toxic"), ("unknown", "none"), (None, "none")):
        sp = _sp(status=status, severity=sev)
        assert gates.unconfirmed_hazard(sp) and not gates.ai_agreed_included(sp), (status, sev)
        assert not gates.obs_passes(ai, set(), frozenset(), sp), (status, sev)
        assert gates.obs_unconfirmed_hazard(ai, sp), (status, sev)
    assert gates.unconfirmed_hazard(None) and gates.obs_unconfirmed_hazard(ai, None)
    # human-confirmed observations pass whatever the verdict (warnings shown by rule 3)
    assert gates.obs_passes(_obs(human=True), set(), frozenset(), _sp(status="toxic", severity="deadly"))


def test_rule_1b_keeps_apiaceae_and_caution_rules():
    conn = _conn()                                                      # no curator warning
    hogweed = _sp(status="edible", sci="Heracleum sphondylium", family="Apiaceae")
    assert gates.ai_agreed_included(hogweed)                            # shown …
    assert gates.edibility_badge(hogweed, _ci(), conn, CFG)["kind"] == "apiaceae"   # … as an ID card only
    caution = _sp(status="caution")
    assert gates.ai_agreed_included(caution)
    assert gates.recipe_allowed(caution, _ci(pw=None), _recipe(), conn, CFG) == (False, gates.CAUTION_WITHHELD)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
