# PRD: Per-Project Isolation in Neo4j

**Version:** 1.0  
**Date:** April 18, 2026  
**Status:** Draft

---

## Problem Statement

rei-graph currently stores all data from all projects in a single shared Neo4j database with no scoping. Node IDs are based on relative file paths (`label:relpath:name`), which means two different projects with overlapping file structures will have ID collisions. Memory nodes (Analysis, Decision, Change), DAG plans, and snapshots are all global — an agent querying context for Project A will receive data from Project B. There is no concept of a "known project" in the graph, so repeated scans of the same project cannot be detected. The `--changed` incremental scan flag exists but must be manually specified every time.

This makes rei-graph fundamentally broken for any user working on more than one project, and wasteful for users re-scanning the same project.

## Solution

Introduce strict per-project isolation across all storage layers. Every node and relationship in Neo4j will be scoped to a specific project via a `project_id` property (the canonical absolute path of the project root). A `Project` node in Neo4j will serve as a registry of known projects, tracking metadata like `last_scanned_at`. All storage clients (`Neo4jClient`, `MemoryClient`, `DagClient`, `SnapshotClient`) will accept `project_id` at construction time and implicitly scope all queries to that project. Node IDs will be globally unique by incorporating a 12-hex-char hash of the project path as a prefix. The TS ingester will accept this prefix as an argument and generate properly-scoped IDs directly.

When a user runs `rei scan <path>` for a project that already exists in the registry, the system will warn and automatically perform an incremental scan (diffing against the stored `last_scanned_at` timestamp) instead of a full rescan. A `--force` flag will allow a full rescan override. If `.rei/project.toml` does not exist at scan time, the system will auto-initialize it.

## User Stories

1. As a developer working on multiple projects, I want each project's graph data stored separately, so that querying one project never returns results from another.
2. As a developer, I want node IDs to be globally unique across projects, so that two projects with the same file structure don't corrupt each other's data.
3. As a developer, I want `rei scan` to auto-initialize a project on first run, so that I don't need a separate `rei init` step.
4. As a developer, I want the system to detect when I'm re-scanning a known project and automatically switch to incremental scanning, so that I save time without remembering the `--changed` flag.
5. As a developer, I want to see a warning when a repeat scan is detected, so that I understand why a full scan isn't happening.
6. As a developer, I want a `--force` flag to override incremental behavior and do a full rescan when needed, so that I have an escape hatch.
7. As a developer, I want snapshots to export only the current project's data, so that snapshots are meaningful and don't contain data from unrelated projects.
8. As a developer, I want memory nodes (Analysis, Decision, Change, Validation, Plan) to be scoped to a project, so that agent memory doesn't leak across projects.
9. As a developer, I want DAG execution plans to be scoped to a project, so that plans from one project don't appear in another.
10. As a developer, I want `rei query` and `rei impact` to only return results from the current project, so that results are relevant.
11. As an agent interacting through MCP, I want to specify a `project_id` on each tool call, so that I can work with multiple projects through a single MCP server.
12. As an agent, I want `graph.search_entities` to only return nodes from my project, so that context is not polluted by other projects.
13. As an agent, I want `memory.get_recent_context` to only return memory nodes from my project, so that I don't get confused by another project's decisions.
14. As an agent, I want `scan.project` and `scan.changed_files` to be project-scoped, so that scanning one project doesn't affect another.
15. As a developer, I want to be able to delete all data for a specific project (code nodes, memory, plans, snapshots), so that I can cleanly remove a project from the graph.
16. As a developer, I want the incremental scan on repeat runs to diff against the last scan timestamp, so that it catches all changes since the previous scan — not just uncommitted changes.
17. As a developer running CI/automation, I want the repeat-scan behavior to be non-interactive by default, so that scripts don't hang waiting for user input.
18. As a developer, I want the system to work out of the box after a clean install without needing to migrate old data, so that setup is simple.
19. As a developer, I want the Project node in Neo4j to store metadata like project name, root path, and last scan time, so that I can inspect project status.
20. As a developer scanning a project from a different working directory, I want the canonical absolute path to be used as project identity, so that the same project is always recognized regardless of how I invoke the command.

## Implementation Decisions

**Isolation mechanism**: Property-based scoping. Every node in Neo4j will have a `project_id` property set to the canonical absolute path of the project root. All Cypher queries will include a `WHERE n.project_id = $project_id` filter (or equivalent MERGE constraint). No `BELONGS_TO_PROJECT` relationship — property only.

**Project identity**: The canonical absolute path of the project root (resolved via `Path.resolve()`). This value is stored in `.rei/project.toml` under `[project] id`.

**Node ID scheme**: Node IDs will use a 12-hex-char SHA256 hash of the absolute project path as a prefix: `label:{hash12}:relpath:name`. This makes IDs globally unique without requiring cross-project coordination.

