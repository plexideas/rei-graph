import json
import subprocess
import time
from pathlib import Path

import click

from dgk_core.config import read_config
from dgk_core.schemas import GraphNode, GraphRelationship, ScanResult
from dgk_storage.neo4j_client import Neo4jClient
from dgk_cli.progress import ScanProgress

TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}


def _find_ingester() -> Path:
    """Find the TS ingester dist/cli.js relative to the project."""
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
    """Walk project tree respecting include/exclude from .dgk/project.toml."""
    config_path = root / ".dgk" / "project.toml"
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


def _scan_single_file(file_path: Path, ingester: Path) -> ScanResult | None:
    """Scan a single file with the TS ingester."""
    result = subprocess.run(
        ["node", str(ingester), str(file_path.resolve())],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click.echo(f"  Warning: failed to scan {file_path} — {result.stderr.strip()}")
        return None
    return _parse_ingester_output(result.stdout)


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


@click.command()
@click.argument("file_path")
@click.option("--changed", is_flag=True, default=False, help="Only scan git-changed files")
def scan(file_path: str, changed: bool):
    """Scan a TypeScript/TSX file or directory and add to the code graph."""
    path = Path(file_path)
    if not path.exists():
        click.echo(f"Error: file not found — {file_path}")
        return

    if changed:
        _scan_changed(path)
        return

    try:
        ingester = _find_ingester()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}")
        return

    if path.is_dir():
        files = _collect_files(path)
        if not files:
            click.echo("No TS/TSX files found to scan.")
            return

        progress = ScanProgress(total=len(files))
        progress.start()
        total_nodes = 0
        total_rels = 0
        start_time = time.monotonic()

        client = Neo4jClient()
        try:
            for f in files:
                scan_result = _scan_single_file(f, ingester)
                if scan_result:
                    client.delete_file_nodes(scan_result.file)
                    client.upsert_nodes(scan_result.nodes)
                    client.upsert_relationships(scan_result.relationships)
                    total_nodes += len(scan_result.nodes)
                    total_rels += len(scan_result.relationships)
                progress.advance(str(f), len(scan_result.nodes) if scan_result else 0, len(scan_result.relationships) if scan_result else 0)
        finally:
            client.close()

        elapsed = time.monotonic() - start_time
        progress.finish(elapsed=elapsed, total_nodes=total_nodes, total_rels=total_rels)
    else:
        click.echo(f"Scanning {file_path}...")

        result = subprocess.run(
            ["node", str(ingester), str(path.resolve())],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            click.echo(f"Error: ingester failed — {result.stderr.strip()}")
            return

        scan_result = _parse_ingester_output(result.stdout)

        client = Neo4jClient()
        try:
            client.upsert_nodes(scan_result.nodes)
            client.upsert_relationships(scan_result.relationships)
        finally:
            client.close()

        click.echo(
            f"Done: {len(scan_result.nodes)} nodes, "
            f"{len(scan_result.relationships)} relationships"
        )


def _scan_changed(root: Path) -> None:
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

    client = Neo4jClient()
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

        click.echo(f"Scanning {len(to_scan)} changed file(s)...")
        total_nodes = 0
        total_rels = 0

        for rel_path in to_scan:
            file_path = root / rel_path
            if not file_path.exists():
                continue
            scan_result = _scan_single_file(file_path, ingester)
            if scan_result:
                client.delete_file_nodes(scan_result.file)
                client.upsert_nodes(scan_result.nodes)
                client.upsert_relationships(scan_result.relationships)
                total_nodes += len(scan_result.nodes)
                total_rels += len(scan_result.relationships)
    finally:
        client.close()

    click.echo(f"Done: {total_nodes} nodes, {total_rels} relationships from {len(to_scan)} changed files")

