#!/usr/bin/env bash
# start.sh — start ForagingID and print local network URL
#
# Usage:
#   ./start.sh            (default port 8000, reload off for production)
#   ./start.sh --dev      (enable --reload for development)
#   PORT=9000 ./start.sh  (custom port)

set -e
cd "$(dirname "$0")"

# Activate the project virtual environment.
# ~/foragingid-venv is the real venv; there is no in-tree ./venv. Guarded so a
# missing venv is loud rather than silently falling through to system Python.
VENV_ACTIVATE="$HOME/foragingid-venv/bin/activate"
if [ -f "$VENV_ACTIVATE" ]; then
  source "$VENV_ACTIVATE"
else
  echo "ERROR: venv not found at $VENV_ACTIVATE" >&2
  exit 1
fi

PORT="${PORT:-8000}"
RELOAD_FLAG=""
if [[ "$*" == *"--dev"* ]]; then
  RELOAD_FLAG="--reload"
fi

# Discover local network IP
LAN_IP=$(python3 -c "
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0])
    s.close()
except Exception:
    print('unknown')
" 2>/dev/null)

echo ""
echo "  🌿  ForagingID"
echo "  ──────────────────────────────────────────"
echo "  Local:    http://localhost:${PORT}"
if [ "$LAN_IP" != "unknown" ]; then
  echo "  Network:  http://${LAN_IP}:${PORT}   ← type this into your phone"
fi
echo "  ──────────────────────────────────────────"
echo ""

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --log-level info \
  $RELOAD_FLAG
