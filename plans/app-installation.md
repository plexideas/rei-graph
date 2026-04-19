# Plan: Application-style Installation via Homebrew

> Source PRD: docs/app-installation-prd.md

## Architectural decisions

Durable decisions that apply across all phases:

- **Distribution**: Homebrew tap (`plexideas/homebrew-tap`) primary, pipx fallback
- **Single artifact**: Python wheel bundles compiled TS ingester JS — no runtime Node.js needed for end users
- **Versioning**: Git tags (`v0.1.0`), single source of truth in root `pyproject.toml`
- **Global paths**: `~/.rei-graph/` for global state, `.rei/` for per-project config (unchanged)
- **Entrypoint**: `rei = "rei_cli.main:cli"` (unchanged)
- **Build system**: Hatchling, `uv build` for wheels/sdist
- **CI**: GitHub Actions release workflow on tag push (`v*`)
- **Homebrew formula**: depends on `python@3.12`, downloads source tarball from GitHub Release, creates virtualenv, symlinks `rei`
- **Detection-based update**: `rei update` inspects the `rei` binary path to determine install method rather than storing metadata

---

## Phase 1: `rei --version` + version infrastructure

**User stories**: 14

### What to build

Add version output to the CLI. The `rei --version` flag reads the installed package version via `importlib.metadata` and prints it. This establishes a single source of truth for versioning that the update command and release workflow will rely on in later phases.

### Acceptance criteria

- [ ] `rei --version` prints the current version (e.g., `rei, version 0.1.0`)
- [ ] Version is read from package metadata at runtime (not hardcoded in `main.py`)
- [ ] Test verifies `rei --version` outputs a version string and exits 0

---

## Phase 2: Bundle TS ingester into the Python wheel

**User stories**: 7, 13, 16

### What to build

Add a build step that compiles the TS ingester (`tsc` in `packages/ingester_ts`) and copies the compiled JS output into the `rei-cli` package as package data. Update `packages/cli/pyproject.toml` to include the bundled JS files in the wheel. Extend `_find_ingester()` in `scan.py` to first check for the bundled ingester inside the installed package (via `importlib.resources` or `__file__`-relative path), then fall back to the development location. After this phase, a wheel built from the repo contains everything needed to scan code without Node.js at runtime.

### Acceptance criteria

- [ ] A build script compiles the TS ingester and copies `dist/cli.js` (+ dependencies) into the CLI package data directory
- [ ] `packages/cli/pyproject.toml` includes the bundled ingester as package data
- [ ] `_find_ingester()` finds the bundled ingester when installed as a package
- [ ] `_find_ingester()` still falls back to the development path (`packages/ingester_ts/dist/cli.js`) when running from source
- [ ] Tests verify both discovery paths (bundled and development)

---

## Phase 3: `rei update` command

**User stories**: 3, 4, 5, 6, 19, 20

### What to build

A new `rei update` command that detects how rei-graph was installed and delegates to the appropriate package manager. If the `rei` binary lives inside a Homebrew prefix, it runs `brew upgrade rei-graph`. If installed via pipx, it runs `pipx upgrade rei-graph`. Otherwise, it prints manual update instructions. The command shows the current version before updating and the new version after, handles subprocess failures with clear error messages, and does not touch Neo4j or Docker.

### Acceptance criteria

- [ ] `rei update` detects Homebrew installation and runs `brew upgrade rei-graph`
- [ ] `rei update` detects pipx installation and runs `pipx upgrade rei-graph`
- [ ] `rei update` prints manual instructions for unknown install methods
- [ ] Before/after version is displayed during update
- [ ] Subprocess failures produce clear error messages with exit code
- [ ] `rei update` does not restart Neo4j or touch Docker
- [ ] Tests mock subprocess and path detection for all three install-method branches

---

## Phase 4: GitHub Actions release workflow

**User stories**: 12, 17

### What to build

A new `.github/workflows/release.yml` triggered on tag pushes matching `v*`. The workflow builds the TS ingester (`npm ci && npm run build`), copies the compiled output into the CLI package data directory, builds the Python wheel and sdist (`uv build`), creates a GitHub Release with the built artifacts attached, and updates the Homebrew tap formula in `plexideas/homebrew-tap` (SHA256, version, URL) via repository dispatch or direct commit.

### Acceptance criteria

- [ ] Pushing a `v*` tag triggers the release workflow
- [ ] Workflow builds TS ingester and bundles it into the CLI package
- [ ] Workflow builds Python wheel and sdist
- [ ] GitHub Release is created with wheel and sdist attached
- [ ] Homebrew tap formula is updated with new version, URL, and SHA256
- [ ] Workflow fails cleanly if any build step fails

---

## Phase 5: Homebrew tap formula

**User stories**: 1, 2, 9, 11

### What to build

Create the `plexideas/homebrew-tap` GitHub repository containing `Formula/rei-graph.rb`. The formula depends on Homebrew's `python@3.12`, downloads the source tarball from the GitHub Release, creates a virtualenv, installs the wheel, and symlinks the `rei` entrypoint into the Homebrew bin directory. No Node.js dependency — the TS ingester is pre-compiled and bundled in the wheel. After this phase, `brew install plexideas/tap/rei-graph` gives users a globally available `rei` command.

### Acceptance criteria

- [x] `brew install plexideas/tap/rei-graph` installs successfully on macOS (arm64 and x86_64)
- [x] `rei` command is globally available after installation
- [x] `rei --version` shows the correct version
- [x] `rei doctor` works from any directory
- [x] `brew upgrade rei-graph` updates to the latest version
- [x] No Node.js runtime dependency required
- [x] Works on Linux via Linuxbrew

---

## Phase 6: Documentation updates

**User stories**: 8, 10, 15, 18

### What to build

Rewrite the installation section of `README.md` with Homebrew as the primary method, pipx as a documented fallback, and `setup.sh` clearly labeled as the contributor/development bootstrap. Update `docs/install.md` with detailed installation instructions, verification steps (`rei --version`, `rei doctor`), updating (`rei update`), and troubleshooting. Include platform-specific notes for macOS (arm64/x86_64) and Linux.

### Acceptance criteria

- [ ] `README.md` installation section shows Homebrew as primary, pipx as fallback
- [ ] `setup.sh` is documented as the contributor workflow, not the end-user path
- [ ] `docs/install.md` covers: install, verify, update, troubleshoot
- [ ] Platform-specific notes for macOS and Linux are included
- [ ] No references to `uv run rei` as the primary usage pattern in user-facing docs
