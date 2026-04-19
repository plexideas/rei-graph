from pathlib import Path

import click

from rei_core.config import generate_default_config, write_config


@click.command()
def init():
    """Initialize a rei-graph project."""
    config_path = Path.cwd() / ".rei" / "project.toml"

    if config_path.exists():
        click.echo("Already initialized — .rei/project.toml exists.")
        return

    project_name = Path.cwd().name
    project_id = str(Path.cwd().resolve())
    config = generate_default_config(project_name, project_id=project_id)
    write_config(config_path, config)
    click.echo(f"Initialized rei-graph in .rei/project.toml")
