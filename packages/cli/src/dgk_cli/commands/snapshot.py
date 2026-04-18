from pathlib import Path

import click

from dgk_storage.snapshot_client import SnapshotClient


@click.command()
@click.option(
    "--snapshot-dir",
    default=None,
    help="Directory to save snapshots (default: ~/.dev-graph-kit/snapshots)",
)
@click.option("--project-id", default="default", help="Project identifier for snapshot naming")
def snapshot(snapshot_dir: str | None, project_id: str) -> None:
    """Export the current graph state to a JSON snapshot file."""
    if snapshot_dir is None:
        snap_dir = Path.home() / ".dev-graph-kit" / "snapshots"
    else:
        snap_dir = Path(snapshot_dir)

    client = SnapshotClient()
    try:
        saved_path = client.save_snapshot(snap_dir, project_id)
    finally:
        client.close()

    click.echo(f"Snapshot saved: {saved_path}")
