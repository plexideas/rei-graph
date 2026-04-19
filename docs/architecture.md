# Architecture

How rei-graph is structured and why.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Coding Agent                            │
│               (Codex / Claude Code / Cursor)                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ MCP protocol (stdio)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server (rei mcp)                       │
│   graph.*   memory.*   dag.*   scan.*   project.*   tools       │
└──────┬─────────────┬───────────────┬────────────────────────────┘
       │             │               │
       ▼             ▼               ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐
│  Neo4j   │  │  Memory  │  │  DagClient   │
│  Client  │  │  Client  │  │  (in-memory) │
└──────────┘  └──────────┘  └──────────────┘
       │
       ▼
┌──────────┐      ┌──────────────────────────┐
│  Neo4j   │◀─────│  TS Ingester (ts-morph)  │
│  Graph   │      │  (Node.js subprocess)    │
└──────────┘      └──────────────────────────┘
```

## Packages

The monorepo is split into four Python packages and one TypeScript package:

### `packages/core`
Shared Pydantic schemas (`GraphNode`, `GraphRelationship`) and project config loading. No external dependencies except Pydantic.

### `packages/storage`
Three Neo4j clients — each a thin wrapper around the `neo4j` driver:

| Client | Purpose |
|--------|---------|
| `Neo4jClient` | Code graph — nodes, relationships, search, impact |
| `MemoryClient` | Agent memory — analyses, decisions, changes, plans |
| `DagClient` | DAG plans — create, run, step status, cancel |
| `SnapshotClient` | Graph export — snapshot the entire graph to JSON |

All clients follow the same pattern: `__init__` takes `uri/user/password`, expose pure methods, `close()` releases the driver.

### `packages/ingester_ts`
TypeScript (ts-morph) scanner that parses `.ts`/`.tsx` files and outputs JSON:

```json
{
  "file": "src/auth.ts",
  "nodes": [{"id": "...", "label": "Module", "name": "auth", ...}],
  "relationships": [{"type": "IMPORTS", "sourceId": "...", "targetId": "..."}]
}
```

Called as a subprocess by the Python CLI: `node ingester/cli.js <file>`.

### `packages/mcp_server`
Python MCP server built with the `mcp` SDK. All tools are pure synchronous functions that accept `arguments: dict` and optional `client: Neo4jClient`. The `@server.call_tool()` handler dispatches to these functions.

### `packages/cli`
Click-based CLI. Each subcommand is a separate module under `commands/`. The `rei` entry point is registered in `pyproject.toml`.

## Data flow: scan

```
rei scan src/auth.ts
  │
  ├─ _find_ingester()        → locate node binary
  ├─ subprocess.run(node ...) → JSON output
  ├─ _parse_ingester_output() → ScanResult(nodes, relationships)
  ├─ Neo4jClient.delete_file_nodes(file)
  ├─ Neo4jClient.upsert_nodes(nodes)
  └─ Neo4jClient.upsert_relationships(relationships)
```

## Data flow: incremental scan (`--changed`)

```
rei scan . --changed
  │
  ├─ _get_deleted_files(root)  → git diff --diff-filter=D HEAD
  ├─ _get_changed_files(root)  → git diff --name-only HEAD
  ├─ Neo4jClient.delete_file_nodes(deleted)
  └─ [for each changed file] → same as scan above
```

## Data flow: agent memory

```
MCP: memory.record_decision({choice, rationale, ...})
  │
  └─ MemoryClient.record_decision(...)
       └─ Neo4j MERGE (d:Decision {id: ...}) SET d += {...}
```

Memory nodes are stored alongside code nodes in Neo4j. They use different labels (`Decision`, `Analysis`, `Change`, etc.) and can be linked to code nodes via relationships (`AFFECTS`, `BASED_ON`, `OBSERVED_IN`).

## Data flow: DAG plans

Plans are stored purely in Neo4j via `DagClient`. Each plan is a `Plan` node linked to `Step` nodes via `HAS_STEP`. Steps track status (`pending`, `running`, `completed`, `failed`, `cancelled`).

```
dag.create_plan({goal, steps: [{name, description}]})
  │
  └─ DagClient.create_plan(goal, steps)
       ├─ MERGE (p:Plan {id: ...})
       └─ MERGE (s:Step {id: ...})-[:HAS_STEP]->(p)

dag.run_plan({planId})
  │
  └─ DagClient.run_plan(planId)
       └─ SET p.status = "running", first step status = "running"
```

## Neo4j schema

Nodes and relationships are upserted with `MERGE ... ON CREATE SET ... ON MATCH SET`. The `id` property is always the unique key.

**Code node IDs follow the pattern:**
```
<label_lower>:<file_path>:<name>
e.g. function:src/auth.ts:login
     component:src/App.tsx:App
     module:src/utils.ts
```

## MCP interface

The server runs in `stdio` mode — the agent spawns it as a subprocess. All tools return JSON-serialisable dicts. Tools that require Neo4j receive a `Neo4jClient` injected by the dispatcher.

See [mcp.md](mcp.md) for the full tool reference.

## Configuration

Project config lives in `.rei/project.toml`. Global config (Neo4j connection, defaults) in `~/.rei-graph/config.toml`. Both are read by `rei_core.config`.

See [PRD.md](PRD.md) § 3.6 for the full config schema.
