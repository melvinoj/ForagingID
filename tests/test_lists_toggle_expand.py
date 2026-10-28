"""
Lists: each selected-species row opens the dropdown with fill status + PDF-include
toggles again (toggleExpand had lost its only caller; Melvin, 28 Oct 2026).

Static check of frontend/lists.html — the live check is Melvin's.
Run from project root:  python tests/test_lists_toggle_expand.py
"""
import os
import re

SRC = open(os.path.join(os.path.dirname(__file__), "..", "frontend", "lists.html"), encoding="utf-8").read()


def _render_body():
    start = SRC.index("function render() {")
    return SRC[start:SRC.index("\n}\n", start)]


def test_each_row_has_a_toggle_and_the_containers_toggle_expand_uses():
    body = _render_body()
    assert "onclick=\"toggleExpand(${lmJsArg(name)})\"" in body
    # toggleExpand looks up card-<safe> and detail-<safe> with the same safe rule.
    assert 'id="card-${safe}"' in body and 'id="detail-${safe}"' in body
    assert "name.replace(/[^a-zA-Z0-9]/g, '_')" in body
    fn = SRC[SRC.index("function toggleExpand(name) {"):]
    assert "document.getElementById('card-' + safe)" in fn[:600]
    assert "document.getElementById('detail-' + safe)" in fn[:600]


def test_the_dropdown_shows_when_expanded():
    assert re.search(r"\.sp-compact-item\.expanded \.lc-detail \{ display: block; \}", SRC)
    assert re.search(r"\.lc-detail \{ display: none;", SRC)


def test_toggle_expand_is_still_defined_once():
    assert SRC.count("function toggleExpand(name)") == 1
    assert SRC.count("function toggleExpandFill(name)") == 1


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
