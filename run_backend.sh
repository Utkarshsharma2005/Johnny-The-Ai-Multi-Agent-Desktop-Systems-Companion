#!/usr/bin/env bash
# run_backend.sh — Universal launcher for Johnny backend server.
# Works from anywhere (project root or any subdirectory).
#
# SECURITY: binds to 127.0.0.1 (host/port from .env) — the API must never be
# exposed to the network. On first run it launches the setup_keys.py wizard
# so the user provides API keys securely (stored 0600, gitignored).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

if [ -f "$ROOT_DIR/backend/venv/bin/activate" ]; then
    VENV_ACTIVATE="$ROOT_DIR/backend/venv/bin/activate"
    PYTHON_BIN="$ROOT_DIR/backend/venv/bin/python"
    UVICORN_BIN="$ROOT_DIR/backend/venv/bin/uvicorn"
elif [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    VENV_ACTIVATE="$ROOT_DIR/venv/bin/activate"
    PYTHON_BIN="$ROOT_DIR/venv/bin/python"
    UVICORN_BIN="$ROOT_DIR/venv/bin/uvicorn"
else
    echo "❌ Error: Could not locate virtualenv. Run setup first."
    exit 1
fi

source "$VENV_ACTIVATE"
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"

cd "$ROOT_DIR"

# ── First-run key wizard: prompt for API keys or use the stored ones ──────────
# SECURITY/UX: the wizard runs here in a PLAIN CLI (before uvicorn exists),
# so Ctrl+C raises normal KeyboardInterrupt and terminates cleanly. Running
# it inside the uvicorn lifespan would swallow Ctrl+C and hang the server.
if [ ! -f "$ROOT_DIR/.johnny/credentials/api_keys.env" ] && [ ! -f "$ROOT_DIR/backend/.johnny/credentials/api_keys.env" ] && [ "$1" != "--skip-setup" ]; then
    echo "🔑 No API keys found — starting first-run setup wizard…"
    echo "   (Keys are stored securely in .johnny/credentials/api_keys.env)"
    echo "   (Press Ctrl+C to cancel setup and EXIT — or run with --skip-setup)"
    if ! "$PYTHON_BIN" "$ROOT_DIR/setup_keys.py"; then
        echo "🛑 Setup cancelled — server NOT started."
        echo "   • To set up later:  python setup_keys.py"
        echo "   • To run MOCK mode with no keys:  ./run_backend.sh --skip-setup"
        exit 0
    fi
fi

# ── Read host/port from .env (default to loopback) ────────────────────────────
JOHNNY_HOST=$(grep -E "^HOST=" "$ROOT_DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || true)
JOHNNY_PORT=$(grep -E "^PORT=" "$ROOT_DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || true)
JOHNNY_HOST=${JOHNNY_HOST:-127.0.0.1}
JOHNNY_PORT=${JOHNNY_PORT:-8000}

# Refuse to bind non-loopback hosts (desktop app, loopback API only)
if [ "$JOHNNY_HOST" != "127.0.0.1" ] && [ "$JOHNNY_HOST" != "localhost" ]; then
    echo "🛡️  SECURITY: overriding non-loopback HOST '$JOHNNY_HOST' → 127.0.0.1"
    JOHNNY_HOST="127.0.0.1"
fi

echo "🚀 Starting Johnny AI Backend on http://$JOHNNY_HOST:$JOHNNY_PORT…"
exec "$UVICORN_BIN" backend.main:app --host "$JOHNNY_HOST" --port "$JOHNNY_PORT" --reload
