# Installation

Get rei-graph running in minutes. The `rei` command is a globally available CLI — no virtualenv activation or `uv run` prefix needed after installation.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |

Node.js is **not** required for end users — the TypeScript scanner is pre-compiled and bundled inside the package.

---

## Install

### macOS — Homebrew (recommended)

Works on both Apple Silicon (arm64) and Intel (x86_64).

```bash
brew install plexideas/tap/rei-graph
```

### Linux — Linuxbrew (recommended)

```bash
brew install plexideas/tap/rei-graph
```

If Homebrew is not installed on Linux: [docs.brew.sh](https://docs.brew.sh/Homebrew-on-Linux)

### All platforms — pipx (fallback)

Use this if you don't have Homebrew or prefer a pure-Python install.

```bash
pipx install rei-graph
```

If `pipx` is not installed: `pip install --user pipx && pipx ensurepath`

---

## Verify

After installation, confirm everything is working:

```bash
# Check the installed version
rei --version

# Start Neo4j
rei dev start

# Initialize your project
rei init

# Full health check
rei doctor
```

Expected output from `rei doctor`:
```
✓ Neo4j reachable at bolt://localhost:7687
✓ Ingester binary found
  All systems healthy
```

---

## Update

```bash
rei update
```

`rei update` detects whether you installed via Homebrew or pipx and runs the appropriate upgrade command automatically. Your `~/.rei-graph/` data and per-project `.rei/` config are preserved across updates.

If the automatic detection does not apply (e.g. manual install), `rei update` prints manual instructions.

---

## Uninstall

### Homebrew

```bash
brew uninstall rei-graph
```

### pipx

```bash
pipx uninstall rei-graph
```

---

## Troubleshooting

### `rei` command not found after install

**Homebrew**: ensure Homebrew's bin is on your `PATH`:
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"   # Apple Silicon
eval "$(/usr/local/bin/brew shellenv)"       # Intel Mac / Linux
```

**pipx**: ensure pipx's bin directory is on your `PATH`:
```bash
pipx ensurepath
# Then restart your shell or run: source ~/.zshrc
```

### Neo4j won't start

```bash
rei dev logs
# or
docker compose logs neo4j
# Check that ports 7474 and 7687 are not already in use
lsof -i :7687
```

### `rei doctor` reports ingester not found

This should not happen with a release build — the ingester is bundled inside the package. If it does occur, try reinstalling:
```bash
brew reinstall rei-graph   # Homebrew
# or
pipx reinstall rei-graph   # pipx
```

### `rei update` fails

`rei update` shows the exit code and error output from the underlying package manager. Common causes:

- **Network issue**: check your internet connection and retry
- **Homebrew permissions**: run `brew doctor` to check for issues
- **pipx permissions**: run `pipx upgrade rei-graph --verbose` directly

---

## Contributors (development setup)

If you want to work on rei-graph itself, use the dev bootstrap instead of the above. This requires Docker, [uv](https://docs.astral.sh/uv), and Node.js 18+.

```bash
git clone https://github.com/org/rei-graph.git
cd rei-graph
./setup.sh
```

`setup.sh` clones dependencies, creates a virtualenv, builds the TS ingester from source, and starts Neo4j. All commands are then run with `uv run rei ...` from the repo root.

This is **not** the end-user installation path.

