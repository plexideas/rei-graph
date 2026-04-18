# PRD: dev-graph-kit

**Version:** 1.1  
**Date:** April 17, 2026  
**Author:** Platform Team  
**Status:** Draft

---

## 1. Overview

### 1.1 What We're Building

Not "another graph DB" — a **local-first developer memory/orchestration kit for coding agents**.

**Product name:** `dev-graph-kit`

**One-line description:**
> "Open-source local graph memory + DAG execution layer for coding agents."

**Full description:**
> "A local-first MCP-compatible developer memory system that turns a codebase, architectural decisions, and agent work history into a queryable graph and executable plans."

### 1.2 Core Capabilities

| Capability | Description |
|------------|-------------|
| **Project Graph** | Store and query code structure, dependencies, architecture |
| **Agent Memory** | Persist analyses, plans, decisions, changes across sessions |
| **DAG Execution** | Build and execute multi-step plans with tracking |
| **MCP Interface** | Standard agent access via MCP tools/resources |
| **Easy Install** | Docker + single CLI, up and running in minutes |

### 1.3 Problem Statement

Modern AI coding agents (Codex, Claude Code, Cursor) lack persistent, structured memory about the codebase they work with. Each session starts from scratch—agents re-discover architecture, re-analyze dependencies, and lose context about past decisions and changes.

Current limitations:
- **No project memory**: Agents don't remember what they learned about a codebase
- **No impact analysis**: Changes are made without understanding ripple effects
- **No structured planning**: Multi-step refactors lack execution tracking
- **No provenance**: No record of why decisions were made

### 1.4 Target Users

| User Type | Use Case |
|-----------|----------|
| **AI Agent Developers** | Build agents that understand and remember codebases |
| **Solo Developers** | Use AI agents with persistent project context |
| **Teams** | Share agent memory across team members |
| **OSS Contributors** | Extend and customize for specific frameworks |

---

## 2. Goals & Success Metrics

### 2.1 Goals

| Priority | Goal |
|----------|------|
| P0 | Agent can query code graph and get accurate dependency/impact information |
| P0 | Agent can record observations and decisions that persist across sessions |
| P0 | Agent can create and execute multi-step plans with status tracking |
| P1 | Setup takes < 5 minutes on any machine with Docker |
| P1 | Works with Codex, Claude Code, and Cursor via MCP |
| P2 | TypeScript/React codebase scanning works out of the box |

### 2.2 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first query | < 5 min | From `git clone` to first successful graph query |
| Graph accuracy | > 90% | Manual validation on test repos |
| Memory retrieval relevance | > 85% | Agent finds relevant past context |
| Plan execution success | > 95% | Completed plans / started plans |

---

## 3. Technical Architecture

### 3.1 Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Graph Database | Neo4j Community | Mature, local-deployable, has MCP server |
| Memory Layer | Graphiti | Temporal context graph for AI agents (Python-native, open-source) |
| DAG Orchestration | Dagster | Simple local dev via `dg dev`, intended local-dev mode |
| Backend | Python (uv) | Graphiti/Dagster ecosystem |
| Code Scanner | TypeScript (ts-morph) | Native AST access for TS/TSX |
| Agent Interface | MCP Server | Standard protocol for all agents |
| CLI | Python (Click/Typer) | `dgk` commands |

**Why Python for core?**
- Graphiti is Python-native/open-source
- Dagster is Python ecosystem, works well with uv/dg
- MCP server is simpler and faster to build in Python
- TS scanner can be a separate package, called as subprocess or Node bridge

### 3.2 Layer Responsibilities

| Layer | Technology | Stores |
|-------|------------|--------|
| **Graph DB** | Neo4j | Project entities, relationships, code structure |
| **Memory** | Graphiti | Evolving facts, episodes, provenance, memory nodes |
| **DAG** | Dagster | Executable steps, dependencies, execution status |
| **Interface** | MCP Server | Tools/resources for agents (Codex, Cursor, Claude Code) |

### 3.3 Project Structure

