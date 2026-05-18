#!/usr/bin/env bash
# ── start-dev.sh ────────────────────────────────────────────────────────────
# Start E.sapiens v2 in development mode — both backend and frontend.
#
# Usage:
#   ./scripts/start-dev.sh
#
# Press Ctrl+C to stop both processes.
# ────────────────────────────────────────────────────────────────────────────

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "┌─────────────────────────────────────────────┐"
echo "│  E.sapiens v2 — Development Mode            │"
echo "└─────────────────────────────────────────────┘"

# ── 1. Check prerequisites ────────────────────────────────────────────────

command -v python3 >/dev/null 2>&1 || { echo "❌ python3 is required but not installed."; exit 1; }
command -v node     >/dev/null 2>&1 || { echo "❌ node is required but not installed."; exit 1; }
command -v npm      >/dev/null 2>&1 || { echo "❌ npm is required but not installed."; exit 1; }

# ── 2. Backend — activate venv, install deps, start uvicorn ──────────────

if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "📦 Creating backend virtual environment..."
    python3 -m venv "$BACKEND_DIR/.venv"
fi

echo "🔧 Activating backend venv and installing dependencies..."
source "$BACKEND_DIR/.venv/bin/activate"
pip install -q -r "$BACKEND_DIR/requirements.txt"

echo "🚀 Starting backend (uvicorn) on http://localhost:8000 ..."
cd "$BACKEND_DIR"
uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-exclude '.venv' &
BACKEND_PID=$!
cd "$ROOT_DIR"

# ── 3. Frontend — install deps, start Vite dev server ────────────────────

echo "📦 Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install --legacy-peer-deps --silent

echo "🚀 Starting frontend (Vite) on http://localhost:5173 ..."
npm run dev &
FRONTEND_PID=$!
cd "$ROOT_DIR"

# ── 4. Trap Ctrl+C and cleanup ────────────────────────────────────────────

cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    echo "✅ All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo "┌─────────────────────────────────────────────┐"
echo "│  Backend:  http://localhost:8000             │"
echo "│  Frontend: http://localhost:5173             │"
echo "│  Press Ctrl+C to stop                       │"
echo "└─────────────────────────────────────────────┘"

# Wait for either process to exit
wait
