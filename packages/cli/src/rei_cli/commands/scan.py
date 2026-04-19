import json
import subprocess
import time
from pathlib import Path

import click

from rei_core.config import generate_default_config, read_config, write_config
from rei_core.hashing import project_hash
from rei_core.schemas import GraphNode, GraphRelationship, ScanResult
from rei_storage.neo4j_client import Neo4jClient
from rei_cli.progress import ScanProgress

TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}

# Path to the ingester bundled inside the installed package (populated at build time)
_PACKAGE_INGESTER_PATH: Path = Path(__file__).resolve().parent / "_ingester" / "cli.js"


def _find_ingester() -> Path:
    """Find the TS ingester dist/cli.js.

    Discovery order:
    1. Bundled ingester inside the installed package (``_ingester/cli.js`` next to this file)
    2. Development path relative to the project root (``packages/ingester_ts/dist/cli.js``)
    """
    if _PACKAGE_INGESTER_PATH.exists():
        return _PACKAGE_INGESTER_PATH

    candidates = [
        Path.cwd() / "packages" / "ingester_ts" / "dist" / "cli.js",
    ]
    this_dir = Path(__file__).resolve()
    for parent in this_dir.parents:
        candidate = parent / "packages" / "ingester_ts" / "dist" / "cli.js"
        if candidate not in candidates:
            candidates.append(candidate)
        if (parent / "pyproject.toml").exists():
            break

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("TS ingester not found. Run 'npm run build' in packages/ingester_ts/")


def _resolve_project(root: Path) -> tuple[str, str]:
    """Resolve project identity for *root*, auto-creating .rei/project.toml if needed.

    Returns ``(project_id, project_name)``.
    """
    project_id = str(root.resolve())
    config_path = root / ".rei" / "project.toml"
    if not config_path.exists():
        project_name = root.resolve().name
        config = generate_default_config(project_name, project_id=project_id)
        write_config(config_path, config)
    else:
        try:
            project_name = read_config(config_path).get("project", {}).get("name") or root.resolve().name
        except Exception:
            project_name = root.resolve().name
    return project_id, project_name


def _parse_ingester_output(raw: str) -> ScanResult:
    """Parse JSON output from the TS ingester into a ScanResult."""
    data = json.loads(raw)
    nodes = [
        GraphNode(
            id=n["id"],
            label=n["label"],
            name=n["name"],
            path=n["path"],
            line=n.get("line", 1),
            properties=n.get("properties", {}),
        )
        for n in data["nodes"]
    ]
    relationships = [
        GraphRelationship(
            type=r["type"],
            source_id=r["sourceId"],
            target_id=r["targetId"],
            properties=r.get("properties", {}),
        )
        for r in data["relationships"]
    ]
    return ScanResult(file=data["file"], nodes=nodes, relationships=relationships)


def _collect_files(root: Path) -> list[Path]:
    """Walk project tree respecting include/exclude from .rei/project.toml."""
    config_path = root / ".rei" / "project.toml"
    include = ["src", "packages", "apps"]
    exclude = ["dist", "build", "node_modules", ".next"]

    if config_path.exists():
        config = read_config(config_path)
        scan_config = config.get("scan", {})
        include = scan_config.get("include", include)
        exclude = scan_config.get("exclude", exclude)

    files: list[Path] = []
    exclude_set = set(exclude)

    for inc_dir in include:
        search_root = root / inc_dir
        if not search_root.is_dir():
            continue
        for filepath in search_root.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix not in TS_EXTENSIONS:
                continue
            # Check if any part of the relative path matches an exclude pattern
            rel_parts = filepath.relative_to(root).parts
            if any(part in exclude_set for part in rel_parts):
                continue
            files.append(filepath)

    return sorted(files)


def _scan_single_file(file_path: Path, ingester: Path, project_prefix: str | None = None) -> tuple[ScanResult | None, str]:
    """Scan a single file with the TS ingester.

    Returns a (result, warning) tuple. `warning` is a non-empty string when
    the ingester fails; callers are responsible for surfacing it.
    """
    cmd = ["node", str(ingester), str(file_path.resolve())]
    if project_prefix:
        cmd.extend(["--project-prefix", project_prefix])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None, f"failed to parse {file_path.name} — {result.stderr.strip()}"
    return _parse_ingester_output(result.stdout), ""


