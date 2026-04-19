"""DagClient: stores and tracks DAG plan execution state in Neo4j."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from neo4j import GraphDatabase


class DagClient:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "devgraphkit",
        project_id: str | None = None,
    ):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self.project_id = project_id

    def close(self) -> None:
        self._driver.close()

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}:{uuid.uuid4().hex[:12]}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_plan(
        self,
        goal: str,
        steps: list[str],
        targets: list[str] | None = None,
    ) -> str:
        """Create a DagPlan node with DagStep nodes; optionally link via PROPOSES."""
        plan_id = self._new_id("plan")
        with self._driver.session() as session:
            plan_query = (
                "MERGE (p:DagPlan {id: $id}) "
                "SET p.goal = $goal, p.status = 'pending', "
                "p.steps_count = $steps_count, p.timestamp = $timestamp"
            )
            plan_params: dict = {
                "id": plan_id,
                "goal": goal,
                "steps_count": len(steps),
                "timestamp": self._now(),
            }
            if self.project_id:
                plan_query += ", p.project_id = $project_id"
                plan_params["project_id"] = self.project_id
            session.run(plan_query, plan_params)
            for index, step_name in enumerate(steps):
                step_id = f"{plan_id}:step:{index}"
                step_query = (
                    "MERGE (s:DagStep {id: $step_id}) "
                    "SET s.plan_id = $plan_id, s.name = $name, s.index = $index, "
                    "s.status = 'pending', s.timestamp = $timestamp "
                    "WITH s "
                    "MATCH (p:DagPlan {id: $plan_id}) "
                    "MERGE (p)-[:HAS_STEP]->(s)"
                )
                step_params: dict = {
                    "step_id": step_id,
                    "plan_id": plan_id,
                    "name": step_name,
                    "index": index,
                    "timestamp": self._now(),
                }
                if self.project_id:
                    step_query = (
                        "MERGE (s:DagStep {id: $step_id}) "
                        "SET s.plan_id = $plan_id, s.name = $name, s.index = $index, "
                        "s.status = 'pending', s.timestamp = $timestamp, "
                        "s.project_id = $project_id "
                        "WITH s "
                        "MATCH (p:DagPlan {id: $plan_id}) "
                        "MERGE (p)-[:HAS_STEP]->(s)"
                    )
                    step_params["project_id"] = self.project_id
                session.run(step_query, step_params)
            for target_id in (targets or []):
                session.run(
                    "MATCH (p:DagPlan {id: $plan_id}) "
                    "MATCH (n {id: $target_id}) "
                    "MERGE (p)-[:PROPOSES]->(n)",
                    {"plan_id": plan_id, "target_id": target_id},
                )
        return plan_id

    def get_plan(self, plan_id: str) -> dict | None:
        """Retrieve a plan and its steps; returns None if not found."""
        with self._driver.session() as session:
            if self.project_id:
                plan_result = session.run(
                    "MATCH (p:DagPlan {id: $id, project_id: $project_id}) RETURN p",
                    {"id": plan_id, "project_id": self.project_id},
                )
            else:
                plan_result = session.run(
                    "MATCH (p:DagPlan {id: $id}) RETURN p",
                    {"id": plan_id},
                )
            plan_record = plan_result.single()
            if plan_record is None:
                return None
            plan = dict(plan_record["p"])

            steps_result = session.run(
                "MATCH (p:DagPlan {id: $id})-[:HAS_STEP]->(s:DagStep) "
                "RETURN s ORDER BY s.index",
                {"id": plan_id},
            )
            steps = [dict(record["s"]) for record in steps_result]
        return {"plan": plan, "steps": steps}

    def run_plan(self, plan_id: str) -> dict:
        """Transition plan to running and activate the first step."""
        with self._driver.session() as session:
            if self.project_id:
                session.run(
                    "MATCH (p:DagPlan {id: $id, project_id: $project_id}) SET p.status = 'running'",
                    {"id": plan_id, "project_id": self.project_id},
                )
                session.run(
                    "MATCH (p:DagPlan {id: $id, project_id: $project_id})-[:HAS_STEP]->(s:DagStep) "
                    "WHERE s.index = 0 SET s.status = 'running'",
                    {"id": plan_id, "project_id": self.project_id},
                )
            else:
                session.run(
                    "MATCH (p:DagPlan {id: $id}) SET p.status = 'running'",
                    {"id": plan_id},
                )
                session.run(
                    "MATCH (p:DagPlan {id: $id})-[:HAS_STEP]->(s:DagStep) "
                    "WHERE s.index = 0 SET s.status = 'running'",
                    {"id": plan_id},
                )
        return {"run_id": plan_id, "status": "running"}

    def step_status(self, plan_id: str, step_name: str) -> dict | None:
        """Get status dict for a named step; returns None if not found."""
        with self._driver.session() as session:
            if self.project_id:
                result = session.run(
                    "MATCH (p:DagPlan {id: $plan_id, project_id: $project_id})-[:HAS_STEP]->(s:DagStep {name: $name}) "
                    "RETURN s",
                    {"plan_id": plan_id, "name": step_name, "project_id": self.project_id},
                )
            else:
                result = session.run(
                    "MATCH (p:DagPlan {id: $plan_id})-[:HAS_STEP]->(s:DagStep {name: $name}) "
                    "RETURN s",
                    {"plan_id": plan_id, "name": step_name},
                )
            record = result.single()
            if record is None:
                return None
            return dict(record["s"])

    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a plan and all its pending/running steps."""
        with self._driver.session() as session:
            if self.project_id:
                session.run(
                    "MATCH (p:DagPlan {id: $id, project_id: $project_id}) SET p.status = 'cancelled'",
                    {"id": plan_id, "project_id": self.project_id},
                )
                session.run(
                    "MATCH (p:DagPlan {id: $id, project_id: $project_id})-[:HAS_STEP]->(s:DagStep) "
                    "WHERE s.status IN ['pending', 'running'] SET s.status = 'cancelled'",
                    {"id": plan_id, "project_id": self.project_id},
                )
            else:
                session.run(
                    "MATCH (p:DagPlan {id: $id}) SET p.status = 'cancelled'",
                    {"id": plan_id},
                )
                session.run(
                    "MATCH (p:DagPlan {id: $id})-[:HAS_STEP]->(s:DagStep) "
                    "WHERE s.status IN ['pending', 'running'] SET s.status = 'cancelled'",
                    {"id": plan_id},
                )
        return True

    def list_open_plans(self, limit: int = 10) -> list[dict]:
        """Return pending/running plans ordered by creation time."""
        with self._driver.session() as session:
            if self.project_id:
                result = session.run(
                    "MATCH (p:DagPlan) WHERE p.status IN ['pending', 'running'] "
                    "AND p.project_id = $project_id "
                    "RETURN p ORDER BY p.timestamp DESC LIMIT $limit",
                    {"limit": limit, "project_id": self.project_id},
                )
            else:
                result = session.run(
                    "MATCH (p:DagPlan) WHERE p.status IN ['pending', 'running'] "
                    "RETURN p ORDER BY p.timestamp DESC LIMIT $limit",
                    {"limit": limit},
                )
            return [dict(record["p"]) for record in result]
