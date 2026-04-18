"""Tests for DagClient — TDD Phase 6."""

from unittest.mock import MagicMock, patch

import pytest

from dgk_storage.dag_client import DagClient


@pytest.fixture
def mock_driver():
    with patch("dgk_storage.dag_client.GraphDatabase") as mock_gdb:
        mock_driver_ = MagicMock()
        mock_session = MagicMock()
        mock_driver_.session.return_value.__enter__ = lambda s, *a: mock_session
        mock_driver_.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value = mock_driver_
        yield mock_driver_, mock_session


class TestCreatePlan:
    def test_returns_plan_id_with_prefix(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        plan_id = client.create_plan("refactor auth", ["scan", "analyze", "apply"])
        assert plan_id.startswith("plan:")

    def test_creates_plan_node_in_neo4j(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        client.create_plan("refactor auth", ["scan"])
        assert mock_session.run.called

    def test_creates_step_nodes_for_each_step(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        client.create_plan("refactor auth", ["scan", "analyze", "apply"])
        # 1 plan node + 3 step nodes = at least 4 calls
        assert mock_session.run.call_count >= 4

    def test_creates_proposes_relationships_for_targets(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        client.create_plan("refactor", ["scan"], targets=["module:abc", "module:def"])
        # 1 plan + 1 step + 2 targets = at least 4 calls
        assert mock_session.run.call_count >= 4

    def test_no_extra_calls_without_targets(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        client.create_plan("refactor", ["scan", "apply"])
        # 1 plan + 2 steps, no PROPOSES calls
        assert mock_session.run.call_count == 3


class TestGetPlan:
    def test_returns_none_for_unknown_plan(self, mock_driver):
        _, mock_session = mock_driver
        mock_session.run.return_value.single.return_value = None
        client = DagClient()
        result = client.get_plan("plan:nonexistent")
        assert result is None

    def test_returns_dict_with_plan_and_steps_keys(self, mock_driver):
        _, mock_session = mock_driver

        mock_plan_result = MagicMock()
        mock_plan_record = MagicMock()
        mock_plan_record.__getitem__ = lambda s, k: {
            "id": "plan:abc123",
            "goal": "refactor",
            "status": "pending",
            "steps_count": 2,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        mock_plan_result.single.return_value = mock_plan_record

        mock_steps_result = MagicMock()
        mock_steps_result.__iter__ = lambda s: iter([])

        mock_session.run.side_effect = [mock_plan_result, mock_steps_result]

        client = DagClient()
        result = client.get_plan("plan:abc123")
        assert result is not None
        assert "plan" in result
        assert "steps" in result

    def test_returns_steps_list(self, mock_driver):
        _, mock_session = mock_driver

        mock_plan_result = MagicMock()
        mock_plan_record = MagicMock()
        mock_plan_record.__getitem__ = lambda s, k: {
            "id": "plan:abc123",
            "goal": "refactor",
            "status": "pending",
            "steps_count": 1,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        mock_plan_result.single.return_value = mock_plan_record

        mock_step_record = MagicMock()
        mock_step_record.__getitem__ = lambda s, k: {
            "id": "plan:abc123:step:0",
            "plan_id": "plan:abc123",
            "name": "scan",
            "index": 0,
            "status": "pending",
            "output": None,
            "error": None,
        }
        mock_steps_result = MagicMock()
        mock_steps_result.__iter__ = lambda s: iter([mock_step_record])

        mock_session.run.side_effect = [mock_plan_result, mock_steps_result]

        client = DagClient()
        result = client.get_plan("plan:abc123")
        assert len(result["steps"]) == 1


class TestRunPlan:
    def test_returns_run_id_and_running_status(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        result = client.run_plan("plan:abc")
        assert result["run_id"] == "plan:abc"
        assert result["status"] == "running"

    def test_updates_plan_status_in_neo4j(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        client.run_plan("plan:abc")
        assert mock_session.run.called


class TestStepStatus:
    def test_returns_none_for_unknown_step(self, mock_driver):
        _, mock_session = mock_driver
        mock_session.run.return_value.single.return_value = None
        client = DagClient()
        result = client.step_status("plan:abc", "nonexistent-step")
        assert result is None

    def test_returns_step_dict(self, mock_driver):
        _, mock_session = mock_driver
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda s, k: {
            "id": "plan:abc:step:0",
            "plan_id": "plan:abc",
            "name": "scan",
            "index": 0,
            "status": "running",
            "output": None,
            "error": None,
        }
        mock_session.run.return_value.single.return_value = mock_record
        client = DagClient()
        result = client.step_status("plan:abc", "scan")
        assert result is not None
        assert isinstance(result, dict)


class TestCancelPlan:
    def test_returns_true(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        result = client.cancel_plan("plan:abc")
        assert result is True

    def test_calls_neo4j_to_cancel(self, mock_driver):
        _, mock_session = mock_driver
        client = DagClient()
        client.cancel_plan("plan:abc")
        assert mock_session.run.called


class TestListOpenPlans:
    def test_returns_empty_list_when_none(self, mock_driver):
        _, mock_session = mock_driver
        mock_session.run.return_value.__iter__ = lambda s: iter([])
        client = DagClient()
        result = client.list_open_plans()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_returns_plan_dicts(self, mock_driver):
        _, mock_session = mock_driver
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda s, k: {
            "id": "plan:abc",
            "goal": "refactor auth",
            "status": "pending",
            "steps_count": 3,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        mock_session.run.return_value.__iter__ = lambda s: iter([mock_record])
        client = DagClient()
        result = client.list_open_plans()
        assert len(result) == 1
