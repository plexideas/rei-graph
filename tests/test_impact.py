from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from dgk_cli.main import cli


def test_impact_shows_direct_dependents():
    """dgk impact <file> shows modules that import the target file."""
    mock_record = MagicMock()
    mock_record.data.return_value = {
        "n": {"id": "module:src/login.ts", "name": "login", "path": "src/login.ts"},
        "depth": 1,
    }

    with patch("dgk_cli.commands.impact.Neo4jClient") as mock_client_cls:
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
    """dgk impact <file> reports when nothing depends on the target."""
    with patch("dgk_cli.commands.impact.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_dependents.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["impact", "src/isolated.ts"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output


def test_impact_shows_transitive_dependents():
    """dgk impact <file> shows both direct and transitive dependents."""
    records = [
        {"n": {"id": "module:src/login.ts", "name": "login", "path": "src/login.ts"}, "depth": 1},
        {"n": {"id": "module:src/app.ts", "name": "app", "path": "src/app.ts"}, "depth": 2},
    ]

    with patch("dgk_cli.commands.impact.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_dependents.return_value = records

        runner = CliRunner()
        result = runner.invoke(cli, ["impact", "src/auth.ts"])

        assert result.exit_code == 0
        assert "login" in result.output
        assert "app" in result.output
