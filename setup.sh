#!/usr/bin/env bash
# setup.sh — one-command bootstrap for rei-graph
set -euo pipefail

echo "==> rei-graph setup"

# ── 1. Check prerequisites ─────────────────────────────────────────────────────
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "  ERROR: '$1' not found. $2"
    exit 1
  fi
}

check_cmd docker   "Install Docker: https://docs.docker.com/get-docker/"
check_cmd uv       "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
check_cmd node     "Install Node.js 18+: https://nodejs.org"
check_cmd git      "Install git"
echo "  Prerequisites: OK"

# ── 2. Environment config ──────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  Created .env from .env.example"
else
  echo "  .env already exists — skipping"
fi

# ── 3. Python dependencies ────────────────────────────────────────────────────
echo "==> Installing Python dependencies (uv sync)..."
uv sync

# ── 4. TypeScript scanner ─────────────────────────────────────────────────────
echo "==> Installing TypeScript ingester dependencies..."
(cd packages/ingester_ts && npm install --silent)

# ── 5. Start Neo4j ────────────────────────────────────────────────────────────
echo "==> Starting Neo4j via Docker Compose..."
docker compose up -d

# ── 6. Wait for Neo4j to be ready ─────────────────────────────────────────────
echo "==> Waiting for Neo4j to be ready..."
MAX_WAIT=30
COUNT=0
until curl -sf http://localhost:7474 > /dev/null 2>&1; do
  COUNT=$((COUNT + 1))
  if [ "$COUNT" -ge "$MAX_WAIT" ]; then
    echo "  ERROR: Neo4j did not start within ${MAX_WAIT}s"
    docker compose logs neo4j | tail -20
    exit 1
  fi
  sleep 1
done
echo "  Neo4j ready"

# ── 7. Initialize project ─────────────────────────────────────────────────────
echo "==> Initializing project..."
uv run rei init

# ── 8. Health check ───────────────────────────────────────────────────────────
echo "==> Running health check..."
uv run rei doctor

echo ""
echo "  rei-graph is ready!"
echo ""
echo "  Next steps:"
echo "    uv run rei scan examples/react_ts_app   # scan a demo project"
echo "    uv run rei query 'LoginForm'             # query the graph"
echo "    uv run rei mcp                           # start MCP server for agents"
echo ""
echo "  Docs: docs/install.md | docs/mcp.md | docs/examples.md"
