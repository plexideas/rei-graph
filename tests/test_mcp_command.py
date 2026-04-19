"""Tests for the rei mcp command."""
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from rei_cli.main import cli


def test_mcp_command_is_registered():
    """rei mcp command exists and shows help without error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "MCP" in result.output or "mcp" in result.output


def test_mcp_command_launches_server_process():
    """rei mcp starts the rei_mcp module as a subprocess."""
    import sys

    with patch("rei_cli.commands.mcp.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["mcp"])

        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args[0][0]
        assert call_args[0] == sys.executable
        assert "-m" in call_args
        assert "rei_mcp" in call_args
