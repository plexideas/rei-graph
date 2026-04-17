import json
import subprocess
from pathlib import Path

import click

from dgk_core.schemas import GraphNode, GraphRelationship, ScanResult
from dgk_storage.neo4j_client import Neo4jClient


def _find_ingester() -> Path:
    """Find the TS ingester dist/cli.js relative to the project."""
    # Walk up from CWD looking for the ingester
    candidates = [
        Path.cwd() / "packages" / "ingester_ts" / "dist" / "cli.js",
    ]
    # Also try relative to this file (for dev installs)
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


@click.command()
@click.argument("file_path")
def scan(file_path: str):
    """Scan a TypeScript/TSX file and add to the code graph."""
    path = Path(file_path)
    if not path.exists():
        click.echo(f"Error: file not found — {file_path}")
        return

    try:
        ingester = _find_ingester()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}")
        return

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
