#!/usr/bin/env bash
# Replit entrypoint: installs backend dependencies and starts the API.
set -euo pipefail

cd "$(dirname "$0")/apps/api"

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi

exec python -m uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
