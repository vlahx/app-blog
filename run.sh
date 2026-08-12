#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
pip install -r requirements.txt >/dev/null 2>&1 || true

exec python -m uvicorn main:app --host 127.0.0.1 --port 8000
