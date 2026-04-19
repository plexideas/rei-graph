"""Tests for `rei delete-project` CLI command — Phase 7."""
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from rei_cli.main import cli


class TestDeleteProjectCli:
    """Verify the rei delete-project CLI command behavior."""

    def test_delete_project_resolves_path_and_calls_delete_project(self, tmp_path):
        """delete-project resolves the absolute path and calls Neo4jClient.delete_project."""
        with patch("rei_cli.commands.delete_project.Neo4jClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["delete-project", str(tmp_path)],
                input="y\n",  # confirm the prompt
            )

            assert result.exit_code == 0
            mock_cls.assert_called_once_with(project_id=str(tmp_path.resolve()))
            mock_client.delete_project.assert_called_once()

    def test_delete_project_removes_rei_directory(self, tmp_path):
        """delete-project removes the .rei/ directory at the given path."""
        rei_dir = tmp_path / ".rei"
        rei_dir.mkdir()
        (rei_dir / "project.toml").write_text("[project]\nid = 'test'\n")

        with patch("rei_cli.commands.delete_project.Neo4jClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["delete-project", str(tmp_path)],
                input="y\n",
            )

            assert result.exit_code == 0
            assert not rei_dir.exists()

    def test_delete_project_aborts_on_no_confirmation(self, tmp_path):
        """delete-project aborts without deleting when user says no."""
        rei_dir = tmp_path / ".rei"
        rei_dir.mkdir()
        (rei_dir / "project.toml").write_text("[project]\nid = 'test'\n")

        with patch("rei_cli.commands.delete_project.Neo4jClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["delete-project", str(tmp_path)],
                input="n\n",
            )

            # Aborted — no deletion
            mock_client.delete_project.assert_not_called()
            assert rei_dir.exists()

    def test_delete_project_no_rei_dir_still_deletes_graph(self, tmp_path):
        """delete-project works even if .rei/ directory does not exist."""
        with patch("rei_cli.commands.delete_project.Neo4jClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["delete-project", str(tmp_path)],
                input="y\n",
            )

            assert result.exit_code == 0
            mock_client.delete_project.assert_called_once()

    def test_delete_project_closes_client(self, tmp_path):
        """delete-project closes the Neo4j client after deletion."""
        with patch("rei_cli.commands.delete_project.Neo4jClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            runner = CliRunner()
            runner.invoke(
                cli,
                ["delete-project", str(tmp_path)],
                input="y\n",
            )

            mock_client.close.assert_called_once()
