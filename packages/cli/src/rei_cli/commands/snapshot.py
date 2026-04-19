from pathlib import Path

import click

from rei_core.config import read_config
from rei_storage.snapshot_client import SnapshotClient


def _resolve_project_id() -> str | None:
    """Read project_id from .rei/project.toml in cwd, or return None."""
    config_path = Path.cwd() / ".rei" / "project.toml"
    if config_path.exists():
        config = read_config(config_path)
        return config.get("project", {}).get("id")
    return None


@click.command()
@click.option(
    "--snapshot-dir",
    default=None,
    help="Directory to save snapshots (default: ~/.rei-graph/snapshots)",
)
@click.option("--project-id", default=None, help="Project identifier for snapshot naming")
def snapshot(snapshot_dir: str | None, project_id: str | None) -> None:
    """Export the current graph state to a JSON snapshot file."""
    if snapshot_dir is None:
        snap_dir = Path.home() / ".rei-graph" / "snapshots"
    else:
        snap_dir = Path(snapshot_dir)

    resolved_project_id = _resolve_project_id()
    client = SnapshotClient(project_id=resolved_project_id)
    try:
        saved_path = client.save_snapshot(snap_dir, project_id)
    finally:
        client.close()

    click.echo(f"Snapshot saved: {saved_path}")
