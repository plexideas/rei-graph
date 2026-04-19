# rei-graph

> Open-source local graph memory + DAG execution layer for coding agents.

[![CI](https://github.com/org/rei-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/org/rei-graph/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What

A local-first MCP-compatible developer memory system that turns a codebase, architectural decisions, and agent work history into a queryable graph and executable plans.

**rei-graph gives agents:**
- **Project graph** — code structure, dependencies, and architecture in Neo4j
- **Agent memory** — persistent analyses, decisions, and changes across sessions
- **DAG execution** — multi-step plans with tracking
- **MCP interface** — standard protocol access for Cursor, Claude Code, and Codex

## Why

Modern AI coding agents (Codex, Claude Code, Cursor) lack persistent, structured memory about the codebase they work with. Each session starts from scratch — agents re-discover architecture, re-analyze dependencies, and lose context about past decisions and changes.

## How to start

### One-command setup

```bash
git clone https://github.com/org/rei-graph.git
cd rei-graph
./setup.sh
```

### Manual setup

**Prerequisites:** Docker, [uv](https://docs.astral.sh/uv), Node.js 18+

```bash
git clone https://github.com/org/rei-graph.git
cd rei-graph
cp .env.example .env
uv sync
cd packages/ingester_ts && npm install && cd ../...
docker compose up -d
uv run rei init
uv run rei doctor
```

### Scan your first project

```bash
# Scan the built-in React demo
uv run rei scan examples/react_ts_app

# Query the graph
uv run rei query "LoginForm"

# Impact analysis
uv run rei impact examples/react_ts_app/src/hooks.ts
```

### Connect an agent

```bash
# Start the MCP server (agents spawn this automatically)
uv run rei mcp
```

See [docs/mcp.md](docs/mcp.md) for agent configuration (Cursor, Claude Code, Codex).

## CLI reference

| Command | Description |
|---------|-------------|
| `rei init` | Initialize project, create `.rei/project.toml` |
| `rei dev` | Start/stop local stack (Neo4j) |
| `rei scan [path]` | Scan TypeScript/TSX files into graph |
| `rei scan --changed` | Incremental scan of git-changed files only |
| `rei query "..."` | Search graph by name or label |
| `rei impact <file>` | Show impact analysis for a file |
| `rei plan "..."` | Create a DAG execution plan |
| `rei plans` | List open plans |
| `rei snapshot` | Export current graph to JSON |
| `rei mcp` | Start MCP server for agent connections |
| `rei doctor` | Check Neo4j and ingester health |

## Services

| Service | URL | Started by |
|---------|-----|------------|
| Neo4j Browser | http://localhost:7474 | `docker compose up -d` |
| Neo4j Bolt | bolt://localhost:7687 | `docker compose up -d` |
| MCP Server | stdio | `rei mcp` |

## MCP tools

| Namespace | Tools |
|-----------|-------|
| `graph.*` | `search_entities`, `get_context`, `get_neighbors`, `impact_analysis`, `upsert_entities`, `upsert_relations` |
| `memory.*` | `record_analysis`, `record_decision`, `record_change`, `record_validation`, `record_plan`, `get_recent_context` |
| `dag.*` | `create_plan`, `run_plan`, `get_plan`, `step_status`, `cancel_plan` |
| `scan.*` | `project`, `file`, `changed_files` |
| `project.*` | `status`, `snapshot` |

Full reference: [docs/mcp.md](docs/mcp.md)

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/install.md](docs/install.md) | Detailed installation guide |
| [docs/architecture.md](docs/architecture.md) | System architecture and data flow |
| [docs/ontology.md](docs/ontology.md) | Graph node types and relationships |
| [docs/mcp.md](docs/mcp.md) | MCP tool reference + agent integration guides |
| [docs/examples.md](docs/examples.md) | Step-by-step usage examples |
| [docs/PRD.md](docs/PRD.md) | Product requirements document |

## Examples

| Example | Description |
|---------|-------------|
| [examples/react_ts_app](examples/react_ts_app) | React/TypeScript app with auth, components, hooks |
| [examples/express_api](examples/express_api) | Express API with routes, middleware, typed models |

## Project structure

```
packages/
  core/          — shared Pydantic schemas
  storage/       — Neo4j, memory, DAG, snapshot clients
  ingester_ts/   — TypeScript (ts-morph) code scanner
  mcp_server/    — MCP server with all tools and resources
  cli/           — rei CLI (Click)
examples/
  react_ts_app/  — demo React/TS project
  express_api/   — demo Express API
docs/            — documentation
tests/           — pytest test suite (124 tests)
```

