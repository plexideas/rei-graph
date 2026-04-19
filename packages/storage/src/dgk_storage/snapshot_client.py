"""SnapshotClient: exports graph state and saves/loads snapshots."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase


class SnapshotClient:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "devgraphkit",
        project_id: str | None = None,
    ):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._project_id = project_id

    def close(self) -> None:
        self._driver.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def export_graph(self) -> dict:
        """Export nodes and relationships from Neo4j as a dict.

        When project_id is set, only nodes/rels for that project are returned.
        """
        with self._driver.session() as session:
            if self._project_id:
                nodes_result = session.run(
                    "MATCH (n) WHERE n.project_id = $project_id RETURN n",
                    project_id=self._project_id,
                )
            else:
                nodes_result = session.run("MATCH (n) RETURN n")
            nodes = [dict(record["n"]) for record in nodes_result]

            if self._project_id:
                rels_result = session.run(
                    "MATCH (a)-[r]->(b) WHERE a.project_id = $project_id AND b.project_id = $project_id "
                    "RETURN a.id AS source, type(r) AS type, b.id AS target, properties(r) AS props",
                    project_id=self._project_id,
                )
            else:
                rels_result = session.run(
                    "MATCH (a)-[r]->(b) RETURN a.id AS source, type(r) AS type, b.id AS target, properties(r) AS props"
                )
            relationships = [
                {
                    "source": record["source"],
                    "type": record["type"],
                    "target": record["target"],
                    "props": dict(record["props"]) if record["props"] else {},
                }
                for record in rels_result
            ]

        return {"nodes": nodes, "relationships": relationships}

    def save_snapshot(self, snapshot_dir: Path, project_id: str | None = None) -> str:
        """Export graph and save to disk. Returns the snapshot file path."""
        dir_label = project_id or "default"
        meta_project_id = self._project_id or project_id or "default"
        data = self.export_graph()
        snapshot_id = f"snapshot:{uuid.uuid4().hex[:12]}"
        data["meta"] = {
            "id": snapshot_id,
            "timestamp": self._now(),
            "project_id": meta_project_id,
            "node_count": len(data["nodes"]),
            "relationship_count": len(data["relationships"]),
        }

        dest_dir = snapshot_dir / dir_label / "snapshots"
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{snapshot_id}.json"
        dest_path = dest_dir / filename

        with open(dest_path, "w") as f:
            json.dump(data, f, indent=2)

        return str(dest_path)
