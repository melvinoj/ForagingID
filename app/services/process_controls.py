"""
Per-row control descriptor for the background-job widget (Phase 3e-1a).

ONE definition of "which controls does this row offer, and at what URL". Both
feed serializers attach it under the "controls" key:
  - app.services.background_processes._row_to_dict   (process feed)
  - app.api.queue_api._row_to_dict                   (queue feed)

It reproduces, server-side and fully resolved, exactly what the widget's
*Target() functions decide client-side today (job-status-widget.js):
pauseTarget / resumeTarget / endTarget / dismissTarget, plus a truthful
`restart` for queue rows (not yet rendered anywhere — 3e-3 consumes it). No ids,
type strings, or regexes are left for the client to resolve.

Import graph / why the lazy import
----------------------------------
    app.api.processes -> app.services.background_processes -> this module
so importing app.api.processes at load time here would close the cycle
    processes -> background_processes -> process_controls -> processes.
CANCELLABLE_TYPES / RESUME_ROUTES therefore stay defined once, in processes.py
(authoritative, untouched); they are read lazily inside build_controls, by which
point every module is loaded and the reference is a sys.modules dict lookup.

The two sets below are the server-side equivalents of the widget's two hard-coded
literals (job-status-widget.js:159-160). They have no other server home, so this
is their single definition — not a second copy of anything.
"""
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# Mirror of the widget's SESSION_PAUSE_TYPES / QUEUE_CANCEL_TYPES literals.
_SESSION_PAUSE_TYPES = frozenset({"p2_delta", "archive_scan"})
_QUEUE_CANCEL_TYPES = frozenset({"ai_draft_backfill", "ai_draft_backfill_id_notes"})

# Same "session:<id>" shape endTarget() parses out of a process row's detail.
_SESSION_RE = re.compile(r"session:(\d+)")

# Every descriptor has these five keys; a control that does not apply is null.
_KEYS = ("pause", "resume", "restart", "end", "dismiss")


def _null_controls() -> dict:
    return {k: None for k in _KEYS}


def _authoritative_sets():
    """CANCELLABLE_TYPES and RESUME_ROUTES, read live from their one home in
    app.api.processes. Lazy by design — see the module docstring."""
    from app.api.processes import CANCELLABLE_TYPES, RESUME_ROUTES  # noqa: E402
    return CANCELLABLE_TYPES, RESUME_ROUTES


def build_controls(row: dict, source: str) -> dict:
    """
    Return {pause, resume, restart, end, dismiss}, each a {"url": ...} or None,
    for one already-assembled feed row. `source` is 'process' or 'queue'.

    Byte-for-byte parity target: the widget's *Target() functions. Any change
    here must keep that parity (guarded live by the 3e-1a client-side gate).
    """
    if source == "process":
        return _process_controls(row)
    if source == "queue":
        return _queue_controls(row)
    return _null_controls()


def _process_controls(row: dict) -> dict:
    pid = row.get("process_id")
    ptype = row.get("process_type")
    raw_status = row.get("status")
    is_stalled = bool(row.get("is_stalled"))

    # Effective status exactly as the widget's mergeItems computes it: a running
    # row whose heartbeat has gone stale is surfaced as 'stalled'. Every *Target()
    # gate reads that effective value, so parity requires computing it the same way.
    eff = "stalled" if (raw_status == "running" and is_stalled) else raw_status

    cancellable, resume_routes = _authoritative_sets()
    # pauseTarget: pausable set is CANCELLABLE_TYPES ∩ RESUME_ROUTES (the server's
    # own /cancellable-types intersection). Today: {auto_enrich}.
    pausable = set(cancellable) & set(resume_routes)

    controls = _null_controls()

    # pauseTarget(): running only, pausable type, pid present.
    if eff == "running" and ptype in pausable and pid is not None:
        controls["pause"] = {"url": f"/api/processes/{pid}/pause"}

    # resumeTarget(): paused only, type has a resume route. enrichment_run has no
    # route (deliberate) → stays null, holding parity with the widget.
    if eff == "paused" and ptype in resume_routes:
        controls["resume"] = {"url": resume_routes[ptype]}

    # endTarget() precedence for a process-source row. Branch 1 (queue) is
    # unreachable here; branch 2 (session) is tried before branch 3 (cancellable),
    # and — like endTarget — a session type with an unparseable detail yields null
    # rather than falling through to branch 3.
    if eff in ("running", "paused", "stalled"):
        if ptype in _SESSION_PAUSE_TYPES:
            m = _SESSION_RE.search(row.get("detail") or "")
            if m:
                controls["end"] = {"url": f"/api/scan/pause/{m.group(1)}"}
            else:
                log.warning(
                    "[controls] %s row (pid=%s) has no parseable session id in "
                    "detail=%r; end control omitted",
                    ptype, pid, row.get("detail"),
                )
        elif ptype in cancellable and pid is not None:
            controls["end"] = {"url": f"/api/processes/{pid}/cancel"}

    # dismissTarget(): stalled/failed/interrupted, pid present.
    if eff in ("stalled", "failed", "interrupted") and pid is not None:
        controls["dismiss"] = {"url": f"/api/processes/{pid}/dismiss"}

    # restart: no process-source affordance today.
    return controls


def _queue_controls(row: dict) -> dict:
    jid = row.get("id")
    jtype = row.get("job_type")
    # Queue _row_to_dict already surfaces a stale 'running' as 'interrupted';
    # queue rows are never mapped to 'stalled'. Use the value as-is.
    status = row.get("status")

    controls = _null_controls()

    # pauseTarget / resumeTarget / dismissTarget are all source=='process' only,
    # so a queue row offers none of them today. They stay null.

    # endTarget() queue branch: the shared status gate (running/paused/stalled)
    # applies to every source, then QUEUE_CANCEL_TYPES + a job id.
    if status in ("running", "paused", "stalled") and jtype in _QUEUE_CANCEL_TYPES and jid is not None:
        controls["end"] = {"url": f"/api/queue/{jid}/cancel"}

    # restart: truthful for queue rows resumable-by-re-entry. NOT compared by the
    # 3e-1a parity gate (the widget renders no Restart yet); consumed in 3e-3.
    if status == "paused" and jid is not None:
        controls["restart"] = {"url": f"/api/queue/{jid}/resume"}

    return controls
