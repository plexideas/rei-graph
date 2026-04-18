# PRD: Scan Progress & Visibility

## Problem Statement

When a developer runs `dgk scan <directory>` on a large TypeScript/TSX project, the process emits a single line ("Scanning N file(s)...") and then goes silent for an indefinite amount of time. Users have no way to tell whether the scan is progressing, stuck, or silently failing. This causes confusion, mistrust, and premature interruptions of legitimate long-running scans.

The same problem affects `dgk scan --changed` (incremental scans) and single-file scans, though to a lesser degree.

---

## Solution

Replace the static "Scanning…" message with a Rich-powered animated progress bar that is always visible without requiring any flag. Add a `--verbose` flag to surface per-file node/relationship counts on top of the progress bar. Collect parse warnings throughout the scan and surface them in the final summary rather than emitting them inline. Show a spinner for single-file scans. Degrade gracefully to plain text in non-TTY environments (CI, pipes). Extend the same UX to the `--changed` incremental path.

---

## User Stories

1. As a developer scanning a large TypeScript monorepo, I want to see an animated progress bar so that I know the tool is actively working and hasn't frozen.
2. As a developer scanning a project, I want to see the percentage and file count (e.g., `42%  21/50 files`) so that I can estimate how long the scan will take.
3. As a developer, I want progress to appear by default without any extra flags so that I don't need to remember a special option to get basic visibility.
4. As a developer running `dgk scan` in a CI pipeline, I want plain-text status lines (no ANSI animation) when stdout is not a TTY so that CI logs are readable and artifact-friendly.
5. As a developer who wants more detail, I want to pass `--verbose` to see the filename and node/relationship counts for each file as it is processed.
6. As a developer scanning a single file, I want to see a spinner so I know the tool is working, even for fast operations.
7. As a developer running `dgk scan --changed`, I want the same progress UX as a full directory scan so that the experience is consistent.
8. As a developer whose project has some unparseable files, I want parse warnings collected and shown once at the end of the scan rather than inline, so that the progress bar is not disrupted.
9. As a developer, I want the final summary to include elapsed time (e.g., `Done in 4.2s: 80 nodes, 120 rels from 12 files`) so I can benchmark scan performance over time.
10. As a developer, I want a warning count in the summary (e.g., `1 file failed to parse`) so I know there were issues without hunting through scrollback.
11. As a developer integrating through MCP, I want `scan.project`, `scan.file`, and `scan.changed_files` tools to return the same final summary data they always have, unaffected by the progress UI changes.
12. As a developer writing automation around `dgk scan`, I want `--verbose` output to include structured detail (file path, nodes, rels) on separate lines so that output can be grep'd or piped.
13. As a developer, I want the progress bar to disappear or resolve cleanly to the final summary line when the scan completes, so that the terminal is not left cluttered.
14. As a developer, I want the scan command to still exit with a non-zero code on fatal errors, regardless of the new progress UI.
15. As a developer scanning an empty or excluded directory, I want a clear message ("No TS/TSX files found to scan.") rather than a confusing empty progress bar.

---

## Implementation Decisions

### Modules to build / modify

**New: `dgk_cli/progress.py` — `ScanProgress` (deep module)**

A standalone, testable class that encapsulates all progress-reporting logic. The rest of the codebase calls only this class; all Rich-specific code lives here.

- Constructor: `ScanProgress(total: int, verbose: bool = False, console: Console | None = None)`. Accepts an injectable `Console` so tests can capture output without a real TTY.
- `start()` — Begin the progress bar or spinner.
- `advance(file: str, nodes: int, rels: int)` — Increment the bar and, in verbose mode, print a detail line.
- `add_warning(msg: str)` — Collect a warning without printing it.
- `finish(elapsed: float, total_nodes: int, total_rels: int)` — Stop the bar, print the enriched summary line, then print any collected warnings.
- Single-file variant: use a Rich `Spinner` instead of a `Progress` bar.
- TTY detection: delegated to Rich's `Console` (no manual ANSI detection needed). Non-TTY mode automatically produces plain-text output.

