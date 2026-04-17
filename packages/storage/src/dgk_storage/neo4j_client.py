from __future__ import annotations

import urllib.request
import urllib.error

from neo4j import GraphDatabase

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
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "devgraphkit"):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def upsert_nodes(self, nodes: list[GraphNode]) -> None:
        with self._driver.session() as session:
            for node in nodes:
                query = (
                    f"MERGE (n:{node.label} {{id: $id}}) "
                    f"SET n.name = $name, n.path = $path, n.line = $line"
                )
                params = {"id": node.id, "name": node.name, "path": node.path, "line": node.line}
                # Set additional properties
                for key, value in node.properties.items():
                    query += f", n.{key} = ${key}"
                    params[key] = value
                session.run(query, params)

    def upsert_relationships(self, relationships: list[GraphRelationship]) -> None:
        with self._driver.session() as session:
            for rel in relationships:
                query = (
                    f"MATCH (a {{id: $source_id}}) "
                    f"MATCH (b {{id: $target_id}}) "
                    f"MERGE (a)-[r:{rel.type}]->(b)"
                )
                params = {"source_id": rel.source_id, "target_id": rel.target_id}
                session.run(query, params)

    def search_nodes(self, query: str, labels: list[str] | None = None, limit: int = 20) -> list[dict]:
        label_filter = ":" + ":".join(labels) if labels else ""
        cypher = (
            f"MATCH (n{label_filter}) "
            f"WHERE n.name CONTAINS $query "
            f"RETURN n LIMIT $limit"
        )
        with self._driver.session() as session:
            result = session.run(cypher, {"query": query, "limit": limit})
            return [record.data() for record in result]

    def delete_file_nodes(self, file_path: str) -> None:
        """Delete all nodes associated with a file path."""
        with self._driver.session() as session:
            session.run(
                "MATCH (n {path: $path}) DETACH DELETE n",
                {"path": file_path},
            )

    def get_dependents(self, file_path: str, max_depth: int = 5) -> list[dict]:
        """Find modules that directly or transitively import the given file."""
        cypher = (
            "MATCH (target:Module {path: $path}) "
            "MATCH (n:Module)-[:IMPORTS*1..$max_depth]->(target) "
            "WITH n, length(shortestPath((n)-[:IMPORTS*]->(target))) AS depth "
            "RETURN n, depth ORDER BY depth"
        ).replace("$max_depth", str(max_depth))
        with self._driver.session() as session:
            result = session.run(cypher, {"path": file_path, "max_depth": max_depth})
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
        if direction == "out":
            pattern = f"(n {{id: $node_id}})-[r{rel_part}*1..{depth_str}]->(m)"
        elif direction == "in":
            pattern = f"(n {{id: $node_id}})<-[r{rel_part}*1..{depth_str}]-(m)"
        else:
            pattern = f"(n {{id: $node_id}})-[r{rel_part}*1..{depth_str}]-(m)"
        cypher = f"MATCH {pattern} RETURN DISTINCT m, type(last(r)) AS relType"
        with self._driver.session() as session:
            result = session.run(cypher, {"node_id": node_id})
            nodes = []
            rels = []
            for record in result:
                nodes.append(dict(record["m"]))
                rels.append({"type": record["relType"]})
        return {"nodes": nodes, "relationships": rels}

    def get_node_relationships(self, node_ids: list[str]) -> list[dict]:
        """Get all relationships between a set of nodes."""
        with self._driver.session() as session:
            result = session.run(
                "MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids "
                "RETURN a.id AS source, type(r) AS relType, b.id AS target",
                {"ids": node_ids},
            )
            return [
                {"type": r["relType"], "sourceId": r["source"], "targetId": r["target"]}
                for r in result
            ]

    def count_nodes(self) -> int:
        """Count total nodes in the graph."""
        with self._driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS count")
            record = result.single()
            return record["count"] if record else 0
