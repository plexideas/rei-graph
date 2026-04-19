from unittest.mock import patch, MagicMock
import subprocess

from click.testing import CliRunner

from rei_cli.main import cli


def test_dev_starts_neo4j(monkeypatch):
    """rei dev starts Neo4j via docker compose."""
    with patch("rei_cli.commands.dev.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Container neo4j started"
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["dev"])
        assert result.exit_code == 0
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args
        assert "docker" in call_args[0][0]
        assert "compose" in call_args[0][0]
        assert "up" in call_args[0][0]


def test_dev_reports_docker_failure(monkeypatch):
    """rei dev reports error when docker compose fails."""
    with patch("rei_cli.commands.dev.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "docker: command not found"
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["dev"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()
