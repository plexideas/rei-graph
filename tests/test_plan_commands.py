from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from dgk_cli.main import cli


def test_plan_creates_plan_and_shows_id():
    """dgk plan <goal> <step>... creates a DAG plan and echoes the plan ID."""
    with patch("dgk_cli.commands.plan.DagClient") as mock_cls:
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
    """dgk plan <goal> with no steps should fail."""
    runner = CliRunner()
    result = runner.invoke(cli, ["plan", "refactor auth"])
    assert result.exit_code != 0


def test_plans_lists_open_plans():
    """dgk plans shows pending/running plans."""
    with patch("dgk_cli.commands.plan.DagClient") as mock_cls:
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
    """dgk plans shows 'no open plans' when list is empty."""
    with patch("dgk_cli.commands.plan.DagClient") as mock_cls:
        mock_dag = MagicMock()
        mock_cls.return_value = mock_dag
        mock_dag.list_open_plans.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["plans"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output
        mock_dag.close.assert_called_once()
