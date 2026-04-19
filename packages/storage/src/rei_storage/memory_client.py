"""MemoryClient: stores and retrieves agent memory nodes in Neo4j."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from neo4j import GraphDatabase


class MemoryClient:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "reigraph",
        project_id: str | None = None,
    ):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self.project_id = project_id

    def close(self) -> None:
        self._driver.close()

    # ─── Internal helpers ──────────────────────────────────────────────────────

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}:{uuid.uuid4().hex[:12]}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ─── Record methods ────────────────────────────────────────────────────────

    def record_analysis(
        self,
        scope: str,
        findings: str,
        related_nodes: list[str] | None = None,
    ) -> str:
        """Create an Analysis memory node; optionally link to code nodes via OBSERVED_IN."""
        analysis_id = self._new_id("analysis")
        with self._driver.session() as session:
            query = (
                "MERGE (a:Analysis {id: $id}) "
                "SET a.scope = $scope, a.findings = $findings, a.timestamp = $timestamp"
            )
            params: dict = {
                "id": analysis_id,
                "scope": scope,
                "findings": findings,
                "timestamp": self._now(),
            }
            if self.project_id:
                query += ", a.project_id = $project_id"
                params["project_id"] = self.project_id
            session.run(query, params)
            for node_id in (related_nodes or []):
                session.run(
                    "MATCH (a:Analysis {id: $analysis_id}) "
                    "MATCH (n {id: $node_id}) "
                    "MERGE (a)-[:OBSERVED_IN]->(n)",
                    {"analysis_id": analysis_id, "node_id": node_id},
                )
        return analysis_id

    def record_decision(
        self,
        context: str,
        choice: str,
        rationale: str,
        based_on: list[str] | None = None,
    ) -> str:
        """Create a Decision memory node; optionally link to Analysis nodes via BASED_ON."""
        decision_id = self._new_id("decision")
        with self._driver.session() as session:
            query = (
                "MERGE (d:Decision {id: $id}) "
                "SET d.context = $context, d.choice = $choice, "
                "d.rationale = $rationale, d.timestamp = $timestamp"
            )
            params: dict = {
                "id": decision_id,
                "context": context,
                "choice": choice,
                "rationale": rationale,
                "timestamp": self._now(),
            }
            if self.project_id:
                query += ", d.project_id = $project_id"
                params["project_id"] = self.project_id
            session.run(query, params)
            for analysis_id in (based_on or []):
                session.run(
                    "MATCH (d:Decision {id: $decision_id}) "
                    "MATCH (a {id: $analysis_id}) "
                    "MERGE (d)-[:BASED_ON]->(a)",
                    {"decision_id": decision_id, "analysis_id": analysis_id},
                )
        return decision_id

    def record_change(
        self,
        change_type: str,
        description: str,
        affected_files: list[str] | None = None,
    ) -> str:
        """Create a Change memory node; optionally link to File nodes via AFFECTS."""
        change_id = self._new_id("change")
        with self._driver.session() as session:
            query = (
                "MERGE (c:Change {id: $id}) "
                "SET c.type = $type, c.description = $description, c.timestamp = $timestamp"
            )
            params: dict = {
                "id": change_id,
                "type": change_type,
                "description": description,
                "timestamp": self._now(),
            }
            if self.project_id:
                query += ", c.project_id = $project_id"
                params["project_id"] = self.project_id
            session.run(query, params)
            for file_path in (affected_files or []):
                session.run(
                    "MATCH (c:Change {id: $change_id}) "
                    "MERGE (f:File {path: $path}) "
                    "MERGE (c)-[:AFFECTS]->(f)",
                    {"change_id": change_id, "path": file_path},
                )
        return change_id

    def record_validation(
        self,
        val_type: str,
        status: str,
        details: str,
        validates: str | None = None,
    ) -> str:
        """Create a Validation memory node; optionally link Change->Validation via VALIDATED_BY."""
        validation_id = self._new_id("validation")
        with self._driver.session() as session:
            query = (
                "MERGE (v:Validation {id: $id}) "
                "SET v.type = $type, v.status = $status, "
                "v.details = $details, v.timestamp = $timestamp"
            )
            params: dict = {
                "id": validation_id,
                "type": val_type,
                "status": status,
                "details": details,
                "timestamp": self._now(),
            }
            if self.project_id:
                query += ", v.project_id = $project_id"
                params["project_id"] = self.project_id
            session.run(query, params)
            if validates:
                session.run(
                    "MATCH (v:Validation {id: $validation_id}) "
                    "MATCH (c {id: $change_id}) "
                    "MERGE (c)-[:VALIDATED_BY]->(v)",
                    {"validation_id": validation_id, "change_id": validates},
                )
        return validation_id

    def record_plan(
        self,
        goal: str,
        steps: list[str],
        targets: list[str] | None = None,
    ) -> str:
        """Create a Plan memory node; optionally link to target nodes via PROPOSES."""
        plan_id = self._new_id("plan")
        with self._driver.session() as session:
            query = (
                "MERGE (p:Plan {id: $id}) "
                "SET p.goal = $goal, p.steps = $steps, p.timestamp = $timestamp"
            )
            params: dict = {
                "id": plan_id,
                "goal": goal,
                "steps": steps,
                "timestamp": self._now(),
            }
            if self.project_id:
                query += ", p.project_id = $project_id"
                params["project_id"] = self.project_id
            session.run(query, params)
            for target_id in (targets or []):
                session.run(
                    "MATCH (p:Plan {id: $plan_id}) "
                    "MATCH (n {id: $target_id}) "
                    "MERGE (p)-[:PROPOSES]->(n)",
                    {"plan_id": plan_id, "target_id": target_id},
                )
        return plan_id

    # ─── Query methods ─────────────────────────────────────────────────────────

    def get_recent_context(self, query: str, limit: int = 10) -> list[dict]:
        """Retrieve recent memory nodes matching a text query across all memory types."""
        if self.project_id:
            cypher = (
                "MATCH (n) WHERE (n:Analysis OR n:Decision OR n:Change OR n:Validation OR n:Plan) "
                "AND n.project_id = $project_id "
                "AND (n.scope CONTAINS $query OR n.findings CONTAINS $query "
                "OR n.context CONTAINS $query OR n.goal CONTAINS $query "
                "OR n.description CONTAINS $query) "
                "RETURN n ORDER BY n.timestamp DESC LIMIT $limit"
            )
            params: dict = {"query": query, "limit": limit, "project_id": self.project_id}
        else:
            cypher = (
                "MATCH (n) WHERE (n:Analysis OR n:Decision OR n:Change OR n:Validation OR n:Plan) "
                "AND (n.scope CONTAINS $query OR n.findings CONTAINS $query "
                "OR n.context CONTAINS $query OR n.goal CONTAINS $query "
                "OR n.description CONTAINS $query) "
                "RETURN n ORDER BY n.timestamp DESC LIMIT $limit"
            )
            params = {"query": query, "limit": limit}
        with self._driver.session() as session:
            result = session.run(cypher, params)
            return [dict(record["n"]) for record in result]

    def get_recent_decisions(self, limit: int = 10) -> list[dict]:
        """Retrieve the most recent Decision nodes."""
        if self.project_id:
            cypher = (
                "MATCH (n:Decision) WHERE n.project_id = $project_id "
                "RETURN n ORDER BY n.timestamp DESC LIMIT $limit"
            )
            params: dict = {"limit": limit, "project_id": self.project_id}
        else:
            cypher = (
                "MATCH (n:Decision) "
                "RETURN n ORDER BY n.timestamp DESC LIMIT $limit"
            )
            params = {"limit": limit}
        with self._driver.session() as session:
            result = session.run(cypher, params)
            return [dict(record["n"]) for record in result]
