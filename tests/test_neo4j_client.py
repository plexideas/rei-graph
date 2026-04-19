from unittest.mock import MagicMock, patch, call

from dgk_core.hashing import project_hash
from dgk_core.schemas import GraphNode, GraphRelationship, ScanResult
from dgk_storage.neo4j_client import Neo4jClient


SAMPLE_NODES = [
    GraphNode(id="module:src/auth.ts", label="Module", name="auth", path="src/auth.ts"),
    GraphNode(
        id="function:src/auth.ts:login",
        label="Function",
        name="login",
        path="src/auth.ts",
        line=5,
        properties={"exported": True},
    ),
]

SAMPLE_RELS = [
    GraphRelationship(
        type="EXPOSES",
        source_id="module:src/auth.ts",
        target_id="function:src/auth.ts:login",
    ),
]


class TestNeo4jClientUpsertNodes:
    def test_upsert_nodes_calls_merge_for_each_node(self):
        """Neo4j client issues MERGE queries for each node."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

            client.upsert_nodes(SAMPLE_NODES)

            assert mock_session.run.call_count == 2
            # Check that MERGE is used (not CREATE) for upsert behavior
            for c in mock_session.run.call_args_list:
                assert "MERGE" in c[0][0]


class TestNeo4jClientUpsertRelationships:
    def test_upsert_relationships_calls_merge(self):
        """Neo4j client issues MERGE queries for relationships."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")
        rels = [
            GraphRelationship(
                type="EXPOSES",
                source_id="module:src/auth.ts",
                target_id="function:src/auth.ts:login",
            ),
        ]

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

            client.upsert_relationships(rels)

            assert mock_session.run.call_count == 1
            assert "MERGE" in mock_session.run.call_args[0][0]


class TestNeo4jClientSearch:
    def test_search_nodes_returns_matching_results(self):
        """Neo4j client searches nodes by name pattern."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        mock_record = MagicMock()
        mock_record.data.return_value = {
            "n": {"id": "function:src/auth.ts:login", "name": "login", "path": "src/auth.ts"}
        }

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value = [mock_record]

            results = client.search_nodes("login")

            assert len(results) == 1
            assert mock_session.run.called

    def test_search_nodes_with_label_filter(self):
        """Neo4j client can filter search by label."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value = []

            client.search_nodes("login", labels=["Function"])

            query = mock_session.run.call_args[0][0]
            assert "Function" in query


class TestNeo4jClientUpsertIdempotency:
    def test_upsert_same_nodes_twice_uses_merge_with_same_id(self):
        """Upserting the same nodes twice issues MERGE with the same id, ensuring no duplicates."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

            # Upsert the same nodes twice
            client.upsert_nodes(SAMPLE_NODES)
            client.upsert_nodes(SAMPLE_NODES)

            # Should be 4 calls total (2 nodes x 2 runs), all using MERGE
            assert mock_session.run.call_count == 4
            for c in mock_session.run.call_args_list:
                assert "MERGE" in c[0][0]
                assert "CREATE" not in c[0][0]

            # Both runs use the same node IDs
            first_ids = [mock_session.run.call_args_list[i][0][1]["id"] for i in range(2)]
            second_ids = [mock_session.run.call_args_list[i][0][1]["id"] for i in range(2, 4)]
            assert first_ids == second_ids

    def test_upsert_same_relationships_twice_uses_merge(self):
        """Upserting the same relationships twice issues MERGE, ensuring no duplicates."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

            client.upsert_relationships(SAMPLE_RELS)
            client.upsert_relationships(SAMPLE_RELS)

            assert mock_session.run.call_count == 2
            for c in mock_session.run.call_args_list:
                assert "MERGE" in c[0][0]


class TestNeo4jClientGetDependents:
    def test_get_dependents_returns_direct_importers(self):
        """get_dependents returns modules that directly IMPORTS the target file."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        mock_record_1 = MagicMock()
        mock_record_1.data.return_value = {
            "n": {"id": "module:src/login.ts", "name": "login", "path": "src/login.ts"},
            "depth": 1,
        }

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value = [mock_record_1]

            results = client.get_dependents("src/auth.ts")

            assert len(results) == 1
            assert results[0]["n"]["path"] == "src/login.ts"
            # Cypher should use variable-length path for IMPORTS
            query = mock_session.run.call_args[0][0]
            assert "IMPORTS" in query

    def test_get_dependents_returns_transitive_importers(self):
        """get_dependents with depth>1 returns transitive dependents."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        mock_record_1 = MagicMock()
        mock_record_1.data.return_value = {
            "n": {"id": "module:src/login.ts", "name": "login", "path": "src/login.ts"},
            "depth": 1,
        }
        mock_record_2 = MagicMock()
        mock_record_2.data.return_value = {
            "n": {"id": "module:src/app.ts", "name": "app", "path": "src/app.ts"},
            "depth": 2,
        }

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value = [mock_record_1, mock_record_2]

            results = client.get_dependents("src/auth.ts", max_depth=3)

            assert len(results) == 2
            query = mock_session.run.call_args[0][0]
            params = mock_session.run.call_args[0][1]
            assert params["max_depth"] == 3


