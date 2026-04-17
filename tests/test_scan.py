import json
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from dgk_cli.main import cli


SAMPLE_INGESTER_OUTPUT = json.dumps({
    "file": "src/auth.ts",
    "nodes": [
        {"id": "module:src/auth.ts", "label": "Module", "name": "auth", "path": "src/auth.ts", "line": 1, "properties": {}},
        {"id": "function:src/auth.ts:login", "label": "Function", "name": "login", "path": "src/auth.ts", "line": 5, "properties": {"exported": True}},
    ],
    "relationships": [
        {"type": "EXPOSES", "sourceId": "module:src/auth.ts", "targetId": "function:src/auth.ts:login", "properties": {}},
        {"type": "IMPORTS", "sourceId": "module:src/auth.ts", "targetId": "module:react", "properties": {"specifiers": ["React"], "moduleSpecifier": "react"}},
    ],
})


def test_scan_invokes_ingester_and_writes_to_neo4j(tmp_path):
    """dgk scan <file> calls the TS ingester and writes results to Neo4j."""
    # Create a dummy TS file
    ts_file = tmp_path / "test.ts"
    ts_file.write_text("export function hello() {}")

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls:

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(ts_file)])

        assert result.exit_code == 0
        # Ingester was called
        mock_subprocess.run.assert_called_once()
        # Nodes were upserted
        mock_client.upsert_nodes.assert_called_once()
        nodes = mock_client.upsert_nodes.call_args[0][0]
        assert len(nodes) == 2
        # Relationships were upserted
        mock_client.upsert_relationships.assert_called_once()
        rels = mock_client.upsert_relationships.call_args[0][0]
        assert len(rels) == 2
        mock_client.close.assert_called_once()


def test_scan_reports_ingester_failure(tmp_path):
    """dgk scan <file> reports error when ingester fails."""
    ts_file = tmp_path / "bad.ts"
    ts_file.write_text("invalid content")

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient"):

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Parse error"
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(ts_file)])

        assert result.exit_code == 0
        assert "error" in result.output.lower() or "fail" in result.output.lower()


def test_scan_reports_file_not_found():
    """dgk scan reports error for non-existent file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "/nonexistent/file.ts"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower() or "error" in result.output.lower()
