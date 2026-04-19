# Plan: Scan-First Workflow

> Source PRD: docs/scan-first-workflow-prd.md

## Architectural decisions

Durable decisions that apply across all phases:

- **CLI framework**: Click (`@click.group` / `@click.command`)
- **Output library**: Rich (progress bars, spinners, console)
- **Phase pipeline order**: project detection → service health → file discovery → scan → summary
- **Status indicator convention**: `✓` for success, `✗` for failure, Rich spinner for in-progress
- **Health check mechanism**: `check_neo4j_health()` HTTP probe against `localhost:7474`
- **Auto-start mechanism**: `docker compose up -d` with bundled compose file resolved from installed package
- **Readiness polling**: Poll `check_neo4j_health()` with 30s timeout, configurable via `REI_SERVICE_TIMEOUT`
- **Scan mode selection**: first-run → full, repeat → incremental (git log --since), `--force` → full, `--changed` → git diff HEAD
- **Error message pattern**: what happened → what it means → what to do next

---

## Phase 1: Optional path + phased scan output

**User stories**: 10, 11

### What to build

Make `rei scan` work without a path argument by defaulting to the current directory. Wrap the existing scan logic with phase status lines so the user sees a step-by-step progression: project name, Neo4j status, scan mode, progress bar, and final summary. The underlying scan behavior (full, incremental, changed) stays the same — this phase only changes the CLI surface and output formatting.

### Acceptance criteria

- [ ] `rei scan` with no argument scans the current directory
- [ ] `rei scan <path>` still works as before
- [ ] Output shows `✓ Project: <name>` before scanning begins
- [ ] Output shows `✓ Neo4j: connected` before file discovery
- [ ] Output shows `✓ Mode: full scan (<N> files)` or `✓ Mode: incremental (<N> files changed)` before the progress bar
- [ ] Output shows `✓ Graph updated: <nodes> nodes, <rels> rels in <time>` after scan completes
- [ ] Existing tests continue to pass (updated for new output format)
- [ ] New tests verify default-path behavior and phased output lines

---

## Phase 2: Service health check and auto-start

**User stories**: 6, 7, 8, 9, 19, 20

### What to build

Before file discovery, `rei scan` probes Neo4j health. If the service is not running, the CLI checks for Docker availability. When Docker is present, it auto-starts Neo4j using a compose file bundled with the rei package (not the user's project), polls for readiness with a spinner, and continues scanning once ready. If Docker is absent, the CLI prints an actionable error with install instructions and exits. If the readiness poll times out (30s default, configurable via `REI_SERVICE_TIMEOUT`), the CLI prints an error suggesting `rei doctor`.

### Acceptance criteria

- [x] When Neo4j is healthy, scan proceeds and output shows `✓ Neo4j: connected`
- [x] When Neo4j is unhealthy and Docker is available, CLI prints `Neo4j is not running. Starting...`, runs `docker compose up -d` with the bundled compose file, and polls readiness
- [x] Readiness polling shows a Rich spinner and succeeds within 30s
- [x] After successful auto-start, scan continues normally
- [x] When Neo4j is unhealthy and Docker is not installed, CLI prints actionable error with Docker install link and exits with code 1
- [x] When readiness poll times out, CLI prints error suggesting `rei doctor` and exits with code 1
- [x] The compose file is resolved from the installed rei package, not the user's working directory
- [x] `REI_SERVICE_TIMEOUT` environment variable overrides the 30s default
- [x] Tests cover: healthy path, unhealthy+docker+success, unhealthy+docker+timeout, unhealthy+no-docker

---

## Phase 3: First-run UX and next-step suggestions

**User stories**: 1, 2, 3, 4, 5, 14, 23

### What to build

Differentiate first-run from repeat-run output. On first run (no `.rei/project.toml`), show `✓ Initialized project: <name> (.rei/project.toml created)` and print next-step suggestions after the scan summary (`rei query`, `rei impact`, `rei mcp`). On repeat runs, show the concise `✓ Project: <name>` and omit next-step suggestions. Handle corrupt or invalid `.rei/project.toml` by warning the user, regenerating with defaults, and continuing.

### Acceptance criteria

- [x] First scan shows `✓ Initialized project: <name> (.rei/project.toml created)`
- [x] First scan shows next-step suggestions block after the summary
- [x] Repeat scan shows `✓ Project: <name>` (no "Initialized")
- [x] Repeat scan does not show next-step suggestions
- [x] Corrupt `.rei/project.toml` triggers a warning, regenerates defaults, and scan continues
- [x] First-run detection uses `last_scanned_at` from the project node (None = first run)
- [x] Tests verify first-run vs repeat-run output, next-step presence/absence, and corrupt config recovery

---

## Phase 4: Action-oriented errors and graceful fallbacks

**User stories**: 13, 22

### What to build

Replace raw exceptions with structured error messages following the "what happened → what it means → what to do next" pattern. When Node.js is not found, show an install link. When git is unavailable or the project is not a git repo, fall back to full scan with a brief note instead of crashing. In normal mode, suppress tracebacks; with `--verbose`, include them for debugging.

### Acceptance criteria

- [ ] Node.js not found produces: clear message + install link + exit 1
- [ ] Git unavailable falls back to full scan with a note in output (no crash)
- [ ] Non-git project directory falls back to full scan with a note
- [ ] Neo4j connection errors during scan (not pre-check) produce actionable messages
- [ ] No raw Python tracebacks shown to user without `--verbose`
- [ ] `--verbose` flag includes traceback details for all error paths
- [ ] Tests verify each error scenario produces expected output strings and exit codes

---

## Phase 5: Rename `rei dev` to `rei service start/stop`

**User story**: 17

### What to build

Replace the `rei dev` command with a `rei service` group containing `start` and `stop` subcommands. `rei service start` runs `docker compose up -d` (same as old `rei dev`). `rei service stop` runs `docker compose down`. Remove the `dev` command registration from the CLI. Both subcommands use the bundled compose file from Phase 2.

### Acceptance criteria

- [ ] `rei service start` starts Neo4j via docker compose and prints status
- [ ] `rei service stop` stops Neo4j via docker compose down and prints status
- [ ] `rei dev` is no longer a registered command
- [ ] `rei --help` shows `service` but not `dev`
- [ ] Both subcommands use the bundled compose file (same resolution as Phase 2 auto-start)
- [ ] Existing `test_dev.py` tests are migrated to test the new `service` command
