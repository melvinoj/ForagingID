"""
Tests for the End Session CHANGELOG rewrite (17-B8, 28 Oct 2026).

A body that began with a dated "## Current State — <date>" heading used to
become the next rewrite's end boundary, so older blocks stayed stacked under the
live one. Now every "## Current State" heading (bare or dated) belongs to the one
section, which ends at the next other "## " heading (## History).

  * stacked bare + dated blocks are all replaced by exactly one block;
  * ## History and everything after it is untouched;
  * an incoming bare or dated header yields exactly one header (a date stays as
    plain text);
  * the rewrite is idempotent;
  * get_current_state reads the whole section, not just up to a dated heading;
  * "### Current State — …" in the Archive is never touched.

Only temp files — CHANGELOG_PATH is pointed away from the real CHANGELOG.

Run from project root:  python tests/test_changelog_service.py
"""
import os
import pathlib
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.services import changelog_service as cs  # noqa: E402

HISTORY = "## History\n\n### 2026-10-28 04:00\nolder entry\n\n## Archive — earlier Current State blocks\n\n### Current State — 15 Oct 2026\nkept\n"

STACKED = (
    "## Current State\n\nlive body\n\n"
    "## Current State — 22 Oct 2026, evening\n\n### Build\nstale one\n\n"
    "## Current State — 21 Oct 2026, evening\n\nstale two\n\n"
    + HISTORY
)


def _with(text):
    d = tempfile.mkdtemp()
    p = pathlib.Path(d, "CHANGELOG.md")
    p.write_text(text, encoding="utf-8")
    cs.CHANGELOG_PATH = p
    return p


def test_stacked_blocks_are_all_replaced():
    p = _with(STACKED)
    cs.rewrite_current_state("### Next\n- new item")
    out = p.read_text(encoding="utf-8")
    assert out.count("## Current State") == 2, out          # live + the Archive's ### one
    assert out.startswith("## Current State\n\n### Next\n- new item\n\n## History\n"), out
    assert "stale one" not in out and "stale two" not in out and "live body" not in out
    assert out.endswith(HISTORY), out


def test_history_and_archive_untouched():
    p = _with(STACKED)
    cs.rewrite_current_state("x")
    out = p.read_text(encoding="utf-8")
    assert out[out.index("## History"):] == HISTORY
    assert "### Current State — 15 Oct 2026\nkept" in out


def test_incoming_bare_header_gives_one_header():
    p = _with(STACKED)
    cs.rewrite_current_state("## Current State\n\nbody A")
    out = p.read_text(encoding="utf-8")
    assert out.startswith("## Current State\n\nbody A\n\n## History"), out


def test_incoming_dated_header_keeps_date_as_text():
    p = _with(STACKED)
    cs.rewrite_current_state("## Current State — 28 Oct 2026, morning\n\nbody B")
    out = p.read_text(encoding="utf-8")
    assert out.startswith("## Current State\n\n28 Oct 2026, morning\n\nbody B\n\n## History"), out
    assert "## Current State — 28 Oct" not in out
    # the next rewrite still replaces it (no stacking)
    cs.rewrite_current_state("body C")
    out = p.read_text(encoding="utf-8")
    assert out.startswith("## Current State\n\nbody C\n\n## History"), out


def test_idempotent():
    p = _with(STACKED)
    cs.rewrite_current_state("## Current State\n\nsame")
    once = p.read_text(encoding="utf-8")
    cs.rewrite_current_state("## Current State\n\nsame")
    assert p.read_text(encoding="utf-8") == once
    cs.rewrite_current_state("same")
    assert p.read_text(encoding="utf-8") == once


def test_get_current_state_reads_whole_section():
    _with(STACKED)
    got = cs.get_current_state()
    assert "live body" in got and "stale one" in got and "stale two" in got
    assert "older entry" not in got


def test_no_section_prepends():
    p = _with(HISTORY)
    cs.rewrite_current_state("fresh")
    assert p.read_text(encoding="utf-8").startswith("## Current State\n\nfresh\n\n## History")


def test_real_changelog_has_one_current_state_block():
    real = pathlib.Path(ROOT, "CHANGELOG.md").read_text(encoding="utf-8")
    heads = [l for l in real.splitlines() if l.startswith("## Current State")]
    assert heads == ["## Current State"], heads


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