```
dev-graph-kit/
├── README.md
├── LICENSE
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── packages/
│   ├── core/
│   │   ├── ontology/           # Node/edge type definitions
│   │   ├── schemas/            # Pydantic models
│   │   └── services/           # Business logic
│   ├── storage/
│   │   ├── neo4j/              # Neo4j client, queries
│   │   └── graphiti/           # Graphiti integration
│   ├── ingester_ts/
│   │   ├── parser/             # ts-morph wrapper
│   │   ├── extractors/         # AST → nodes
│   │   └── resolvers/          # Import resolution
│   ├── ingester_sql/
│   │   ├── parser/             # SQL parser
│   │   └── extractors/         # Schema → nodes
│   ├── dag/
│   │   ├── defs/               # Dagster definitions
│   │   │   ├── __init__.py
│   │   │   └── repository.py
│   │   ├── jobs/               # Job definitions
│   │   │   ├── full_scan.py
│   │   │   ├── incremental_scan.py
│   │   │   └── refactor_plan.py
│   │   ├── ops/                # Operations
│   │   │   ├── scan_files.py
│   │   │   ├── build_code_graph.py
│   │   │   ├── resolve_dependencies.py
│   │   │   ├── impact_analysis.py
│   │   │   ├── generate_plan.py
│   │   │   ├── record_memory.py
│   │   │   └── validate_changes.py
│   │   └── sensors/            # Triggers
│   ├── mcp_server/
│   │   ├── server.py
│   │   ├── tools/              # MCP tool implementations
│   │   ├── resources/          # MCP resource providers
│   │   └── prompts/            # MCP prompt templates
│   └── cli/
│       ├── __init__.py
│       └── commands/           # CLI command handlers
├── examples/
│   ├── react_ts_app/           # Demo React/TS project
│   └── express_api/            # Demo Express API
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── ontology.md
│   ├── mcp.md
│   ├── install.md
│   └── examples.md
└── tests/
```

### 3.4 Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Codebase   │────▶│  Ingester   │────▶│   Neo4j     │
│  (TS/TSX)   │     │  (ts-morph) │     │  Code Graph │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
             ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
             │  Graphiti   │           │   Dagster   │           │ MCP Server  │
             │   Memory    │◀─────────▶│     DAG     │◀─────────▶│   (Agent)   │
             └─────────────┘           └─────────────┘           └─────────────┘
```

### 3.5 Local Data Storage

```
~/.dev-graph-kit/
├── config.toml                 # Global CLI config
└── projects/
    └── <project-id>/
        ├── snapshots/          # Graph state snapshots
        ├── cache/              # Cached scan artifacts
        └── logs/               # Execution logs
```

### 3.6 Project Configuration

```toml
# .dgk/project.toml
[project]
name = "my-app"
language = "typescript"
root = "."

[scan]
include = ["src", "packages", "apps"]
exclude = ["dist", "build", "node_modules", ".next"]

[memory]
enabled = true
scope = "project"

[dag]
engine = "dagster"

