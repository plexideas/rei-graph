from unittest.mock import patch, MagicMock
from pathlib import Path

from click.testing import CliRunner

from rei_cli.main import cli


def test_plan_creates_plan_and_shows_id():
    """rei plan <goal> <step>... creates a DAG plan and echoes the plan ID."""
    with patch("rei_cli.commands.plan.DagClient") as mock_cls:
        mock_dag = MagicMock()
        mock_cls.return_value = mock_dag
        mock_dag.create_plan.return_value = "plan:abc123"

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "refactor auth", "scan", "apply", "test"])

        assert result.exit_code == 0
        mock_dag.create_plan.assert_called_once_with(
            goal="refactor auth", steps=["scan", "apply", "test"]
        )
        assert "plan:abc123" in result.output
        mock_dag.close.assert_called_once()


def test_plan_requires_at_least_one_step():
    """rei plan <goal> with no steps should fail."""
    runner = CliRunner()
    result = runner.invoke(cli, ["plan", "refactor auth"])
    assert result.exit_code != 0


def test_plans_lists_open_plans():
    """rei plans shows pending/running plans."""
    with patch("rei_cli.commands.plan.DagClient") as mock_cls:
        mock_dag = MagicMock()
        mock_cls.return_value = mock_dag
        mock_dag.list_open_plans.return_value = [
            {"id": "plan:abc123", "goal": "refactor auth", "status": "pending"}
        ]

        runner = CliRunner()
        result = runner.invoke(cli, ["plans"])

        assert result.exit_code == 0
        assert "plan:abc123" in result.output
        assert "refactor auth" in result.output
        mock_dag.close.assert_called_once()


def test_plans_shows_message_when_no_open_plans():
    """rei plans shows 'no open plans' when list is empty."""
    with patch("rei_cli.commands.plan.DagClient") as mock_cls:
        mock_dag = MagicMock()
        mock_cls.return_value = mock_dag
        mock_dag.list_open_plans.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["plans"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output
        mock_dag.close.assert_called_once()


# ─── Project scoping ─────────────────────────────────────────────────────────

def test_plan_resolves_project_id(tmp_path):
    """rei plan resolves the current directory as project_id and passes it to DagClient."""
    # Create a .rei/project.toml with a project id
    rei_dir = tmp_path / ".rei"
    rei_dir.mkdir()
    (rei_dir / "project.toml").write_text(
        '[project]\nid = "/home/user/myproject"\n'
    )

    with patch("rei_cli.commands.plan.DagClient") as mock_cls, \
         patch("rei_cli.commands.plan._resolve_project_id", return_value="/home/user/myproject"):
        mock_dag = MagicMock()
        mock_cls.return_value = mock_dag
        mock_dag.create_plan.return_value = "plan:abc123"

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "refactor auth", "scan", "apply"])

        assert result.exit_code == 0
        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("project_id") == "/home/user/myproject"


def test_plans_resolves_project_id():
    """rei plans resolves the current directory as project_id and passes it to DagClient."""
    with patch("rei_cli.commands.plan.DagClient") as mock_cls, \
         patch("rei_cli.commands.plan._resolve_project_id", return_value="/home/user/myproject"):
        mock_dag = MagicMock()
        mock_cls.return_value = mock_dag
        mock_dag.list_open_plans.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["plans"])

        assert result.exit_code == 0
        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("project_id") == "/home/user/myproject"
