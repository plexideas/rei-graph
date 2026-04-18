from __future__ import annotations

import json
import subprocess

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool
from pydantic import AnyUrl

from dgk_core.schemas import GraphNode, GraphRelationship
from dgk_storage.neo4j_client import Neo4jClient, check_neo4j_health
from dgk_storage.memory_client import MemoryClient
from dgk_storage.dag_client import DagClient
from dgk_storage.snapshot_client import SnapshotClient

server = Server("dev-graph-kit")


# ─── Pure sync helpers (testable) ─────────────────────────────────────────────

def search_entities(arguments: dict, client: Neo4jClient) -> dict:
    """graph.search_entities: search nodes by name/type."""
    query = arguments.get("query", "")
    labels = arguments.get("labels")
    limit = arguments.get("limit", 20)
    results = client.search_nodes(query, labels=labels, limit=limit)
    entities = [r["n"] for r in results if "n" in r]
    return {"entities": entities}


def get_context(arguments: dict, client: Neo4jClient) -> dict:
    """graph.get_context: nodes + relationships + summary for a query."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 20)
    raw = client.search_nodes(query, limit=limit)
    nodes = [r["n"] for r in raw if "n" in r]
    node_ids = [n["id"] for n in nodes if "id" in n]
    rels = client.get_node_relationships(node_ids) if node_ids else []
    summary = f"Found {len(nodes)} node(s) related to '{query}'."
    return {"nodes": nodes, "relationships": rels, "summary": summary}


def get_neighbors(arguments: dict, client: Neo4jClient) -> dict:
    """graph.get_neighbors: adjacent nodes with direction/type filters."""
    node_id = arguments.get("nodeId", "")
    direction = arguments.get("direction", "both")
    rel_types = arguments.get("types")
    depth = arguments.get("depth", 1)
    return client.get_neighbors(node_id, direction=direction, rel_types=rel_types, depth=depth)


def impact_analysis(arguments: dict, client: Neo4jClient) -> dict:
    """graph.impact_analysis: dependents + risk score for a file path."""
    target = arguments.get("target", "")
    dependents = client.get_dependents(target, max_depth=5)
    direct = [d for d in dependents if d.get("depth", 1) == 1]
    transitive = [d for d in dependents if d.get("depth", 1) > 1]
    risk_score = round(min(1.0, len(dependents) / 10.0), 2)
    return {
        "directlyAffected": direct,
        "transitivelyAffected": transitive,
        "riskScore": risk_score,
        "recommendations": _build_recommendations(len(direct), len(transitive)),
    }


def _build_recommendations(n_direct: int, n_transitive: int) -> list[str]:
    recs: list[str] = []
    if n_direct > 0:
        recs.append(f"Review {n_direct} directly dependent module(s).")
    if n_transitive > 0:
        recs.append(f"Check {n_transitive} transitively affected module(s).")
    if not recs:
        recs.append("No dependents found — safe to change.")
    return recs


def upsert_entities(arguments: dict, client: Neo4jClient) -> dict:
    """graph.upsert_entities: create/update nodes."""
    raw_entities = arguments.get("entities", [])
    nodes = [GraphNode(**e) for e in raw_entities]
    client.upsert_nodes(nodes)
    return {"upserted": len(nodes)}


def upsert_relations(arguments: dict, client: Neo4jClient) -> dict:
    """graph.upsert_relations: create/update relationships."""
    raw_relations = arguments.get("relations", [])
    rels = [
        GraphRelationship(
            type=r["type"],
            source_id=r["from"],
            target_id=r["to"],
            properties=r.get("properties", {}),
        )
        for r in raw_relations
    ]
    client.upsert_relationships(rels)
    return {"upserted": len(rels)}


def scan_project(arguments: dict) -> dict:
    """scan.project: trigger full project scan via dgk scan."""
    path = arguments.get("path", ".")
    result = subprocess.run(["dgk", "scan", path], capture_output=True, text=True)
    status = "ok" if result.returncode == 0 else "error"
    return {"status": status, "output": result.stdout.strip()}


def scan_file(arguments: dict) -> dict:
    """scan.file: trigger single-file scan via dgk scan."""
    path = arguments.get("path", "")
    result = subprocess.run(["dgk", "scan", path], capture_output=True, text=True)
    status = "ok" if result.returncode == 0 else "error"
    return {"status": status, "output": result.stdout.strip()}


def scan_changed_files(arguments: dict) -> dict:
    """scan.changed_files: incrementally scan git-changed files via dgk scan --changed."""
    from pathlib import Path

    path = arguments.get("path", ".")
    result = subprocess.run(
        ["dgk", "scan", path, "--changed"], capture_output=True, text=True
    )
    status = "ok" if result.returncode == 0 else "error"
    return {"status": status, "output": result.stdout.strip()}


def project_snapshot(arguments: dict) -> dict:
    """project.snapshot: export current graph state to a snapshot file."""
    from pathlib import Path

    snapshot_dir = arguments.get("snapshot_dir")
    project_id = arguments.get("project_id", "default")
    if snapshot_dir is None:
        snapshot_dir = Path.home() / ".dev-graph-kit" / "snapshots"
    else:
        snapshot_dir = Path(snapshot_dir)

    client = SnapshotClient()
    try:
        path = client.save_snapshot(snapshot_dir, project_id)
    finally:
        client.close()

    return {"status": "ok", "path": path}


def project_status(arguments: dict, client: Neo4jClient) -> dict:
    """project.status: graph stats + service health."""
    health = check_neo4j_health()
    node_count = client.count_nodes()
    return {"neo4j": health, "nodeCount": node_count}


def get_schema() -> str:
    """project://schema: graph schema as text."""
    return (
        "Node labels: Module, Function, Component, Hook, Class, "
        "Type, Interface, Package\n"
        "Relationships: IMPORTS, EXPOSES, DEPENDS_ON, CALLS, USES_TYPE"
    )