[graph]
backend = "neo4j"
```

---

## 4. Ontology v1

> Limited model by design. Not trying to describe everything.

### 4.1 Code Nodes

| Label | Description |
|-------|-------------|
| `Repository` | Root repository |
| `Package` | npm/pip package |
| `Directory` | Folder in project |
| `File` | Source file |
| `Module` | ES/Python module |
| `Function` | Function/method |
| `Class` | Class definition |
| `Component` | React/Vue component |
| `Hook` | React hook |
| `Type` | TypeScript type |
| `Interface` | TypeScript interface |
| `Endpoint` | API endpoint |
| `Table` | Database table |
| `Query` | SQL/ORM query |

### 4.2 Architecture Nodes

| Label | Description |
|-------|-------------|
| `Feature` | Product feature |
| `DomainEntity` | Domain model entity |
| `BusinessRule` | Business constraint |
| `Integration` | External service |
| `ConfigFlag` | Feature flag/config |

### 4.3 Agent Memory Nodes

| Label | Description |
|-------|-------------|
| `Analysis` | Agent analysis session |
| `Plan` | Multi-step execution plan |
| `Decision` | Recorded decision with rationale |
| `Change` | Code change record |
| `Validation` | Test/validation result |
| `Hypothesis` | Agent hypothesis |
| `Todo` | Pending task |
| `Session` | Agent session |

### 4.4 Provenance Nodes

| Label | Description |
|-------|-------------|
| `Commit` | Git commit |
| `PR` | Pull request |
| `Issue` | Issue/ticket |
| `Snapshot` | Graph state snapshot |
| `Document` | Documentation file |

### 4.5 Relationships

| Type | Description |
|------|-------------|
| `IMPORTS` | Module imports module |
| `CALLS` | Function calls function |
| `USES_TYPE` | Uses type definition |
| `READS` | Reads from table/state |
| `WRITES` | Writes to table/state |
| `EXPOSES` | Module exposes symbol |
| `DEPENDS_ON` | Package dependency |
| `IMPLEMENTS` | Code implements feature |
| `AFFECTS` | Change affects entity |
| `BELONGS_TO` | Entity belongs to domain |
| `CONSTRAINED_BY` | Constrained by rule |
| `BASED_ON` | Decision based on analysis |
| `PROPOSES` | Plan proposes change |
| `RESULTED_IN` | Change resulted in validation |
| `SUPERSEDES` | Decision supersedes decision |
| `VALIDATED_BY` | Change validated by test |
| `OBSERVED_IN` | Fact observed in session |
| `DERIVED_FROM` | Snapshot derived from snapshot |
| `CHANGED_BY` | Node changed by commit |

---

## 5. Graph vs DAG: What Goes Where

This is critical. The two stores serve different purposes.

### 5.1 Graph DB Stores (Neo4j + Graphiti)

- Permanent knowledge about the project
- Module relationships and dependencies
- Domain connections
- Agent memory (analyses, decisions, changes)
- Provenance and history

### 5.2 DAG Stores (Dagster)

- Executable plans
- Step ordering
- Step dependencies
- Execution status
- Run history

### 5.3 Example

**In Graph:**
```cypher
// Knowledge and memory
(c:Component {name: "AuthForm"})-[:USES_TYPE]->(t:Type {name: "LoginPayload"})
(d:Decision {summary: "don't duplicate session parsing"})-[:AFFECTS]->(m:Module {path: "auth/shared"})
```

**In DAG:**
```
scan_auth_files
  → find_usages
    → generate_refactor_plan
      → apply_changes
        → run_tests
          → record_results
```

DAG does not replace the knowledge graph. It only executes workflows.

---

## 6. MCP Tools Interface

### 6.1 Graph Tools

```yaml
graph.get_context:
  description: Get relevant code context for a query
  params:
    query: string           # Natural language or node reference
    depth: number           # Traversal depth (default: 2)
    include: Array<string>  # Node labels to include
  returns: {nodes: Array, relationships: Array, summary: string}

graph.search_entities:
  description: Search for entities by name/type
  params:
    query: string           # Search query
    labels: Array<string>   # Filter by node labels
    limit: number           # Max results
  returns: {entities: Array<Node>}

graph.get_neighbors:
  description: Get neighboring nodes
  params:
    nodeId: string          # Target node
    direction: string       # 'in' | 'out' | 'both'
    types: Array<string>    # Relationship types to follow
    depth: number
  returns: {nodes: Array, relationships: Array}

graph.impact_analysis:
  description: Analyze impact of changes to a node
  params:
    target: string          # Node identifier
    changeType: string      # 'modify' | 'delete' | 'rename'
  returns: {
    directlyAffected: Array<Node>,
    transitivelyAffected: Array<Node>,
    riskScore: number,
    recommendations: Array<string>
  }

graph.upsert_entities:
  description: Create or update nodes in the code graph
  params:
    entities: Array<{label, properties}>
  returns: {created: number, updated: number}

graph.upsert_relations:
  description: Create or update relationships
  params:
    relations: Array<{type, from, to, properties}>
  returns: {created: number, updated: number}
```

### 6.2 Memory Tools

```yaml
memory.record_analysis:
  description: Record an analysis session
  params:
    scope: string           # What was analyzed
    summary: string         # Key findings
    findings: Array<{type, detail, severity}>
    relatedNodes: Array<string>
  returns: {analysisId: string}

