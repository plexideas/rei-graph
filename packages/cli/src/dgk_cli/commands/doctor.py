import click

from dgk_storage.neo4j_client import check_neo4j_health


@click.command()
def doctor():
    """Check service health."""
    click.echo("Checking services...\n")

    neo4j_health = check_neo4j_health()
    status = neo4j_health["status"]
    url = neo4j_health["url"]

    if status == "healthy":
        click.echo(f"  Neo4j: healthy ({url})")
    else:
        error = neo4j_health.get("error", "unknown")
        click.echo(f"  Neo4j: unhealthy ({url}) — {error}")
