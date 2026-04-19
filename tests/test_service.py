from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from rei_cli.main import cli


# ---------------------------------------------------------------------------
# service start
# ---------------------------------------------------------------------------

def test_service_start_calls_docker_compose_up():
    """rei service start runs docker compose up -d with the bundled compose file."""
    with patch("rei_cli.commands.service.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["service", "start"])
        assert result.exit_code == 0, result.output
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args[0][0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert "up" in call_args
        assert "-d" in call_args


def test_service_start_uses_compose_file_flag():
    """rei service start passes -f <compose_path> so it uses the bundled file."""
    with patch("rei_cli.commands.service.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["service", "start"])
        assert result.exit_code == 0, result.output
        call_args = mock_subprocess.run.call_args[0][0]
        assert "-f" in call_args


def test_service_start_prints_success():
    """rei service start prints success message when docker compose succeeds."""
    with patch("rei_cli.commands.service.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["service", "start"])
        assert result.exit_code == 0, result.output
        assert "neo4j" in result.output.lower()


def test_service_start_reports_failure():
    """rei service start prints error when docker compose fails."""
    with patch("rei_cli.commands.service.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "docker: command not found"
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["service", "start"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower() or "✗" in result.output


# ---------------------------------------------------------------------------
# service stop
# ---------------------------------------------------------------------------

def test_service_stop_calls_docker_compose_down():
    """rei service stop runs docker compose down."""
    with patch("rei_cli.commands.service.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["service", "stop"])
        assert result.exit_code == 0, result.output
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args[0][0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert "down" in call_args


def test_service_stop_prints_success():
    """rei service stop prints success message when docker compose succeeds."""
    with patch("rei_cli.commands.service.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["service", "stop"])
        assert result.exit_code == 0, result.output
        assert "stopped" in result.output.lower() or "✓" in result.output


def test_service_stop_reports_failure():
    """rei service stop prints error when docker compose fails."""
    with patch("rei_cli.commands.service.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "No such container"
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["service", "stop"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower() or "✗" in result.output


# ---------------------------------------------------------------------------
# CLI registration
# ---------------------------------------------------------------------------

def test_service_appears_in_help():
    """rei --help shows service command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "service" in result.output


def test_dev_not_in_help():
    """rei --help does not show dev command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "dev" not in result.output


def test_dev_command_not_registered():
    """rei dev returns an error (not a registered command)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["dev"])
    assert result.exit_code != 0
