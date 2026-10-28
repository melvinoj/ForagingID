"""
Tests for three small batch-14 items (21 Oct 2026):

E-04  End Session's "since the previous snapshot" date: the old parse cut every
      date containing "-0" and fell back to exporting ALL encounters; the kept
      part was also local time compared against UTC encounter dates.
D1-03 The PDF disclaimer promised provenance markers no print output has.
D2-01 Export summary: the "Also here" repeat-line warning badge was always red,
      including "⚠ toxicity unknown" (amber in the full block and in the app).

Run from project root:  python -m pytest tests/test_batch14_e04_d1_03_d2_01.py -v
Or standalone:          python tests/test_batch14_e04_d1_03_d2_01.py
"""

import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.dev import git_commit_time_utc  # noqa: E402
from app.api.sharing import (WalkExportRequest, WalkRepeat, WalkSpecies, WalkStop,  # noqa: E402
                             _build_walk_html)

ROOT = os.path.join(os.path.dirname(__file__), "..")


# ── E-04 ──────────────────────────────────────────────────────────────────────

def test_git_commit_time_is_parsed_as_utc_for_every_date():
    cases = {
        "2026-06-05T21:09:29+01:00": datetime(2026, 6, 5, 20, 9, 29),   # "-0" in month and day
        "2026-10-20T21:19:16+02:00": datetime(2026, 10, 20, 19, 19, 16),
        "2026-01-01T00:30:00+02:00": datetime(2025, 12, 31, 22, 30, 0),  # crosses the year in UTC
        "2026-12-12T08:00:00Z":      datetime(2026, 12, 12, 8, 0, 0),
        "2026-07-03T09:00:00-04:00": datetime(2026, 7, 3, 13, 0, 0),
    }
    for ts, want in cases.items():
        got = git_commit_time_utc(ts)
        assert got == want and got.tzinfo is None, (ts, got)


def test_git_commit_time_refuses_a_time_with_no_offset():
    try:
        git_commit_time_utc("2026-06-05T21:09:29")
    except ValueError:
        return
    raise AssertionError("a time without an offset must not be guessed")


def test_old_parse_broke_on_dash_zero_dates():
    """Proof of the bug the fix removes (the pre-fix expression, %ci format)."""
    old = lambda ts: datetime.fromisoformat(ts.split("+")[0].split("-0")[0].strip())  # noqa: E731
    try:
        old("2026-06-05 21:09:29 +0100")
    except ValueError:
        pass
    else:
        raise AssertionError("expected the old parse to fail on a '-0' date")
    assert old("2026-11-12 21:09:29 +0100") == datetime(2026, 11, 12, 21, 9, 29)   # local, not UTC


def test_end_session_uses_the_strict_iso_format_and_the_helper():
    src = open(os.path.join(ROOT, "app", "api", "dev.py"), encoding="utf-8").read()
    assert '"--format=%cI"' in src and "git_commit_time_utc(ts_line)" in src
    assert 'ts_line.split(' not in src and '"--format=%ci"' not in src


# ── D1-03 ─────────────────────────────────────────────────────────────────────

def test_pdf_disclaimer_no_longer_promises_provenance_markers():
    tpl = open(os.path.join(ROOT, "app", "templates", "print_pdf.html"), encoding="utf-8").read()
    para = re.search(r'<div class="final-disclaimer">.*?<p>(.*?)</p>', tpl, re.S).group(1)
    assert "indicated where shown" not in para
    # everything else word for word
    assert para == (
        "Edibility and medicinal information in this booklet is for educational reference only. "
        "Always verify identification with multiple authoritative sources before consuming any wild "
        "plant or fungi. Never rely on any single source, including this booklet, as your sole basis "
        "for a consumption decision. Identification and content may be AI-assisted. LandMemory is an "
        "educational tool, not a safety-certified identification system.")
    for rel in ("frontend/print.html", "frontend/lists.html", "app/api/lists_pdf.py", "app/api/sharing.py"):
        assert "indicated where shown" not in open(os.path.join(ROOT, rel), encoding="utf-8").read(), rel


# ── D2-01 ─────────────────────────────────────────────────────────────────────

def _badge_style(html, label):
    m = re.search(r'<span style="([^"]*)">' + re.escape(label) + r'</span>', html)
    assert m, label
    return m.group(1)


def test_repeat_line_badge_matches_the_full_block_colour():
    body = WalkExportRequest(title="t", stops=[
        WalkStop(num=1, label="1", species=[
            WalkSpecies(species_scientific="Heracleum sibiricum", toxicity_warning="⚠ toxicity unknown"),
            WalkSpecies(species_scientific="Hedera helix", toxicity_warning="☠ toxic"),
        ]),
        WalkStop(num=2, label="2", also_here=[
            WalkRepeat(species_scientific="Heracleum sibiricum", first_label="1",
                       toxicity_warning="⚠ toxicity unknown"),
            WalkRepeat(species_scientific="Hedera helix", species_common="Ivy", first_label="1",
                       toxicity_warning="☠ toxic"),
        ]),
    ])
    html = _build_walk_html(body)
    repeat = html[html.index("Also here:"):]
    full = html[:html.index("Also here:")]
    assert "background:#fef3c7;color:#92400e" in _badge_style(repeat, "⚠ toxicity unknown")   # amber
    assert "background:#dc2626;color:#fff" in _badge_style(repeat, "☠ toxic")                  # red
    assert "background:#fef3c7;color:#92400e" in _badge_style(full, "⚠ toxicity unknown")
    assert "background:#dc2626;color:#fff" in _badge_style(full, "☠ toxic")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
