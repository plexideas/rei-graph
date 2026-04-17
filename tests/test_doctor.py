from unittest.mock import patch

from click.testing import CliRunner

from dgk_cli.main import cli


def test_doctor_reports_healthy_neo4j(monkeypatch):
    """dgk doctor reports healthy when Neo4j is reachable."""
    with patch("dgk_cli.commands.doctor.check_neo4j_health") as mock_check:
        mock_check.return_value = {"status": "healthy", "url": "http://localhost:7474"}
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "healthy" in result.output.lower()
        assert "neo4j" in result.output.lower()


def test_doctor_reports_unhealthy_neo4j(monkeypatch):
    """dgk doctor reports unhealthy when Neo4j is not reachable."""
    with patch("dgk_cli.commands.doctor.check_neo4j_health") as mock_check:
        mock_check.return_value = {
            "status": "unhealthy",
            "url": "http://localhost:7474",
            "error": "Connection refused",
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "unhealthy" in result.output.lower()
