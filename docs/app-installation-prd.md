# PRD: Application-style installation via Homebrew with `rei update` self-update

## Problem Statement

rei-graph currently behaves like a development checkout rather than an installed application. Users must clone the repository, run `setup.sh`, and prefix every command with `uv run rei ...` or manually activate a virtualenv. The `rei` command is not globally available — it only works from within the project directory with the correct environment active. There is no update mechanism; users must manually run `git pull`, `uv sync`, and `npm install` in the ingester directory.

This makes the tool inaccessible to non-technical users, agents that expect a globally available binary, and anyone who wants a "install once, use everywhere" experience.

## Solution

Package rei-graph as a proper CLI application distributed via Homebrew (primary) and pipx (fallback). After installation, the `rei` command is globally available from any directory. Updates are handled by a single `rei update` command that delegates to the platform's package manager.

**Key design decisions:**
- **Homebrew** via a custom tap (`plexideas/homebrew-tap`) is the primary distribution channel, supporting macOS (arm64 + x86_64) and Linux
- **pipx** is the fallback for non-Homebrew environments
- The **TS ingester** (compiled JS) is embedded inside the Python wheel so it ships with both distribution methods — no Node.js required at runtime
- **Versioning** uses git tags (`v0.1.0`, `v0.2.0`, etc.)
- **`rei update`** detects the installation method (brew or pipx) and delegates to the appropriate upgrade command
- **Neo4j/Docker** remains a user-managed prerequisite — not bundled
- **Global config/data** lives in `~/.rei-graph/`; per-project config stays in `.rei/`
- User data and config are preserved across updates

## User Stories

1. As a developer, I want to install rei-graph with `brew install plexideas/tap/rei-graph`, so that the `rei` command is immediately available globally
2. As a developer, I want to run `rei scan`, `rei query`, etc. from any directory without activating a virtualenv or prefixing with `uv run`
3. As a developer, I want to run `rei update` to update to the latest version with a single command
4. As a developer, I want `rei update` to detect whether I installed via brew or pipx and use the correct update mechanism
5. As a developer, I want `rei update` to show me what version I'm updating from and to
6. As a developer, I want `rei update` to preserve my `~/.rei-graph/` config and data across updates
7. As a developer, I want `rei update` to handle the TS ingester update automatically without requiring Node.js on my machine
8. As a non-technical user, I want clear installation instructions in the README that don't assume familiarity with Python packaging
9. As a Linux user, I want to install rei-graph via Linuxbrew with the same command as macOS users
10. As a user without Homebrew, I want to install via `pipx install rei-graph` as a documented fallback
11. As an agent (Cursor/Claude Code/Codex), I want `rei` to be a globally available binary so I can invoke it without environment setup
12. As a maintainer, I want releases to be automated: pushing a git tag triggers a CI workflow that builds the package and updates the Homebrew tap formula
13. As a maintainer, I want the TS ingester's compiled output bundled into the Python wheel so there's a single artifact to distribute
14. As a user, I want `rei --version` to show the installed version so I can verify my installation
15. As a user, I want `rei doctor` to continue working and validate that Neo4j/Docker are available regardless of how I installed the CLI
16. As a user, I want the `rei scan` command to find the bundled TS ingester automatically without requiring me to build it manually
17. As a maintainer, I want CI to run on tagged releases, build wheels, create GitHub Releases with artifacts, and update the Homebrew formula
18. As a developer, I want `setup.sh` to remain as a development bootstrap for contributors working on rei-graph itself
19. As a user, I want clear error messages if I run `rei update` and the update fails (e.g., network issues, permission errors)
20. As a user, I want `rei update` to not touch Neo4j or Docker — it should only update the CLI tool itself

## Implementation Decisions

### Modules to build/modify

1. **TS ingester bundling into the Python package**
   - Add a build step (in CI and in a build script) that compiles the TS ingester (`tsc` in `packages/ingester_ts`) and copies the output (`dist/cli.js` + dependencies) into the `rei-cli` wheel as package data
   - Modify `packages/cli/pyproject.toml` to include the bundled JS as package data
   - Modify `_find_ingester()` in `scan.py` to also check for the bundled ingester inside the installed package (e.g., via `importlib.resources` or `__file__`-relative path), falling back to the development location

2. **`rei update` command**
   - New command module in `packages/cli/src/rei_cli/commands/update.py`
   - Detects installation method:
     - Check if the `rei` binary lives inside a Homebrew prefix → run `brew upgrade rei-graph`
     - Check if installed via pipx (inspect path or `pipx list`) → run `pipx upgrade rei-graph`
     - Otherwise, print instructions for manual update
   - Runs the upgrade command, captures and displays output
   - Shows before/after version

3. **`rei --version` support**
   - Add `version` parameter to the Click group in `main.py` using `click.version_option()`
   - Read version from package metadata (`importlib.metadata.version`)

