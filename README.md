# dev-graph-kit

> Open-source local graph memory + DAG execution layer for coding agents.

## What

A local-first MCP-compatible developer memory system that turns a codebase, architectural decisions, and agent work history into a queryable graph and executable plans.

## Why

Modern AI coding agents (Codex, Claude Code, Cursor) lack persistent, structured memory about the codebase they work with. Each session starts from scratch — agents re-discover architecture, re-analyze dependencies, and lose context about past decisions and changes.

**dev-graph-kit** gives agents:
- **Project graph** — code structure, dependencies, and architecture in Neo4j
- **Agent memory** — persistent analyses, decisions, and changes across sessions
- **DAG execution** — multi-step plans with tracking via Dagster
- **MCP interface** — standard protocol access for any compatible agent

## How to start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Setup

```bash
# Clone the repo
git clone https://github.com/org/dev-graph-kit.git
cd dev-graph-kit

# Copy environment config
cp .env.example .env

# Install dependencies
uv sync

# Initialize a project
uv run dgk init

# Start Neo4j
uv run dgk dev

# Check health
uv run dgk doctor
```

### Services

| Service | URL |
|---------|-----|
| Neo4j Browser | http://localhost:7474 |
| Dagster UI | http://localhost:3000 (future) |
| MCP Server | http://localhost:8080 (future) |
