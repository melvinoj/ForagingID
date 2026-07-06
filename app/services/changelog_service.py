"""
changelog_service.py — Read and write CHANGELOG.md.

Structure expected:

    ## Current State
    (replaced entirely on each session-end / snapshot)

    ## History
    (append-only; new entries prepended after the ## History header)
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

CHANGELOG_PATH = Path(__file__).parent.parent.parent / "CHANGELOG.md"


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
        if line.strip() == "## Current State":
            in_section = True
            continue
        if in_section and line.startswith("## "):
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
        if line.strip() == "## Current State":
            state_start = i
        elif state_start is not None and line.startswith("## ") and i > state_start:
            state_end = i
            break

    new_block = f"## Current State\n\n{new_state.strip()}"

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
