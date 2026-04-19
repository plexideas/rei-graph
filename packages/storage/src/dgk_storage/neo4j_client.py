from __future__ import annotations

import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

from dgk_core.hashing import project_hash as _project_hash
from dgk_core.schemas import GraphNode, GraphRelationship


def check_neo4j_health(host: str = "localhost", http_port: int = 7474) -> dict:
    """Check if Neo4j is reachable via its HTTP API."""
    url = f"http://{host}:{http_port}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return {"status": "healthy", "url": url}
    except (urllib.error.URLError, OSError) as e:
        return {"status": "unhealthy", "url": url, "error": str(e)}


class Neo4jClient:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "devgraphkit",
        project_id: str | None = None,
    ):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self.project_id = project_id
        self.project_hash = _project_hash(project_id) if project_id else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prefix_id(self, raw_id: str) -> str:
        """Prefix a node ID with the project hash if scoped."""
        if not self.project_hash:
            return raw_id
        # raw_id format: "label:relpath:name" → "label:{hash}:relpath:name"
        label, rest = raw_id.split(":", 1)
        return f"{label}:{self.project_hash}:{rest}"

    def _ensure_project_node(self) -> None:
        """MERGE a Project registry node for the current project."""
        if not self.project_id:
            return
        with self._driver.session() as session:
            session.run(
                "MERGE (p:Project {id: $id}) "
                "SET p.name = $name, p.hash = $hash, p.root_path = $root_path, "
                "p.created_at = coalesce(p.created_at, $created_at)",
                {
                    "id": self.project_id,
                    "name": Path(self.project_id).name,
                    "hash": self.project_hash,
                    "root_path": self.project_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def close(self):
        self._driver.close()

    def upsert_nodes(self, nodes: list[GraphNode]) -> None:
        with self._driver.session() as session:
            for node in nodes:
                node_id = self._prefix_id(node.id)
                query = (
                    f"MERGE (n:{node.label} {{id: $id}}) "
                    f"SET n.name = $name, n.path = $path, n.line = $line"
                )
                params: dict = {"id": node_id, "name": node.name, "path": node.path, "line": node.line}
                if self.project_id:
                    query += ", n.project_id = $project_id"
                    params["project_id"] = self.project_id
                # Set additional properties
                for key, value in node.properties.items():
                    query += f", n.{key} = ${key}"
                    params[key] = value
                session.run(query, params)

    def upsert_relationships(self, relationships: list[GraphRelationship]) -> None:
        with self._driver.session() as session:
            for rel in relationships:
                source_id = self._prefix_id(rel.source_id)
                target_id = self._prefix_id(rel.target_id)
                if self.project_id:
                    query = (
                        f"MATCH (a {{id: $source_id, project_id: $project_id}}) "
                        f"MATCH (b {{id: $target_id, project_id: $project_id}}) "
                        f"MERGE (a)-[r:{rel.type}]->(b)"
                    )
                    params = {
                        "source_id": source_id,
                        "target_id": target_id,
                        "project_id": self.project_id,
                    }
                else:
                    query = (
                        f"MATCH (a {{id: $source_id}}) "
                        f"MATCH (b {{id: $target_id}}) "
                        f"MERGE (a)-[r:{rel.type}]->(b)"
                    )
                    params = {"source_id": source_id, "target_id": target_id}
                session.run(query, params)

    def search_nodes(self, query: str, labels: list[str] | None = None, limit: int = 20) -> list[dict]:
        label_filter = ":" + ":".join(labels) if labels else ""
        if self.project_id:
            cypher = (
                f"MATCH (n{label_filter}) "
                f"WHERE n.name CONTAINS $query AND n.project_id = $project_id "
                f"RETURN n LIMIT $limit"
            )
            params = {"query": query, "limit": limit, "project_id": self.project_id}
        else:
            cypher = (
                f"MATCH (n{label_filter}) "
                f"WHERE n.name CONTAINS $query "
                f"RETURN n LIMIT $limit"
            )
            params = {"query": query, "limit": limit}
        with self._driver.session() as session:
            result = session.run(cypher, params)
            return [record.data() for record in result]

    def delete_file_nodes(self, file_path: str) -> None:
        """Delete all nodes associated with a file path."""
        if self.project_id:
            cypher = "MATCH (n {path: $path, project_id: $project_id}) DETACH DELETE n"
            params = {"path": file_path, "project_id": self.project_id}
        else:
            cypher = "MATCH (n {path: $path}) DETACH DELETE n"
            params = {"path": file_path}
        with self._driver.session() as session:
            session.run(cypher, params)

    def get_dependents(self, file_path: str, max_depth: int = 5) -> list[dict]:
        """Find modules that directly or transitively import the given file."""
        if self.project_id:
            cypher = (
                "MATCH (target:Module {path: $path, project_id: $project_id}) "
                "MATCH (n:Module {project_id: $project_id})-[:IMPORTS*1..$max_depth]->(target) "
                "WITH n, length(shortestPath((n)-[:IMPORTS*]->(target))) AS depth "
                "RETURN n, depth ORDER BY depth"
            ).replace("$max_depth", str(max_depth))
            params = {"path": file_path, "max_depth": max_depth, "project_id": self.project_id}
        else:
            cypher = (
                "MATCH (target:Module {path: $path}) "
                "MATCH (n:Module)-[:IMPORTS*1..$max_depth]->(target) "
                "WITH n, length(shortestPath((n)-[:IMPORTS*]->(target))) AS depth "
                "RETURN n, depth ORDER BY depth"
            ).replace("$max_depth", str(max_depth))
            params = {"path": file_path, "max_depth": max_depth}
        with self._driver.session() as session:
            result = session.run(cypher, params)
            return [record.data() for record in result]

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        rel_types: list[str] | None = None,
        depth: int = 1,
    ) -> dict:
        """Get neighboring nodes with optional direction and relationship type filters."""
        rel_part = ":" + "|".join(rel_types) if rel_types else ""
        depth_str = str(depth)
        if self.project_id:
            scope = ", project_id: $project_id"
        else:
            scope = ""
        if direction == "out":
            pattern = f"(n {{id: $node_id{scope}}})-[r{rel_part}*1..{depth_str}]->(m)"
        elif direction == "in":
            pattern = f"(n {{id: $node_id{scope}}})<-[r{rel_part}*1..{depth_str}]-(m)"
        else:
            pattern = f"(n {{id: $node_id{scope}}})-[r{rel_part}*1..{depth_str}]-(m)"
        cypher = f"MATCH {pattern} RETURN DISTINCT m, type(last(r)) AS relType"
        params: dict = {"node_id": node_id}
        if self.project_id:
            params["project_id"] = self.project_id
        with self._driver.session() as session:
            result = session.run(cypher, params)
            nodes = []
            rels = []
            for record in result:
                nodes.append(dict(record["m"]))
                rels.append({"type": record["relType"]})
        return {"nodes": nodes, "relationships": rels}

    def get_node_relationships(self, node_ids: list[str]) -> list[dict]:
        """Get all relationships between a set of nodes."""
        with self._driver.session() as session:
            if self.project_id:
                cypher = (
                    "MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids "
                    "AND a.project_id = $project_id "
                    "RETURN a.id AS source, type(r) AS relType, b.id AS target"
                )
                params = {"ids": node_ids, "project_id": self.project_id}
            else:
                cypher = (
                    "MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids "
                    "RETURN a.id AS source, type(r) AS relType, b.id AS target"
                )
                params = {"ids": node_ids}
            result = session.run(cypher, params)
            return [
                {"type": r["relType"], "sourceId": r["source"], "targetId": r["target"]}
                for r in result
            ]

    def count_nodes(self) -> int:
        """Count total nodes in the graph."""
        with self._driver.session() as session:
            if self.project_id:
                result = session.run(
                    "MATCH (n) WHERE n.project_id = $project_id RETURN count(n) AS count",
                    {"project_id": self.project_id},
                )
            else:
                result = session.run("MATCH (n) RETURN count(n) AS count")
            record = result.single()
            return record["count"] if record else 0

    def get_project(self) -> dict | None:
        """Look up the Project registry node for the current project_id.

        Returns a dict of project properties, or None if not found / no project_id.
        """
        if not self.project_id:
            return None
        with self._driver.session() as session:
            result = session.run(
                "MATCH (p:Project {id: $id}) RETURN p",
                {"id": self.project_id},
            )
            record = result.single()
            if record is None:
                return None
            return dict(record["p"])

    def update_last_scanned(self) -> None:
        """Set last_scanned_at on the Project node to the current UTC time."""
        if not self.project_id:
            return
        with self._driver.session() as session:
            session.run(
                "MATCH (p:Project {id: $id}) SET p.last_scanned_at = $last_scanned_at",
                {
                    "id": self.project_id,
                    "last_scanned_at": datetime.now(timezone.utc).isoformat(),
                },
            )
