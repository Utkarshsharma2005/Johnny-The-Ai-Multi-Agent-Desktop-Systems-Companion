#!/usr/bin/env bash
# backend/run.sh — Local launcher when inside backend directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/venv/bin/activate"
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"

echo "🚀 Starting Johnny AI Backend on http://0.0.0.0:8000..."
exec "$SCRIPT_DIR/venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000 --reload
