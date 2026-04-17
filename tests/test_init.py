import os
import tomllib

from click.testing import CliRunner

from dgk_cli.main import cli


def test_init_creates_config_file(tmp_path, monkeypatch):
    """dgk init creates .dgk/project.toml with sensible defaults."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0

    config_path = tmp_path / ".dgk" / "project.toml"
    assert config_path.exists()

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    assert config["project"]["name"] == tmp_path.name
    assert config["project"]["root"] == "."
    assert config["scan"]["exclude"] is not None
    assert config["graph"]["backend"] == "neo4j"


def test_init_does_not_overwrite_existing(tmp_path, monkeypatch):
    """dgk init does not overwrite an existing config."""
    monkeypatch.chdir(tmp_path)
    dgk_dir = tmp_path / ".dgk"
    dgk_dir.mkdir()
    (dgk_dir / "project.toml").write_text("# custom config\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "already initialized" in result.output.lower()
    assert (dgk_dir / "project.toml").read_text() == "# custom config\n"