memory.record_plan:
  description: Record a plan (links to DAG)
  params:
    goal: string
    steps: Array<{name, description}>
    targets: Array<string>  # Node IDs
  returns: {planId: string}

memory.record_decision:
  description: Record a decision with rationale
  params:
    context: string         # Why this decision was needed
    choice: string          # What was decided
    rationale: string       # Why this choice
    alternatives: Array<{option, reason}>
    basedOn: Array<string>  # Analysis IDs
  returns: {decisionId: string}

memory.record_change:
  description: Record a code change
  params:
    type: string            # 'refactor' | 'feature' | 'fix' | 'chore'
    description: string
    files: Array<{path, changeType}>
    proposedBy: string      # Plan ID
  returns: {changeId: string}

memory.record_validation:
  description: Record validation/test results
  params:
    type: string            # 'test' | 'lint' | 'typecheck' | 'review'
    result: string          # 'pass' | 'fail' | 'partial'
    details: object
    validates: string       # Change ID
  returns: {validationId: string}

memory.get_recent_context:
  description: Retrieve relevant memory context
  params:
    query: string           # Natural language query
    scope: string           # Optional scope filter
    timeRange: {from, to}   # Optional time bounds
    types: Array<string>    # Memory node types
    limit: number
  returns: {memories: Array<MemoryNode>}
```

### 6.3 DAG Tools

```yaml
dag.create_plan:
  description: Create a multi-step execution plan
  params:
    goal: string
    steps: Array<{
      id: string,
      name: string,
      description: string,
      dependencies: Array<string>,
      toolCalls: Array<{tool, params}>
    }>
  returns: {planId: string, dagsterRunId: string}

dag.get_plan:
  description: Get plan details
  params:
    planId: string
  returns: {plan: Plan, steps: Array<Step>}

dag.run_plan:
  description: Execute a plan
  params:
    planId: string
    startFrom: string       # Optional step to start from
  returns: {runId: string, status: string}

dag.step_status:
  description: Get status of a specific step
  params:
    planId: string
    stepId: string
  returns: {status: string, output: any, error: string}

dag.cancel_plan:
  description: Cancel a running plan
  params:
    planId: string
  returns: {cancelled: boolean}
```

### 6.4 Scan Tools

```yaml
scan.project:
  description: Full project scan
  params:
    path: string            # Project root
    options: {incremental: boolean}
  returns: {nodesCreated: number, relationsCreated: number}

scan.file:
  description: Scan a single file
  params:
    path: string
  returns: {nodes: Array, relations: Array}

scan.changed_files:
  description: Scan only changed files (git-based)
  params:
    since: string           # Commit SHA or 'HEAD~1'
  returns: {filesScanned: number, changes: object}
```

### 6.5 Utility Tools

```yaml
project.status:
  description: Get project status
  returns: {
    graph: {nodes: number, relations: number},
    memory: {analyses: number, decisions: number},
    lastScan: timestamp,
    services: {neo4j: boolean, dagster: boolean}
  }

project.reindex:
  description: Rebuild entire graph from scratch
  returns: {status: string, duration: number}

project.snapshot:
  description: Create a graph snapshot
  params:
    name: string
  returns: {snapshotId: string, path: string}
```

---

## 7. MCP Resource Model

Resources that agents can read directly:

| Resource URI | Description |
|--------------|-------------|
| `project://schema` | Graph schema (node/edge types) |
| `project://summary` | Project overview and stats |
| `project://recent-decisions` | Last N decisions |
| `project://open-plans` | Currently open plans |
| `file://<path>/context` | Context for a specific file |
| `entity://<id>` | Full entity details |
| `plan://<id>` | Plan details and status |

This simplifies agent access to "ready context" beyond just tool calls.

---

## 8. CLI Commands

### 8.1 Command Reference

