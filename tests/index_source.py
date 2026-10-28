"""
The map page's source after batch 16 (index.html split, 28 Oct 2026).

frontend/index.html now loads static/css/index.css and static/js/index/*.js.
The split was verbatim, so re-inlining those files rebuilds the pre-split page
byte for byte; tests that read "frontend/index.html" as one text read this.

  index_source()       the re-inlined page (one text, as before the split)
  index_parts()        [(published path, file path)] in load order
"""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND = os.path.join(ROOT, "frontend")
INDEX_HTML = os.path.join(FRONTEND, "index.html")

CSS_LINK = '  <link rel="stylesheet" href="/static/css/index.css">\n'
SCRIPT_RE = re.compile(r'^<script src="(/static/js/index/[a-z-]+\.js)"></script>\n', re.M)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _file(published):
    return os.path.join(FRONTEND, published.lstrip("/"))


def index_parts():
    html = _read(INDEX_HTML)
    parts = [("/static/css/index.css", _file("/static/css/index.css"))] if CSS_LINK in html else []
    parts += [(p, _file(p)) for p in SCRIPT_RE.findall(html)]
    return parts


def index_source(html=None):
    html = _read(INDEX_HTML) if html is None else html
    assert html.count(CSS_LINK) == 1, "index.css link missing or repeated"
    html = html.replace(CSS_LINK, "  <style>\n" + _read(_file("/static/css/index.css")) + "  </style>\n")
    tags = list(SCRIPT_RE.finditer(html))
    assert tags, "no static/js/index/*.js script tags"
    first, last = tags[0].start(), tags[-1].end()
    assert html[first:last] == "".join(t.group(0) for t in tags), "index script tags are not consecutive"
    body = "".join(_read(_file(t.group(1))) for t in tags)
    return html[:first] + "<script>\n" + body + "</script>\n" + html[last:]
