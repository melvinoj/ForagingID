"""
Tests for fix batch 14 (21 Oct 2026): the nav Review badge must equal the
Review page's default queue. Before, site-header.js added pending_review +
needs_review (2,080) while the page opens on Status = "Needs review" (386).
Both now read one definition — app.services.observation_counts.REVIEW_QUEUE —
through GET /api/observations/stats (review_queue_count) and
GET /api/observations?review_status=needs_review.

Run from project root:  python -m pytest tests/test_review_queue_count.py -v
Or standalone:          python tests/test_review_queue_count.py
"""

import asyncio
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
from app.database import Base  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.api.observations import list_observations, observation_stats  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
MIX = {"needs_review": 7, "pending": 11, "approved": 3, "manually_verified": 2, "rejected": 5}


def _run(coro):
    return asyncio.run(coro)


async def _setup():
    path = os.path.join(tempfile.mkdtemp(prefix="rqtest_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        n = 0
        for status, k in MIX.items():
            for _ in range(k):
                n += 1
                s.add(Observation(file_path=f"/tmp/x{n}.jpg", file_hash=f"h{n}", review_status=status,
                                  identification_status="identified"))
        await s.commit()
    return eng, S


def _queue_and_stats():
    async def run():
        eng, S = await _setup()
        async with S() as s:
            stats = await observation_stats(db=s)
            rows = await list_observations(limit=500, offset=0, geotagged_only=False, no_gps=False,
                                           named_only=False, unnamed_only=False, review_status="needs_review",
                                           upload_source=None, obs_category=None, prefilter_category=None,
                                           review_label=None, q=None, exclude_not_plant=False,
                                           sort="date_desc", db=s)
        await eng.dispose()
        return stats, rows
    return _run(run())


def test_badge_count_equals_default_queue():
    stats, rows = _queue_and_stats()
    assert stats["review_queue_status"] == "needs_review"
    assert stats["review_queue_count"] == len(rows) == MIX["needs_review"]
    # the page's own count for its default filter (getFilteredCount → by_status[status])
    assert stats["by_status"]["needs_review"] == len(rows)


def test_badge_no_longer_adds_pending():
    stats, _ = _queue_and_stats()
    assert stats["review_queue_count"] != stats["pending_review"] + stats["needs_review"]
    assert stats["pending_review"] == MIX["pending"]


def test_review_page_defaults_to_the_queue_the_badge_counts():
    html = open(os.path.join(ROOT, "frontend", "review.html"), encoding="utf-8").read()
    sel = re.search(r'<select id="filter-status"[^>]*>\s*<option value="([^"]*)"', html)
    assert sel and sel.group(1) == "needs_review", "the Review page's default Status filter changed"


def test_header_badge_reads_the_shared_count():
    js = open(os.path.join(ROOT, "frontend", "static", "js", "site-header.js"), encoding="utf-8").read()
    body = js[js.index("function _initReviewBadge"):js.index("_buildHeader();")]
    assert "d.review_queue_count" in body
    assert "pending_review" not in body and "pending + flagged" not in body


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
