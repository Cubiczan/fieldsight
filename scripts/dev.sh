#!/usr/bin/env bash
# Start the inspection API and the Next.js app together.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
fi
if [[ ! -d node_modules ]]; then
  npm install
fi
if [[ ! -f public/samples/clear-ready.png ]]; then
  .venv/bin/python backend/scripts/generate_samples.py
fi

.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 43124 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

echo "API  http://127.0.0.1:43124/health"
echo "App  http://127.0.0.1:43123"
npm run dev
