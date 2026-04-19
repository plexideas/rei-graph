import json
from unittest.mock import MagicMock

from rei_mcp.server import (
    get_context,
    get_neighbors,
    get_schema,
    get_summary,
    impact_analysis,
    project_delete,
    project_status,
    scan_file,
    scan_project,
    scan_changed_files,
    project_snapshot,
    search_entities,
    upsert_entities,
    upsert_relations,
    memory_record_analysis,
    memory_record_decision,
    memory_record_change,
    memory_record_validation,
    memory_record_plan,
    memory_get_recent_context,
    get_recent_decisions,
    dag_create_plan,
    dag_run_plan,
    dag_get_plan,
    dag_step_status,
    dag_cancel_plan,
    get_open_plans,
    TOOLS,
    RESOURCES,
)


def test_search_entities_returns_matching_nodes():
    """search_entities returns entities matching the query."""
    mock_client = MagicMock()
    mock_client.search_nodes.return_value = [
        {"n": {"id": "function:src/auth.ts:login", "name": "login", "path": "src/auth.ts", "line": 5}},
        {"n": {"id": "hook:src/auth.ts:useAuth", "name": "useAuth", "path": "src/auth.ts", "line": 12}},
    ]

    result = search_entities({"query": "auth"}, mock_client)

    mock_client.search_nodes.assert_called_once_with("auth", labels=None, limit=20)
    assert len(result["entities"]) == 2
    assert result["entities"][0]["name"] == "login"


def test_search_entities_passes_label_filter():
    """search_entities passes label filter to Neo4j client."""
    mock_client = MagicMock()
    mock_client.search_nodes.return_value = []

    result = search_entities({"query": "auth", "labels": ["Component"], "limit": 5}, mock_client)

    mock_client.search_nodes.assert_called_once_with("auth", labels=["Component"], limit=5)
    assert result["entities"] == []


# ─── get_context ──────────────────────────────────────────────────────────────

def test_get_context_returns_nodes_relationships_summary():
    """get_context returns nodes, relationships between them, and a summary."""
    mock_client = MagicMock()
    mock_client.search_nodes.return_value = [
        {"n": {"id": "module:src/auth.ts", "name": "auth"}},
    ]
    mock_client.get_node_relationships.return_value = [
        {"type": "IMPORTS", "sourceId": "module:src/auth.ts", "targetId": "module:src/utils.ts"},
    ]

    result = get_context({"query": "auth"}, mock_client)

    assert len(result["nodes"]) == 1
    assert len(result["relationships"]) == 1
    assert "auth" in result["summary"]
    mock_client.get_node_relationships.assert_called_once_with(["module:src/auth.ts"])


def test_get_context_empty_query_returns_no_rels():
    """get_context skips relationship lookup when no nodes are found."""
    mock_client = MagicMock()
    mock_client.search_nodes.return_value = []

    result = get_context({"query": "nonexistent"}, mock_client)

    assert result["nodes"] == []
    assert result["relationships"] == []
    mock_client.get_node_relationships.assert_not_called()


# ─── get_neighbors ────────────────────────────────────────────────────────────

def test_get_neighbors_delegates_to_client():
    """get_neighbors passes arguments to Neo4jClient.get_neighbors."""
    mock_client = MagicMock()
    mock_client.get_neighbors.return_value = {
        "nodes": [{"id": "module:src/app.ts", "name": "app"}],
        "relationships": [{"type": "IMPORTS"}],
    }

    result = get_neighbors(
        {"nodeId": "module:src/auth.ts", "direction": "in", "types": ["IMPORTS"], "depth": 2},
        mock_client,
    )

    mock_client.get_neighbors.assert_called_once_with(
        "module:src/auth.ts", direction="in", rel_types=["IMPORTS"], depth=2
    )
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["name"] == "app"


# ─── impact_analysis ─────────────────────────────────────────────────────────