| Command | Description |
|---------|-------------|
| `dgk init` | Initialize project, create config, check dependencies |
| `dgk dev` | Start local stack (Neo4j, Dagster, MCP server) |
| `dgk scan [path]` | Scan codebase, build/update graph |
| `dgk scan --changed` | Incremental scan of git-changed files |
| `dgk query "..."` | Quick graph search |
| `dgk impact <file>` | Show impact analysis for a file |
| `dgk plan "..."` | Create a DAG plan from description |
| `dgk plans` | List open plans |
| `dgk snapshot` | Create graph state snapshot |
| `dgk doctor` | Check Neo4j/MCP/Dagster health |

### 8.2 Example Usage

```bash
# Initialize a project
dgk init

# Start development environment
dgk dev

# Scan the project
dgk scan .
dgk scan --changed

# Query the graph
dgk query "auth module"

# Analyze impact
dgk impact src/features/auth/LoginForm.tsx

# Create and manage plans
dgk plan "extract auth shared logic"
dgk plans

# Maintenance
dgk snapshot
dgk doctor
```

---

## 9. User Flows

### 9.1 Initial Setup

```bash
# 1. Clone and setup
git clone https://github.com/org/dev-graph-kit.git
cd dev-graph-kit
cp .env.example .env

# 2. Start services
docker compose up -d        # Neo4j

# 3. Install dependencies
uv sync                     # Python packages
pnpm install                # TypeScript packages (optional, for ingester)

# 4. Initialize
uv run dgk init

# 5. Start development
uv run dgk dev
```

**Result:**
- Neo4j available at `localhost:7474`
- Dagster UI at `localhost:3000`
- MCP server at `localhost:8080`

### 9.2 Typical Working Session

```bash
# Scan the project
uv run dgk scan .

# Create a plan
uv run dgk plan "refactor auth flow"

# Check status
uv run dgk status
```

Meanwhile, the agent can call MCP tools to read/write the graph.

### 9.3 Agent Lifecycle

Typical agent cycle:

1. **Get context**: `graph.get_context("auth flow")` → returns related entities, decisions, changes, neighboring modules
2. **Create plan**: `dag.create_plan(...)` → returns executable DAG
3. **Execute steps**: Agent runs through DAG steps
4. **Record after each step**:
   - `memory.record_analysis(...)` — what was found
   - `memory.record_change(...)` — what was modified
   - `memory.record_validation(...)` — what passed/failed
5. **Record decision**: `memory.record_decision(...)` — why this approach was chosen
6. **Update graph**: `graph.upsert_relations(...)` — update connections

This is how the tool becomes memory, not just a viewer.

### 9.4 Example Scenario

**User asks agent:**
> "Extract shared auth logic from feature A into common package"

**Agent workflow:**
```
1. graph.search_entities("auth logic shared package")
2. graph.impact_analysis(entity="Module:featureA/auth")
3. memory.get_recent_context(scope="auth")
4. dag.create_plan(goal="extract auth shared logic")
```

**Generated DAG:**
```
1. Scan auth-related files
2. Find imports/calls
3. Detect shared logic candidates
4. Generate extraction target
5. Apply move/refactor
6. Update imports
7. Run tests
8. Record results and decision
```

**After execution, agent records:**
- `Analysis`: what was found
- `Change`: what was modified
- `Validation`: what passed/failed
- `Decision`: why this extraction approach was chosen

---

## 10. Docker Compose

Minimal setup for v1:

```yaml
services:
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc"]
  
  # Optional: Dagster webserver
  dagster-webserver:
    build: .
    command: dagster-webserver -h 0.0.0.0 -p 3000
    ports:
      - "3000:3000"
    depends_on:
      - neo4j
    profiles:
      - full
  
  # Optional: Dagster daemon
  dagster-daemon:
    build: .
    command: dagster-daemon run
    depends_on:
      - neo4j
    profiles:
      - full

volumes:
  neo4j_data:
```

**Note:** MCP server and CLI run locally from venv, not containerized in v1. This simplifies debugging and development.

---

## 11. MVP Roadmap

### v0.1 — Usable Local Prototype

**Goal:** Basic graph operations working

