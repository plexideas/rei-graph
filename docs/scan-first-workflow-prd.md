# Scan-First Workflow PRD

## Problem Statement

The current rei CLI requires users to understand and manually execute several technical steps before they can scan a project: start local infrastructure (`rei dev`), initialize the project (`rei init`), verify environment health (`rei doctor`), and only then run a scan (`rei scan <path>`). This multi-step onboarding creates unnecessary friction, especially for first-time users, and makes the product feel more complex than it needs to be. Users must remember command ordering, diagnose raw connection errors when services aren't running, and mentally model internal infrastructure concerns that should be invisible.

## Solution

Make `rei scan` the single entrypoint for both first-time setup and daily usage. The command should automatically detect project state, initialize when needed, check and start required services, choose the right scan mode, and provide clear guided output throughout. The everyday workflow becomes:

```
cd <project>
rei scan
rei query ... / rei impact ... / rei mcp
```

No separate `init`, `dev`, or `doctor` commands should be required for normal usage. The CLI should feel guided, reliable, and self-healing — automatically recovering from common problems and always telling the user what is happening, what went wrong, and what to do next.

## User Stories

1. As a first-time user, I want to run `rei scan` in my project directory and have everything set up automatically, so that I don't need to read documentation or learn multiple commands before getting value.
2. As a first-time user, I want the CLI to create `.rei/project.toml` automatically when it doesn't exist, so that I never need to run a separate init command.
3. As a first-time user, I want to see a slightly more explanatory first-run output (e.g., what rei created, what it's doing), so that I understand what just happened without needing docs.
4. As a returning user, I want `rei scan` to default to incremental scanning automatically, so that repeat scans are fast without me needing to know about scan modes.
5. As a returning user, I want repeat-run output to be concise, so that I'm not re-reading onboarding text every time.
6. As a user whose Neo4j service is not running, I want `rei scan` to detect this before attempting the scan, so that I don't see a raw connection error.
7. As a user whose Neo4j service is not running, I want the CLI to offer to start it for me automatically, so that I don't need to remember infrastructure commands.
8. As a user whose Neo4j service is not running and auto-start succeeds, I want the CLI to wait for the service to become ready and then continue scanning, so that the workflow is uninterrupted.
9. As a user whose Neo4j service is not running and auto-start is not possible (e.g., Docker not installed), I want a single clear recovery command shown to me, so that I know exactly what to do.
10. As a user scanning a large project, I want to see step-by-step phase indicators (project detection, service check, file discovery, indexing, graph update), so that I can tell the process is active and not frozen.
11. As a user, I want `rei scan` to work from my current directory without passing a path argument, so that the workflow matches `cd <project> && rei scan`.
12. As a user, I want to force a full rescan when I need to, using an explicit flag like `--force` or `--full`, so that I have an escape hatch when incremental scanning produces stale results.
13. As a user who encounters an error, I want every error message to explain what happened, what it means, and what I should do next, so that I can recover without searching for help.
14. As a user who just completed a scan, I want to see suggested next commands (e.g., `rei query`, `rei impact`, `rei mcp`), so that I know what to do next.
15. As a user, I want `rei doctor` to still be available as a troubleshooting command, so that I can run deeper diagnostics when something goes wrong.
16. As a user, I do not want `rei doctor` to be a required onboarding step, so that my first-run experience is simpler.
17. As a user, I want the `rei dev` command to either be hidden, removed, or renamed to something that clearly communicates "manage graph services," so that the command list isn't confusing.
18. As a user, I want `rei init` to remain available as an advanced/optional command for pre-configuring scan settings, so that power users can customize `.rei/project.toml` before first scan.
19. As a user, I want the service health check to happen early in the scan flow (before file discovery), so that I don't wait for file collection only to fail on a connection error.
20. As a user, I want the CLI to detect whether Docker is available before attempting to auto-start Neo4j, so that the error message is specific and actionable.
21. As a user with Git available, I want incremental scans to use git history to detect changes automatically, so that I don't need to specify what changed.
22. As a user without Git (or in a non-git project), I want the scan to fall back to a full scan gracefully, so that the tool still works.
23. As a user, I want the scan to handle a corrupted or invalid `.rei/project.toml` by warning me and regenerating defaults, so that a bad config file doesn't block my workflow.

## Implementation Decisions

### `rei scan` becomes the primary entrypoint

- The `file_path` argument becomes optional, defaulting to the current working directory (`.`).
- On invocation, `rei scan` executes a pipeline of phases in order: **project detection → project initialization → service health check → service auto-start → file discovery → scanning/indexing → graph update → summary + next steps**.
- Each phase reports its status to the user with a checkmark or failure indicator.

### Automatic project initialization

- If `.rei/project.toml` does not exist, `rei scan` creates it using `generate_default_config()` (this already happens today in `_resolve_project()`).
- On first run, the output should include a line like: `✓ Initialized new project: my-app (.rei/project.toml created)`
- On repeat runs, the output should say: `✓ Project: my-app`

### Service health check and auto-start

- Before file discovery, `rei scan` calls `check_neo4j_health()`.
- If healthy: `✓ Neo4j: connected` and continue.
- If unhealthy: check whether Docker is available (`shutil.which("docker")`).
  - If Docker is available: show `Neo4j is not running. Starting...`, run `docker compose up -d` using the compose file shipped with rei (resolved relative to the rei package, not the user's project), then poll `check_neo4j_health()` with a spinner until ready or a 30-second timeout.
  - If Docker is not available: show a clear error message with a single recovery command (e.g., `Install Docker and run: rei scan`), then exit with a non-zero code.
- The compose file location should be resolved from the installed rei package, not from the user's working directory. This avoids conflicts with user project compose files.

### Scan mode auto-selection

- The existing logic is mostly correct and should be preserved:
  - First scan (no `last_scanned_at`): full scan
  - Repeat scan: incremental via git history
  - `--force` flag: full rescan
- The `--changed` flag should remain for users who want to scan only staged/uncommitted changes specifically.
- If git is not available or the project is not a git repo, fall back to full scan with a brief note.

### `rei init` disposition

- Keep `rei init` as a visible command but document it as "optional — useful if you want to customize `.rei/project.toml` before your first scan."
- No code changes needed to init itself.

### `rei dev` disposition

- Rename `rei dev` to `rei service` (or `rei service start`) to clearly communicate its purpose.
- This command remains available for users who want to manually manage the Neo4j service.
- Add `rei service stop` as a counterpart (runs `docker compose down`).
- Hide or remove the `dev` name.

### `rei doctor` disposition

- Keep `rei doctor` as-is. It remains a troubleshooting tool.
- It is no longer part of the onboarding documentation or required workflow.
- Consider expanding it in the future (check Docker, Node.js, ingester) but that is out of scope for this PRD.

### Error message standards

- Every user-facing error must follow the pattern: **what happened → what it means → what to do next**.
- Examples:
  - `✗ Neo4j is not running. The graph database is required to store scan results. Starting it now...`
  - `✗ Docker is not installed. rei needs Docker to run Neo4j locally. Install Docker: https://docs.docker.com/get-docker/`
  - `✗ Node.js not found. The TypeScript parser requires Node.js >= 18. Install it: https://nodejs.org/`
- Raw exception tracebacks should never be shown to the user in normal operation. Use `--verbose` to expose them for debugging.

### Post-scan summary and next steps

- After a successful scan, always show a summary: `✓ Done in 2.1s: 45 nodes, 23 rels from 12 files`
- On first run, show next-step suggestions:
  ```
  Next steps:
    rei query "auth"        Search the graph
    rei impact src/app.ts   Analyze change impact
    rei mcp                 Start MCP server
  ```
- On repeat runs, omit the next-step suggestions unless `--verbose` is set, to keep output concise.

### Phase output format

The standard scan output for a repeat run should look like:

```
✓ Project: my-app
✓ Neo4j: connected
✓ Mode: incremental (8 files changed)
Scanning ████████████████ 8/8
✓ Graph updated: 34 nodes, 18 rels in 1.4s
```

First run:

```
✓ Initialized project: my-app (.rei/project.toml created)
✓ Neo4j: connected
✓ Mode: full scan (142 files)
Scanning ████████████████ 142/142
✓ Graph updated: 1,204 nodes, 876 rels in 12.3s

Next steps:
  rei query "auth"        Search the graph
  rei impact src/app.ts   Analyze change impact
  rei mcp                 Start MCP server
```

### Recovery behaviors

| Condition | Recovery |
|-----------|----------|
| `.rei/project.toml` missing | Auto-create with defaults |
| `.rei/project.toml` corrupt/invalid | Warn, regenerate with defaults |
| Neo4j not running + Docker available | Auto-start, poll readiness (30s timeout) |
| Neo4j not running + no Docker | Clear error + install instructions, exit 1 |
| Node.js not installed | Clear error + install link, exit 1 |
| Git not available | Fall back to full scan, brief note |
| Neo4j auto-start timeout | Error message + suggest `rei doctor` |

## Testing Decisions

### What makes a good test

Tests should verify external behavior from the user's perspective — CLI exit codes, stdout/stderr output, and side effects (files created, subprocesses invoked) — not internal function call ordering or private state. Mock at system boundaries (subprocess calls, Neo4j driver, filesystem) and assert on observable outcomes.

### Modules to test

1. **Scan command orchestration** — The new phase pipeline (project detection, service check, auto-start, mode selection, scan execution, summary). Test each phase's happy path and failure path. Prior art: `tests/test_scan.py` (already tests full/incremental/changed modes, ingester discovery, progress output via CliRunner).

2. **Service health check and auto-start** — Test the decision matrix: Neo4j healthy → skip, Neo4j unhealthy + Docker available → start + poll, Neo4j unhealthy + no Docker → error message. Test the readiness polling timeout. Prior art: `tests/test_doctor.py` (mocks `check_neo4j_health`), `tests/test_dev.py` (mocks `subprocess.run` for docker compose).

3. **Error message formatting** — Test that each failure scenario produces an actionable message (not a raw traceback). Assert on specific output strings.

4. **Service command (renamed from dev)** — Test start and stop subcommands. Prior art: `tests/test_dev.py`.

5. **Post-scan summary** — Test that first-run output includes next-step suggestions and repeat-run output omits them.

### Prior art

All existing tests use `click.testing.CliRunner` with `unittest.mock.patch` to mock subprocess, Neo4jClient, and `_find_ingester`. The same pattern should be used for new tests.

## Out of Scope

- **Remote Neo4j support**: This PRD assumes a local Docker-based Neo4j. Supporting remote/cloud Neo4j instances is a separate concern.
- **Non-TypeScript language support**: The ingester currently only handles TypeScript/JavaScript. Multi-language support is covered by a separate PRD.
- **`rei doctor` expansion**: Adding more health checks (Docker version, Node.js version, disk space) to doctor is desirable but not part of this PRD.
- **Interactive configuration wizard**: We will not add an interactive setup wizard. Auto-detection with sensible defaults is sufficient.
- **Neo4j authentication configuration**: The hardcoded Neo4j credentials (`neo4j`/`reigraph`) are not addressed here.
- **Parallel/concurrent file scanning**: Performance optimization of the scan loop itself is out of scope.
- **Windows support**: Docker and compose path resolution assumes Unix-like systems.

## Further Notes

- The compose file for Neo4j should be resolvable from the installed rei package (e.g., bundled as package data) so that `rei scan` can auto-start Neo4j regardless of the user's working directory. This may require shipping the compose file inside the wheel, similar to how the ingester is bundled.
- The 30-second readiness timeout for Neo4j auto-start should be configurable via an environment variable (e.g., `REI_SERVICE_TIMEOUT`) for CI environments where startup may be slower.
- The `--changed` flag semantics (git staged/uncommitted vs. git history since last scan) should be clearly documented. Currently `--changed` uses `git diff HEAD` while auto-incremental uses `git log --since`. These are distinct behaviors and both should be preserved.
- First-run detection (for showing next-step suggestions) can reuse the existing `client.get_project()` / `last_scanned_at` check — if `last_scanned_at` is None, it's the first run.
