# Plan: rei-graph

> Source PRD: docs/PRD.md (v1.1, 2026-04-17)

## Architectural decisions

Durable decisions that apply across all phases:

- **Tech stack**: Python monorepo (uv), Neo4j Community (Docker), Graphiti (memory), Dagster (DAG), TypeScript ts-morph (code scanner), MCP protocol (agent interface)
- **CLI**: `rei` command via Click/Typer — subcommands `init`, `dev`, `scan`, `query`, `impact`, `plan`, `plans`, `snapshot`, `doctor`
- **Graph ontology**:
  - Code nodes: `Repository`, `Package`, `Directory`, `File`, `Module`, `Function`, `Class`, `Component`, `Hook`, `Type`, `Interface`, `Endpoint`, `Table`, `Query`
  - Architecture nodes: `Feature`, `DomainEntity`, `BusinessRule`, `Integration`, `ConfigFlag`
  - Memory nodes: `Analysis`, `Plan`, `Decision`, `Change`, `Validation`, `Hypothesis`, `Todo`, `Session`
  - Provenance nodes: `Commit`, `PR`, `Issue`, `Snapshot`, `Document`
- **Relationships**: `IMPORTS`, `CALLS`, `USES_TYPE`, `READS`, `WRITES`, `EXPOSES`, `DEPENDS_ON`, `IMPLEMENTS`, `AFFECTS`, `BELONGS_TO`, `CONSTRAINED_BY`, `BASED_ON`, `PROPOSES`, `RESULTED_IN`, `SUPERSEDES`, `VALIDATED_BY`, `OBSERVED_IN`, `DERIVED_FROM`, `CHANGED_BY`
- **MCP tool namespaces**: `graph.*`, `memory.*`, `dag.*`, `scan.*`, `project.*`
- **MCP resource URIs**: `project://schema`, `project://summary`, `project://recent-decisions`, `project://open-plans`, `file://<path>/context`, `entity://<id>`, `plan://<id>`
- **Services (local)**: Neo4j at `localhost:7474`/`7687`, Dagster UI at `localhost:3000`, MCP server at `localhost:8080`
- **Config**: `.rei/project.toml` (per-project), `~/.rei-graph/config.toml` (global)
- **Package layout**: `packages/` with `core/`, `storage/`, `ingester_ts/`, `dag/`, `mcp_server/`, `cli/`
- **Graph vs DAG separation**: Neo4j + Graphiti store permanent knowledge and memory; Dagster stores executable plans, step ordering, and execution status

---

## Phase 1: Project skeleton + Neo4j up/down

**Goals**: P1 setup < 5 min, Docker dependency

### What to build

Scaffold the Python monorepo with `pyproject.toml`, `docker-compose.yml` (Neo4j service), and `.env.example`. Create the `rei` CLI entry point with three subcommands: `rei init` creates `.rei/project.toml` with default config, `rei dev` starts/stops the Neo4j container, and `rei doctor` checks that Neo4j is reachable and returns a health status. The entire flow — init, start services, verify health — works end-to-end.

### Acceptance criteria