def get_summary(client: Neo4jClient) -> str:
    """project://summary: project overview and stats."""
    count = client.count_nodes()
    return f"dev-graph-kit graph: {count} node(s) indexed."


# ─── Memory helpers (testable) ────────────────────────────────────────────────

def memory_record_analysis(arguments: dict, mem: MemoryClient) -> dict:
    """memory.record_analysis: store an Analysis memory node."""
    analysis_id = mem.record_analysis(
        scope=arguments["scope"],
        findings=arguments["findings"],
        related_nodes=arguments.get("relatedNodes"),
    )
    return {"analysisId": analysis_id}


def memory_record_decision(arguments: dict, mem: MemoryClient) -> dict:
    """memory.record_decision: store a Decision memory node."""
    decision_id = mem.record_decision(
        context=arguments["context"],
        choice=arguments["choice"],
        rationale=arguments["rationale"],
        based_on=arguments.get("basedOn"),
    )
    return {"decisionId": decision_id}


def memory_record_change(arguments: dict, mem: MemoryClient) -> dict:
    """memory.record_change: store a Change memory node."""
    change_id = mem.record_change(
        change_type=arguments["type"],
        description=arguments["description"],
        affected_files=arguments.get("affectedFiles"),
    )
    return {"changeId": change_id}


def memory_record_validation(arguments: dict, mem: MemoryClient) -> dict:
    """memory.record_validation: store a Validation memory node."""
    validation_id = mem.record_validation(
        val_type=arguments["type"],
        status=arguments["status"],
        details=arguments["details"],
        validates=arguments.get("validates"),
    )
    return {"validationId": validation_id}


def memory_record_plan(arguments: dict, mem: MemoryClient) -> dict:
    """memory.record_plan: store a Plan memory node."""
    plan_id = mem.record_plan(
        goal=arguments["goal"],
        steps=arguments["steps"],
        targets=arguments.get("targets"),
    )
    return {"planId": plan_id}


