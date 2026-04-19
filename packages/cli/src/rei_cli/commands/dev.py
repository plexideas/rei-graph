import subprocess

import click


@click.command()
def dev():
    """Start development services (Neo4j)."""
    click.echo("Starting services...")

    result = subprocess.run(
        ["docker", "compose", "up", "-d"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        click.echo("Neo4j started at http://localhost:7474")
    else:
        click.echo(f"Failed to start services: {result.stderr}")