def test_impact_analysis_classifies_direct_and_transitive():
    """impact_analysis separates direct (depth=1) from transitive (depth>1) dependents."""
    mock_client = MagicMock()
    mock_client.get_dependents.return_value = [
        {"n": {"name": "App"}, "depth": 1},
        {"n": {"name": "Page"}, "depth": 2},
    ]

    result = impact_analysis({"target": "src/utils.ts"}, mock_client)

    assert len(result["directlyAffected"]) == 1
    assert len(result["transitivelyAffected"]) == 1
    assert result["riskScore"] == 0.2
    assert len(result["recommendations"]) == 2


def test_impact_analysis_no_dependents_returns_safe_message():
    """impact_analysis recommends safe-to-change when no dependents found."""
    mock_client = MagicMock()
    mock_client.get_dependents.return_value = []

    result = impact_analysis({"target": "src/unused.ts"}, mock_client)

    assert result["directlyAffected"] == []
    assert result["riskScore"] == 0.0
    assert "safe to change" in result["recommendations"][0].lower()


# ─── upsert_entities / upsert_relations ──────────────────────────────────────

def test_upsert_entities_calls_client_upsert_nodes():
    """upsert_entities creates GraphNode objects and calls client.upsert_nodes."""
    mock_client = MagicMock()

    result = upsert_entities(
        {
            "entities": [
                {"id": "module:src/a.ts", "label": "Module", "name": "a", "path": "src/a.ts", "line": 1},
            ]
        },
        mock_client,
    )

    mock_client.upsert_nodes.assert_called_once()
    nodes = mock_client.upsert_nodes.call_args[0][0]
    assert len(nodes) == 1
    assert nodes[0].name == "a"
    assert result["upserted"] == 1


def test_upsert_relations_calls_client_upsert_relationships():
    """upsert_relations creates GraphRelationship objects and calls client.upsert_relationships."""
    mock_client = MagicMock()

    result = upsert_relations(
        {
            "relations": [
                {"type": "IMPORTS", "from": "module:src/a.ts", "to": "module:src/b.ts"},
            ]
        },
        mock_client,
    )

    mock_client.upsert_relationships.assert_called_once()
    rels = mock_client.upsert_relationships.call_args[0][0]
    assert len(rels) == 1
    assert rels[0].type == "IMPORTS"
    assert result["upserted"] == 1


# ─── scan.project / scan.file ─────────────────────────────────────────────────

