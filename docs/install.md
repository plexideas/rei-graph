# Installation

Get dev-graph-kit running in under 5 minutes.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) (for TypeScript scanner) |
| Git | any | pre-installed on most systems |

## Quick start (automated)

```bash
git clone https://github.com/org/dev-graph-kit.git
cd dev-graph-kit
./setup.sh
```

`setup.sh` does everything below in one step.

## Manual setup

### 1. Clone

```bash
git clone https://github.com/org/dev-graph-kit.git
cd dev-graph-kit
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env if needed (default Neo4j password is fine for local dev)
```

### 3. Install Python dependencies

```bash
uv sync
```

### 4. Install TypeScript scanner dependencies

```bash
cd packages/ingester_ts && npm install && cd ../..
```

### 5. Start Neo4j

```bash
docker compose up -d
```

### 6. Initialize project

```bash
uv run dgk init
```

### 7. Verify everything works

```bash
uv run dgk doctor
```

Expected output:
```
✓ Neo4j reachable at bolt://localhost:7687
✓ Ingester binary found
  All systems healthy
```

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| Neo4j Browser | http://localhost:7474 | Graph visualization / Cypher queries |
| Neo4j Bolt | bolt://localhost:7687 | Database connection |
| MCP Server | stdio (via `dgk mcp`) | Agent protocol interface |

## Scanning your first project

```bash
# Scan the built-in demo
uv run dgk scan examples/react_ts_app

# Query the graph
uv run dgk query "LoginForm"

# Run impact analysis
uv run dgk impact examples/react_ts_app/src/hooks.ts
```

## Updating

```bash
git pull
uv sync
cd packages/ingester_ts && npm install && cd ../..
```

## Troubleshooting

### Neo4j won't start
```bash
docker compose logs neo4j
# Check ports 7474 and 7687 are not in use
lsof -i :7687
```

### `dgk` command not found
```bash
uv run dgk --help
# Or activate the venv: source .venv/bin/activate
```

### Ingester fails on scan
```bash
# Ensure Node.js 18+ is installed
node --version
# Rebuild ingester
cd packages/ingester_ts && npm install
```
