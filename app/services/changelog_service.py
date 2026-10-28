"""
changelog_service.py — Read and write CHANGELOG.md.

Structure expected:

    ## Current State
    (replaced entirely on each session-end / snapshot)

    ## History
    (append-only; new entries prepended after the ## History header)
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

CHANGELOG_PATH = Path(__file__).parent.parent.parent / "CHANGELOG.md"

# "## Current State" bare or dated ("## Current State — 22 Oct 2026, evening").
# A dated heading used to count as a DIFFERENT section, so a body that began
# with one became the next rewrite's end boundary and every older block stayed
# stacked under the live one (17-B8, 28 Oct 2026). Both forms are now part of
# the one section; it ends at the first other "## " heading (## History).
_CURRENT_STATE_RE = re.compile(r"^## Current State(?:\s*$|\s+[—–-]\s*(?P<date>.*)$)")


def _is_current_state_heading(line: str) -> bool:
    return bool(_CURRENT_STATE_RE.match(line.strip()))


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def read_changelog() -> str:
    """Return full CHANGELOG.md text, or empty string if file doesn't exist."""
    if CHANGELOG_PATH.exists():
        return CHANGELOG_PATH.read_text(encoding="utf-8")
    return ""


def get_current_state() -> str:
    """Return the text of the ## Current State section (without the header line)."""
    text = read_changelog()
    lines = text.splitlines()
    in_section = False
    result: list[str] = []
    for line in lines:
        if not in_section and _is_current_state_heading(line):
            in_section = True
            continue
        # Stop at the next section that is not a Current State heading (bare or
        # dated) — a stacked duplicate never ends the section early.
        if in_section and line.startswith("## ") and not _is_current_state_heading(line):
            break
        if in_section:
            result.append(line)
    return "\n".join(result).strip()


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def rewrite_current_state(new_state: str) -> None:
    """Replace the entire ## Current State block with *new_state*."""
    text = read_changelog()
    lines = text.splitlines()

    state_start: Optional[int] = None
    state_end:   Optional[int] = None

    for i, line in enumerate(lines):
        if _is_current_state_heading(line):
            # Anchor to the FIRST header only. Later Current State headings (bare
            # or dated) fall through as no-ops, so the replaced span
            # [state_start, state_end) covers every stacked block beneath.
            if state_start is None:
                state_start = i
        elif state_start is not None and line.startswith("## "):
            # The next section that is not a Current State heading (## History).
            state_end = i
            break

    # Flaw 2: new_state may already carry its own "## Current State" header (the
    # CLAUDE.md end-session contract invites "a fresh ## Current State block").
    # Strip a leading header line + its trailing blanks so exactly one header is
    # prepended. Idempotent: input with or without the header yields the same block.
    # A dated header ("## Current State — 28 Oct 2026") keeps its date as the
    # body's first line, so it never becomes a heading of its own.
    body_lines = new_state.strip().splitlines()
    m = _CURRENT_STATE_RE.match(body_lines[0].strip()) if body_lines else None
    if m:
        body_lines = body_lines[1:]
        while body_lines and body_lines[0].strip() == "":
            body_lines = body_lines[1:]
        if m.group("date"):
            body_lines = [m.group("date").strip(), ""] + body_lines
    body = "\n".join(body_lines).strip()
    new_block = f"## Current State\n\n{body}"

    if state_start is None:
        # Prepend — no existing section
        new_text = new_block + "\n\n" + text
    else:
        end = state_end if state_end is not None else len(lines)
        before = "\n".join(lines[:state_start])
        after  = "\n".join(lines[end:])
        new_text = (before.rstrip() + "\n\n" if before.strip() else "") \
                 + new_block + "\n\n" \
                 + after.lstrip()

    CHANGELOG_PATH.write_text(new_text.rstrip() + "\n", encoding="utf-8")


def append_history_entry(entry: str) -> None:
    """Prepend a timestamped entry directly under the ## History header."""
    text = read_changelog()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    full_entry = f"\n### {ts}\n{entry.strip()}\n"

    if "## History" in text:
        idx = text.index("## History")
        eol = text.index("\n", idx)
        new_text = text[: eol + 1] + full_entry + text[eol + 1 :]
    else:
        new_text = text.rstrip() + "\n\n## History\n" + full_entry

    CHANGELOG_PATH.write_text(new_text, encoding="utf-8")
