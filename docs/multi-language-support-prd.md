# Multi-Language Support PRD

## Problem Statement

rei-graph currently only works with TypeScript/JavaScript projects. The entire scan pipeline — from file collection to parsing to ingestion — is hardwired to TypeScript via `ingester_ts` (a ts-morph-based Node.js CLI), a hardcoded extension set (`.ts`, `.tsx`, `.js`, `.jsx`), and a single-ingester dispatch path. This limits the tool's usefulness to a fraction of real-world codebases.

Developers and AI agents working across polyglot repositories (e.g., Go backend + TypeScript frontend + Python tooling) cannot use rei-graph to understand, navigate, or plan changes across their full stack. The `language` config field exists but is never read. There is no abstraction for language-specific parsing, no plugin interface, and no way to add a new language without modifying core scan logic.

## Solution

Refactor rei-graph into a **language-agnostic framework** where language support is modular and extensible. Each language is supported by an independent **ingester** — a standalone executable that conforms to a versioned subprocess protocol (JSON over stdin/stdout). The scan pipeline gains a **component detector** that identifies sub-projects within a repository by manifest files and file extension density, and an **ingester dispatcher** that routes each component to the correct ingester binary.

The existing TypeScript ingester is preserved and wrapped to conform to the new protocol. A new Go ingester (tree-sitter-based) validates the framework across a compiled-language ecosystem. Adding a future language (Python, Java, Swift, C++, etc.) requires only creating a new ingester binary — no core changes.

## User Stories

1. As a developer with a Go backend and TypeScript frontend in one repo, I want `rei scan` to detect and parse both components, so that the graph captures my full codebase.
2. As a developer, I want `rei scan` to auto-detect the languages in my project without manual configuration, so that I get zero-config setup.
3. As a developer, I want to override or refine auto-detected components in `project.toml`, so that I can exclude vendor directories, split ambiguous components, or assign custom ingesters.
4. As a developer working on a Go project, I want the scanner to detect `go.mod` and route my files to a Go-specific parser, so that functions, structs, interfaces, and packages are captured in the graph.
5. As a developer, I want TypeScript scanning to continue working exactly as before after the refactor, so that I don't lose existing functionality.
6. As an AI agent using MCP tools, I want `scan.project` to work on any supported language without changes to my tool invocations, so that multi-language support is transparent.
7. As a developer, I want each detected component to be a first-class node in the graph (`Component -[:CONTAINS]-> Module`), so that I can reason about project structure at a higher level.
8. As a developer, I want incremental scanning to be tracked per-component, so that rescanning one component doesn't force a full rescan of others.
9. As a developer, I want to see which components were detected and their languages when running `rei scan --verbose`, so that I can verify detection is correct.
10. As a contributor, I want clear documentation explaining how to write a new ingester for an unsupported language, so that I can add language support without understanding the full codebase.
11. As a developer, I want a standardized universal set of node labels (Function, Class, Module, Interface, etc.) across all languages, so that queries and MCP tools work uniformly regardless of language.
12. As a developer scanning a monorepo, I want the system to handle multiple components with different languages in nested directories, so that complex project structures are supported.
13. As a developer, I want the ingester protocol to be versioned, so that future protocol changes don't silently break existing ingesters.
14. As a developer, I want the scan command to gracefully handle missing ingesters (e.g., no Go ingester installed) by warning and skipping that component, so that partial scans still produce useful results.
15. As a developer, I want `rei init` to detect languages and pre-populate `project.toml` with the discovered components, so that my config reflects reality from the start.
16. As a developer, I want node IDs to remain deterministic and include the component context, so that project isolation and idempotent upserts continue to work.
17. As an AI agent, I want `graph.search_entities` to optionally filter by language or component, so that I can scope queries to relevant parts of a polyglot repo.
18. As a developer, I want the scan progress display to show per-component progress, so that I can see which component is being processed.
19. As a developer, I want `rei doctor` to report which ingesters are available on PATH, so that I can verify my setup supports the languages in my project.
20. As a developer, I want the system to handle mixed-language repositories where some files don't match any known language, by silently skipping them rather than failing.
21. As a developer, I want to be able to run `rei scan --component <name>` to rescan a specific component without touching others.
22. As a developer, I want `project://summary` MCP resource to include a breakdown of components and their languages.
23. As a contributor, I want ingester binaries to follow the naming convention `rei-parse-{lang}`, so that discovery is automatic and predictable.
24. As a developer, I want the system to detect components using strong signals (manifest files like `go.mod`, `package.json`, `pyproject.toml`, `pom.xml`, `Package.swift`, `CMakeLists.txt`) complemented by weaker signals (extension density, directory structure).
25. As a developer, I want error output from a failing ingester to be captured and reported clearly, so that I can debug parser issues.

## Implementation Decisions

### Ingester Protocol (Versioned Subprocess Contract)

Each ingester is a standalone executable that conforms to a versioned JSON protocol:

