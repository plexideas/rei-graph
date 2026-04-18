# Plan: Scan Progress & Visibility

> Source PRD: `docs/scan-progress-prd.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **New module**: `dgk_cli/progress.py` — `ScanProgress` deep module; all Rich-specific code lives here
- **New dependency**: `rich` added to `packages/cli/pyproject.toml`
- **New CLI flag**: `--verbose / -v` on the `scan` Click command
- **ScanProgress public API**: `__init__(total, verbose, console)`, `start()`, `advance(file, nodes, rels)`, `add_warning(msg)`, `finish(elapsed, total_nodes, total_rels)` — only stdlib types exposed
- **Testability**: injectable `Console(file=StringIO(), force_terminal=False)` for captured output assertions; no Rich internals in test assertions
- **Non-TTY**: Rich's `Console` handles plain-text fallback automatically; no manual ANSI detection
- **MCP unchanged**: `dgk_mcp/server.py` scan tools remain fire-and-forget subprocess calls returning final stdout

---

## Phase 1: Directory scan progress bar + enriched summary

**User stories**: 1, 2, 3, 9, 13

### What to build

Add `rich` as a dependency. Create the `ScanProgress` class with multi-file mode: an animated progress bar showing percentage and file count that advances as each file is scanned. Wire it into the directory scan path in `scan.py`, replacing the static "Scanning N file(s)…" and "Done: …" messages. The enriched summary line includes elapsed time, node count, relationship count, and file count. The progress bar resolves cleanly to the summary line on completion. Unit-test `ScanProgress` normal mode with an injected `Console` and integration-test the directory scan CLI output for the new summary format.

### Acceptance criteria

- [ ] `rich` is listed in `packages/cli/pyproject.toml` dependencies
- [ ] `ScanProgress` class exists with `start()`, `advance()`, `finish()` methods accepting only stdlib types
- [ ] `dgk scan <directory>` shows an animated progress bar with percentage and file count during scan
- [ ] Final summary line contains elapsed time, node count, relationship count, and file count (e.g. `Done in 4.2s: 80 nodes, 120 rels from 12 files`)
- [ ] Progress bar disappears cleanly when scan completes, leaving only the summary
- [ ] Unit tests for `ScanProgress` normal-mode `finish()` output pass
- [ ] Integration test for directory scan output contains elapsed time in summary
- [ ] All existing `test_scan.py` tests continue to pass

---

## Phase 2: Verbose mode + warning collection

**User stories**: 5, 8, 10, 12

### What to build

Add `--verbose / -v` flag to the `scan` Click command. In verbose mode, each call to `advance()` prints a per-file detail line with file path, node count, and relationship count on its own line, suitable for grep/pipe. Add `add_warning()` to `ScanProgress` to collect parse warnings without printing them inline. Replace any existing inline warning echoes in `scan.py` with `add_warning()`. `finish()` appends collected warnings after the summary line, including a warning count. Unit-test verbose output and warning collection; integration-test that warnings appear in summary section and not inline.

### Acceptance criteria

- [ ] `dgk scan <directory> --verbose` prints a detail line per file (file path, nodes, rels)
- [ ] Verbose detail lines are structured (one per line, greppable)
- [ ] Parse warnings are collected during scan and not printed inline
- [ ] `finish()` prints warning count and warning messages after the summary line
- [ ] Unit tests for verbose-mode `advance()` output pass
- [ ] Unit tests for warning collection and `finish()` output pass
- [ ] Integration test confirms no inline warnings in non-verbose directory scan output
- [ ] `--verbose` flag is documented in `--help` output

---

## Phase 3: Single-file spinner, `--changed` path, and edge cases

**User stories**: 4, 6, 7, 11, 14, 15

### What to build

Use a Rich `Spinner` instead of a progress bar for single-file scans. Extend `ScanProgress` integration to the `--changed` incremental scan path so it gets the same progress bar, verbose mode, and warning collection as directory scans. Handle the empty-directory edge case with a clear "No TS/TSX files found to scan." message instead of an empty progress bar. Verify that non-TTY output (CI, pipes) contains no ANSI escape sequences. Confirm MCP tools (`scan.project`, `scan.file`, `scan.changed_files`) continue to return the same data unaffected by progress UI. Verify non-zero exit code on fatal errors is preserved.

### Acceptance criteria

- [ ] `dgk scan <single-file>` shows a spinner during processing
- [ ] `dgk scan <directory> --changed` shows progress bar, verbose detail, and enriched summary identical to full scan
- [ ] `dgk scan <empty-or-excluded-directory>` prints "No TS/TSX files found to scan." and exits cleanly
- [ ] Output contains no ANSI escape sequences when run in non-TTY mode (verified via `Console(force_terminal=False)`)
- [ ] MCP scan tools return unchanged response shape
- [ ] Fatal errors still produce non-zero exit code
- [ ] Unit tests for single-file spinner mode pass
- [ ] Integration tests for `--changed` scan output pass
- [ ] Integration test for empty directory message passes
