import shutil
from pathlib import Path

import click

from rei_storage.neo4j_client import Neo4jClient


@click.command("delete-project")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
def delete_project(path: str):
    """Delete all graph data for a project and remove its .rei/ directory.

    PATH is the root directory of the project to delete. Defaults to the
    current directory.
    """
    project_root = Path(path).resolve()
    project_id = str(project_root)

    click.confirm(
        f"Delete all graph data for project '{project_root.name}' ({project_id})? "
        "This cannot be undone.",
        abort=True,
    )

    client = Neo4jClient(project_id=project_id)
    try:
        client.delete_project()
    finally:
        client.close()

    rei_dir = project_root / ".rei"
    if rei_dir.exists():
        shutil.rmtree(rei_dir)

    click.echo(f"Deleted project data for {project_id}.")
