"""
Observation file cleanup on reject.

Moves files to /tmp/foragingid_undo/ with a 30s undo window, then hard-deletes.
"""

import asyncio
import shutil
from pathlib import Path
from typing import List, Optional


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
