#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate

export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"

uvicorn backend:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

streamlit run admin.py &
ADMIN_PID=$!

python bot.py &
BOT_PID=$!

trap 'kill $BACKEND_PID $ADMIN_PID $BOT_PID' EXIT
wait