def memory_get_recent_context(arguments: dict, mem: MemoryClient) -> dict:
    """memory.get_recent_context: retrieve relevant memory nodes by query."""
    memories = mem.get_recent_context(
        query=arguments["query"],
        limit=arguments.get("limit", 10),
    )
    return {"memories": memories}


def get_recent_decisions(mem: MemoryClient) -> str:
    """project://recent-decisions: format recent Decision nodes as text."""
    decisions = mem.get_recent_decisions()
    if not decisions:
        return "No decisions recorded yet."
    lines = []
    for d in decisions:
        choice = d.get("choice", "(unknown)")
        rationale = d.get("rationale", "")
        timestamp = d.get("timestamp", "")
        lines.append(f"- [{timestamp}] {choice}: {rationale}")
    return "\n".join(lines)


# ─── DAG helpers (testable) ───────────────────────────────────────────────────

def dag_create_plan(arguments: dict, dag: DagClient) -> dict:
    """dag.create_plan: create a new execution plan."""
    plan_id = dag.create_plan(
        goal=arguments["goal"],
        steps=arguments["steps"],
        targets=arguments.get("targets"),
    )
    return {"planId": plan_id}


def dag_run_plan(arguments: dict, dag: DagClient) -> dict:
    """dag.run_plan: start executing a plan."""
    return dag.run_plan(arguments["planId"])


def dag_get_plan(arguments: dict, dag: DagClient) -> dict:
    """dag.get_plan: get plan details and step statuses."""
    result = dag.get_plan(arguments["planId"])
    if result is None:
        return {"error": f"Plan '{arguments['planId']}' not found"}
    return result


def dag_step_status(arguments: dict, dag: DagClient) -> dict:
    """dag.step_status: get status of a single step."""
    result = dag.step_status(arguments["planId"], arguments["stepName"])
    if result is None:
        return {"error": f"Step '{arguments['stepName']}' not found in plan '{arguments['planId']}'"}
    return result


def dag_cancel_plan(arguments: dict, dag: DagClient) -> dict:
    """dag.cancel_plan: cancel a running or pending plan."""
    cancelled = dag.cancel_plan(arguments["planId"])
    return {"cancelled": cancelled}


def get_open_plans(dag: DagClient) -> str:
    """project://open-plans: list open (pending/running) plans."""
    plans = dag.list_open_plans()
    if not plans:
        return "No open plans."
    lines = []
    for p in plans:
        lines.append(f"- [{p.get('status', '?')}] {p.get('id', '?')}: {p.get('goal', '')}")
    return "\n".join(lines)


