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

