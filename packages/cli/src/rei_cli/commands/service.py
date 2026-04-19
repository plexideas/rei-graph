import subprocess
from pathlib import Path

import click

_PACKAGE_COMPOSE_PATH: Path = Path(__file__).resolve().parent / "_compose" / "docker-compose.yml"


def _resolve_compose_path() -> Path:
    """Return the compose file path: bundled package copy first, then repo root fallback."""
    if _PACKAGE_COMPOSE_PATH.exists():
        return _PACKAGE_COMPOSE_PATH
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docker-compose.yml"
        if candidate.exists():
            return candidate
    return _PACKAGE_COMPOSE_PATH


@click.group()
def service():
    """Manage the rei graph services (Neo4j)."""
    pass


@service.command()
def start():
    """Start Neo4j via docker compose."""
    click.echo("Starting services...")
    compose_path = _resolve_compose_path()
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "up", "-d"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo("✓ Neo4j started at http://localhost:7474")
    else:
        click.echo(f"✗ Failed to start services: {result.stderr.strip()}")


@service.command()
def stop():
    """Stop Neo4j via docker compose."""
    click.echo("Stopping services...")
    compose_path = _resolve_compose_path()
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "down"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo("✓ Neo4j stopped")
    else:
        click.echo(f"✗ Failed to stop services: {result.stderr.strip()}")