| Deliverable | Description |
|-------------|-------------|
| Docker Compose | Neo4j up/down |
| TS Scanner | ts-morph based code graph builder |
| Basic Graph | Code nodes and relationships |
| MCP Server | Read/write/query operations |
| CLI | `init`, `dev`, `scan`, `query` |
| Impact Analysis | Basic dependency traversal |
| Memory Nodes | Simple analysis/decision nodes |

**Exit Criteria:** Scan a React app, query dependencies, record analysis

### v0.2 — Agent Memory

**Goal:** Persistent agent context

| Deliverable | Description |
|-------------|-------------|
| Graphiti Integration | Temporal memory layer |
| Full Memory Model | Decisions, plans, changes, validations |
| Snapshots | Graph state snapshots |
| Context Retrieval | `memory.get_recent_context` |
| Incremental Scan | `scan --changed` for git changes |

**Exit Criteria:** Agent can record and retrieve past analyses across sessions

### v0.3 — DAG Execution

**Goal:** Multi-step plan execution

| Deliverable | Description |
|-------------|-------------|
| Dagster Setup | Jobs, ops, resources |
| Plan Creation | `dag.create_plan` |
| Plan Execution | `dag.run_plan` |
| Step Status | Real-time status tracking |
| Plan History | List and inspect past plans |

**Exit Criteria:** Agent can create and execute multi-step refactor plans

### v0.4 — Public OSS Release

**Goal:** Ready for community

| Deliverable | Description |
|-------------|-------------|
| Example Projects | react_ts_app, express_api |
| Documentation | install.md, architecture.md, examples.md |
| One-Command Bootstrap | `./setup.sh` or similar |
| Agent Guides | Cursor/Codex/Claude Code integration |
| Tests + CI | pytest, GitHub Actions |
| Polish | Error handling, logging, performance |

**Exit Criteria:** Stranger can clone, setup in 5 min, and use with their agent

---

## 12. Technical Decisions

### 12.1 Why Neo4j over alternatives?

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Neo4j** | Mature, Docker-ready, MCP server exists | Heavier than embedded | ✅ Selected |
| Memgraph | Fast, Cypher-compatible | Smaller ecosystem | ❌ |
| DGraph | GraphQL native | Different query language | ❌ |
| SQLite + joins | Simple | Not a real graph | ❌ |

### 12.2 Why Dagster over Airflow?

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Dagster** | Simple local dev via `dg dev`, modern | Smaller community | ✅ Selected |
| Airflow | Popular, mature | Complex local setup (docs note this) | ❌ |
| Prefect | Good DX | Cloud-first focus | ❌ |
| Custom | Minimal deps | Reinventing the wheel | ❌ |

### 12.3 Why Graphiti for memory?

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Graphiti** | Built for AI agents, temporal, episodes, evolving facts | Newer project | ✅ Selected |
| Raw Neo4j | Direct control | Must build memory logic ourselves | ❌ |
| Mem0 | Simple API | Less graph-native | ❌ |
| Custom | Tailored | Significant effort | ❌ |

### 12.4 Why Python for core?

| Aspect | Reasoning |
|--------|-----------|
| Graphiti | Python-native, open-source |
| Dagster | Python ecosystem, `dg dev` workflow |
| MCP Server | Faster to build in Python |
| TS Scanner | Separate package, called via subprocess/bridge |

---

## 13. What NOT to Do in v1

Critical scope constraints:

| Don't | Why |
|-------|-----|
| Build custom graph DB | Neo4j exists and works |
| Build custom workflow engine | Dagster exists and works |
| Support 10 languages immediately | Focus on TS/JS first |
| Build full semantic indexing | Start with AST-based extraction |
| Build "universal autonomous agent platform" | Focus on memory + DAG for coding agents |

**v1 Focus:**
- TS/JS codebases
- Local install
- Graph memory
- Plan DAG
- MCP access

---

## 14. README Requirements

README must answer three questions immediately:

### What is it?
> "Local-first graph memory and DAG orchestration kit for coding agents."

### Why use it?
> "Helps agents remember project architecture, past decisions, and build executable plans."

### How to start?