- [ ] `uv sync` installs all Python dependencies
- [ ] `docker compose up -d` starts Neo4j, accessible at `localhost:7474`
- [ ] `rei init` creates `.rei/project.toml` with sensible defaults
- [ ] `rei dev` starts Neo4j (or reports it's already running)
- [ ] `rei doctor` reports Neo4j connectivity status
- [ ] README has "What / Why / How to start" sections

---

## Phase 2: TS scanner → Neo4j code graph (single file)

**Goals**: P0 query code graph, P2 TS/React scanning

### What to build

The TypeScript ingester (`ingester_ts`) parses a single `.ts`/`.tsx` file using ts-morph, extracts code nodes (`Module`, `Function`, `Class`, `Component`, `Hook`, `Type`, `Interface`) and relationships (`IMPORTS`, `CALLS`, `USES_TYPE`, `EXPOSES`), and writes them to Neo4j. The `rei scan <file>` command invokes the ingester for one file, and `rei query "<search>"` retrieves nodes by name or label. End-to-end: scan a single file, query its entities back from the graph.

### Acceptance criteria

- [ ] `ingester_ts` parses a TS/TSX file and outputs structured nodes + relationships
- [ ] Nodes written to Neo4j with correct labels and properties
- [ ] Relationships written to Neo4j with correct types
- [ ] `rei scan <file>` triggers single-file ingestion
- [ ] `rei query "<name>"` returns matching nodes from Neo4j
- [ ] Scanning the same file twice upserts (no duplicates)

---

## Phase 3: Full project scan + impact analysis

**Goals**: P0 accurate dependency/impact info, P2 TS/React out-of-box

### What to **build**

Extend `rei scan .` to walk the project tree (respecting include/exclude from `.rei/project.toml`), scan all TS/TSX files, and resolve cross-file imports into `IMPORTS` and `DEPENDS_ON` relationships. Add `rei impact <file>` which traverses the graph to find directly and transitively affected nodes when a file changes. The code graph is now complete enough to answer dependency questions across an entire React/TS project.

### Acceptance criteria

- [ ] `rei scan .` scans all matching files in the project tree
- [ ] Cross-file `IMPORTS` relationships resolved correctly
- [ ] `DEPENDS_ON` relationships created between packages
- [ ] `rei impact <file>` returns direct and transitive dependents
- [ ] Scan respects `include`/`exclude` patterns from project config
- [ ] Demo: scan `examples/react_ts_app`, query dependencies, run impact analysis

---

## Phase 4: MCP server with graph tools

**Goals**: P1 works with Codex/Claude Code/Cursor via MCP

### What to build

A Python MCP server that exposes the graph and scan capabilities to agents. Tools: `graph.get_context`, `graph.search_entities`, `graph.get_neighbors`, `graph.impact_analysis`, `graph.upsert_entities`, `graph.upsert_relations`, `scan.project`, `scan.file`, `project.status`. Resources: `project://schema`, `project://summary`. The server starts via `rei mcp` (stdio mode) or as part of `rei dev`. An agent can connect, query the code graph, and get structured results.

### Acceptance criteria

- [ ] MCP server starts and responds to `initialize` handshake
- [ ] `graph.search_entities` returns nodes matching a query
- [ ] `graph.get_context` returns nodes + relationships + summary for a query
- [ ] `graph.get_neighbors` traverses from a node with direction/type filters
- [ ] `graph.impact_analysis` returns affected nodes and risk score
- [ ] `graph.upsert_entities` and `graph.upsert_relations` write to graph
- [ ] `scan.project` and `scan.file` trigger scanning via MCP
- [ ] `project.status` returns graph stats and service health
- [ ] `project://schema` and `project://summary` resources readable
- [ ] MCP config example works with at least one agent (Cursor, Claude Code, or Codex)

---

## Phase 5: Agent memory (record + retrieve)

**Goals**: P0 persist observations/decisions across sessions

### What to build

Integrate Graphiti as the temporal memory layer. Expose MCP tools: `memory.record_analysis`, `memory.record_decision`, `memory.record_change`, `memory.record_validation`, `memory.record_plan`, and `memory.get_recent_context`. Memory nodes (`Analysis`, `Decision`, `Change`, `Validation`) are stored in Graphiti with timestamps, linked to code graph nodes via relationships (`AFFECTS`, `BASED_ON`, `VALIDATED_BY`, `OBSERVED_IN`). A new agent session can query past context and get relevant memories. Add `project://recent-decisions` resource.

### Acceptance criteria

- [ ] Graphiti integrated and storing memory nodes in Neo4j
- [ ] `memory.record_analysis` creates an `Analysis` node linked to related code nodes
- [ ] `memory.record_decision` creates a `Decision` with rationale, alternatives, and `BASED_ON` links
- [ ] `memory.record_change` creates a `Change` linked to affected files
- [ ] `memory.record_validation` creates a `Validation` linked to a `Change`
- [ ] `memory.get_recent_context` retrieves relevant memories by query, scope, and time range
- [ ] Memory persists across MCP server restarts (stored in Neo4j)
- [ ] `project://recent-decisions` resource returns last N decisions
- [ ] Demo: agent records analysis + decision in session 1, retrieves them in session 2

---

## Phase 6: DAG execution (create + run plans)

**Goals**: P0 create and execute multi-step plans with status tracking

### What to build

Set up Dagster with jobs, ops, and resources. Expose MCP tools: `dag.create_plan`, `dag.run_plan`, `dag.get_plan`, `dag.step_status`, `dag.cancel_plan`. Plans are recorded in the knowledge graph via `memory.record_plan` with `PROPOSES` links. `rei plan "<goal>"` creates a plan from the CLI, `rei plans` lists open plans. Dagster UI available at `localhost:3000` for visual inspection. Add `project://open-plans` and `plan://<id>` resources.

### Acceptance criteria

- [ ] Dagster configured with job definitions and ops
- [ ] `dag.create_plan` creates a multi-step plan with dependencies between steps
- [ ] `dag.run_plan` executes the plan, steps run in dependency order
- [ ] `dag.step_status` returns current status and output of a step
- [ ] `dag.get_plan` returns full plan details
- [ ] `dag.cancel_plan` stops a running plan
- [ ] Plans linked to knowledge graph via `memory.record_plan`
- [ ] `rei plan "<goal>"` and `rei plans` CLI commands work
- [ ] Dagster UI shows plan runs at `localhost:3000`
- [ ] `project://open-plans` and `plan://<id>` resources readable
- [ ] Demo: create a plan, execute it, check step status, see it in Dagster UI

---

## Phase 7: Incremental scan + snapshots

**Goals**: P0 accurate graph (kept up to date), operational robustness

### What to build

Add `rei scan --changed` which uses git diff to identify modified files and re-scans only those, updating the graph incrementally (removing stale nodes for deleted entities). Add `rei snapshot` to save the current graph state and `project.snapshot` MCP tool. Add `scan.changed_files` MCP tool. Snapshots stored under `~/.rei-graph/projects/<id>/snapshots/`.

### Acceptance criteria

- [ ] `rei scan --changed` detects git-changed files and scans only those
- [ ] Incremental scan removes nodes for deleted/renamed entities
- [ ] `scan.changed_files` MCP tool works with a `since` parameter
- [ ] `rei snapshot` exports current graph state
- [ ] `project.snapshot` MCP tool creates snapshots
- [ ] Snapshots stored in `~/.rei-graph/projects/<id>/snapshots/`
- [ ] Demo: modify a file, run incremental scan, verify only changed nodes updated

---

## Phase 8: Examples, docs, and OSS polish

**Goals**: P1 setup < 5 min for strangers, community readiness

### What to build

Create `examples/react_ts_app` and `examples/express_api` as demo projects that can be scanned out of the box. Write documentation: `install.md`, `architecture.md`, `ontology.md`, `mcp.md`, `examples.md`. Add a one-command bootstrap script. Write agent integration guides for Cursor, Codex, and Claude Code. Add pytest test suite and GitHub Actions CI. Polish error handling, logging, and CLI output.

### Acceptance criteria

- [ ] `examples/react_ts_app` is a scannable React/TS project with meaningful structure
- [ ] `examples/express_api` is a scannable Express API project
- [ ] All docs written and accurate: install, architecture, ontology, MCP, examples
- [ ] One-command bootstrap: clone → setup → running in < 5 minutes
- [ ] Agent integration guides for Cursor, Codex, and Claude Code
- [ ] Test suite with meaningful coverage for core, storage, ingester, MCP server
- [ ] GitHub Actions CI runs tests on push
- [ ] Demo: new user follows README, scans example project, connects agent — all works
