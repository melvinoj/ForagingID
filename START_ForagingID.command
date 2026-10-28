#!/bin/bash
# START_ForagingID.command — runs the ForagingID server in the FOREGROUND of
# this Terminal window.
#
#   Stop it:  Ctrl+C (graceful) — or close the window.
#   Log:      everything you see here is also written to logs/server_<timestamp>.log
#
# Rewritten 15 Oct 2026. The previous version started uvicorn with '&'. Bash
# makes a background command in a script IGNORE SIGINT, so Ctrl+C killed the
# script but not the server: uvicorn was re-parented to launchd and kept running
# invisibly, holding the database. Nothing here runs detached any more.
#
# ngrok is NOT started here — sharing is started from Settings → "Start sharing".
# The app's database setup (init_db) runs at server startup (app/main.py
# lifespan), so this script no longer runs it separately.

cd "$(dirname "$0")" || exit 1

if ! source "$HOME/foragingid-venv/bin/activate"; then
  echo "ERROR: venv not found at $HOME/foragingid-venv"
  read -rp "Press Enter to close…"
  exit 1
fi

PORT=8000
mkdir -p logs
# Keep the 9 newest server logs; this start adds the 10th (E-12, 28 Oct 2026).
ls -t logs/server_*.log 2>/dev/null | tail -n +10 | while IFS= read -r old; do rm -f -- "$old"; done
LOG="logs/server_$(date +%Y%m%d_%H%M%S).log"

# Never kill -9 a running server (it may be mid-write). If the port is taken,
# show what holds it and stop without starting anything.
PIDS=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN)
if [ -n "$PIDS" ]; then
  echo "Port $PORT is already in use — a server is already running:"
  ps -o pid,ppid,lstart,command -p $PIDS
  echo
  echo "Stop it first (Ctrl+C in its window, or: kill -INT <pid>). Nothing was started."
  read -rp "Press Enter to close…"
  exit 1
fi

OPENER_PID=""
cleanup() {
  trap - EXIT INT TERM HUP
  # The browser opener is the only background job; make sure it is gone.
  [ -n "$OPENER_PID" ] && kill "$OPENER_PID" 2>/dev/null
  # Belt and braces: if anything is still listening on the port (e.g. a
  # reloader worker), ask it to shut down gracefully.
  LEFT=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN)
  [ -n "$LEFT" ] && kill -INT $LEFT 2>/dev/null
  echo "[$(date)] Launcher exited (PID $$)" >> "$LOG"
}
trap cleanup EXIT INT TERM HUP

echo "[$(date)] Server starting (launcher PID $$)" >> "$LOG"
echo "Log: $PWD/$LOG"

# Short-lived helper: opens the browser once, then exits.
( sleep 3; open "http://127.0.0.1:$PORT" ) &
OPENER_PID=$!

# FOREGROUND — no '&'. Ctrl+C reaches uvicorn directly (graceful shutdown);
# tee shows live output here and writes the same output to $LOG.
# tee ignores Ctrl+C (SIGINT): otherwise it exits on the same keypress and
# uvicorn's shutdown output never reaches the log. It still ends when uvicorn
# closes the pipe, and closing the window (SIGHUP) still stops it.
#
# Reload scope (16 Oct 2026): uvicorn 0.32.1 IGNORES --reload-dir for any folder
# inside the project and always watches the whole repo, so edits under scripts/
# reloaded the server (and orphaned caffeinate). The excludes must be ABSOLUTE
# paths — relative ones are silently ignored (checked against uvicorn's
# FileFilter). --timeout-graceful-shutdown 5: an open browser tab (event stream)
# can no longer hold a reload or Ctrl+C on "Waiting for connections to close".
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload --reload-dir app \
  --reload-exclude "$PWD/scripts" --reload-exclude "$PWD/migrations" --reload-exclude "$PWD/tests" \
  --timeout-graceful-shutdown 5 2>&1 \
  | (trap '' INT; exec tee -a "$LOG")
