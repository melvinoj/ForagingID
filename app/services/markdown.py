"""
One Markdown dialect for recipe text (batch 15, P4, 28 Oct 2026).

Python twin of frontend/static/js/md.js — the two must produce byte-identical
HTML for the same input (tests/test_batch15_markdown.py runs both on one golden
list). Before this there were five renderers with four rule sets; the PDF one
rendered only the first line of a "#" block and silently dropped the rest
(recipe 125 lost its whole ingredient list).

Rules (a superset of the old ones):
  * escape first (& < > " ') — recipe text can never inject HTML; no raw HTML,
    and a Markdown link renders as its text only, never <a>;
  * blocks split on blank lines; inside a block every line is classified on its
    own: "# …" … "###### …" heading, "- / * / + / 1. / 1)" list item, else a
    paragraph line (paragraph lines join with <br>);
  * inline: **bold** / __bold__, *italic* / _italic_ (not inside words, so
    snake_case and 2*3*4 stay as they are), `code`;
  * a block that is only --- / *** / ___ (a horizontal rule) is dropped.

Only recipe text goes through here. Curator warnings (look_alike_warnings,
preparation_warnings) are escaped plain text on every surface and must never be
rendered as Markdown — safety text renders verbatim.
"""
import re
from typing import Callable, List, Optional, Tuple

_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}
_ESC_RE = re.compile(r"[&<>\"']")

_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_CODE = re.compile(r"`([^`\n]+)`")
_BOLD_A = re.compile(r"\*\*(.+?)\*\*")
_BOLD_U = re.compile(r"__(.+?)__")
_EM_A = re.compile(r"(^|[^A-Za-z0-9_*])\*(?=\S)(.*?\S)\*(?![A-Za-z0-9_*])")
_EM_U = re.compile(r"(^|[^A-Za-z0-9_])_(?=\S)(.*?\S)_(?![A-Za-z0-9_])")

_BLOCK_SPLIT = re.compile(r"\n[ \t]*\n")
_HR = re.compile(r"^[-*_]{3,}$")
_HEAD = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
_ITEM = re.compile(r"^[ \t]*([-*+]|[0-9]+[.)])[ \t]+(.*)$")
_CITATION = re.compile(r"\[[^\]]*\]\s*")

Block = Tuple  # ("h", level, text) | ("ul" | "ol", [items]) | ("p", [lines])


def esc(s) -> str:
    """5-character HTML escape — the same table as static/js/esc.js."""
    return "" if s is None else _ESC_RE.sub(lambda m: _ESC[m.group(0)], str(s))


def inline(text: str) -> str:
    """Escape, then link text / code / bold / italic."""
    t = esc(text)
    t = _LINK.sub(r"\1", t)
    t = _CODE.sub(r"<code>\1</code>", t)
    t = _BOLD_A.sub(r"<strong>\1</strong>", t)
    t = _BOLD_U.sub(r"<strong>\1</strong>", t)
    t = _EM_A.sub(r"\1<em>\2</em>", t)
    t = _EM_U.sub(r"\1<em>\2</em>", t)
    return t


def raw_blocks(text) -> List[str]:
    """The blank-line-separated blocks, stripped, empties and rules dropped."""
    out = []
    for b in _BLOCK_SPLIT.split(str(text or "").replace("\r", "")):
        b = b.strip()
        if b and not _HR.match(b):
            out.append(b)
    return out


def parse_block(b: str) -> List[Block]:
    """One raw block → headings / lists / paragraphs, line by line (raw text)."""
    out: List[Block] = []
    para: List[str] = []
    lst: Optional[list] = None
    for line in b.split("\n"):
        s = line.strip()
        if not s:
            continue
        h = _HEAD.match(s)
        it = None if h else _ITEM.match(line)
        if h:
            if para:
                out.append(("p", para)); para = []
            if lst:
                out.append(tuple(lst)); lst = None
            out.append(("h", len(h.group(1)), h.group(2)))
        elif it:
            if para:
                out.append(("p", para)); para = []
            kind = "ol" if it.group(1)[0] in "0123456789" else "ul"
            if lst and lst[0] == kind:
                lst[1].append(it.group(2))
            else:
                if lst:
                    out.append(tuple(lst))
                lst = [kind, [it.group(2)]]
        else:
            if lst:
                out.append(tuple(lst)); lst = None
            para.append(s)
    if para:
        out.append(("p", para))
    if lst:
        out.append(tuple(lst))
    return out


def _default_heading(level: int) -> Tuple[str, Optional[str]]:
    return "h3", None


def render_md(text, heading: Callable[[int], Tuple[str, Optional[str]]] = _default_heading) -> str:
    """Recipe Markdown → safe HTML. `heading(level)` gives (tag, class) — the
    handouts use h3 for every level, the species page h4–h6 class recipe-h."""
    out = []
    for b in raw_blocks(text):
        for blk in parse_block(b):
            if blk[0] == "h":
                tag, cls = heading(blk[1])
                attr = f' class="{cls}"' if cls else ""
                out.append(f"<{tag}{attr}>{inline(blk[2])}</{tag}>")
            elif blk[0] in ("ul", "ol"):
                items = "".join(f"<li>{inline(i)}</li>" for i in blk[1])
                out.append(f"<{blk[0]}>{items}</{blk[0]}>")
            else:
                out.append("<p>" + "<br>".join(inline(l) for l in blk[1]) + "</p>")
    return "".join(out)


def _norm_title(s: str) -> str:
    return re.sub(r"[#*_\s]+", " ", s or "").strip().lower()


_S_HEAD = "<div style='font-weight:600;color:#2d5016;margin:6px 0 2px'>"


def md_snippet(body: str, title: str, limit: int = 700) -> str:
    """Recipe Markdown → small inline-styled HTML for the walk stop card / Export
    summary (the same dialect as render_md). A leading heading that repeats the
    recipe title is dropped (the title is already shown). Whole blocks are kept
    up to ~limit characters, then '…'. Paragraph lines join with a space."""
    blocks = raw_blocks(body)
    title_norm = _norm_title(title)
    out, used = [], 0
    for i, b in enumerate(blocks):
        first = b.split("\n", 1)[0]
        m = _HEAD.match(first.strip())
        if i <= 1 and not out and _norm_title(b) == title_norm:
            continue                                            # "**Title**" / "# Title" alone
        if m and i == 0 and _norm_title(m.group(2)) == title_norm:
            rest = b.split("\n", 1)[1].strip() if "\n" in b else ""
            if not rest:
                continue
            b = rest
        if used and used + len(b) > limit:
            out.append("<p style='margin:4px 0 0'>…</p>")
            break
        used += len(b)
        for blk in parse_block(b):
            if blk[0] == "h":
                out.append(f"{_S_HEAD}{inline(blk[2])}</div>")
            elif blk[0] in ("ul", "ol"):
                items = "".join(f"<li>{inline(x)}</li>" for x in blk[1])
                out.append(f"<{blk[0]} style='margin:4px 0 4px 18px;padding:0'>{items}</{blk[0]}>")
            else:
                out.append(f"<p style='margin:4px 0'>{inline(' '.join(blk[1]))}</p>")
    return "".join(out)


def strip_citations(text) -> str:
    """Drop PFAF-style [n] / [source] citation brackets (the id_notes clean-up)."""
    return _CITATION.sub("", text or "").strip()
