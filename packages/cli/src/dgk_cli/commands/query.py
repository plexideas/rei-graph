import click

from dgk_storage.neo4j_client import Neo4jClient


@click.command()
@click.argument("search")
@click.option("--label", default=None, help="Filter by node label (e.g. Function, Class, Component)")
def query(search: str, label: str | None):
    """Search the code graph for entities by name."""
    labels = [label] if label else None

    client = Neo4jClient()
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
