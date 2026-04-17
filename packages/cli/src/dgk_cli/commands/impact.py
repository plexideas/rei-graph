import click

from dgk_storage.neo4j_client import Neo4jClient


@click.command()
@click.argument("file_path")
@click.option("--depth", default=5, help="Max traversal depth for transitive dependents")
def impact(file_path: str, depth: int):
    """Show what depends on a file (impact analysis)."""
    client = Neo4jClient()
    try:
        results = client.get_dependents(file_path, max_depth=depth)
    finally:
        client.close()

    if not results:
        click.echo(f"No dependents found for {file_path}")
        return

    click.echo(f"Impact analysis for {file_path}:\n")
    click.echo(f"  {len(results)} dependent(s) found:\n")

    for record in results:
        node = record.get("n", {})
        name = node.get("name", "?")
        path = node.get("path", "?")
        d = record.get("depth", "?")
        kind = "direct" if d == 1 else f"transitive (depth {d})"
        click.echo(f"  {name}  ({path})  [{kind}]")