# ─── TOOL / RESOURCE definitions ──────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="graph.search_entities",
        description="Search for entities by name/type",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="graph.get_context",
        description="Get relevant code context for a query",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="graph.get_neighbors",
        description="Get neighboring nodes with optional direction/type filters",
        inputSchema={
            "type": "object",
            "properties": {
                "nodeId": {"type": "string"},
                "direction": {"type": "string", "enum": ["in", "out", "both"]},
                "types": {"type": "array", "items": {"type": "string"}},
                "depth": {"type": "integer", "default": 1},
            },
            "required": ["nodeId"],
        },
    ),
    Tool(
        name="graph.impact_analysis",
        description="Analyze impact of changes to a file",
        inputSchema={
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
        },
    ),
    Tool(
        name="graph.upsert_entities",
        description="Create or update nodes in the code graph",
        inputSchema={
            "type": "object",
            "properties": {"entities": {"type": "array"}},
            "required": ["entities"],
        },
    ),
    Tool(
        name="graph.upsert_relations",
        description="Create or update relationships",
        inputSchema={
            "type": "object",
            "properties": {"relations": {"type": "array"}},
            "required": ["relations"],
        },
    ),
    Tool(
        name="scan.project",
        description="Full project scan",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
        },
    ),
    Tool(
        name="scan.file",
        description="Scan a single file",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    ),
    Tool(
        name="scan.changed_files",
        description="Incrementally scan only git-changed TypeScript/TSX files",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
        },
    ),
    Tool(
        name="project.snapshot",
        description="Export the current graph state to a JSON snapshot file",
        inputSchema={
            "type": "object",
            "properties": {
                "snapshot_dir": {"type": "string"},
                "project_id": {"type": "string", "default": "default"},
            },
        },
    ),
    Tool(
        name="project.status",
        description="Get project status — graph stats and service health",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="memory.record_analysis",
        description="Record an agent analysis session",
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {"type": "string"},
                "findings": {"type": "string"},
                "relatedNodes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["scope", "findings"],
        },
    ),
    Tool(
        name="memory.record_decision",
        description="Record a decision with rationale",
        inputSchema={
            "type": "object",
            "properties": {
                "context": {"type": "string"},
                "choice": {"type": "string"},
                "rationale": {"type": "string"},
                "basedOn": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["context", "choice", "rationale"],
        },
    ),
    Tool(
        name="memory.record_change",
        description="Record a code change",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["refactor", "feature", "fix", "chore"]},
                "description": {"type": "string"},
                "affectedFiles": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["type", "description"],
        },
    ),
    Tool(
        name="memory.record_validation",
        description="Record validation or test results",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["test", "lint", "typecheck", "review"]},
                "status": {"type": "string", "enum": ["passed", "failed"]},
                "details": {"type": "string"},
                "validates": {"type": "string"},
            },
            "required": ["type", "status", "details"],
        },
    ),
    Tool(
        name="memory.record_plan",
        description="Record a multi-step plan",
        inputSchema={
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "string"}},
                "targets": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["goal", "steps"],
        },
    ),
    Tool(
        name="memory.get_recent_context",
        description="Retrieve relevant memory context by query",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="dag.create_plan",
        description="Create a new execution plan with ordered steps",
        inputSchema={
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "string"}},
                "targets": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["goal", "steps"],
        },
    ),
    Tool(
        name="dag.run_plan",
        description="Start executing a plan",
        inputSchema={
            "type": "object",
            "properties": {"planId": {"type": "string"}},
            "required": ["planId"],
        },
    ),
    Tool(
        name="dag.get_plan",
        description="Get plan details and step statuses",
        inputSchema={
            "type": "object",
            "properties": {"planId": {"type": "string"}},
            "required": ["planId"],
        },
    ),
    Tool(
        name="dag.step_status",
        description="Get status of a single step within a plan",
        inputSchema={
            "type": "object",
            "properties": {
                "planId": {"type": "string"},
                "stepName": {"type": "string"},
            },
            "required": ["planId", "stepName"],
        },
    ),
    Tool(
        name="dag.cancel_plan",
        description="Cancel a running or pending plan",
        inputSchema={
            "type": "object",
            "properties": {"planId": {"type": "string"}},
            "required": ["planId"],
        },
    ),
]

RESOURCES: list[Resource] = [
    Resource(
        name="Schema",
        uri=AnyUrl("project://schema"),
        description="Graph schema (node/edge types)",
        mimeType="text/plain",
    ),
    Resource(
        name="Summary",
        uri=AnyUrl("project://summary"),
        description="Project overview and stats",
        mimeType="text/plain",
    ),
    Resource(
        name="Recent Decisions",
        uri=AnyUrl("project://recent-decisions"),
        description="Last N agent decisions",
        mimeType="text/plain",
    ),
    Resource(
        name="Open Plans",
        uri=AnyUrl("project://open-plans"),
        description="List of pending/running execution plans",
        mimeType="text/plain",
    ),
    Resource(
        name="Plan",
        uri=AnyUrl("plan://placeholder"),
        description="Execution plan details by ID (use plan://<id>)",
        mimeType="text/plain",
    ),
]

_TOOL_NAMES = {t.name for t in TOOLS}


# ─── MCP server handlers ───────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


_MEMORY_TOOL_NAMES = {
    "memory.record_analysis",
    "memory.record_decision",
    "memory.record_change",
    "memory.record_validation",
    "memory.record_plan",
    "memory.get_recent_context",
}

