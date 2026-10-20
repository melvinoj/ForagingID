"""
Prevent macOS from sleeping during long-running jobs.

Usage:
    from app.utils.caffeinate import keep_awake

    with keep_awake("Folder scan in progress"):
        ...  # system stays awake for the duration

No-op on non-macOS platforms. Safe to call from async contexts —
subprocess.Popen is non-blocking and the cleanup on exit is near-instant.
"""

import os
import subprocess
import sys
from contextlib import contextmanager


def server_watch_pid() -> int:
    """The PID a user-toggled caffeinate should `-w` watch: the long-lived
    server process, not this worker.

    Under `uvicorn --reload` this process is a worker that the reloader
    replaces on every app/ save, so watching os.getpid() switched caffeinate
    off at every reload (16–20 Oct 2026). The reloader parent survives
    reloads and exits when the server is really stopped, so watching it keeps
    the no-orphan guarantee. Only adopted when the parent really is the
    uvicorn reloader; otherwise (no --reload, or ps unavailable) this process
    is the server, and it is watched as before.
    """
    ppid = os.getppid()
    try:
        cmd = subprocess.run(["ps", "-o", "command=", "-p", str(ppid)],
                             capture_output=True, text=True, timeout=3).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return os.getpid()
    if "uvicorn" in cmd and "--reload" in cmd:
        return ppid
    return os.getpid()


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
        # -w <server pid>: exits with the server even if the finally below
        # never runs (crash / --reload restart mid-job) — same class of bug
        # as the scan caffeinate endpoints.
        proc = subprocess.Popen(
            ["caffeinate", "-i", "-w", str(os.getpid())],
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
