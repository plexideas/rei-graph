from unittest.mock import MagicMock, patch, call

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
