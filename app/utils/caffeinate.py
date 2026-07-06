"""
Prevent macOS from sleeping during long-running jobs.

Usage:
    from app.utils.caffeinate import keep_awake

    with keep_awake("Folder scan in progress"):
        ...  # system stays awake for the duration

No-op on non-macOS platforms. Safe to call from async contexts —
subprocess.Popen is non-blocking and the cleanup on exit is near-instant.
"""

import subprocess
import sys
from contextlib import contextmanager


@contextmanager
def keep_awake(reason: str = "ForagingID job running"):
    """
    Run `caffeinate -i` for the duration of the block, then terminate it.

    -i  prevent idle sleep (covers normal auto-sleep from inactivity)

    Does NOT prevent lid-close sleep (that is a forced sleep, not idle,
    and is usually the right behaviour).
    """
    if sys.platform != "darwin":
        yield
        return

    proc = None
    try:
        proc = subprocess.Popen(
            ["caffeinate", "-i"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        yield
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
