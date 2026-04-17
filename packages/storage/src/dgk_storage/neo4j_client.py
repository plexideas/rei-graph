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
