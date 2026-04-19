from click.testing import CliRunner

from rei_cli.main import cli


def test_version_flag_outputs_version_string():
    """rei --version prints a version string and exits 0."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "version" in result.output.lower()
