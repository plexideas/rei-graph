# Plan: Per-Project Isolation in Neo4j

> Source PRD: [docs/project-isolation-prd.md](../docs/project-isolation-prd.md)

## Architectural decisions

Durable decisions that apply across all phases:

- **Project identity**: Canonical absolute path of the project root (`Path.resolve()`), stored in `.dgk/project.toml` under `[project] id`
- **Node ID scheme**: `label:{hash12}:relpath:name` — 12-hex-char SHA256 hash of the absolute project path as prefix, making IDs globally unique without cross-project coordination
- **Scoping mechanism**: Property-based — every Neo4j node gets a `project_id` property (the absolute path). All Cypher queries include `WHERE n.project_id = $project_id` (or equivalent MERGE constraint). No `BELONGS_TO_PROJECT` relationship.
- **Project registry**: `Project` node in Neo4j with properties: `id` (absolute path), `name`, `hash` (12-char hex), `root_path`, `last_scanned_at`, `created_at`
- **Client architecture**: `Neo4jClient`, `MemoryClient`, `DagClient`, `SnapshotClient` all accept `project_id` at construction. All operations are implicitly scoped — no caller passes `project_id` per method call.
- **TS ingester**: `--project-prefix <hash>` CLI argument. Optional for backward compatibility; Python CLI always passes it.
- **MCP multi-project**: `project_id` is a required parameter on every MCP tool call. Server maintains a lazy cache of `{project_id: client_instances}`.
- **Neo4j indexing**: Composite index on `(project_id, name)` for search queries; index on `project_id` for all node labels.
- **Migration**: None. Clean-slate approach — existing unscoped data is orphaned; users rescan after upgrading.

---

## Phase 1: Project identity + Neo4jClient scoping

**User stories**: 1, 2, 19, 20

### What to build

Add a `project_hash(project_id: str) -> str` utility to `dgk_core` that computes the 12-hex-char SHA256 prefix from an absolute path. Update `Neo4jClient` to accept `project_id` at construction and implicitly scope all operations: `upsert_nodes` stamps every node with `project_id` and prefixes node IDs; `upsert_relationships` matches nodes within the project; `search_nodes`, `get_dependents`, `get_neighbors`, `count_nodes`, and `delete_file_nodes` all filter by `project_id`. On first use, MERGE a `Project` registry node with `id`, `name`, `hash`, `root_path`, `created_at`. Update `dgk init` to write `project_id` (resolved absolute path) into `.dgk/project.toml` under `[project] id`.

### Acceptance criteria

- [ ] `project_hash()` in `dgk_core` returns deterministic 12-hex-char SHA256 prefix for a given absolute path
- [ ] `Neo4jClient(project_id=...)` stores `project_id` and computes hash at construction
- [ ] `upsert_nodes` sets `project_id` property on every node and prefixes node IDs with hash
- [ ] `upsert_relationships` matches source/target within the scoped project
- [ ] `search_nodes`, `get_dependents`, `get_neighbors`, `count_nodes`, `delete_file_nodes` all include `project_id` filter
- [ ] `Project` node is MERGEd in Neo4j on client construction with correct properties
- [ ] `dgk init` writes `project_id` (absolute path) to `.dgk/project.toml`
- [ ] Tests: two `Neo4jClient` instances with different `project_id`s produce isolated upsert/search results (mock-level verification that Cypher params include correct `project_id`)
- [ ] All existing tests pass (updated to supply `project_id`)

---

## Phase 2: TS ingester prefix + scan integration

**User stories**: 2, 3

### What to build

Add a `--project-prefix <hash>` CLI argument to the TS ingester. When provided, `makeId()` incorporates the hash into every generated node ID (`label:{hash}:relpath:name` instead of `label:relpath:name`). When omitted, current behavior is preserved. Update `dgk scan` to resolve the project's absolute path, compute the hash, and pass `--project-prefix` to the ingester subprocess. If `.dgk/project.toml` does not exist at scan time, auto-create it (equivalent to `dgk init`) before scanning. Construct `Neo4jClient` with the resolved `project_id` for all storage operations during scan.

### Acceptance criteria

- [x] TS ingester accepts `--project-prefix <hash>` argument
- [x] When `--project-prefix` is provided, all node IDs in output JSON include the hash prefix
- [x] When `--project-prefix` is omitted, output is identical to current behavior
- [x] `dgk scan <path>` resolves absolute path, computes hash, passes `--project-prefix` to ingester
- [x] `dgk scan <path>` on a directory without `.dgk/project.toml` auto-creates it before scanning
- [x] `Neo4jClient` in scan path is constructed with the resolved `project_id`
- [x] Tests: ingester output with `--project-prefix` contains prefixed IDs; scan integration test verifies prefix is passed
- [x] All existing tests pass

---

## Phase 3: Repeat-scan detection + incremental auto-switch

**User stories**: 4, 5, 6, 16, 17

### What to build

When `dgk scan <path>` runs, query the `Project` node for the resolved path. If it exists and has a `last_scanned_at` timestamp: print a warning ("Project already scanned (last: {timestamp}). Running incremental scan. Use --force for full rescan."), then perform an incremental scan by diffing against that timestamp via `git diff --name-only --since={timestamp}` instead of `HEAD`. Add a `--force` flag to `dgk scan` that bypasses this and does a full rescan. After any successful scan (full or incremental), update `last_scanned_at` on the `Project` node. Behavior is non-interactive — no TTY prompt.

