import os
import tomllib

from click.testing import CliRunner

from rei_cli.main import cli


def test_init_creates_config_file(tmp_path, monkeypatch):
    """rei init creates .rei/project.toml with sensible defaults."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0

    config_path = tmp_path / ".rei" / "project.toml"
    assert config_path.exists()

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    assert config["project"]["name"] == tmp_path.name
    assert config["project"]["root"] == "."
    assert config["scan"]["exclude"] is not None
    assert config["graph"]["backend"] == "neo4j"


def test_init_does_not_overwrite_existing(tmp_path, monkeypatch):
    """rei init does not overwrite an existing config."""
    monkeypatch.chdir(tmp_path)
    rei_dir = tmp_path / ".rei"
    rei_dir.mkdir()
    (rei_dir / "project.toml").write_text("# custom config\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "already initialized" in result.output.lower()
    assert (rei_dir / "project.toml").read_text() == "# custom config\n"


def test_init_writes_project_id_as_absolute_path(tmp_path, monkeypatch):
    """rei init writes project_id (resolved absolute path) into .rei/project.toml."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0

    config_path = tmp_path / ".rei" / "project.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    assert config["project"]["id"] == str(tmp_path)