class TestNeo4jClientGetNeighbors:
    def test_get_neighbors_queries_adjacent_nodes(self):
        """get_neighbors returns nodes adjacent to the given node."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(side_effect=lambda k: {"m": {"id": "module:src/utils.ts"}, "relType": "IMPORTS"}[k])

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value = [mock_record]

            result = client.get_neighbors("module:src/auth.ts", direction="out")

            query = mock_session.run.call_args[0][0]
            assert "node_id" in str(mock_session.run.call_args)
            assert "->" in query  # outgoing direction
            assert len(result["nodes"]) == 1
            assert result["relationships"][0]["type"] == "IMPORTS"

    def test_get_neighbors_in_direction_uses_incoming_arrow(self):
        """get_neighbors with direction='in' uses incoming arrow in Cypher."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value = []

            client.get_neighbors("module:src/auth.ts", direction="in")

            query = mock_session.run.call_args[0][0]
            assert "<-" in query  # incoming direction


class TestNeo4jClientCountNodes:
    def test_count_nodes_returns_integer(self):
        """count_nodes returns the total number of nodes."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=42)

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value.single.return_value = mock_record

            count = client.count_nodes()

            assert count == 42
            query = mock_session.run.call_args[0][0]
            assert "count" in query.lower()


class TestNeo4jClientGetNodeRelationships:
    def test_get_node_relationships_returns_rels_between_given_ids(self):
        """get_node_relationships returns relationships between a set of node IDs."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")

        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "source": "module:src/auth.ts",
                "relType": "IMPORTS",
                "target": "module:src/utils.ts",
            }[k]
        )

        with patch.object(client, "_driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value = [mock_record]

            results = client.get_node_relationships(["module:src/auth.ts", "module:src/utils.ts"])

            assert len(results) == 1
            assert results[0]["type"] == "IMPORTS"
            assert results[0]["sourceId"] == "module:src/auth.ts"
            assert results[0]["targetId"] == "module:src/utils.ts"


# ---------------------------------------------------------------------------
# Phase 1 – Project isolation tests
# ---------------------------------------------------------------------------

PROJECT_A = "/home/user/project-a"
PROJECT_B = "/home/user/project-b"
HASH_A = project_hash(PROJECT_A)
HASH_B = project_hash(PROJECT_B)


def _make_scoped_client(project_id: str) -> Neo4jClient:
    """Create a Neo4jClient with project_id, patching out the driver."""
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
        project_id=project_id,
    )
    return client