4. **Homebrew tap repository (`plexideas/homebrew-tap`)**
   - Create a new GitHub repository `plexideas/homebrew-tap`
   - Contains `Formula/rei-graph.rb` — a Homebrew formula that:
     - Depends on `python@3.12` (Homebrew-managed Python)
     - Downloads the source tarball from the GitHub Release
     - Creates a virtualenv, installs the wheel, and symlinks the `rei` entrypoint
     - Does NOT depend on Node.js (TS ingester is pre-compiled and bundled)

5. **GitHub Actions release workflow**
   - New workflow `.github/workflows/release.yml` triggered on tag push (`v*`)
   - Steps:
     1. Build TS ingester (`npm ci && npm run build` in `packages/ingester_ts`)
     2. Copy compiled ingester into CLI package data
     3. Build Python wheels/sdist (`uv build`)
     4. Create GitHub Release with the built artifacts
     5. Update the Homebrew tap formula (SHA256, version, URL) via a repository dispatch or direct commit to `plexideas/homebrew-tap`

6. **CLI package metadata updates**
   - `packages/cli/pyproject.toml`: add package data for bundled ingester, ensure version is read from a single source
   - Root `pyproject.toml`: version bump strategy (single source of truth)

7. **Documentation updates**
   - `README.md`: rewrite installation section with Homebrew as primary, pipx as fallback, `setup.sh` for contributors
   - `docs/install.md`: detailed installation, verification, updating, and troubleshooting guide
   - Platform-specific notes (macOS arm64/x86_64, Linux)

### Technical clarifications

- The `rei` entrypoint (`rei_cli.main:cli`) already exists in `packages/cli/pyproject.toml` — no entrypoint wiring changes needed
- `_find_ingester()` currently only looks for `packages/ingester_ts/dist/cli.js` relative to CWD or the source file — must be extended to find bundled ingester
- `rei update` does NOT restart Neo4j or touch Docker
- `~/.rei-graph/` is used for global state (snapshots already default to `~/.rei-graph/snapshots`)
- Per-project `.rei/project.toml` is untouched by updates

### Architectural decisions

- **Single artifact**: the Python wheel contains everything (Python code + compiled JS ingester). No separate downloads.
- **No runtime Node.js**: end users never need Node.js installed. The TS ingester is pre-compiled to JS during the build/release process.
- **Detection-based update**: `rei update` inspects the `rei` binary path to determine install method rather than storing metadata about how it was installed.
- **Homebrew formula uses `python@3.12`**: Homebrew's managed Python, avoiding system Python issues.

## Testing Decisions

Good tests for this feature test external behavior (command output, exit codes, side effects) rather than internal implementation details.

### Modules to test

1. **`rei update` command** (`tests/test_update.py`)
   - Test detection of brew-installed path → calls `brew upgrade`
   - Test detection of pipx-installed path → calls `pipx upgrade`
   - Test unknown install method → prints manual instructions
   - Test subprocess failure handling (non-zero exit code)
   - Mock `subprocess.run` and `shutil.which` — same pattern as existing `test_scan.py`, `test_dev.py`

2. **Ingester bundling / discovery** (`tests/test_scan.py` — extend existing)
   - Test `_find_ingester()` finds bundled ingester when installed as package
   - Test `_find_ingester()` falls back to development path

3. **Version output**
   - Test `rei --version` outputs version string

### Prior art
- `tests/test_dev.py`: mocks `subprocess.run` for `docker compose` — same pattern for `brew upgrade` / `pipx upgrade`
- `tests/test_scan.py`: mocks `_find_ingester`, `subprocess`, and `Neo4jClient` — extends naturally for bundled ingester discovery
- `tests/test_mcp_command.py`: tests CLI command that wraps a subprocess

## Out of Scope

- **Publishing to PyPI** — the package is installed from GitHub releases or the tap, not from PyPI (can be added later)
- **Publishing to homebrew-core** — custom tap only for now
- **Windows support** — Homebrew is macOS/Linux; Windows users can use pipx but it's not a primary target
- **Auto-update checks** — `rei update` is manual; no background version checking or update prompts
- **Neo4j bundling** — Docker remains a prerequisite managed by the user
- **Migration scripts** — no data migrations needed for this change; schema is unchanged
- **Multi-version support** — only latest version is supported at a time

## Further Notes

- The existing `setup.sh` remains as the contributor/development bootstrap. It is NOT the end-user installation path.
- The `uv run rei ...` invocation style continues to work for development but is not documented as the primary usage path.
- Future: once on PyPI, `pipx install rei-graph` becomes even simpler. The Homebrew formula could also be simplified to `pip install` from PyPI inside its virtualenv.
- The release workflow should be designed so that cutting a release is: `git tag v0.x.0 && git push --tags` — everything else is automated.
