from unittest.mock import patch, MagicMock


def _make_client_with_export(nodes, rels):
    """Helper: create a SnapshotClient with mocked Neo4j returning given data."""
    from dgk_storage.snapshot_client import SnapshotClient

    mock_session = MagicMock()
    mock_nodes_result = MagicMock()
    mock_nodes_result.__iter__ = MagicMock(return_value=iter([{"n": n} for n in nodes]))
    mock_rels_result = MagicMock()
    mock_rels_result.__iter__ = MagicMock(return_value=iter(rels))
    mock_session.run.side_effect = [mock_nodes_result, mock_rels_result]

    with patch("dgk_storage.snapshot_client.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        client = SnapshotClient()
        client._driver = mock_driver
    return client, mock_session


def test_export_graph_returns_nodes_and_relationships():
    """SnapshotClient.export_graph returns all nodes and relationships from Neo4j."""
    from dgk_storage.snapshot_client import SnapshotClient

    mock_session = MagicMock()
    mock_nodes_result = MagicMock()
    mock_nodes_result.__iter__ = MagicMock(return_value=iter([
        {"n": {"id": "module:src/auth.ts", "name": "auth", "label": "Module"}},
        {"n": {"id": "function:src/auth.ts:login", "name": "login", "label": "Function"}},
    ]))
    mock_rels_result = MagicMock()
    mock_rels_result.__iter__ = MagicMock(return_value=iter([
        {"source": "module:src/auth.ts", "type": "EXPOSES", "target": "function:src/auth.ts:login", "props": {}},
    ]))
    mock_session.run.side_effect = [mock_nodes_result, mock_rels_result]

    with patch("dgk_storage.snapshot_client.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        client = SnapshotClient()
        data = client.export_graph()

    assert "nodes" in data
    assert "relationships" in data
    assert len(data["nodes"]) == 2
    assert len(data["relationships"]) == 1


def test_save_snapshot_writes_json_file(tmp_path):
    """SnapshotClient.save_snapshot writes a .json file under <dir>/<project>/snapshots/."""
    import json
    from dgk_storage.snapshot_client import SnapshotClient

    mock_session = MagicMock()
    mock_nodes_result = MagicMock()
    mock_nodes_result.__iter__ = MagicMock(return_value=iter([
        {"n": {"id": "module:src/foo.ts", "name": "foo"}},
    ]))
    mock_rels_result = MagicMock()
    mock_rels_result.__iter__ = MagicMock(return_value=iter([]))
    mock_session.run.side_effect = [mock_nodes_result, mock_rels_result]

    with patch("dgk_storage.snapshot_client.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        client = SnapshotClient()
        path_str = client.save_snapshot(tmp_path, project_id="my-project")

    assert path_str.endswith(".json")
    saved = json.loads(open(path_str).read())
    assert "nodes" in saved
    assert "meta" in saved
    assert saved["meta"]["node_count"] == 1
    assert saved["meta"]["project_id"] == "my-project"


# ── Phase 5: project_id scoping tests ──


class TestSnapshotClientProjectScoping:
    """SnapshotClient scopes export_graph() by project_id when provided."""

    def test_export_graph_filters_by_project_id(self):
        """export_graph() only returns nodes with matching project_id."""
        nodes_project_a = [
            {"id": "module:abc123:src/auth.ts", "name": "auth", "project_id": "/home/user/projectA"},
        ]
        nodes_project_b = [
            {"id": "module:def456:src/auth.ts", "name": "auth", "project_id": "/home/user/projectB"},
        ]
        all_nodes = nodes_project_a + nodes_project_b

        rels_a = [
            {
                "source": "module:abc123:src/auth.ts",
                "type": "IMPORTS",
                "target": "module:abc123:src/utils.ts",
                "props": {},
                "source_project": "/home/user/projectA",
            },
        ]
        rels_b = [
            {
                "source": "module:def456:src/auth.ts",
                "type": "IMPORTS",
                "target": "module:def456:src/utils.ts",
                "props": {},
                "source_project": "/home/user/projectB",
            },
        ]

        # Build a mock that returns all nodes/rels — the client should filter
        client_a, mock_session = _make_client_with_export(all_nodes, rels_a + rels_b)
        # Reconstruct with project_id
        from dgk_storage.snapshot_client import SnapshotClient

        with patch("dgk_storage.snapshot_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_gdb.driver.return_value = mock_driver
            client_a = SnapshotClient(project_id="/home/user/projectA")
            client_a._driver = mock_driver

            # Mock session with project-filtered query
            mock_session = MagicMock()
            mock_nodes_result = MagicMock()
            mock_nodes_result.__iter__ = MagicMock(return_value=iter(
                [{"n": n} for n in nodes_project_a]
            ))
            mock_rels_result = MagicMock()
            mock_rels_result.__iter__ = MagicMock(return_value=iter(rels_a))
            mock_session.run.side_effect = [mock_nodes_result, mock_rels_result]
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

            data = client_a.export_graph()

        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["project_id"] == "/home/user/projectA"
        assert len(data["relationships"]) == 1

        # Verify the Cypher query includes project_id filter
        calls = mock_session.run.call_args_list
        node_query = calls[0][0][0]
        assert "project_id" in node_query

    def test_export_graph_unscoped_when_no_project_id(self):
        """export_graph() returns all nodes when project_id is None."""
        nodes = [
            {"id": "module:src/auth.ts", "name": "auth"},
            {"id": "module:src/utils.ts", "name": "utils"},
        ]
        client, mock_session = _make_client_with_export(nodes, [])
        data = client.export_graph()

        assert len(data["nodes"]) == 2
        # Verify the Cypher query does NOT include project_id filter
        calls = mock_session.run.call_args_list
        node_query = calls[0][0][0]
        assert "project_id" not in node_query

    def test_save_snapshot_metadata_includes_project_id(self, tmp_path):
        """save_snapshot() includes project_id in metadata when set."""
        import json
        from dgk_storage.snapshot_client import SnapshotClient

        nodes = [{"id": "module:abc123:src/foo.ts", "name": "foo", "project_id": "/home/user/projectA"}]

        with patch("dgk_storage.snapshot_client.GraphDatabase") as mock_gdb:
            mock_driver = MagicMock()
            mock_gdb.driver.return_value = mock_driver
            client = SnapshotClient(project_id="/home/user/projectA")
            client._driver = mock_driver

            mock_session = MagicMock()
            mock_nodes_result = MagicMock()
            mock_nodes_result.__iter__ = MagicMock(return_value=iter([{"n": n} for n in nodes]))
            mock_rels_result = MagicMock()
            mock_rels_result.__iter__ = MagicMock(return_value=iter([]))
            mock_session.run.side_effect = [mock_nodes_result, mock_rels_result]
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

            path_str = client.save_snapshot(tmp_path)

        saved = json.loads(open(path_str).read())
        assert saved["meta"]["project_id"] == "/home/user/projectA"