### Acceptance criteria

- [ ] `dgk scan <path>` on a known project (existing `Project` node) prints a warning with last scan timestamp
- [ ] Known-project scan automatically switches to incremental mode (git diff by `last_scanned_at` timestamp)
- [ ] `--force` flag overrides incremental behavior and performs a full rescan
- [ ] `last_scanned_at` is updated on the `Project` node after every successful scan
- [ ] First-time scan (no `Project` node) does a full scan with no warning
- [ ] Non-interactive: no TTY prompts — `--force` is the only override mechanism
- [ ] Tests: mock `Project` node lookup to verify warning output, incremental vs full behavior, `--force` bypass, timestamp update
- [ ] All existing tests pass

---

## Phase 4: MemoryClient + DagClient scoping

**User stories**: 8, 9

### What to build

Update `MemoryClient` to accept `project_id` at construction. All memory node creation methods (`record_analysis`, `record_decision`, `record_change`, `record_validation`, `record_plan`) stamp nodes with `project_id`. All query methods (`get_recent_context`, `get_recent_decisions`) filter by `project_id`. Update `DagClient` similarly: `create_plan` stamps `DagPlan` and `DagStep` nodes with `project_id`; `list_open_plans`, `get_plan`, `step_status`, `run_plan`, `cancel_plan` all filter by `project_id`. Update CLI commands (`dgk plan`, `dgk plans`) to resolve and pass `project_id`.

### Acceptance criteria

- [x] `MemoryClient(project_id=...)` stores and uses `project_id` for all operations
- [x] Memory nodes created with `project_id` property; queries filter by it
- [x] `DagClient(project_id=...)` stores and uses `project_id` for all operations
- [x] DAG plan/step nodes created with `project_id` property; queries filter by it
- [x] `dgk plan` and `dgk plans` CLI commands resolve and pass `project_id`
- [x] Tests: two `MemoryClient` instances with different `project_id`s produce isolated results; same for `DagClient`
- [x] All existing tests pass (updated to supply `project_id`)

---

## Phase 5: SnapshotClient + query + impact scoping

**User stories**: 7, 10

### What to build

Update `SnapshotClient` to accept `project_id` at construction. `export_graph()` filters to only return nodes and relationships matching the scoped `project_id`. Snapshot metadata includes the `project_id`. Update `dgk query` and `dgk impact` CLI commands to resolve the current project's absolute path and construct `Neo4jClient` with the correct `project_id`, so results are scoped. Update `dgk snapshot` to resolve and pass `project_id`.

### Acceptance criteria

- [x] `SnapshotClient(project_id=...)` stores and uses `project_id`
- [x] `export_graph()` only returns nodes/relationships for the scoped project
- [x] Snapshot JSON metadata includes `project_id`
- [x] `dgk query` resolves project and constructs scoped `Neo4jClient` — results only from current project
- [x] `dgk impact` resolves project and constructs scoped `Neo4jClient` — dependents only from current project
- [x] `dgk snapshot` resolves project and constructs scoped `SnapshotClient`
- [x] Tests: snapshot export with two projects in DB only returns scoped data; query/impact return scoped results
- [x] All existing tests pass

---

## Phase 6: MCP server multi-project

**User stories**: 11, 12, 13, 14

### What to build

Add `project_id` as a required parameter to every MCP tool's `inputSchema`. The MCP server maintains a lazy cache (`dict[str, ClientInstances]`) keyed by `project_id`. On each tool call, look up or create the appropriate scoped client (`Neo4jClient`, `MemoryClient`, `DagClient`, `SnapshotClient`) for the given `project_id`. All tool handlers use the scoped client. Update MCP resources (`project://summary`, `project://recent-decisions`, `project://open-plans`) to accept `project_id` as a URI parameter and return scoped data.

### Acceptance criteria

- [ ] Every MCP tool requires `project_id` in its input schema
- [ ] Server caches client instances per `project_id` (lazy creation on first use)
- [ ] `graph.search_entities` with different `project_id`s returns isolated results
- [ ] `memory.get_recent_context` with different `project_id`s returns isolated results
- [ ] `scan.project`, `scan.file`, `scan.changed_files` are scoped to the given `project_id`
- [ ] MCP resources return scoped data when `project_id` is provided
- [ ] Tests: MCP tool calls with different `project_id`s verify correct scoped clients are used
- [ ] All existing tests pass (updated to include `project_id` in tool arguments)

---

## Phase 7: Project deletion + cleanup

**User stories**: 15

### What to build

Add a `delete_project(project_id: str)` method to `Neo4jClient` (or a standalone utility) that removes ALL nodes with the given `project_id` — code nodes, memory nodes, DAG plans/steps, and the `Project` registry node itself. Expose this via a `dgk delete-project <path>` CLI command (with confirmation prompt) and an MCP tool `project.delete(project_id)`. The CLI command also removes the local `.dgk/` directory if it exists at the given path.

### Acceptance criteria

- [ ] `delete_project(project_id)` removes all nodes (code, memory, DAG, Project) with that `project_id` via `DETACH DELETE`
- [ ] `dgk delete-project <path>` CLI command resolves path, confirms with user, then deletes
- [ ] CLI command removes local `.dgk/` directory at the project path
- [ ] MCP `project.delete(project_id)` tool calls delete without TTY prompt
- [ ] Tests: after delete, queries for that `project_id` return no results; other projects are unaffected
- [ ] All existing tests pass
