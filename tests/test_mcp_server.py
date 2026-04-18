import json
from unittest.mock import MagicMock

from dgk_mcp.server import (
    get_context,
    get_neighbors,
    get_schema,
    get_summary,
    impact_analysis,
    project_status,
    scan_file,
    scan_project,
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
    """scan_project calls dgk scan <path> and returns status."""
    from unittest.mock import patch

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Done: 5 nodes, 3 relationships"

    with patch("dgk_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_project({"path": str(tmp_path)})

    mock_subprocess.run.assert_called_once_with(
        ["dgk", "scan", str(tmp_path)], capture_output=True, text=True
    )
    assert result["status"] == "ok"
    assert "5 nodes" in result["output"]


def test_scan_file_invokes_dgk_scan(tmp_path):
    """scan_file calls dgk scan <file> and returns status."""
    from unittest.mock import patch

    ts_file = str(tmp_path / "app.ts")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "Error: file not found"

    with patch("dgk_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_file({"path": ts_file})

    assert result["status"] == "error"


# ─── project.status ───────────────────────────────────────────────────────────

def test_project_status_returns_health_and_node_count():
    """project_status returns Neo4j health + total node count."""
    from unittest.mock import patch

    mock_client = MagicMock()
    mock_client.count_nodes.return_value = 42

    with patch("dgk_mcp.server.check_neo4j_health") as mock_health:
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
    """scan_project calls dgk scan <path> and returns status."""
    from unittest.mock import patch

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Done: 5 nodes, 3 relationships"

    with patch("dgk_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_project({"path": str(tmp_path)})

    mock_subprocess.run.assert_called_once_with(
        ["dgk", "scan", str(tmp_path)], capture_output=True, text=True
    )
    assert result["status"] == "ok"
    assert "5 nodes" in result["output"]


def test_scan_file_invokes_dgk_scan(tmp_path):
    """scan_file calls dgk scan <file> and returns status."""
    from unittest.mock import patch

    ts_file = str(tmp_path / "app.ts")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "Error: file not found"

    with patch("dgk_mcp.server.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        result = scan_file({"path": ts_file})

    assert result["status"] == "error"


# ─── project.status ───────────────────────────────────────────────────────────

def test_project_status_returns_health_and_node_count():
    """project_status returns Neo4j health + total node count."""
    from unittest.mock import patch

    mock_client = MagicMock()
    mock_client.count_nodes.return_value = 42

    with patch("dgk_mcp.server.check_neo4j_health") as mock_health:
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