- **Input (stdin):** A JSON object describing the component to parse:
  - `protocol_version` — integer, currently `1`
  - `component_root` — absolute path to the component root directory
  - `files` — list of absolute file paths to parse
  - `project_prefix` — hash string for node ID namespacing
- **Output (stdout):** A JSON object containing:
  - `protocol_version` — echoed back
  - `results` — list of `ScanResult` objects (same schema: `file`, `nodes[]`, `relationships[]`)
  - `errors` — list of per-file error objects (`file`, `message`) for files that failed to parse
- **Exit code:** 0 on success (even if some files had parse errors), non-zero for fatal failures.
- **Stderr:** Free-form diagnostic output, captured and displayed in verbose mode.

### Ingester Discovery

Ingesters are discovered by **convention**: the scan command looks for `rei-parse-{lang}` on `$PATH`. For example, `rei-parse-typescript`, `rei-parse-go`. Config can override the binary path for a given language.

### Component Detector

A new module that walks the project tree and identifies components:

- **Strong signals:** Presence of language-specific manifest/build files (`go.mod` → Go, `package.json` → TypeScript/JavaScript, `pyproject.toml`/`setup.py` → Python, `pom.xml`/`build.gradle` → Java, `Package.swift` → Swift, `CMakeLists.txt`/`Makefile` → C++).
- **Weak signals:** File extension density within directories, directory naming conventions.
- **Output:** A structured list of detected components, each with: `path` (relative root), `language`, `confidence` (high/medium/low), `detected_signals` (list of reasons).
- **Config override layer:** `project.toml` can define explicit components, exclude directories, force languages, or assign custom ingester binaries.
- Components become first-class `Component` nodes in Neo4j, linked to their `Module` nodes via `CONTAINS` relationships.

### Language Registry

A central registry (Python dict/config) mapping language identifiers to:

- File extensions (e.g., `go` → `[".go"]`)
- Manifest files (e.g., `go` → `["go.mod"]`)
- Ingester binary name (e.g., `go` → `rei-parse-go`)
- Default include/exclude patterns

This registry is the single source of truth for language metadata. Adding a new language starts here.

### Universal Node Labels

All languages produce nodes with a standardized label set. The universal labels are:

| Label | Description | Examples across languages |
|-------|-------------|--------------------------|
| `Module` | A source file | `.ts`, `.go`, `.py`, `.java` file |
| `Function` | A function or method | TS function, Go func, Python def, Java method |
| `Class` | A class definition | TS/Python/Java class, Go struct (with methods) |
| `Interface` | An interface or protocol | TS interface, Go interface, Java interface, Swift protocol |
| `Type` | A type definition | TS type alias, Go type, Python TypedDict |
| `Component` | A UI component | React component, SwiftUI View |
| `Package` | An external dependency | npm package, Go module, pip package, Maven artifact |
| `Enum` | An enumeration | TS enum, Go const iota block, Java enum, Python Enum |
| `Constant` | A named constant | TS const, Go const, Python module-level constant |

Language-specific labels (e.g., `Hook` for React) remain valid but are considered specializations of the universal set. Ingesters may emit them when appropriate.

### Scan Pipeline Refactoring

The current `scan.py` is refactored from a TS-specific pipeline to a multi-language dispatch pipeline:

1. Resolve project (unchanged — `.rei/project.toml` auto-creation)
2. **Detect components** — run the component detector on the project root
3. **For each component:**
   a. Find the ingester binary (`rei-parse-{lang}` on PATH, or config override)
   b. Collect files matching the language's extensions, respecting include/exclude patterns
   c. Check incremental scan state (`last_scanned_at` per component)
   d. Invoke the ingester via subprocess with component descriptor on stdin
   e. Parse stdout JSON into `ScanResult` objects
   f. Upsert component node, module nodes, and relationships into Neo4j
4. Update `last_scanned_at` per component
5. Report summary (files scanned per component, warnings, errors)

### Incremental Scanning Per-Component

