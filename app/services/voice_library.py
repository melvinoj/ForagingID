"""
Voice library loader — reads voice_library/ folder, returns a context block
for injection into AI prompt builders.

Filename convention (for future context filtering):
  {context}_{descriptor}.md  e.g. recipe_elder_rob_jelly.md
  Untagged files (no underscore prefix matching a known context) = always eligible.

Known contexts: recipe, foraging_note, medicinal
"""
import random
import re
from pathlib import Path
from typing import Optional

VOICE_LIBRARY_DIR = Path(__file__).parent.parent.parent / "voice_library"
KNOWN_CONTEXTS = {"recipe", "foraging_note", "medicinal"}
SAMPLE_SIZE = 3  # number of recipe examples to include per prompt call


def _parse_file(path: Path) -> dict:
    """Return {context, name, body} for a voice library file."""
    stem = path.stem  # filename without extension
    parts = stem.split("_", 1)
    context = parts[0] if parts[0] in KNOWN_CONTEXTS else None
    return {"context": context, "path": path}


def _extract_sections(md_text: str) -> "tuple[str, list[str]]":
    """
    Split melvin_voice.md into:
      - values_block: everything under '## Values'
      - examples: list of individual recipe blocks under '## Recipe examples'
    For other files, treat entire content as a single example with no values block.
    """
    values_block = ""
    examples = []

    values_match = re.search(r"## Values.*?\n(.*?)(?=##|\Z)", md_text, re.DOTALL)
    if values_match:
        values_block = values_match.group(1).strip()

    # Split recipe examples on HTML comment markers or bold headers
    recipe_section_match = re.search(r"## Recipe examples.*?\n(.*)", md_text, re.DOTALL)
    if recipe_section_match:
        recipe_body = recipe_section_match.group(1)
        # Split on <!-- recipe_* --> markers
        parts = re.split(r"<!--.*?-->", recipe_body)
        examples = [p.strip() for p in parts if p.strip()]
    elif not values_block:
        # Plain file with no sections — treat whole content as one example
        examples = [md_text.strip()]

    return values_block, examples


def load_voice_context(context: Optional[str] = None) -> str:
    """
    Build a voice context string for injection into AI prompts.

    Args:
        context: optional filter — 'recipe', 'foraging_note', 'medicinal'.
                 None = all examples eligible.

    Returns:
        A formatted string ready for insertion into a system prompt.
        Returns empty string if voice_library/ folder does not exist.
    """
    if not VOICE_LIBRARY_DIR.exists():
        return ""

    values_block = ""
    all_examples = []

    for path in sorted(VOICE_LIBRARY_DIR.glob("*.md")):
        meta = _parse_file(path)
        text = path.read_text(encoding="utf-8")
        vb, examples = _extract_sections(text)
        if vb:
            values_block = vb  # use values from whichever file has them (melvin_voice.md)
        # Filter by context if requested; untagged files always eligible
        if context is None or meta["context"] is None or meta["context"] == context:
            all_examples.extend(examples)

    if not values_block and not all_examples:
        return ""

    sampled = random.sample(all_examples, min(SAMPLE_SIZE, len(all_examples)))

    parts = []
    if values_block:
        parts.append(f"Cooking voice and values:\n{values_block}")
    if sampled:
        parts.append("Example recipes in this voice:\n\n" + "\n\n---\n\n".join(sampled))

    return "\n\n".join(parts)
