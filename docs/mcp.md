# MCP Integration

How to connect dev-graph-kit to your AI coding agent via MCP.

## Overview

dev-graph-kit exposes a Model Context Protocol (MCP) server that runs in `stdio` mode. Your agent spawns it as a subprocess and communicates via JSON-RPC over stdin/stdout.

## Starting the MCP server

```bash
uv run dgk mcp
```

Or, if you've activated the venv:
```bash
dgk mcp
```

## Agent configuration

### Cursor

Add to `~/.cursor/mcp.json` (or workspace `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "dev-graph-kit": {
      "command": "uv",
      "args": ["--directory", "/path/to/dev-graph-kit", "run", "dgk", "mcp"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "devgraphkit"
      }
    }
  }
}
```

### Claude Code

Add to your Claude Code MCP config (`~/.claude/mcp_servers.json`):

```json
{
  "dev-graph-kit": {
    "command": "uv",
    "args": ["--directory", "/path/to/dev-graph-kit", "run", "dgk", "mcp"],
    "env": {
      "NEO4J_URI": "bolt://localhost:7687",
      "NEO4J_USER": "neo4j",
      "NEO4J_PASSWORD": "devgraphkit"
    }
  }
}
```

Or via the Claude Code CLI:
```bash
claude mcp add dev-graph-kit \
  --command "uv" \
  --args "--directory /path/to/dev-graph-kit run dgk mcp" \
  --env NEO4J_URI=bolt://localhost:7687 \
  --env NEO4J_USER=neo4j \
  --env NEO4J_PASSWORD=devgraphkit
```

### Codex (OpenAI)

Add to your Codex agent config:

```json
{
  "tools": [
    {
      "type": "mcp",
      "server": {
        "command": "uv",
        "args": ["--directory", "/path/to/dev-graph-kit", "run", "dgk", "mcp"],
        "env": {
          "NEO4J_URI": "bolt://localhost:7687",
          "NEO4J_USER": "neo4j",
          "NEO4J_PASSWORD": "devgraphkit"
        }
      }
    }
  ]
}
```

## Tool reference

### Graph tools

#### `graph.search_entities`
Search for code entities by name or partial match.

```json
{ "query": "useAuth", "labels": ["Hook"], "limit": 10 }
→ { "entities": [{ "id": "hook:src/hooks.ts:useAuth", "name": "useAuth", ... }] }
```

#### `graph.get_context`
Get nodes, relationships, and a summary for a natural-language query.

```json
{ "query": "auth flow" }
→ { "nodes": [...], "relationships": [...], "summary": "Found 3 nodes related to auth..." }
```

#### `graph.get_neighbors`
Traverse from a node with direction/type filters.

```json
{ "nodeId": "module:src/auth.ts", "direction": "out", "types": ["IMPORTS"], "depth": 2 }
→ { "nodes": [...], "relationships": [...] }
```

#### `graph.impact_analysis`
Find everything affected if a node changes.

```json
{ "target": "src/utils.ts" }
→ { "directlyAffected": [...], "transitivelyAffected": [...], "riskScore": 0.4, "recommendations": [...] }
```

#### `graph.upsert_entities`
Write or update nodes in the graph.

```json
{ "entities": [{ "id": "module:src/new.ts", "label": "Module", "name": "new", "path": "src/new.ts", "line": 1 }] }
→ { "upserted": 1 }
```

#### `graph.upsert_relations`
Write or update relationships.

```json
{ "relations": [{ "type": "IMPORTS", "from": "module:src/a.ts", "to": "module:src/b.ts" }] }
→ { "upserted": 1 }
```

### Memory tools

#### `memory.record_analysis`
Persist an analysis observation.

```json
{ "scope": "auth module", "findings": "LoginForm duplicates session parsing from Dashboard", "relatedNodes": ["component:src/LoginForm.tsx:LoginForm"] }
→ { "id": "analysis:...", "recorded": true }
```

#### `memory.record_decision`
Persist a decision with rationale.

```json
{ "context": "auth refactor", "choice": "extract to shared/auth.ts", "rationale": "avoid duplication found in analysis", "alternatives": ["keep in each feature"] }
→ { "id": "decision:...", "recorded": true }
```

#### `memory.record_change`
Record a code change.

```json
{ "description": "Extracted session parsing to shared/auth.ts", "affectedFiles": ["src/LoginForm.tsx", "shared/auth.ts"] }
→ { "id": "change:...", "recorded": true }
```

#### `memory.record_validation`
Record a validation result.

```json
{ "type": "test", "passed": true, "notes": "All 47 auth tests pass" }
→ { "id": "validation:...", "recorded": true }
```

#### `memory.record_plan`
Record a high-level plan (separate from DAG execution).

```json
{ "goal": "refactor auth", "steps": ["analyze", "extract", "test"] }
→ { "id": "plan:...", "recorded": true }
```

#### `memory.get_recent_context`
Retrieve relevant past memories.

```json
{ "query": "auth", "limit": 5 }
→ { "memories": [{ "type": "Decision", "summary": "...", "timestamp": "..." }] }
```

### DAG tools

#### `dag.create_plan`
Create an executable multi-step plan.

```json
{ "goal": "extract auth shared logic", "steps": [{ "name": "scan", "description": "Scan auth files" }, { "name": "extract", "description": "Move shared logic" }] }
→ { "planId": "plan:abc123", "status": "pending" }
```

#### `dag.run_plan`
Start executing a plan.

```json
{ "planId": "plan:abc123" }
→ { "planId": "plan:abc123", "status": "running" }
```

#### `dag.step_status`
Check the status of a specific step.

```json
{ "planId": "plan:abc123", "stepName": "scan" }
→ { "status": "completed", "output": "Scanned 12 files" }
```

#### `dag.get_plan`
Get full plan details including all steps.

```json
{ "planId": "plan:abc123" }
→ { "plan": { "goal": "...", "status": "running" }, "steps": [...] }
```

#### `dag.cancel_plan`
Cancel a running plan.

```json
{ "planId": "plan:abc123" }
→ { "cancelled": true }
```

### Scan tools

#### `scan.project`
Trigger a full project scan.

```json
{ "path": "." }
→ { "status": "ok", "output": "Done: 42 nodes, 38 relationships from 5 files" }
```

#### `scan.file`
Scan a single file.

```json
{ "path": "src/auth.ts" }
→ { "status": "ok", "output": "Done: 3 nodes, 2 relationships" }
```

#### `scan.changed_files`
Incrementally scan only git-changed files.

```json
{ "path": "." }
→ { "status": "ok", "output": "Done: 2 nodes, 1 relationships from 1 changed files" }
```

### Project tools

#### `project.status`
Get Neo4j health and total node count.

```json
{}
→ { "neo4j": { "status": "healthy" }, "nodeCount": 156 }
```

#### `project.snapshot`
Export the current graph to a JSON snapshot.

```json
{ "snapshot_dir": "~/.dev-graph-kit/snapshots", "project_id": "my-app" }
→ { "status": "ok", "path": "/Users/.../.dev-graph-kit/snapshots/my-app/snapshots/snap_20260418.json" }
```

## Resources

Resources provide ready-to-read context without a tool call:

| URI | Description |
|-----|-------------|
| `project://schema` | Graph schema (node labels, relationship types) |
| `project://summary` | Project overview and node count |
| `project://recent-decisions` | Last 10 decisions recorded by agents |
| `project://open-plans` | All pending/running plans |
| `plan://<id>` | Full details for a specific plan |

## Recommended agent workflow

```
1. graph.get_context("feature area")        → understand current state
2. memory.get_recent_context("feature area") → check past decisions
3. dag.create_plan({goal, steps})           → create execution plan
4. [for each step]:
     - do the work
     - dag.step_status (update)
     - memory.record_analysis / record_change
5. memory.record_decision(...)              → capture why
6. graph.upsert_entities / upsert_relations → update graph
```