Each `Component` node in Neo4j stores its own `last_scanned_at` timestamp. When `rei scan` is run without `--force`, it checks each component independently and only rescans components with changes since their last scan (using `git log --since` scoped to the component's directory).

### Config Changes

`project.toml` evolves to support multi-component configuration:

```toml
[project]
name = "my-app"
root = "."

[scan]
exclude = ["vendor", "build", "dist", "node_modules"]

# Optional explicit component definitions (override auto-detection)
[[scan.components]]
path = "backend"
language = "go"

[[scan.components]]
path = "frontend"
language = "typescript"
```

If no `[[scan.components]]` are defined, auto-detection runs. If components are defined, they take precedence.

### TS Ingester Wrapping

The existing `ingester_ts` is wrapped to conform to the new protocol:

- A thin entry point reads stdin JSON (component descriptor), extracts the file list, calls the existing `parseFile()` for each file, and writes the aggregated results to stdout.
- The binary is renamed/aliased to `rei-parse-typescript`.
- Existing ts-morph parsing logic is preserved unchanged.

### Go Ingester (New Package)

A new `packages/ingester_go/` package implements a Go ingester using tree-sitter:

- Written in Python using `tree-sitter` and `tree-sitter-go` bindings.
- Extracts: packages, functions, methods, structs, interfaces, type definitions, imports, dependencies (from `go.mod`).
- Produces the same `ScanResult` JSON shape as the TS ingester.
- Installed as `rei-parse-go` entry point.

### CLI Changes

- `rei scan`: Refactored to multi-language dispatch as described above. New flags: `--component <name>` to scan a single component.
- `rei init`: Enhanced to run component detection and pre-populate `project.toml`.
- `rei doctor`: Reports which `rei-parse-*` binaries are available on PATH.
- `rei scan --verbose`: Shows detected components, languages, and per-component progress.

### MCP Server Changes

- `scan.project` / `scan.changed_files`: Continue to shell out to `rei scan`, which now handles multi-language internally. No MCP protocol changes needed.
- `graph.search_entities`: Add optional `language` and `component` filter parameters.
- `project://summary` resource: Include component breakdown (language, file count, last scanned).

### Schema Changes

- `GraphNode` gains an optional `language` property (string, e.g., `"go"`, `"typescript"`).
- `ScanResult` remains unchanged (ingesters produce the same shape).
- New `Component` node label in Neo4j with properties: `id`, `name`, `path`, `language`, `last_scanned_at`, `project_id`.
- New `CONTAINS` relationship: `Component -[:CONTAINS]-> Module`.

## Testing Decisions

Good tests verify external behavior through public interfaces, not implementation details. Tests should be resilient to refactoring — they break only when behavior changes, not when internals are reorganized.

### Modules Under Test

**1. Language Registry** — Unit tests verifying registration, lookup by extension, lookup by manifest file, and extensibility (adding a new language entry).

**2. Component Detector** — Unit tests with mock filesystem trees. Test cases: single-language project, multi-language monorepo, nested components, ambiguous structures, config overrides, exclusion patterns. Verify the structured output (path, language, confidence, signals).

**3. Ingester Protocol** — Unit tests for serialization/deserialization of the protocol messages. Verify protocol version validation, error handling for malformed input/output.

**4. Ingester Dispatcher** — Unit tests mocking subprocess calls. Verify: correct binary is invoked per language, stdin contains well-formed component descriptor, stdout is parsed into ScanResult objects, missing ingester produces a warning (not a crash), ingester stderr is captured, non-zero exit codes are handled.

**5. TS Ingester (Wrapped)** — Integration tests confirming the wrapped ingester reads stdin protocol, invokes existing parsing, and produces valid stdout protocol. Regression tests ensuring existing TS parsing behavior is preserved.

**6. Go Ingester** — Integration tests with real Go source files (small fixtures). Verify extraction of functions, structs, interfaces, methods, imports, and dependencies. Verify ScanResult JSON shape matches schema.

**7. Scan Command (End-to-End)** — CLI integration tests using `CliRunner`. Mock ingesters (or use fixture repos). Test: multi-component scan, incremental per-component scan, `--component` flag, `--force` flag, graceful handling of missing ingesters.

### Prior Art

Existing tests in `tests/test_scan.py` and `tests/test_neo4j_client.py` establish the testing patterns: Click `CliRunner` for CLI tests, mocked `Neo4jClient` and `subprocess` for isolation, hardcoded JSON fixtures for ingester output.

## Out of Scope

- **Cross-language relationship detection** (e.g., matching Go API endpoints to TypeScript fetch calls). This requires a post-scan correlation pass and will be addressed in a follow-up PRD.
- **Runtime/dynamic analysis** (call graphs, runtime type information).
- **Implementation of ingesters for Java, Swift, C++, or Python.** The framework supports them, but only TypeScript and Go ingesters are built in this phase.
- **Language Server Protocol (LSP) integration** for richer semantic analysis.
- **Refactoring the TS ingester to tree-sitter.** The existing ts-morph implementation is preserved and wrapped.
- **Changes to the memory, DAG, or snapshot subsystems.** These are already language-agnostic.
- **GUI or visual component map.**

## Further Notes

- The ingester protocol is designed for forward compatibility. The `protocol_version` field allows future evolution (e.g., adding call-graph extraction) without breaking existing ingesters. Ingesters that don't understand a newer protocol version should exit with an error.
- Tree-sitter is the recommended technology for new ingesters because it provides grammar bindings for 100+ languages with a consistent API. However, the subprocess protocol is runtime-agnostic — an ingester can be written in any language using any parser.
- The component model aligns with how real-world polyglot repos are structured: a monorepo typically has distinct sub-projects (each with their own manifest) that should be understood as first-class entities.
- The `rei-parse-{lang}` naming convention enables a simple, discoverable plugin ecosystem. Third-party ingesters can be installed via package managers and automatically picked up.