def _get_changed_files(root: Path) -> list[str]:
    """Return list of git-changed TS/TSX file paths relative to root."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [p for p in lines if Path(p).suffix in TS_EXTENSIONS]


def _get_changed_files_since(root: Path, since: str) -> list[str]:
    """Return TS/TSX files changed in commits since *since* (ISO timestamp)."""
    result = subprocess.run(
        ["git", "log", "--name-only", "--pretty=format:", "--since", since],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if result.returncode != 0:
        return []
    seen: set[str] = set()
    unique: list[str] = []
    for line in result.stdout.splitlines():
        p = line.strip()
        if p and p not in seen and Path(p).suffix in TS_EXTENSIONS:
            seen.add(p)
            unique.append(p)
    return unique


def _get_deleted_files(root: Path) -> list[str]:
    """Return list of git-deleted file paths relative to root."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=D", "HEAD"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _get_deleted_files_since(root: Path, since: str) -> list[str]:
    """Return files deleted in commits since *since* (ISO timestamp)."""
    result = subprocess.run(
        ["git", "log", "--diff-filter=D", "--name-only", "--pretty=format:", "--since", since],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if result.returncode != 0:
        return []
    seen: set[str] = set()
    unique: list[str] = []
    for line in result.stdout.splitlines():
        p = line.strip()
        if p and p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


@click.command()
@click.argument("file_path", default=".", required=False)
@click.option("--changed", is_flag=True, default=False, help="Only scan git-changed files")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Print per-file node/rel counts")
@click.option("--force", is_flag=True, default=False, help="Force full rescan even if project was scanned before")
def scan(file_path: str, changed: bool, verbose: bool, force: bool):
    """Scan a TypeScript/TSX file or directory and add to the code graph."""
    path = Path(file_path)
    if not path.exists():
        click.echo(f"Error: file not found — {file_path}")
        return

    # Resolve project identity (auto-init .rei/project.toml if missing)
    project_root = path if path.is_dir() else path.parent
    project_id, project_name = _resolve_project(project_root)
    prefix = project_hash(project_id)

    click.echo(f"✓ Project: {project_name}")

    if changed:
        _scan_changed(path, verbose=verbose, project_id=project_id, project_prefix=prefix)
        return

    # Repeat-scan detection: check if project was already scanned
    client = Neo4jClient(project_id=project_id)
    click.echo("✓ Neo4j: connected")
    try:
        project_info = client.get_project()
        if project_info and project_info.get("last_scanned_at") and not force:
            last_ts = project_info["last_scanned_at"]
            changed_files = _get_changed_files_since(project_root, last_ts)
            deleted_files = _get_deleted_files_since(project_root, last_ts)
            file_count = len(changed_files) + len(deleted_files)
            click.echo(f"✓ Mode: incremental ({file_count} file(s) changed)")
            _scan_changed_since(
                path,
                since=last_ts,
                verbose=verbose,
                project_id=project_id,
                project_prefix=prefix,
                client=client,
            )
            return
    except Exception:
        pass

    try:
        ingester = _find_ingester()
    except FileNotFoundError as e:
        client.close()
        click.echo(f"Error: {e}")
        return

    if path.is_dir():
        files = _collect_files(path)
        if not files:
            click.echo("No TS/TSX files found to scan.")
            return
        click.echo(f"✓ Mode: full scan ({len(files)} files)")

        progress = ScanProgress(total=len(files), verbose=verbose)
        progress.start()
        total_nodes = 0
        total_rels = 0
        start_time = time.monotonic()

        try:
            for f in files:
                scan_result, warning = _scan_single_file(f, ingester, project_prefix=prefix)
                if warning:
                    progress.add_warning(warning)
                if scan_result:
                    client.delete_file_nodes(scan_result.file)
                    client.upsert_nodes(scan_result.nodes)
                    client.upsert_relationships(scan_result.relationships)
                    total_nodes += len(scan_result.nodes)
                    total_rels += len(scan_result.relationships)
                progress.advance(
                    str(f),
                    len(scan_result.nodes) if scan_result else 0,
                    len(scan_result.relationships) if scan_result else 0,
                )
        finally:
            client.close()

        elapsed = time.monotonic() - start_time
        client.update_last_scanned()
        progress.finish(elapsed=elapsed, total_nodes=total_nodes, total_rels=total_rels)
    else:
        click.echo("✓ Mode: full scan (1 file)")
        start_time = time.monotonic()
        progress = ScanProgress(total=1, verbose=verbose)
        progress.start()

        scan_result, warning = _scan_single_file(path, ingester, project_prefix=prefix)
        elapsed = time.monotonic() - start_time

        if warning:
            progress.stop()
            client.close()
            click.echo(f"Error: {warning}")
            return

        try:
            client.upsert_nodes(scan_result.nodes)
            client.upsert_relationships(scan_result.relationships)
        finally:
            client.close()

        client.update_last_scanned()
        progress.advance(
            str(path),
            len(scan_result.nodes),
            len(scan_result.relationships),
        )
        progress.finish(
            elapsed=elapsed,
            total_nodes=len(scan_result.nodes),
            total_rels=len(scan_result.relationships),
        )


def _scan_changed(root: Path, verbose: bool = False, project_id: str | None = None, project_prefix: str | None = None) -> None:
    """Scan only git-changed files and remove nodes for deleted files."""
    # Remove nodes for deleted files first
    deleted = _get_deleted_files(root)
    changed = _get_changed_files(root)

    # Filter out deleted files from changed list
    deleted_set = set(deleted)
    to_scan = [p for p in changed if p not in deleted_set]

    if not to_scan and not deleted:
        click.echo("No changed files found.")
        return

    client = Neo4jClient(project_id=project_id)
    try:
        for rel_path in deleted:
            client.delete_file_nodes(rel_path)

        if not to_scan:
            click.echo(f"No changed TS/TSX files to scan (removed {len(deleted)} file(s)).")
            return

        try:
            ingester = _find_ingester()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}")
            return

        total_nodes = 0
        total_rels = 0
        start_time = time.monotonic()
        progress = ScanProgress(total=len(to_scan), verbose=verbose)
        progress.start()

        for rel_path in to_scan:
            file_path = root / rel_path
            if not file_path.exists():
                continue
            scan_result, warning = _scan_single_file(file_path, ingester, project_prefix=project_prefix)
            if warning:
                progress.add_warning(warning)
            if scan_result:
                client.delete_file_nodes(scan_result.file)
                client.upsert_nodes(scan_result.nodes)
                client.upsert_relationships(scan_result.relationships)
                total_nodes += len(scan_result.nodes)
                total_rels += len(scan_result.relationships)
            progress.advance(
                str(file_path),
                len(scan_result.nodes) if scan_result else 0,
                len(scan_result.relationships) if scan_result else 0,
            )
    finally:
        client.close()

    elapsed = time.monotonic() - start_time
    progress.finish(elapsed=elapsed, total_nodes=total_nodes, total_rels=total_rels)


