"""
Per-row control descriptor for the background-job widget (Phase 3e-1a).

ONE definition of "which controls does this row offer, and at what URL". Both
feed serializers attach it under the "controls" key:
  - app.services.background_processes._row_to_dict   (process feed)
  - app.api.queue_api._row_to_dict                   (queue feed)

It resolves, server-side and fully, which controls a feed row offers and at what
URL: pause / resume / end / dismiss, plus a truthful `restart` for queue rows
(carried but not rendered by the widget yet — 3e-3 consumes it). The widget
renders straight from this; no ids, type strings, or regexes are resolved
client-side.

Single home for the control vocabularies
----------------------------------------
This module is a leaf — it imports nothing from app.api or app.services — so all
four control-vocabulary constants live here with no circular-import risk:

  - CANCELLABLE_TYPES / RESUME_ROUTES: which process types honour a pause/cancel
    signal, and which have a widget resume route. app.api.processes imports these
    for its endpoints (/pause enforcement, /cancellable-types). Moved here in
    Phase 3e-1b; processes -> background_processes -> this module used to be a
    cycle only because the constants lived in processes.py and were read back
    lazily. With them here that lazy import is gone.
  - _SESSION_PAUSE_TYPES / _QUEUE_CANCEL_TYPES: the two sets the widget used to
    hard-code as literals. This is their single server definition — not a second
    copy of anything.
"""
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# Mirror of the widget's old SESSION_PAUSE_TYPES / QUEUE_CANCEL_TYPES literals
# (deleted from the widget in 3e-1b; this is now their only home).
_SESSION_PAUSE_TYPES = frozenset({"p2_delta", "archive_scan"})
_QUEUE_CANCEL_TYPES = frozenset({"ai_draft_backfill", "ai_draft_backfill_id_notes"})

# ── Which process types actually honour a pause/cancel signal ────────────────
# A process is listed here ONLY if its worker loop reads its own
# background_processes.status and stops when it sees paused/cancelled. Both
# entries below run through run_enrichment_batch(cancel_check_fn=…), which
# checks the signal before each species and returns cleanly with stopped_at.
#
# This set exists to make one specific lie impossible. Before it, these
# endpoints accepted ANY process_id: the row flipped to 'cancelled', the worker
# — which never reads that column — carried on to the end, and its bp_finish
# then flipped the row to 'complete'. The user saw a cancel that visibly undid
# itself while the work they cancelled ran to completion. Refusing the request
# up front is the fix; guarding bp_finish would only have hidden the flip-back
# while the work still ran.
#
# Types NOT listed here are not cancellable *through /api/processes* — some have
# their own real stop route, which is where their UI must send the signal:
#   p2_delta, archive_scan            → POST /api/scan/pause/{session_id}
#   ai_draft_backfill, *_id_notes     → POST /api/queue/{id}/cancel
# The rest (bulk_*, itis_backfill, fungi_edibility_backfill, reprocess_pending,
# p1_syncthing, p1_reprocess, folder_scan, rescan_unknown, elevation_enrich)
# have no cooperative stop at all and must not offer one.
CANCELLABLE_TYPES = {"enrichment_run", "auto_enrich"}

# ── Which process types can be RESUMED from a paused row, and where ─────────
# Same principle as CANCELLABLE_TYPES: listed only if a route genuinely restarts
# the run from its stop index rather than from zero.
#
# 'enrichment_run' is deliberately absent even though it does support resume.
# Its resume is folded into POST /api/enrichment/run — the same route that
# STARTS a run — which falls back to a fresh run from 0 when it finds no paused
# job in memory. That is fine behind review.html's own button, which is driven
# by that page's job state, but a generic Resume button firing it could silently
# launch a whole new enrichment. Its affordance stays where it is.
RESUME_ROUTES = {
    "auto_enrich": "/api/enrich/resume",
}

# Same "session:<id>" shape endTarget() parses out of a process row's detail.
_SESSION_RE = re.compile(r"session:(\d+)")

# Every descriptor has these five keys; a control that does not apply is null.
_KEYS = ("pause", "resume", "restart", "end", "dismiss")


def _null_controls() -> dict:
    return {k: None for k in _KEYS}


def build_controls(row: dict, source: str) -> dict:
    """
    Return {pause, resume, restart, end, dismiss}, each a {"url": ...} or None,
    for one already-assembled feed row. `source` is 'process' or 'queue'.

    As of Phase 3e-1b this descriptor is the sole driver of the widget's per-row
    buttons — the client renders one button per non-null key and posts its url
    verbatim. There is no client-side fallback, so a control that must not appear
    MUST be null here.
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

    # pauseTarget: pausable set is CANCELLABLE_TYPES ∩ RESUME_ROUTES (the server's
    # own /cancellable-types intersection). Today: {auto_enrich}.
    pausable = set(CANCELLABLE_TYPES) & set(RESUME_ROUTES)

    controls = _null_controls()

    # pauseTarget(): running only, pausable type, pid present.
    if eff == "running" and ptype in pausable and pid is not None:
        controls["pause"] = {"url": f"/api/processes/{pid}/pause"}

    # resumeTarget(): paused only, type has a resume route. enrichment_run has no
    # route (deliberate) → stays null, holding parity with the widget.
    if eff == "paused" and ptype in RESUME_ROUTES:
        controls["resume"] = {"url": RESUME_ROUTES[ptype]}

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
        elif ptype in CANCELLABLE_TYPES and pid is not None:
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

    # endTarget() queue branch: the status gate is running/paused, then
    # QUEUE_CANCEL_TYPES + a job id. 'stalled' is deliberately NOT tested here:
    # queue_api._row_to_dict surfaces a stale 'running' as 'interrupted' (never
    # 'stalled'), so a queue row is never 'stalled' and that branch was dead.
    if status in ("running", "paused") and jtype in _QUEUE_CANCEL_TYPES and jid is not None:
        controls["end"] = {"url": f"/api/queue/{jid}/cancel"}

    # restart: truthful for queue rows resumable-by-re-entry. NOT compared by the
    # 3e-1a parity gate (the widget renders no Restart yet); consumed in 3e-3.
    if status == "paused" and jid is not None:
        controls["restart"] = {"url": f"/api/queue/{jid}/resume"}

    return controls
