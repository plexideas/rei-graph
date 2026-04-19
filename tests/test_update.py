"""Tests for the rei update command."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rei_cli.main import cli


# ---------------------------------------------------------------------------
# _detect_install_method
# ---------------------------------------------------------------------------

def test_detect_brew_from_opt_homebrew():
    """Binary in /opt/homebrew is detected as brew (macOS arm64)."""
    from rei_cli.commands.update import _detect_install_method

    with patch("rei_cli.commands.update.shutil.which", return_value="/opt/homebrew/bin/rei"):
        assert _detect_install_method() == "brew"


def test_detect_brew_from_usr_local():
    """Binary in /usr/local/Cellar is detected as brew (macOS x86_64)."""
    from rei_cli.commands.update import _detect_install_method

    with patch("rei_cli.commands.update.shutil.which", return_value="/usr/local/Cellar/rei-graph/0.1.0/bin/rei"):
        assert _detect_install_method() == "brew"


def test_detect_brew_from_linuxbrew():
    """Binary in /home/linuxbrew is detected as brew (Linux)."""
    from rei_cli.commands.update import _detect_install_method

    with patch("rei_cli.commands.update.shutil.which", return_value="/home/linuxbrew/.linuxbrew/bin/rei"):
        assert _detect_install_method() == "brew"


def test_detect_pipx():
    """Binary in ~/.local/pipx path is detected as pipx."""
    from rei_cli.commands.update import _detect_install_method

    with patch(
        "rei_cli.commands.update.shutil.which",
        return_value="/Users/alice/.local/pipx/venvs/rei-cli/bin/rei",
    ):
        assert _detect_install_method() == "pipx"


def test_detect_unknown_when_which_returns_none():
    """Returns 'unknown' when rei is not on PATH."""
    from rei_cli.commands.update import _detect_install_method

    with patch("rei_cli.commands.update.shutil.which", return_value=None):
        assert _detect_install_method() == "unknown"


def test_detect_unknown_for_arbitrary_path():
    """Returns 'unknown' for a path that is neither brew nor pipx."""
    from rei_cli.commands.update import _detect_install_method

    with patch("rei_cli.commands.update.shutil.which", return_value="/usr/bin/rei"):
        assert _detect_install_method() == "unknown"


# ---------------------------------------------------------------------------
# rei update — brew path
# ---------------------------------------------------------------------------

def test_update_brew_runs_brew_upgrade():
    """rei update calls 'brew upgrade rei-graph' when installed via Homebrew."""
    runner = CliRunner()

    with (
        patch("rei_cli.commands.update._detect_install_method", return_value="brew"),
        patch("rei_cli.commands.update.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="Updated.", stderr="")
        result = runner.invoke(cli, ["update"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd == ["brew", "upgrade", "rei-graph"]


def test_update_brew_shows_current_version():
    """rei update prints the current version before upgrading."""
    runner = CliRunner()

    with (
        patch("rei_cli.commands.update._detect_install_method", return_value="brew"),
        patch("rei_cli.commands.update.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = runner.invoke(cli, ["update"])

    assert result.exit_code == 0
    assert "version" in result.output.lower() or "updating" in result.output.lower()


# ---------------------------------------------------------------------------
# rei update — pipx path
# ---------------------------------------------------------------------------

def test_update_pipx_runs_pipx_upgrade():
    """rei update calls 'pipx upgrade rei-graph' when installed via pipx."""
    runner = CliRunner()

    with (
        patch("rei_cli.commands.update._detect_install_method", return_value="pipx"),
        patch("rei_cli.commands.update.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="upgraded", stderr="")
        result = runner.invoke(cli, ["update"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd == ["pipx", "upgrade", "rei-graph"]


# ---------------------------------------------------------------------------
# rei update — unknown install method
# ---------------------------------------------------------------------------

def test_update_unknown_prints_manual_instructions():
    """rei update prints manual instructions when install method is unknown."""
    runner = CliRunner()

    with patch("rei_cli.commands.update._detect_install_method", return_value="unknown"):
        result = runner.invoke(cli, ["update"])

    assert result.exit_code == 0
    output = result.output.lower()
    assert "manual" in output or "pip" in output or "pipx" in output or "brew" in output


def test_update_unknown_does_not_call_subprocess():
    """rei update does not run any subprocess for unknown install method."""
    runner = CliRunner()

    with (
        patch("rei_cli.commands.update._detect_install_method", return_value="unknown"),
        patch("rei_cli.commands.update.subprocess.run") as mock_run,
    ):
        runner.invoke(cli, ["update"])

    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# rei update — subprocess failure handling
# ---------------------------------------------------------------------------

def test_update_brew_failure_shows_error():
    """rei update shows error message and non-zero exit code on brew failure."""
    runner = CliRunner()

    with (
        patch("rei_cli.commands.update._detect_install_method", return_value="brew"),
        patch("rei_cli.commands.update.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="network error")
        result = runner.invoke(cli, ["update"])

    assert result.exit_code != 0
    assert "error" in result.output.lower() or "fail" in result.output.lower() or "network error" in result.output.lower()


def test_update_pipx_failure_shows_error():
    """rei update shows error message and non-zero exit code on pipx failure."""
    runner = CliRunner()

    with (
        patch("rei_cli.commands.update._detect_install_method", return_value="pipx"),
        patch("rei_cli.commands.update.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="permission denied")
        result = runner.invoke(cli, ["update"])

    assert result.exit_code != 0
    assert "error" in result.output.lower() or "fail" in result.output.lower() or "permission denied" in result.output.lower()


# ---------------------------------------------------------------------------
# rei update — does not touch Docker/Neo4j
# ---------------------------------------------------------------------------

def test_update_does_not_invoke_docker():
    """rei update never calls docker regardless of install method."""
    runner = CliRunner()

    for method in ("brew", "pipx", "unknown"):
        with (
            patch("rei_cli.commands.update._detect_install_method", return_value=method),
            patch("rei_cli.commands.update.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.invoke(cli, ["update"])

            for call in mock_run.call_args_list:
                cmd = call[0][0] if call[0] else []
                assert "docker" not in cmd, f"docker should not be invoked for method={method}"
