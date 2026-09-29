#!/usr/bin/env bash
# One-shot local demo: backend on :8000, UI on :5173. Works with zero credentials (simulated executors).
set -e
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
[ -d backend/.venv ] || python3 -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements.txt
[ -d frontend/node_modules ] || (cd frontend && npm install)
(cd backend && .venv/bin/uvicorn app.main:app --port 8000 --reload) &
(cd frontend && npm run dev) &
wait
