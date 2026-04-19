from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from rei_cli.main import cli


def test_impact_shows_direct_dependents():
    """rei impact <file> shows modules that import the target file."""
    mock_record = MagicMock()
    mock_record.data.return_value = {
        "n": {"id": "module:src/login.ts", "name": "login", "path": "src/login.ts"},
        "depth": 1,
    }

    with patch("rei_cli.commands.impact.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_dependents.return_value = [mock_record.data()]

        runner = CliRunner()
        result = runner.invoke(cli, ["impact", "src/auth.ts"])

        assert result.exit_code == 0
        mock_client.get_dependents.assert_called_once()
        assert "login" in result.output or "login.ts" in result.output
        mock_client.close.assert_called_once()


def test_impact_shows_no_dependents():
    """rei impact <file> reports when nothing depends on the target."""
    with patch("rei_cli.commands.impact.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_dependents.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["impact", "src/isolated.ts"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output


def test_impact_shows_transitive_dependents():
    """rei impact <file> shows both direct and transitive dependents."""
    records = [
        {"n": {"id": "module:src/login.ts", "name": "login", "path": "src/login.ts"}, "depth": 1},
        {"n": {"id": "module:src/app.ts", "name": "app", "path": "src/app.ts"}, "depth": 2},
    ]

    with patch("rei_cli.commands.impact.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_dependents.return_value = records

        runner = CliRunner()
        result = runner.invoke(cli, ["impact", "src/auth.ts"])

        assert result.exit_code == 0
        assert "login" in result.output
        assert "app" in result.output


# ── Phase 5: project scoping tests ──


def test_impact_resolves_project_id_from_toml(tmp_path):
    """rei impact reads .rei/project.toml and constructs Neo4jClient with project_id."""
    with patch("rei_cli.commands.impact.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.impact._resolve_project_id", return_value=str(tmp_path)):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_dependents.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["impact", "src/auth.ts"])

        assert result.exit_code == 0
        mock_client_cls.assert_called_once_with(project_id=str(tmp_path))


def test_impact_works_without_project_toml():
    """rei impact without .rei/project.toml constructs Neo4jClient with project_id=None."""
    with patch("rei_cli.commands.impact.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.impact._resolve_project_id", return_value=None):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_dependents.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["impact", "src/auth.ts"])

        assert result.exit_code == 0
        mock_client_cls.assert_called_once_with(project_id=None)
