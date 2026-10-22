"""
net_health.py — tell "the source has no entry" apart from "the network failed"
(22 Oct 2026, after the 21 Oct offline run bp 203: 712 DNS failures were stored
as "no data", lowered 382 confidence scores and discarded 354 drafts).

Every source fetcher reports each attempt here:
  note_failure(source, detail)  DNS / connect / timeout / TLS error, or a 5xx /
                                429 gateway answer — the source could not be asked.
  note_success(source)          the source answered (200, or a real 404 "no entry").

enrich_species() wraps its fetches in track(): a fresh FetchLog collects what
this species' fetches reported (contextvars — the asyncio.gather tasks share the
same FetchLog object). run_enrichment_batch() sums those into the circuit
breaker. network_up() is the cheap probe used before resuming.
"""
import asyncio
import contextvars
import logging
import socket
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class FetchLog:
    failures: List[Tuple[str, str]] = field(default_factory=list)   # (source, detail)
    successes: List[str] = field(default_factory=list)

    @property
    def failed_sources(self) -> set:
        return {s for s, _ in self.failures}

    @property
    def answered_sources(self) -> set:
        return set(self.successes)


_current: contextvars.ContextVar[Optional[FetchLog]] = contextvars.ContextVar("lm_fetch_log", default=None)


@contextmanager
def track():
    """Collect the fetch outcomes of one species (nested calls share it)."""
    outer = _current.get()
    fl = FetchLog()
    token = _current.set(fl)
    try:
        yield fl
    finally:
        _current.reset(token)
        if outer is not None:                     # an outer tracker sees them too
            outer.failures.extend(fl.failures)
            outer.successes.extend(fl.successes)


def note_failure(source: str, detail: object = "") -> None:
    fl = _current.get()
    if fl is not None:
        fl.failures.append((source, str(detail)[:200]))


def note_success(source: str) -> None:
    fl = _current.get()
    if fl is not None:
        fl.successes.append(source)


def is_gateway_failure(status_code: int) -> bool:
    """A status that means the source could not be asked (not 'no entry')."""
    return status_code >= 500 or status_code == 429


# curl exit codes that mean the network failed (6 resolve, 7 connect, 28 timeout,
# 35 TLS, 52 empty reply, 56 receive error) — not "page not found".
CURL_NETWORK_EXIT = {5, 6, 7, 28, 35, 52, 55, 56}

PROBE_HOSTS = ("pfaf.org", "www.wikidata.org", "api.inaturalist.org")


async def network_up(timeout: float = 5.0) -> bool:
    """True when at least one source host resolves (DNS was what failed on 21 Oct)."""
    loop = asyncio.get_running_loop()
    for host in PROBE_HOSTS:
        try:
            await asyncio.wait_for(loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM), timeout)
            return True
        except Exception:
            continue
    return False
