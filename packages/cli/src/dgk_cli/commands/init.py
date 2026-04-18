from pathlib import Path

import click

from dgk_core.config import generate_default_config, write_config


@click.command()
def init():
    """Initialize a dev-graph-kit project."""
    config_path = Path.cwd() / ".dgk" / "project.toml"

    if config_path.exists():
        click.echo("Already initialized — .dgk/project.toml exists.")
        return

    project_name = Path.cwd().name
    project_id = str(Path.cwd().resolve())
    config = generate_default_config(project_name, project_id=project_id)
    write_config(config_path, config)
    click.echo(f"Initialized dev-graph-kit in .dgk/project.toml")