**TS ingester changes**: The ingester CLI will accept a `--project-prefix <hash>` argument. When provided, all generated node IDs will be prefixed with this hash (e.g., `module:{hash}:src/App.tsx` instead of `module:src/App.tsx`). When omitted, current behavior is preserved for backward compatibility.

**Project registry**: A `Project` node in Neo4j with properties: `id` (absolute path), `name`, `hash` (12-char hex), `root_path`, `last_scanned_at`, `created_at`. This node is MERGEd on first scan and updated on subsequent scans.

**Client architecture**: `Neo4jClient`, `MemoryClient`, `DagClient`, and `SnapshotClient` will all accept `project_id` in their constructors. All operations are implicitly scoped. No caller needs to remember to pass `project_id` per method call.

**MCP server**: Multi-project capable. `project_id` is a required parameter on every MCP tool call. The server maintains a cache (dict) of `{project_id: client_instances}` to reuse Neo4j connections across calls for the same project. Client instances are created lazily on first use.

**Scan behavior for known projects**: When `rei scan <path>` detects an existing Project node (by resolved absolute path):
  - Print a warning: "Project already scanned (last: {timestamp}). Running incremental scan. Use --force for full rescan."
  - Perform an incremental scan using git diff against the `last_scanned_at` timestamp (e.g., `git diff --name-only --since={timestamp}`)
  - Update `last_scanned_at` on the Project node after completion
  - `--force` flag bypasses this and does a full rescan
  - Non-interactive by default — no TTY prompt. The `--force` flag is the only way to get a full rescan.

**Auto-init**: If `rei scan <path>` is run on a path without `.rei/project.toml`, the system will auto-create it (equivalent to running `rei init`) before scanning.

**Snapshot scoping**: `SnapshotClient.export_graph()` will only export nodes matching the current `project_id`. The snapshot meta will include the `project_id`.

**Data cleanup**: When deleting a project, ALL nodes with that `project_id` are removed — code nodes, memory nodes, DAG plans, everything. The Project node itself is also removed.

**Migration**: None. This is a clean-slate approach. Existing unscoped data will be orphaned; users should rescan after upgrading.

## Testing Decisions

Tests should verify **external behavior** — that project-scoped operations return only the correct project's data and never leak across project boundaries. Tests should not assert on internal Cypher query structure or internal method calls.

**Modules to test:**

- **`Neo4jClient`** — Verify that upsert and search operations with different `project_id`s return isolated results. Two projects with the same relative file structure should not collide.
- **`MemoryClient`** — Verify that memory nodes (Analysis, Decision, Change, Validation, Plan) created for project A are not visible when querying project B.
- **`DagClient`** — Verify that DAG plans for project A don't appear in project B's plan list.
- **`SnapshotClient`** — Verify that export only includes nodes for the scoped project.
- **`scan` command** — Verify: (a) first scan creates a Project node, (b) repeat scan prints warning and runs incrementally, (c) `--force` overrides to full scan, (d) auto-init creates `.rei/project.toml` when missing.
- **`MCP server`** — Verify that tool calls with different `project_id` values are routed to correctly-scoped client instances and return isolated results.
- **`init` command** — Verify that `project_id` (absolute path) is written to `.rei/project.toml`.

**Prior art**: The existing test suite in `tests/` uses pytest with mocked Neo4j drivers (e.g., `test_neo4j_client.py`, `test_memory_client.py`, `test_scan.py`). New tests should follow the same mocking patterns.

## Out of Scope

- **Multi-machine / remote Neo4j**: Project identity is based on absolute local paths. Sharing a Neo4j instance across machines with different paths is not supported.
- **Project renaming / moving**: If a project directory is moved, it will be treated as a new project. No migration path for path changes.
- **Cross-project queries**: No support for querying across projects (e.g., "find all Functions named X across all projects").
- **Neo4j multi-database support**: We are not using separate Neo4j databases per project (would require Enterprise edition).
- **Python / non-TypeScript scanning**: Isolation applies to the existing TS/TSX ingester only.
- **Access control / permissions**: No per-project auth. All projects in the same Neo4j instance are accessible to anyone with DB credentials.
- **Embedding / vector search scoping**: If vector embeddings are added later, they will need separate scoping work.

## Further Notes

- **Index performance**: A Neo4j index should be created on `project_id` for all node labels to ensure property-based filtering remains fast as the database grows. Consider a composite index on `(project_id, name)` for search queries.
- **Git diff by timestamp**: The `--since` flag in `git diff` works with ISO timestamps. The `last_scanned_at` stored on the Project node must be in a format compatible with git's date parsing.
- **Backward compatibility**: The TS ingester's `--project-prefix` argument is optional, preserving backward compatibility for standalone ingester use. However, the Python CLI will always pass it during scans.
- **Future multi-tenant**: The property-based approach leaves the door open for moving to label-based or database-based isolation later if needed, since the `project_id` property is a simple superset of those approaches.