def _mock_driver(client: Neo4jClient) -> tuple[MagicMock, MagicMock]:
    """Patch the driver on *client* and return (driver_mock, session_mock)."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    client._driver = mock_driver
    return mock_driver, mock_session


class TestNeo4jClientProjectScoping:
    """Verify that project_id scoping is applied to all Neo4j operations."""

    def test_client_stores_project_id_and_hash(self):
        """Neo4jClient stores the project_id and computes the hash at construction."""
        client = _make_scoped_client(PROJECT_A)
        _mock_driver(client)

        assert client.project_id == PROJECT_A
        assert client.project_hash == HASH_A

    def test_upsert_nodes_stamps_project_id_and_prefixes_ids(self):
        """upsert_nodes sets project_id property and prefixes node IDs with the hash."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)

        nodes = [GraphNode(id="module:src/auth.ts", label="Module", name="auth", path="src/auth.ts")]
        client.upsert_nodes(nodes)

        # Exactly one MERGE call for the node (Project MERGE happens at construction)
        args = mock_session.run.call_args_list
        # Find the MERGE call for the Module node
        node_calls = [c for c in args if "Module" in c[0][0]]
        assert len(node_calls) == 1
        cypher, params = node_calls[0][0]
        assert params["id"] == f"module:{HASH_A}:src/auth.ts"
        assert params["project_id"] == PROJECT_A
        assert "project_id" in cypher

    def test_upsert_relationships_scopes_match_to_project(self):
        """upsert_relationships matches source/target within the scoped project."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)

        rels = [
            GraphRelationship(
                type="EXPOSES",
                source_id="module:src/auth.ts",
                target_id="function:src/auth.ts:login",
            ),
        ]
        client.upsert_relationships(rels)

        cypher, params = mock_session.run.call_args[0]
        assert params["source_id"] == f"module:{HASH_A}:src/auth.ts"
        assert params["target_id"] == f"function:{HASH_A}:src/auth.ts:login"
        assert "project_id" in cypher

    def test_search_nodes_filters_by_project_id(self):
        """search_nodes includes project_id filter in the Cypher query."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)
        mock_session.run.return_value = []

        client.search_nodes("login")

        cypher, params = mock_session.run.call_args[0]
        assert "project_id" in cypher
        assert params["project_id"] == PROJECT_A

    def test_get_dependents_filters_by_project_id(self):
        """get_dependents includes project_id filter in the Cypher query."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)
        mock_session.run.return_value = []

        client.get_dependents("src/auth.ts")

        cypher, params = mock_session.run.call_args[0]
        assert params["project_id"] == PROJECT_A
        assert "project_id" in cypher

    def test_count_nodes_filters_by_project_id(self):
        """count_nodes includes project_id filter in the Cypher query."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=5)
        mock_session.run.return_value.single.return_value = mock_record

        client.count_nodes()

        cypher, params = mock_session.run.call_args[0]
        assert params["project_id"] == PROJECT_A
        assert "project_id" in cypher

    def test_delete_file_nodes_filters_by_project_id(self):
        """delete_file_nodes includes project_id filter in the Cypher query."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)

        client.delete_file_nodes("src/auth.ts")

        cypher, params = mock_session.run.call_args[0]
        assert params["project_id"] == PROJECT_A
        assert "project_id" in cypher

    def test_get_neighbors_filters_by_project_id(self):
        """get_neighbors includes project_id filter."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)
        mock_session.run.return_value = []

        client.get_neighbors("module:src/auth.ts")

        cypher, params = mock_session.run.call_args[0]
        assert params["project_id"] == PROJECT_A

    def test_two_projects_produce_different_node_ids(self):
        """Two clients with different project_ids prefix node IDs differently."""
        client_a = _make_scoped_client(PROJECT_A)
        _, sess_a = _mock_driver(client_a)
        client_b = _make_scoped_client(PROJECT_B)
        _, sess_b = _mock_driver(client_b)

        nodes = [GraphNode(id="module:src/auth.ts", label="Module", name="auth", path="src/auth.ts")]

        client_a.upsert_nodes(nodes)
        client_b.upsert_nodes(nodes)

        # Extract the id param from each call (skip Project MERGE calls)
        id_a = [c for c in sess_a.run.call_args_list if "Module" in c[0][0]][0][0][1]["id"]
        id_b = [c for c in sess_b.run.call_args_list if "Module" in c[0][0]][0][0][1]["id"]

        assert id_a != id_b
        assert HASH_A in id_a
        assert HASH_B in id_b

    def test_project_node_merged_on_construction(self):
        """A Project registry node is MERGEd when the client is constructed."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)

        # The Project MERGE should have been issued during construction
        # but since we mock after construction, let's verify via ensure_project
        client._ensure_project_node()

        calls = mock_session.run.call_args_list
        project_calls = [c for c in calls if "Project" in c[0][0] and "MERGE" in c[0][0]]
        assert len(project_calls) >= 1
        params = project_calls[0][0][1]
        assert params["id"] == PROJECT_A
        assert params["hash"] == HASH_A


class TestNeo4jClientProjectLookup:
    """Tests for get_project and update_last_scanned methods."""

    def test_get_project_returns_none_when_not_found(self):
        """get_project returns None when no Project node exists for the id."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)
        mock_session.run.return_value.single.return_value = None

        result = client.get_project()

        assert result is None
        cypher = mock_session.run.call_args[0][0]
        assert "Project" in cypher
        assert mock_session.run.call_args[0][1]["id"] == PROJECT_A

    def test_get_project_returns_properties_when_found(self):
        """get_project returns a dict of project properties when the node exists."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(
            return_value={
                "id": PROJECT_A,
                "name": "project-a",
                "hash": HASH_A,
                "last_scanned_at": "2026-04-18T10:00:00+00:00",
            }
        )
        mock_session.run.return_value.single.return_value = mock_record

        result = client.get_project()

        assert result is not None
        assert result["id"] == PROJECT_A
        assert result["last_scanned_at"] == "2026-04-18T10:00:00+00:00"

    def test_get_project_returns_none_without_project_id(self):
        """get_project returns None when client has no project_id."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")
        _, mock_session = _mock_driver(client)

        result = client.get_project()

        assert result is None
        mock_session.run.assert_not_called()

    def test_update_last_scanned_sets_timestamp(self):
        """update_last_scanned sets last_scanned_at on the Project node."""
        client = _make_scoped_client(PROJECT_A)
        _, mock_session = _mock_driver(client)

        client.update_last_scanned()

        cypher, params = mock_session.run.call_args[0]
        assert "last_scanned_at" in cypher
        assert "Project" in cypher
        assert params["id"] == PROJECT_A
        # Timestamp should be an ISO-format string
        assert "T" in params["last_scanned_at"]

    def test_update_last_scanned_noop_without_project_id(self):
        """update_last_scanned is a no-op when client has no project_id."""
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test")
        _, mock_session = _mock_driver(client)

        client.update_last_scanned()

        mock_session.run.assert_not_called()
