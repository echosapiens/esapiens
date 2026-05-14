#!/usr/bin/env bash
# ── start-prod.sh ───────────────────────────────────────────────────────────
# Start E.sapiens v2 in production mode using Docker Compose.
#
# Usage:
#   export OPENROUTER_API_KEY=sk-or-v1-...
#   ./scripts/start-prod.sh
#
# Or pass the key inline:
#   OPENROUTER_API_KEY=sk-or-v1-... ./scripts/start-prod.sh
# ────────────────────────────────────────────────────────────────────────────

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "┌─────────────────────────────────────────────┐"
echo "│  E.sapiens v2 — Production Mode (Docker)    │"
echo "└─────────────────────────────────────────────┘"

# ── Check prerequisites ───────────────────────────────────────────────────

command -v docker >/dev/null 2>&1 || { echo "❌ docker is required but not installed."; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "❌ docker compose is required but not installed."; exit 1; }

# ── Validate OPENROUTER_API_KEY ────────────────────────────────────────────

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "⚠️  OPENROUTER_API_KEY is not set."
    echo "   Create a backend/.env file or export the variable."
    echo ""
    echo "   Examples:"
    echo "     export OPENROUTER_API_KEY=sk-or-v1-..."
    echo "     ./scripts/start-prod.sh"
    echo ""
    echo "   Or use the included .env.example:"
    echo "     cp backend/.env.example backend/.env"
    echo "     # Edit backend/.env with your key"
    exit 1
fi

cd "$ROOT_DIR"

echo "🐳 Building and starting containers..."
docker compose up --build -d

echo ""
echo "┌─────────────────────────────────────────────┐"
echo "│  Backend:  http://localhost:8000             │"
echo "│  Frontend: http://localhost:5173             │"
echo "│                                              │"
echo "│  To stop:    docker compose down             │"
echo "│  To follow   docker compose logs -f          │"
echo "└─────────────────────────────────────────────┘"