_DAG_TOOL_NAMES = {
    "dag.create_plan",
    "dag.run_plan",
    "dag.get_plan",
    "dag.step_status",
    "dag.cancel_plan",
}


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in _TOOL_NAMES:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    # Memory tools use MemoryClient, not Neo4jClient
    if name in _MEMORY_TOOL_NAMES:
        mem = MemoryClient()
        try:
            match name:
                case "memory.record_analysis":
                    result = memory_record_analysis(arguments, mem)
                case "memory.record_decision":
                    result = memory_record_decision(arguments, mem)
                case "memory.record_change":
                    result = memory_record_change(arguments, mem)
                case "memory.record_validation":
                    result = memory_record_validation(arguments, mem)
                case "memory.record_plan":
                    result = memory_record_plan(arguments, mem)
                case "memory.get_recent_context":
                    result = memory_get_recent_context(arguments, mem)
                case _:
                    result = {"error": f"Unknown memory tool: {name}"}
            return [TextContent(type="text", text=json.dumps(result))]
        finally:
            mem.close()

    # DAG tools use DagClient
    if name in _DAG_TOOL_NAMES:
        dag = DagClient()
        try:
            match name:
                case "dag.create_plan":
                    result = dag_create_plan(arguments, dag)
                case "dag.run_plan":
                    result = dag_run_plan(arguments, dag)
                case "dag.get_plan":
                    result = dag_get_plan(arguments, dag)
                case "dag.step_status":
                    result = dag_step_status(arguments, dag)
                case "dag.cancel_plan":
                    result = dag_cancel_plan(arguments, dag)
                case _:
                    result = {"error": f"Unknown dag tool: {name}"}
            return [TextContent(type="text", text=json.dumps(result))]
        finally:
            dag.close()

    client = Neo4jClient()
    try:
        match name:
            case "graph.search_entities":
                result = search_entities(arguments, client)
            case "graph.get_context":
                result = get_context(arguments, client)
            case "graph.get_neighbors":
                result = get_neighbors(arguments, client)
            case "graph.impact_analysis":
                result = impact_analysis(arguments, client)
            case "graph.upsert_entities":
                result = upsert_entities(arguments, client)
            case "graph.upsert_relations":
                result = upsert_relations(arguments, client)
            case "scan.project":
                client.close()
                result = scan_project(arguments)
                return [TextContent(type="text", text=json.dumps(result))]
            case "scan.file":
                client.close()
                result = scan_file(arguments)
                return [TextContent(type="text", text=json.dumps(result))]
            case "scan.changed_files":
                client.close()
                result = scan_changed_files(arguments)
                return [TextContent(type="text", text=json.dumps(result))]
            case "project.snapshot":
                client.close()
                result = project_snapshot(arguments)
                return [TextContent(type="text", text=json.dumps(result))]
            case "project.status":
                result = project_status(arguments, client)
            case _:  # unreachable but satisfies type checker
                result = {"error": f"Unknown tool: {name}"}
        return [TextContent(type="text", text=json.dumps(result))]
    finally:
        client.close()


@server.list_resources()
async def list_resources() -> list[Resource]:
    return RESOURCES


@server.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    uri_str = str(uri)
    if uri_str == "project://schema":
        return get_schema()
    if uri_str == "project://summary":
        client = Neo4jClient()
        try:
            return get_summary(client)
        finally:
            client.close()
    if uri_str == "project://recent-decisions":
        mem = MemoryClient()
        try:
            return get_recent_decisions(mem)
        finally:
            mem.close()
    if uri_str == "project://open-plans":
        dag = DagClient()
        try:
            return get_open_plans(dag)
        finally:
            dag.close()
    if uri_str.startswith("plan://"):
        plan_id = uri_str[len("plan://"):]
        dag = DagClient()
        try:
            result = dag.get_plan(plan_id)
            if result is None:
                return f"Plan '{plan_id}' not found."
            return json.dumps(result, indent=2)
        finally:
            dag.close()
    raise ValueError(f"Unknown resource URI: {uri}")