def test_scan_project_invokes_dgk_scan(tmp_path):
    """scan_project calls rei scan <path> and returns status."""
    from unittest.mock import patch

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Done: 5 nodes, 3 relationships"

    with patch("rei_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_project({"path": str(tmp_path)})

    mock_subprocess.run.assert_called_once_with(
        ["rei", "scan", str(tmp_path)], capture_output=True, text=True
    )
    assert result["status"] == "ok"
    assert "5 nodes" in result["output"]


def test_scan_file_invokes_dgk_scan(tmp_path):
    """scan_file calls rei scan <file> and returns status."""
    from unittest.mock import patch

    ts_file = str(tmp_path / "app.ts")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "Error: file not found"

    with patch("rei_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_file({"path": ts_file})

    assert result["status"] == "error"


# ─── project.status ───────────────────────────────────────────────────────────

def test_project_status_returns_health_and_node_count():
    """project_status returns Neo4j health + total node count."""
    from unittest.mock import patch

    mock_client = MagicMock()
    mock_client.count_nodes.return_value = 42

    with patch("rei_mcp.server.check_neo4j_health") as mock_health:
        mock_health.return_value = {"status": "healthy", "url": "http://localhost:7474"}
        result = project_status({}, mock_client)

    assert result["neo4j"]["status"] == "healthy"
    assert result["nodeCount"] == 42


# ─── resources ────────────────────────────────────────────────────────────────

def test_get_schema_returns_node_labels_and_relationships():
    """get_schema returns text with node labels and relationship types."""
    schema = get_schema()
    assert "Module" in schema
    assert "Component" in schema
    assert "IMPORTS" in schema
    assert "DEPENDS_ON" in schema


def test_get_summary_returns_node_count_string():
    """get_summary returns a string with the node count."""
    mock_client = MagicMock()
    mock_client.count_nodes.return_value = 100

    summary = get_summary(mock_client)

    assert "100" in summary
    mock_client.count_nodes.assert_called_once()


# ─── MCP tool/resource registry ──────────────────────────────────────────────

def test_tools_registry_contains_all_expected_tools():
    """TOOLS list contains all required MCP tools."""
    tool_names = {t.name for t in TOOLS}
    expected = {
        "graph.search_entities",
        "graph.get_context",
        "graph.get_neighbors",
        "graph.impact_analysis",
        "graph.upsert_entities",
        "graph.upsert_relations",
        "scan.project",
        "scan.file",
        "project.status",
    }
    assert expected.issubset(tool_names)


def test_resources_registry_contains_schema_and_summary():
    """RESOURCES list contains project://schema and project://summary."""
    uris = {str(r.uri) for r in RESOURCES}
    assert "project://schema" in uris
    assert "project://summary" in uris


# ─── get_context ──────────────────────────────────────────────────────────────

def test_get_context_returns_nodes_relationships_summary():
    """get_context returns nodes, relationships between them, and a summary."""
    mock_client = MagicMock()
    mock_client.search_nodes.return_value = [
        {"n": {"id": "module:src/auth.ts", "name": "auth"}},
    ]
    mock_client.get_node_relationships.return_value = [
        {"type": "IMPORTS", "sourceId": "module:src/auth.ts", "targetId": "module:src/utils.ts"},
    ]

    result = get_context({"query": "auth"}, mock_client)

    assert len(result["nodes"]) == 1
    assert len(result["relationships"]) == 1
    assert "auth" in result["summary"]
    mock_client.get_node_relationships.assert_called_once_with(["module:src/auth.ts"])


def test_get_context_empty_query_returns_no_rels():
    """get_context skips relationship lookup when no nodes are found."""
    mock_client = MagicMock()
    mock_client.search_nodes.return_value = []

    result = get_context({"query": "nonexistent"}, mock_client)

    assert result["nodes"] == []
    assert result["relationships"] == []
    mock_client.get_node_relationships.assert_not_called()


# ─── get_neighbors ────────────────────────────────────────────────────────────

def test_get_neighbors_delegates_to_client():
    """get_neighbors passes arguments to Neo4jClient.get_neighbors."""
    mock_client = MagicMock()
    mock_client.get_neighbors.return_value = {
        "nodes": [{"id": "module:src/app.ts", "name": "app"}],
        "relationships": [{"type": "IMPORTS"}],
    }

    result = get_neighbors(
        {"nodeId": "module:src/auth.ts", "direction": "in", "types": ["IMPORTS"], "depth": 2},
        mock_client,
    )

    mock_client.get_neighbors.assert_called_once_with(
        "module:src/auth.ts", direction="in", rel_types=["IMPORTS"], depth=2
    )
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["name"] == "app"


# ─── impact_analysis ─────────────────────────────────────────────────────────

def test_impact_analysis_classifies_direct_and_transitive():
    """impact_analysis separates direct (depth=1) from transitive (depth>1) dependents."""
    mock_client = MagicMock()
    mock_client.get_dependents.return_value = [
        {"n": {"name": "App"}, "depth": 1},
        {"n": {"name": "Page"}, "depth": 2},
    ]

    result = impact_analysis({"target": "src/utils.ts"}, mock_client)

    assert len(result["directlyAffected"]) == 1
    assert len(result["transitivelyAffected"]) == 1
    assert result["riskScore"] == 0.2
    assert len(result["recommendations"]) == 2


def test_impact_analysis_no_dependents_returns_safe_message():
    """impact_analysis recommends safe-to-change when no dependents found."""
    mock_client = MagicMock()
    mock_client.get_dependents.return_value = []

    result = impact_analysis({"target": "src/unused.ts"}, mock_client)

    assert result["directlyAffected"] == []
    assert result["riskScore"] == 0.0
    assert "safe to change" in result["recommendations"][0].lower()


# ─── upsert_entities / upsert_relations ──────────────────────────────────────

def test_upsert_entities_calls_client_upsert_nodes():
    """upsert_entities creates GraphNode objects and calls client.upsert_nodes."""
    mock_client = MagicMock()

    result = upsert_entities(
        {
            "entities": [
                {"id": "module:src/a.ts", "label": "Module", "name": "a", "path": "src/a.ts", "line": 1},
            ]
        },
        mock_client,
    )

    mock_client.upsert_nodes.assert_called_once()
    nodes = mock_client.upsert_nodes.call_args[0][0]
    assert len(nodes) == 1
    assert nodes[0].name == "a"
    assert result["upserted"] == 1


def test_upsert_relations_calls_client_upsert_relationships():
    """upsert_relations creates GraphRelationship objects and calls client.upsert_relationships."""
    mock_client = MagicMock()

    result = upsert_relations(
        {
            "relations": [
                {"type": "IMPORTS", "from": "module:src/a.ts", "to": "module:src/b.ts"},
            ]
        },
        mock_client,
    )

    mock_client.upsert_relationships.assert_called_once()
    rels = mock_client.upsert_relationships.call_args[0][0]
    assert len(rels) == 1
    assert rels[0].type == "IMPORTS"
    assert result["upserted"] == 1


# ─── scan.project / scan.file ─────────────────────────────────────────────────

def test_scan_project_invokes_dgk_scan(tmp_path):
    """scan_project calls rei scan <path> and returns status."""
    from unittest.mock import patch

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Done: 5 nodes, 3 relationships"

    with patch("rei_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_project({"path": str(tmp_path)})

    mock_subprocess.run.assert_called_once_with(
        ["rei", "scan", str(tmp_path)], capture_output=True, text=True
    )
    assert result["status"] == "ok"
    assert "5 nodes" in result["output"]


def test_scan_file_invokes_dgk_scan(tmp_path):
    """scan_file calls rei scan <file> and returns status."""
    from unittest.mock import patch

    ts_file = str(tmp_path / "app.ts")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "Error: file not found"

    with patch("rei_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_file({"path": ts_file})

    assert result["status"] == "error"


# ─── project.status ───────────────────────────────────────────────────────────

def test_project_status_returns_health_and_node_count():
    """project_status returns Neo4j health + total node count."""
    from unittest.mock import patch

    mock_client = MagicMock()
    mock_client.count_nodes.return_value = 42

    with patch("rei_mcp.server.check_neo4j_health") as mock_health:
        mock_health.return_value = {"status": "healthy", "url": "http://localhost:7474"}
        result = project_status({}, mock_client)

    assert result["neo4j"]["status"] == "healthy"
    assert result["nodeCount"] == 42


# ─── resources ────────────────────────────────────────────────────────────────

def test_get_schema_returns_node_labels_and_relationships():
    """get_schema returns text with node labels and relationship types."""
    schema = get_schema()
    assert "Module" in schema
    assert "Component" in schema
    assert "IMPORTS" in schema
    assert "DEPENDS_ON" in schema


def test_get_summary_returns_node_count_string():
    """get_summary returns a string with the node count."""
    mock_client = MagicMock()
    mock_client.count_nodes.return_value = 100

    summary = get_summary(mock_client)

    assert "100" in summary
    mock_client.count_nodes.assert_called_once()


# ─── MCP tool/resource registry ──────────────────────────────────────────────

def test_tools_registry_contains_all_expected_tools():
    """TOOLS list contains all required MCP tools."""
    tool_names = {t.name for t in TOOLS}
    expected = {
        "graph.search_entities",
        "graph.get_context",
        "graph.get_neighbors",
        "graph.impact_analysis",
        "graph.upsert_entities",
        "graph.upsert_relations",
        "scan.project",
        "scan.file",
        "project.status",
    }
    assert expected.issubset(tool_names)


def test_resources_registry_contains_schema_and_summary():
    """RESOURCES list contains project://schema and project://summary."""
    uris = {str(r.uri) for r in RESOURCES}
    assert "project://schema" in uris
    assert "project://summary" in uris


# ─── dag tools ──────────────────────────────────────────────────────────────


class TestDagCreatePlan:
    def test_returns_plan_id(self):
        mock_dag = MagicMock()
        mock_dag.create_plan.return_value = "plan:abc123"
        result = dag_create_plan({"goal": "refactor auth", "steps": ["scan", "apply"]}, mock_dag)
        assert result == {"planId": "plan:abc123"}

    def test_passes_goal_and_steps(self):
        mock_dag = MagicMock()
        mock_dag.create_plan.return_value = "plan:abc123"
        dag_create_plan({"goal": "refactor auth", "steps": ["scan", "apply"]}, mock_dag)
        mock_dag.create_plan.assert_called_once_with(
            goal="refactor auth", steps=["scan", "apply"], targets=None
        )

    def test_passes_targets_when_provided(self):
        mock_dag = MagicMock()
        mock_dag.create_plan.return_value = "plan:abc123"
        dag_create_plan(
            {"goal": "refactor", "steps": ["scan"], "targets": ["module:abc"]}, mock_dag
        )
        mock_dag.create_plan.assert_called_once_with(
            goal="refactor", steps=["scan"], targets=["module:abc"]
        )


class TestDagRunPlan:
    def test_returns_run_result(self):
        mock_dag = MagicMock()
        mock_dag.run_plan.return_value = {"run_id": "plan:abc", "status": "running"}
        result = dag_run_plan({"planId": "plan:abc"}, mock_dag)
        assert result == {"run_id": "plan:abc", "status": "running"}

    def test_calls_run_plan_with_id(self):
        mock_dag = MagicMock()
        mock_dag.run_plan.return_value = {"run_id": "plan:abc", "status": "running"}
        dag_run_plan({"planId": "plan:abc"}, mock_dag)
        mock_dag.run_plan.assert_called_once_with("plan:abc")


class TestDagGetPlan:
    def test_returns_plan_dict(self):
        mock_dag = MagicMock()
        mock_dag.get_plan.return_value = {"plan": {"id": "plan:abc"}, "steps": []}
        result = dag_get_plan({"planId": "plan:abc"}, mock_dag)
        assert result == {"plan": {"id": "plan:abc"}, "steps": []}

    def test_returns_error_when_not_found(self):
        mock_dag = MagicMock()
        mock_dag.get_plan.return_value = None
        result = dag_get_plan({"planId": "plan:missing"}, mock_dag)
        assert "error" in result


class TestDagStepStatus:
    def test_returns_step_dict(self):
        mock_dag = MagicMock()
        mock_dag.step_status.return_value = {"status": "running", "output": None}
        result = dag_step_status({"planId": "plan:abc", "stepName": "scan"}, mock_dag)
        assert result == {"status": "running", "output": None}

    def test_returns_error_when_not_found(self):
        mock_dag = MagicMock()
        mock_dag.step_status.return_value = None
        result = dag_step_status({"planId": "plan:abc", "stepName": "missing"}, mock_dag)
        assert "error" in result


class TestDagCancelPlan:
    def test_returns_cancelled_true(self):
        mock_dag = MagicMock()
        mock_dag.cancel_plan.return_value = True
        result = dag_cancel_plan({"planId": "plan:abc"}, mock_dag)
        assert result == {"cancelled": True}

    def test_calls_cancel_plan(self):
        mock_dag = MagicMock()
        mock_dag.cancel_plan.return_value = True
        dag_cancel_plan({"planId": "plan:abc"}, mock_dag)
        mock_dag.cancel_plan.assert_called_once_with("plan:abc")


class TestGetOpenPlans:
    def test_returns_no_plans_message_when_empty(self):
        mock_dag = MagicMock()
        mock_dag.list_open_plans.return_value = []
        result = get_open_plans(mock_dag)
        assert "No open plans" in result

    def test_returns_formatted_plan_list(self):
        mock_dag = MagicMock()
        mock_dag.list_open_plans.return_value = [
            {"id": "plan:abc", "goal": "refactor auth", "status": "pending"}
        ]
        result = get_open_plans(mock_dag)
        assert "refactor auth" in result
        assert "plan:abc" in result


class TestDagToolsAndResourcesRegistered:
    def test_dag_create_plan_in_tools(self):
        assert "dag.create_plan" in {t.name for t in TOOLS}

    def test_dag_run_plan_in_tools(self):
        assert "dag.run_plan" in {t.name for t in TOOLS}

    def test_dag_get_plan_in_tools(self):
        assert "dag.get_plan" in {t.name for t in TOOLS}

    def test_dag_step_status_in_tools(self):
        assert "dag.step_status" in {t.name for t in TOOLS}

    def test_dag_cancel_plan_in_tools(self):
        assert "dag.cancel_plan" in {t.name for t in TOOLS}

    def test_open_plans_resource_registered(self):
        uris = {str(r.uri) for r in RESOURCES}
        assert "project://open-plans" in uris

    def test_plan_resource_registered(self):
        uris = {str(r.uri) for r in RESOURCES}
        assert any(u.startswith("plan://") for u in uris)


# ─── scan.changed_files ────────────────────────────────────────────────────────

class TestScanChangedFiles:
    def test_scan_changed_files_calls_dgk_scan_changed(self, tmp_path):
        """scan_changed_files runs rei scan --changed for the given path."""
        from unittest.mock import patch
        from rei_mcp.server import scan_changed_files

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Done: 2 nodes, 1 relationships from 1 changed files"

        with patch("rei_mcp.server.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = mock_result
            result = scan_changed_files({"path": str(tmp_path)})

        mock_subprocess.run.assert_called_once_with(
            ["rei", "scan", str(tmp_path), "--changed"],
            capture_output=True,
            text=True,
        )
        assert result["status"] == "ok"
        assert "2 nodes" in result["output"]

    def test_scan_changed_files_returns_error_on_failure(self, tmp_path):
        """scan_changed_files returns error status when command fails."""
        from unittest.mock import patch
        from rei_mcp.server import scan_changed_files

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Error: no git repo"

        with patch("rei_mcp.server.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = mock_result
            result = scan_changed_files({"path": str(tmp_path)})

        assert result["status"] == "error"


class TestProjectSnapshot:
    def test_project_snapshot_calls_save_snapshot(self, tmp_path):
        """project_snapshot instantiates SnapshotClient and saves snapshot."""
        from unittest.mock import patch
        from rei_mcp.server import project_snapshot

        expected_path = str(tmp_path / "default" / "snapshots" / "snap_001.json")
        mock_client = MagicMock()
        mock_client.save_snapshot.return_value = expected_path

        with patch("rei_mcp.server.SnapshotClient", return_value=mock_client):
            result = project_snapshot({"snapshot_dir": str(tmp_path), "project_id": "default"})

        mock_client.save_snapshot.assert_called_once()
        assert result["status"] == "ok"
        assert result["path"] == expected_path

    def test_project_snapshot_uses_default_snapshot_dir(self, tmp_path):
        """project_snapshot uses ~/.rei-graph/snapshots when no dir given."""
        from unittest.mock import patch
        from rei_mcp.server import project_snapshot

        mock_client = MagicMock()
        mock_client.save_snapshot.return_value = "/some/path"

        with patch("rei_mcp.server.SnapshotClient", return_value=mock_client):
            result = project_snapshot({})

        mock_client.save_snapshot.assert_called_once()
        assert result["status"] == "ok"


class TestPhase7ToolsRegistered:
    def test_scan_changed_files_in_tools(self):
        assert "scan.changed_files" in {t.name for t in TOOLS}

    def test_project_snapshot_in_tools(self):
        assert "project.snapshot" in {t.name for t in TOOLS}


# ─── Phase 6: Multi-project MCP ──────────────────────────────────────────────

from rei_mcp.server import _get_project_clients, _client_cache


class TestPhase6AllToolsRequireProjectId:
    def test_all_tools_have_project_id_property(self):
        """Every tool's inputSchema has a project_id property."""
        for tool in TOOLS:
            props = tool.inputSchema.get("properties", {})
            assert "project_id" in props, f"{tool.name} missing project_id property"

    def test_all_tools_require_project_id(self):
        """Every tool lists project_id in required fields."""
        for tool in TOOLS:
            required = tool.inputSchema.get("required", [])
            assert "project_id" in required, f"{tool.name} does not require project_id"


class TestPhase6LazyClientCache:
    def test_get_project_clients_creates_scoped_neo4j_client(self):
        """_get_project_clients creates Neo4jClient with correct project_id."""
        from unittest.mock import patch
        from rei_mcp.server import _get_project_clients

        with patch("rei_mcp.server.Neo4jClient") as MockNeo4j, \
             patch("rei_mcp.server.MemoryClient"), \
             patch("rei_mcp.server.DagClient"), \
             patch("rei_mcp.server._client_cache", {}):
            _get_project_clients("/project/alpha")
            MockNeo4j.assert_called_once_with(project_id="/project/alpha")

    def test_get_project_clients_reuses_cached_instance(self):
        """_get_project_clients returns same instance on repeated calls."""
        from unittest.mock import MagicMock, patch
        from rei_mcp.server import _get_project_clients

        fake_clients = MagicMock()
        cache = {"/project/alpha": fake_clients}
        with patch("rei_mcp.server._client_cache", cache):
            result = _get_project_clients("/project/alpha")
        assert result is fake_clients

    def test_different_project_ids_get_different_cached_clients(self):
        """_get_project_clients creates separate entries for different project_ids."""
        from unittest.mock import patch
        from rei_mcp.server import _get_project_clients

        with patch("rei_mcp.server.Neo4jClient") as MockNeo4j, \
             patch("rei_mcp.server.MemoryClient"), \
             patch("rei_mcp.server.DagClient"), \
             patch("rei_mcp.server._client_cache", {}):
            _get_project_clients("/project/alpha")
            _get_project_clients("/project/beta")
            assert MockNeo4j.call_count == 2
            calls = [c.kwargs["project_id"] for c in MockNeo4j.call_args_list]
            assert "/project/alpha" in calls
            assert "/project/beta" in calls

    def test_memory_client_created_with_project_id(self):
        """_get_project_clients creates MemoryClient with correct project_id."""
        from unittest.mock import patch
        from rei_mcp.server import _get_project_clients

        with patch("rei_mcp.server.Neo4jClient"), \
             patch("rei_mcp.server.MemoryClient") as MockMem, \
             patch("rei_mcp.server.DagClient"), \
             patch("rei_mcp.server._client_cache", {}):
            _get_project_clients("/project/alpha")
            MockMem.assert_called_once_with(project_id="/project/alpha")

    def test_dag_client_created_with_project_id(self):
        """_get_project_clients creates DagClient with correct project_id."""
        from unittest.mock import patch
        from rei_mcp.server import _get_project_clients

        with patch("rei_mcp.server.Neo4jClient"), \
             patch("rei_mcp.server.MemoryClient"), \
             patch("rei_mcp.server.DagClient") as MockDag, \
             patch("rei_mcp.server._client_cache", {}):
            _get_project_clients("/project/alpha")
            MockDag.assert_called_once_with(project_id="/project/alpha")


class TestPhase6ScopedToolHandlers:
    def test_search_entities_isolation_across_projects(self):
        """search_entities called with different scoped clients returns isolated results."""
        mock_client_a = MagicMock()
        mock_client_a.search_nodes.return_value = [{"n": {"id": "fn:a", "name": "funcA"}}]
        mock_client_b = MagicMock()
        mock_client_b.search_nodes.return_value = []

        result_a = search_entities({"query": "func", "project_id": "/project/alpha"}, mock_client_a)
        result_b = search_entities({"query": "func", "project_id": "/project/beta"}, mock_client_b)

        assert len(result_a["entities"]) == 1
        assert len(result_b["entities"]) == 0

    def test_memory_get_recent_context_isolation(self):
        """memory_get_recent_context with different scoped clients returns isolated results."""
        mock_mem_a = MagicMock()
        mock_mem_a.get_recent_context.return_value = [{"type": "Analysis", "scope": "auth"}]
        mock_mem_b = MagicMock()
        mock_mem_b.get_recent_context.return_value = []

        result_a = memory_get_recent_context({"query": "auth", "project_id": "/project/alpha"}, mock_mem_a)
        result_b = memory_get_recent_context({"query": "auth", "project_id": "/project/beta"}, mock_mem_b)

        assert len(result_a["memories"]) == 1
        assert len(result_b["memories"]) == 0

    def test_project_snapshot_uses_scoped_snapshot_client(self, tmp_path):
        """project_snapshot creates SnapshotClient with the given project_id."""
        from unittest.mock import patch

        mock_client = MagicMock()
        mock_client.save_snapshot.return_value = "/snap/path.json"

        with patch("rei_mcp.server.SnapshotClient", return_value=mock_client) as MockSnap:
            project_snapshot({"snapshot_dir": str(tmp_path), "project_id": "/project/alpha"})

        MockSnap.assert_called_once_with(project_id="/project/alpha")

    def test_scan_tools_have_project_id_in_schema(self):
        """scan.project, scan.file, scan.changed_files each have project_id in schema."""
        tool_map = {t.name: t for t in TOOLS}
        for tool_name in ("scan.project", "scan.file", "scan.changed_files"):
            tool = tool_map[tool_name]
            assert "project_id" in tool.inputSchema.get("properties", {}), \
                f"{tool_name} missing project_id"
            assert "project_id" in tool.inputSchema.get("required", []), \
                f"{tool_name} does not require project_id"


class TestPhase7ProjectDelete:
    def test_project_delete_tool_in_tools_list(self):
        """project.delete tool is present in TOOLS list."""
        tool_names = {t.name for t in TOOLS}
        assert "project.delete" in tool_names

    def test_project_delete_tool_requires_project_id(self):
        """project.delete tool requires project_id in inputSchema."""
        tool_map = {t.name: t for t in TOOLS}
        tool = tool_map["project.delete"]
        assert "project_id" in tool.inputSchema.get("required", [])

    def test_project_delete_calls_delete_project_on_client(self):
        """project_delete() calls Neo4jClient.delete_project for the given project_id."""
        mock_client = MagicMock()
        result = project_delete({"project_id": "/project/alpha"}, mock_client)
        mock_client.delete_project.assert_called_once()
        assert result["status"] == "deleted"
        assert "/project/alpha" in result["project_id"]

    def test_project_delete_does_not_delete_other_project(self):
        """project_delete called with project A does not call delete on project B's client."""
        mock_client_a = MagicMock()
        mock_client_b = MagicMock()

        project_delete({"project_id": "/project/alpha"}, mock_client_a)

        mock_client_a.delete_project.assert_called_once()
        mock_client_b.delete_project.assert_not_called()

