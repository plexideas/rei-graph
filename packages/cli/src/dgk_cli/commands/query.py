from pathlib import Path

import click

from dgk_core.config import read_config
from dgk_storage.neo4j_client import Neo4jClient


def _resolve_project_id() -> str | None:
    """Read project_id from .dgk/project.toml in cwd, or return None."""
    config_path = Path.cwd() / ".dgk" / "project.toml"
    if config_path.exists():
        config = read_config(config_path)
        return config.get("project", {}).get("id")
    return None


@click.command()
@click.argument("search")
@click.option("--label", default=None, help="Filter by node label (e.g. Function, Class, Component)")
def query(search: str, label: str | None):
    """Search the code graph for entities by name."""
    labels = [label] if label else None
    project_id = _resolve_project_id()

    client = Neo4jClient(project_id=project_id)
    try:
        results = client.search_nodes(search, labels=labels)
    finally:
        client.close()

    if not results:
        click.echo("No matching nodes found.")
        return

    click.echo(f"Found {len(results)} node(s):\n")
    for record in results:
        node = record.get("n", {})
        name = node.get("name", "?")
        path = node.get("path", "?")
        line = node.get("line", "")
        node_id = node.get("id", "")

        line_str = f":{line}" if line else ""
        click.echo(f"  {name}  ({path}{line_str})  [{node_id}]")
