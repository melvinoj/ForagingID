"""
Observation file cleanup on reject.

Moves files to /tmp/foragingid_undo/ with a 30s undo window, then hard-deletes.
"""

import asyncio
import shutil
from pathlib import Path
from typing import List, Optional

from app.models.observation import is_phone_origin


def _print(fmt, *args):
    print(f"[file_cleanup] {fmt % args}", flush=True)


UNDO_DIR = Path("/tmp/foragingid_undo")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DELETABLE_SEGMENTS = {"/uploads/", "/photos/pipeline2/", "/photos/confirmed_plants/"}

_pending_deletes: dict = {}  # {obs_id: asyncio.Task}


async def _hard_delete_after_delay(obs_id: int, temp_paths: List[Path], delay_s: int = 30) -> None:
    await asyncio.sleep(delay_s)
    for tp in temp_paths:
        try:
            if tp.exists():
                tp.unlink()
                _print("obs %d: hard-deleted %s", obs_id, tp)
        except Exception as exc:
            _print("obs %d: hard-delete failed for %s: %s", obs_id, tp, exc)
    _pending_deletes.pop(obs_id, None)


def _is_deletable(path_str: str) -> bool:
    return any(seg in path_str for seg in _DELETABLE_SEGMENTS)


def _move_to_undo(obs_id: int, src: Path, label: str) -> Optional[Path]:
    UNDO_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UNDO_DIR / f"{obs_id}_{label}_{src.name}"
    shutil.move(str(src), str(temp_path))
    return temp_path


def delete_observation_file(obs) -> None:
    """
    Queue file deletion for a rejected observation's file_path,
    confirmed_copy_path, and thumbnail_path.

    file_path / confirmed_copy_path: only acts on paths containing a
    segment in _DELETABLE_SEGMENTS. Archive/source paths are skipped.

    thumbnail_path: always eligible (stored as relative path, resolved
    against _PROJECT_ROOT derived from __file__).

    Moves qualifying files to /tmp/foragingid_undo/ and schedules a
    single hard-delete task after 30s.
    """
    obs_id = obs.id

    # never_reject (migration 0050) — hard veto at the destructive call site.
    # True means no other copy of this photo is known to exist: for 21212/21215/
    # 21216 the thumbnail is the only surviving copy, the original is already
    # gone from uploads/, and DIGIERA/PhoneForaging are not on disk. Deleting
    # here would destroy the last copy with no route back.
    #
    # Enforced here rather than in the callers because every reject path funnels
    # through this function — observations.py, bulk_actions.py, identify.py,
    # upload.py, audit.py, prefilter.py and scan.py all call it. A guard in any
    # one caller would leave the other six open. Returns without touching a file
    # so a reject still marks the row; only the unlink is refused.
    if getattr(obs, "never_reject", False):
        _print("obs %d: REFUSED file delete — never_reject is set (no other copy on disk)", obs_id)
        return

    # Provenance veto — P1/syncthing files are never deleted, for either path.
    #
    # The segment list below is a location test, not an origin test, and the two
    # stopped agreeing at the copy-on-ingest cutover (~3 June 2026, migration
    # 0021). Before it, P1 originals sat in PhoneForaging/ and were skipped by
    # _is_deletable(); after it they are copied to photos/pipeline2/, which IS in
    # _DELETABLE_SEGMENTS — so a reject began hard-deleting phone originals that
    # the earlier behaviour had protected. 12 P1 originals were destroyed this
    # way. A phone original has no second copy once the source leaves the device,
    # so this is unrecoverable loss; a P2 upload is a copy of a file the user
    # still holds elsewhere.
    #
    # Vetoes the thumbnail too: thumbnail_path is unconditionally eligible below
    # (no segment check), so without this it would still be destroyed, and for a
    # row whose original is already gone the thumbnail is the last surviving
    # copy — the exact situation never_reject exists to prevent.
    #
    # Enforced here, alongside never_reject, for the same reason: all six reject
    # call sites funnel through this function, so a guard in any one of them
    # would leave the other five open.
    if is_phone_origin(obs):
        _print("obs %d: REFUSED file delete — phone-origin (P1/syncthing), no second copy", obs_id)
        return

    paths_to_check = []

    if obs.file_path:
        paths_to_check.append(("file_path", str(obs.file_path), True))
    if getattr(obs, "confirmed_copy_path", None):
        paths_to_check.append(("confirmed_copy_path", str(obs.confirmed_copy_path), True))
    if getattr(obs, "thumbnail_path", None):
        tp = Path(obs.thumbnail_path)
        if not tp.is_absolute():
            tp = _PROJECT_ROOT / tp
        paths_to_check.append(("thumbnail_path", str(tp), False))

    if not paths_to_check:
        return

    moved: List[Path] = []
    for col_name, path_str, needs_segment_check in paths_to_check:
        if needs_segment_check and not _is_deletable(path_str):
            _print("obs %d: skip %s=%s — not in deletable directory", obs_id, col_name, path_str)
            continue

        src = Path(path_str)
        if not src.exists():
            _print("obs %d: skip %s=%s — file does not exist on disk", obs_id, col_name, path_str)
            continue

        try:
            temp_path = _move_to_undo(obs_id, src, col_name)
            moved.append(temp_path)
            _print("obs %d: queued delete %s=%s → %s (30s undo window)", obs_id, col_name, path_str, temp_path)
        except Exception as exc:
            _print("obs %d: failed to move %s=%s to undo dir: %s", obs_id, col_name, path_str, exc)

    if moved:
        if obs_id in _pending_deletes:
            _pending_deletes[obs_id].cancel()
        _pending_deletes[obs_id] = asyncio.get_event_loop().create_task(
            _hard_delete_after_delay(obs_id, moved, delay_s=30)
        )