**Modified: `dgk_cli/commands/scan.py`**

- Add `--verbose / -v` flag to the `scan` Click command.
- Instantiate `ScanProgress` at the start of each scan path (directory, `--changed`, single-file).
- Replace inline `click.echo` warning calls with `ScanProgress.add_warning()`.
- Replace final summary `click.echo` with `ScanProgress.finish()`.
- Pass `verbose` through to `ScanProgress`.

### New dependency

- `rich` added to `packages/cli/pyproject.toml` dependencies. Rich handles TTY detection, ANSI rendering, and plain-text fallback automatically.

### Interface contracts

- The `ScanProgress` interface does not expose Rich types in its public API (only stdlib types: `str`, `int`, `float`, `bool`). This means tests need no Rich knowledge.
- `scan.py` does not directly import Rich; it only imports `ScanProgress`.
- MCP tool implementations (`dgk_mcp/server.py`) are not changed; they call the same internal scan functions and get back the same `ScanResult` data.

### Non-TTY behaviour

When `Console` detects a non-TTY environment (no `force_terminal`), Rich automatically emits plain-text lines instead of animated output. No separate code path is needed.

### Backward compatibility

- No existing CLI flags are removed or renamed.
- Default output (no flags) becomes more informative but remains human-readable.
- Machine-parseable output is not guaranteed by this feature (out of scope).

---

## Testing Decisions

**What makes a good test here:** test the _output visible to the user_, not the internal Rich widgets. Tests should assert what text appears in the captured output under specific conditions (normal mode, verbose mode, non-TTY, warnings present, errors present). Do not assert on Rich markup tags, bar widths, or animation frames.

**Prior art:** `tests/test_scan.py` already mocks `subprocess`, `Neo4jClient`, and uses `click.testing.CliRunner`. New tests should follow this exact pattern.

### Modules to test

**1. `dgk_cli/progress.py` — unit tests (new `tests/test_progress.py`)**
- `ScanProgress` in normal mode: `finish()` output contains elapsed time, node count, rel count, file count.
- `ScanProgress` in verbose mode: `advance()` output contains filename, node count, rel count.
- `ScanProgress` with warnings: `finish()` output contains the collected warning messages.
- `ScanProgress` with no files: `finish()` handles zero totals cleanly.
- Non-TTY mode: output contains no ANSI escape sequences (inject a `Console` with `force_terminal=False`).

**2. `dgk_cli/commands/scan.py` — CLI integration tests (extend `tests/test_scan.py`)**
- Directory scan: output contains a summary with elapsed time.
- Directory scan `--verbose`: output contains per-file lines.
- `--changed` scan: output contains a summary with elapsed time.
- Single-file scan: output is non-empty and contains summary.
- Warnings are deferred: no inline "Warning:" lines appear in non-verbose output; they appear in the summary section.
- Non-TTY: no ANSI in output (CliRunner with `color=False`).

---

## Out of Scope

- Streaming or live progress over MCP/stdio — MCP tools return final results only.
- JSON or machine-readable output mode for `dgk scan`.
- Progress reporting for `dgk query`, `dgk impact`, or other commands.
- Persisting scan timing metrics to the graph or to `.dgk/`.
- A `--quiet` flag to suppress the progress bar entirely.
- Windows ANSI compatibility (Rich handles this, but it is not explicitly tested).
- Parallel/concurrent file scanning to speed up the operation itself.

---

## Further Notes

- Rich is the right library choice here: it handles TTY detection, ANSI reset on completion, and non-TTY plain-text fallback all automatically, eliminating fragile manual detection code.
- The `ScanProgress` deep-module pattern ensures that if the progress library is swapped in the future, only `progress.py` changes — `scan.py` and all tests are unaffected.
- The injectable `Console` in `ScanProgress` is the key testability enabler: tests construct `Console(file=StringIO(), force_terminal=False)` and read the StringIO to assert output without any mock patching of Rich internals.
- `click.testing.CliRunner` passes `color=False` by default, which causes Rich to omit ANSI sequences automatically — no extra setup needed in existing-style tests.
