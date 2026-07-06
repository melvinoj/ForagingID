"""
Tests for normalize_taxon_key.

Run from project root:  python -m pytest tests/test_taxonomy.py -v
Or standalone:          python tests/test_taxonomy.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.taxonomy import normalize_taxon_key as nk, collapse_autonym as ca


def test_x_inside_word_preserved():
    """x within an epithet (Taxus, Larix, etc.) must never be stripped."""
    assert nk("Taxus baccata") == "taxus baccata"

def test_autonym_trinomial_larix():
    assert nk("Larix decidua decidua") == "larix decidua"

def test_autonym_trinomial_daucus():
    assert nk("Daucus carota carota") == "daucus carota"

def test_autonym_trinomial_verbascum():
    assert nk("Verbascum thapsus thapsus") == "verbascum thapsus"

def test_unicode_hybrid_collapsed():
    """× should collapse to same key as plain name."""
    assert nk("Geranium × oxonianum") == nk("Geranium oxonianum")

def test_ascii_hybrid_x_collapsed_prunus_fruticans():
    assert nk("Prunus × fruticans") == nk("Prunus fruticans")

def test_ascii_hybrid_x_collapsed_prunus_syriaca():
    assert nk("Prunus × syriaca") == nk("Prunus syriaca")

def test_cross_genus_synonym_different_polyporus():
    """True cross-genus synonyms must NOT be merged by the normalizer."""
    assert nk("Polyporus versicolor") != nk("Trametes versicolor")

def test_cross_genus_synonym_different_stellaria():
    assert nk("Stellaria holostea") != nk("Rabelera holostea")

def test_empty_string():
    assert nk("") == ""

def test_extra_whitespace():
    assert nk("  Rosa  canina  ") == "rosa canina"

def test_bare_x_token_stripped():
    """Standalone ASCII x (as hybrid marker) must be stripped as a token."""
    assert nk("Mentha x piperita") == nk("Mentha piperita")

def test_rank_abbrev_not_collapsed():
    """subsp. trinomials with distinct epithet[2] must NOT be autonym-collapsed."""
    # Solanum tuberosum subsp. tuberosum IS an autonym — but only if token[2]==token[1]
    # and token[1] is a rank abbrev, autonym collapse is skipped
    assert nk("Rosa canina subsp. vosagiaca") == "rosa canina subsp. vosagiaca"


# ---------------------------------------------------------------------------
# collapse_autonym tests
# ---------------------------------------------------------------------------

def test_collapse_autonym_larix():
    assert ca("Larix decidua decidua") == "Larix decidua"

def test_collapse_autonym_hybrid_unchanged():
    assert ca("Geranium × oxonianum") == "Geranium × oxonianum"

def test_collapse_autonym_binomial_unchanged():
    assert ca("Taxus baccata") == "Taxus baccata"

def test_collapse_autonym_real_infraspecific_unchanged():
    assert ca("Daucus carota subsp. sativus") == "Daucus carota subsp. sativus"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
