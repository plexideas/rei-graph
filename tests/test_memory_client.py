"""Tests for MemoryClient — TDD (red/green per slice)."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch


# ─── Slice 1: record_analysis creates an Analysis node ───────────────────────

class TestRecordAnalysis:
    def _make_client(self):
        with patch("dgk_storage.memory_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            from dgk_storage.memory_client import MemoryClient
            client = MemoryClient()
        return client, mock_session

    def test_record_analysis_returns_analysis_id(self):
        client, _ = self._make_client()
        result = client.record_analysis(scope="auth module", findings="No caching found")
        assert result.startswith("analysis:")

    def test_record_analysis_creates_analysis_node(self):
        client, mock_session = self._make_client()
        client.record_analysis(scope="auth module", findings="No caching found")
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("Analysis" in q for q in queries), "Expected Analysis node creation"

    def test_record_analysis_stores_scope_and_findings(self):
        client, mock_session = self._make_client()
        client.record_analysis(scope="auth module", findings="No caching found")
        params_list = [c.args[1] if len(c.args) > 1 else c.kwargs for c in mock_session.run.call_args_list]
        combined = str(params_list)
        assert "auth module" in combined
        assert "No caching found" in combined

    def test_record_analysis_with_related_nodes_creates_observed_in_rels(self):
        client, mock_session = self._make_client()
        client.record_analysis(
            scope="auth module",
            findings="No caching",
            related_nodes=["module:src/auth.ts"],
        )
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("OBSERVED_IN" in q for q in queries), "Expected OBSERVED_IN relationship"


# ─── Slice 2: record_decision creates a Decision node ────────────────────────

class TestRecordDecision:
    def _make_client(self):
        with patch("dgk_storage.memory_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            from dgk_storage.memory_client import MemoryClient
            client = MemoryClient()
        return client, mock_session

    def test_record_decision_returns_decision_id(self):
        client, _ = self._make_client()
        result = client.record_decision(
            context="session parsing", choice="reuse middleware", rationale="DRY principle"
        )
        assert result.startswith("decision:")

    def test_record_decision_creates_decision_node(self):
        client, mock_session = self._make_client()
        client.record_decision(
            context="session parsing", choice="reuse middleware", rationale="DRY principle"
        )
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("Decision" in q for q in queries)

    def test_record_decision_based_on_creates_based_on_rels(self):
        client, mock_session = self._make_client()
        client.record_decision(
            context="session parsing",
            choice="reuse middleware",
            rationale="DRY principle",
            based_on=["analysis:abc123"],
        )
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("BASED_ON" in q for q in queries)


# ─── Slice 3: record_change creates a Change node ────────────────────────────

class TestRecordChange:
    def _make_client(self):
        with patch("dgk_storage.memory_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            from dgk_storage.memory_client import MemoryClient
            client = MemoryClient()
        return client, mock_session

    def test_record_change_returns_change_id(self):
        client, _ = self._make_client()
        result = client.record_change(change_type="refactor", description="Extract auth logic")
        assert result.startswith("change:")

    def test_record_change_creates_change_node(self):
        client, mock_session = self._make_client()
        client.record_change(change_type="refactor", description="Extract auth logic")
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("Change" in q for q in queries)

    def test_record_change_with_affected_files_creates_affects_rels(self):
        client, mock_session = self._make_client()
        client.record_change(
            change_type="refactor",
            description="Extract auth",
            affected_files=["src/auth.ts", "src/login.tsx"],
        )
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("AFFECTS" in q for q in queries)


# ─── Slice 4: record_validation creates a Validation node ────────────────────

class TestRecordValidation:
    def _make_client(self):
        with patch("dgk_storage.memory_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            from dgk_storage.memory_client import MemoryClient
            client = MemoryClient()
        return client, mock_session

    def test_record_validation_returns_validation_id(self):
        client, _ = self._make_client()
        result = client.record_validation(val_type="test", status="passed", details="All tests pass")
        assert result.startswith("validation:")

    def test_record_validation_creates_validation_node(self):
        client, mock_session = self._make_client()
        client.record_validation(val_type="test", status="passed", details="All tests pass")
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("Validation" in q for q in queries)

    def test_record_validation_with_validates_creates_validated_by_rel(self):
        client, mock_session = self._make_client()
        client.record_validation(
            val_type="test",
            status="passed",
            details="All tests pass",
            validates="change:abc123",
        )
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("VALIDATED_BY" in q for q in queries)


# ─── Slice 5: record_plan creates a Plan node ────────────────────────────────

class TestRecordPlan:
    def _make_client(self):
        with patch("dgk_storage.memory_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            from dgk_storage.memory_client import MemoryClient
            client = MemoryClient()
        return client, mock_session

    def test_record_plan_returns_plan_id(self):
        client, _ = self._make_client()
        result = client.record_plan(goal="extract auth", steps=["scan", "refactor"])
        assert result.startswith("plan:")

    def test_record_plan_creates_plan_node(self):
        client, mock_session = self._make_client()
        client.record_plan(goal="extract auth", steps=["scan", "refactor"])
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("Plan" in q for q in queries)

    def test_record_plan_with_targets_creates_proposes_rels(self):
        client, mock_session = self._make_client()
        client.record_plan(
            goal="extract auth",
            steps=["scan", "refactor"],
            targets=["module:src/auth.ts"],
        )
        queries = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("PROPOSES" in q for q in queries)


# ─── Slice 6: get_recent_context queries memory nodes ────────────────────────

class TestGetRecentContext:
    def _make_client_with_result(self, rows):
        with patch("dgk_storage.memory_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            mock_session.run.return_value = rows
            from dgk_storage.memory_client import MemoryClient
            client = MemoryClient()
        return client, mock_session

    def test_get_recent_context_returns_list(self):
        client, _ = self._make_client_with_result([])
        result = client.get_recent_context(query="auth")
        assert isinstance(result, list)

    def test_get_recent_context_runs_query(self):
        client, mock_session = self._make_client_with_result([])
        client.get_recent_context(query="auth")
        assert mock_session.run.called

    def test_get_recent_context_uses_text_filter(self):
        client, mock_session = self._make_client_with_result([])
        client.get_recent_context(query="auth")
        query_str = mock_session.run.call_args[0][0]
        assert "CONTAINS" in query_str or "$query" in query_str

    def test_get_recent_context_respects_limit(self):
        client, mock_session = self._make_client_with_result([])
        client.get_recent_context(query="auth", limit=5)
        params = mock_session.run.call_args[0][1] if len(mock_session.run.call_args[0]) > 1 else mock_session.run.call_args[1]
        assert params.get("limit") == 5 or "5" in str(mock_session.run.call_args)


# ─── Slice 7: get_recent_decisions returns Decision nodes ────────────────────

class TestGetRecentDecisions:
    def _make_client_with_result(self, rows):
        with patch("dgk_storage.memory_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = lambda s, *a: mock_session
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            mock_session.run.return_value = []
            from dgk_storage.memory_client import MemoryClient
            client = MemoryClient()
        return client, mock_session

    def test_get_recent_decisions_returns_list(self):
        client, _ = self._make_client_with_result([])
        result = client.get_recent_decisions()
        assert isinstance(result, list)

    def test_get_recent_decisions_queries_decision_nodes(self):
        client, mock_session = self._make_client_with_result([])
        client.get_recent_decisions()
        query_str = mock_session.run.call_args[0][0]
        assert "Decision" in query_str