def _scan_changed_since(
    root: Path,
    since: str,
    verbose: bool = False,
    project_id: str | None = None,
    project_prefix: str | None = None,
    client: "Neo4jClient | None" = None,
) -> None:
    """Scan files changed since *since* timestamp and remove deleted ones."""
    deleted = _get_deleted_files_since(root, since)
    changed = _get_changed_files_since(root, since)

    deleted_set = set(deleted)
    to_scan = [p for p in changed if p not in deleted_set]

    owns_client = client is None
    if owns_client:
        client = Neo4jClient(project_id=project_id)

    try:
        for rel_path in deleted:
            client.delete_file_nodes(rel_path)

        if not to_scan and not deleted:
            click.echo("No changes since last scan.")
            client.update_last_scanned()
            return

        if not to_scan:
            click.echo(f"No changed TS/TSX files to scan (removed {len(deleted)} file(s)).")
            client.update_last_scanned()
            return

        try:
            ingester = _find_ingester()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}")
            return

        total_nodes = 0
        total_rels = 0
        start_time = time.monotonic()
        progress = ScanProgress(total=len(to_scan), verbose=verbose)
        progress.start()

        for rel_path in to_scan:
            file_path = root / rel_path
            if not file_path.exists():
                continue
            scan_result, warning = _scan_single_file(file_path, ingester, project_prefix=project_prefix)
            if warning:
                progress.add_warning(warning)
            if scan_result:
                client.delete_file_nodes(scan_result.file)
                client.upsert_nodes(scan_result.nodes)
                client.upsert_relationships(scan_result.relationships)
                total_nodes += len(scan_result.nodes)
                total_rels += len(scan_result.relationships)
            progress.advance(
                str(file_path),
                len(scan_result.nodes) if scan_result else 0,
                len(scan_result.relationships) if scan_result else 0,
            )

        elapsed = time.monotonic() - start_time
        client.update_last_scanned()
        progress.finish(elapsed=elapsed, total_nodes=total_nodes, total_rels=total_rels)
    finally:
        if owns_client:
            client.close()

