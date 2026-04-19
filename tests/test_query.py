from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from dgk_cli.main import cli


def test_query_returns_matching_nodes():
    """dgk query returns matching nodes from Neo4j."""
    with patch("dgk_cli.commands.query.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search_nodes.return_value = [
            {"n": {"id": "function:src/auth.ts:login", "name": "login", "path": "src/auth.ts", "line": 5}},
            {"n": {"id": "hook:src/auth.ts:useAuth", "name": "useAuth", "path": "src/auth.ts", "line": 12}},
        ]

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "auth"])

        assert result.exit_code == 0
        mock_client.search_nodes.assert_called_once()
        assert "login" in result.output
        assert "useAuth" in result.output
        mock_client.close.assert_called_once()


def test_query_no_results():
    """dgk query reports when no nodes match."""
    with patch("dgk_cli.commands.query.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search_nodes.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "nonexistent"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output
        mock_client.close.assert_called_once()


def test_query_with_label_filter():
    """dgk query --label filters by node label."""
    with patch("dgk_cli.commands.query.Neo4jClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search_nodes.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "login", "--label", "Function"])

        assert result.exit_code == 0
        call_args = mock_client.search_nodes.call_args
        assert call_args[1].get("labels") == ["Function"] or \
               (len(call_args[0]) > 1 and call_args[0][1] == ["Function"])


# ── Phase 5: project scoping tests ──


def test_query_resolves_project_id_from_toml(tmp_path):
    """dgk query reads .dgk/project.toml and constructs Neo4jClient with project_id."""
    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
        f'[project]\nid = "{tmp_path}"\nname = "test"\n'
    )

    with patch("dgk_cli.commands.query.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.query._resolve_project_id", return_value=str(tmp_path)):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search_nodes.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "auth"])

        assert result.exit_code == 0
        mock_client_cls.assert_called_once_with(project_id=str(tmp_path))


def test_query_works_without_project_toml():
    """dgk query without .dgk/project.toml constructs Neo4jClient with project_id=None."""
    with patch("dgk_cli.commands.query.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.query._resolve_project_id", return_value=None):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search_nodes.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "auth"])

        assert result.exit_code == 0
        mock_client_cls.assert_called_once_with(project_id=None)