```bash
git clone https://github.com/org/dev-graph-kit.git
cd dev-graph-kit
cp .env.example .env
docker compose up -d
uv sync
uv run dgk init
uv run dgk dev
```

**Plus:** GIF/screenshot showing:
- Scan project
- Query graph
- Create plan
- Use from MCP client

---

## 15. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Neo4j Community limits | Medium | Low | Schema designed for single-instance |
| Graphiti API changes | Medium | Medium | Pin version, abstract interface |
| MCP protocol evolution | High | Medium | Isolate MCP layer, easy to update |
| TypeScript scanner edge cases | Medium | High | Start with common patterns, iterate |
| Performance at scale | Medium | Medium | Incremental scanning, query limits |
| Dagster complexity for simple use | Low | Low | Use minimal job structure |

---

## 16. Open Questions

| Question | Options | Decision Needed By |
|----------|---------|-------------------|
| Support Python codebases in v1? | Yes / No / Stretch goal | v0.2 planning |
| Graph persistence across machines? | Export/import / Git-based / Cloud sync | v0.3 |
| Multi-repo support? | Single repo / Multi-repo | v0.2 |
| Custom node types via config? | Yes / No / Plugin system | v0.3 |

---

## 17. Appendix

### A. Example Cypher Queries

```cypher
// Find all components using a specific hook
MATCH (c:Component)-[:USES_TYPE]->(h:Hook {name: 'useAuth'})
RETURN c.name, c.path

// Impact analysis: what calls this function?
MATCH (caller:Function)-[:CALLS*1..3]->(target:Function {name: 'validateUser'})
RETURN caller.name, caller.path

// Find circular dependencies
MATCH path = (m1:Module)-[:IMPORTS*]->(m1)
RETURN path

// Get recent agent decisions about a file
MATCH (d:Decision)-[:AFFECTS]->(f:File {path: 'src/auth/login.tsx'})
WHERE d.timestamp > datetime() - duration('P7D')
RETURN d.choice, d.rationale, d.timestamp
ORDER BY d.timestamp DESC

// Find all modules affected by a type change
MATCH (t:Type {name: 'UserSession'})<-[:USES_TYPE]-(f:Function)<-[:CONTAINS]-(m:Module)
RETURN DISTINCT m.path
```

### B. Environment Variables

```bash
# .env.example

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Graphiti
GRAPHITI_NEO4J_URI=${NEO4J_URI}

# Dagster
DAGSTER_HOME=.dagster

# MCP Server
MCP_SERVER_PORT=8080
MCP_SERVER_HOST=localhost

# Scanning
SCAN_IGNORE=node_modules,dist,build,.git
SCAN_EXTENSIONS=.ts,.tsx,.js,.jsx
```

### C. MCP Server Configuration

```json
{
  "mcpServers": {
    "dev-graph-kit": {
      "command": "uv",
      "args": ["run", "dgk", "mcp"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687"
      }
    }
  }
}
```

### D. Dagster Job Example

```python
# packages/dag/jobs/full_scan.py
from dagster import job, op

@op
def scan_files(context, path: str):
    """Scan all files in path."""
    # Call TS ingester
    pass

@op
def build_code_graph(context, scan_result):
    """Build graph from scan results."""
    pass

@op
def record_scan_memory(context, graph_result):
    """Record scan in memory layer."""
    pass
Why 
@job
def full_scan_job():
    result = scan_files()
    graph = build_code_graph(result)
    record_scan_memory(graph)
```

### E. Recommended v1 Stack Summary

| Component | Choice | Notes |
|-----------|--------|-------|
| Language | Python monorepo | Graphiti/Dagster ecosystem |
| Graph DB | Neo4j Community | Docker-based |
| Memory | Graphiti | Temporal memory layer |
| DAG | Dagster | Local via `dg dev` |
| MCP | Python MCP Server | Neo4j MCP as reference |
| Code Ingester | TypeScript + ts-morph | Separate package |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-04-17 | Major update: renamed to dev-graph-kit, detailed ontology, MCP resources, agent lifecycle, expanded roadmap, scope constraints |
| 1.0 | 2026-04-17 | Initial PRD |
