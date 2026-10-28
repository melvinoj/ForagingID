"""
Safety batch item 6 (CLOSEOUT 28 Oct section 4 #7, GPT 4): the sightings photo
viewer showed only name + date, so a pending photo looked confirmed once opened.
The caption now carries "pending review" exactly when the grid tile does
(stateLabel); confirmed and scene captions are unchanged.

Run: python tests/test_safety_sightings_viewer_pending.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_batch8_guest_and_culinary_warnings import _extract, _jsc  # noqa: E402

SRC = open(os.path.join(ROOT, "frontend", "sightings.html"), encoding="utf-8").read()


def test_viewer_caption_says_pending_like_the_tile():
    fns = (_extract(SRC, "function displayName(obs)", "// ── Rendering")
           + _extract(SRC, "function openPhoto(id)", "// Pin button"))
    obs = [
        {"id": 1, "species_primary": "Rumex acetosa", "review_status": "needs_review", "photo_taken_at": "2026-10-01T10:00:00"},
        {"id": 2, "species_primary": "Rumex acetosa", "review_status": "approved", "photo_taken_at": "2026-10-01T10:00:00"},
        {"id": 3, "species_primary": None, "obs_category": "landscape", "review_status": "pending"},
        {"id": 4, "species_suggested": "Urtica dioica", "review_status": "pending"},
    ]
    script = (f"var _images = {json.dumps(obs)}; var _got;\n"
              "function openLightbox(items, i) { _got = items.map(x => x.caption); }\n"
              "function _syncSpeciesLink() {}\n"
              + fns + "\nopenPhoto(1); print(JSON.stringify(_got));")
    caps = _jsc(script)
    assert caps[0].startswith("Rumex acetosa · pending review · "), caps
    assert "pending" not in caps[1] and caps[1].startswith("Rumex acetosa · "), caps
    assert caps[2] == "Unidentified", caps                      # scene: tile says "scene", not pending
    assert caps[3] == "Urtica dioica · pending review", caps


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
