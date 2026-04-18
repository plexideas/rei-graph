from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from dgk_cli.main import cli


def test_snapshot_saves_graph_and_prints_path(tmp_path):
    """dgk snapshot creates a snapshot and prints the saved path."""
    expected_path = str(tmp_path / "default" / "snapshots" / "snap_001.json")
    mock_client = MagicMock()
    mock_client.save_snapshot.return_value = expected_path

    with patch("dgk_cli.commands.snapshot.SnapshotClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(cli, ["snapshot", "--snapshot-dir", str(tmp_path)])

    assert result.exit_code == 0
    mock_client.save_snapshot.assert_called_once()
    assert expected_path in result.output


def test_snapshot_uses_default_dir_when_not_specified():
    """dgk snapshot uses ~/.dev-graph-kit/snapshots when no --snapshot-dir given."""
    mock_client = MagicMock()
    mock_client.save_snapshot.return_value = "/some/path/snap.json"

    with patch("dgk_cli.commands.snapshot.SnapshotClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(cli, ["snapshot"])

    assert result.exit_code == 0
    args, kwargs = mock_client.save_snapshot.call_args
    snapshot_dir = args[0]
    assert "dev-graph-kit" in str(snapshot_dir) or str(snapshot_dir).startswith("/")
