#!/bin/bash
cd "$(dirname "$0")"

# Kill any stale servers on port 8000
lsof -ti :8000 | xargs kill -9 2>/dev/null; true

source "$HOME/foragingid-venv/bin/activate"

# Ensure DB is initialised
python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.config import settings
settings.ensure_dirs()
from app.database import init_db
asyncio.run(init_db())
print('Database ready.')
"

# Set up timestamped log
LOG="$HOME/ForagingID/logs/server_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$LOG")"
echo "[$(date)] Server starting" >> "$LOG"

# Start uvicorn with reload, tee output to log
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app 2>&1 | tee -a "$LOG" &
UVICORN_PID=$!

# Log on exit
trap 'echo "[$(date)] Server stopped (PID $UVICORN_PID)" >> "$LOG"' EXIT

sleep 2
open http://127.0.0.1:8000

wait $UVICORN_PID
echo "[$(date)] uvicorn exited with code $?" >> "$LOG"