# Graph Ontology

Node labels and relationship types stored in Neo4j by rei-graph.

## Code Nodes

Extracted by the TypeScript ingester from `.ts`/`.tsx` source files.

| Label | Description | Key properties |
|-------|-------------|----------------|
| `Module` | ES module (file) | `id`, `name`, `path` |
| `Function` | Function or method | `id`, `name`, `path`, `line`, `exported` |
| `Class` | Class definition | `id`, `name`, `path`, `line` |
| `Component` | React/Vue component | `id`, `name`, `path`, `line` |
| `Hook` | React hook (`use*`) | `id`, `name`, `path`, `line` |
| `Type` | TypeScript type alias | `id`, `name`, `path`, `line` |
| `Interface` | TypeScript interface | `id`, `name`, `path`, `line` |
| `Repository` | Root repository | `id`, `name`, `path` |
| `Package` | npm/pip package | `id`, `name`, `version` |
| `Directory` | Folder in project | `id`, `path` |
| `File` | Source file | `id`, `path`, `language` |
| `Endpoint` | API endpoint | `id`, `method`, `path` |
| `Table` | Database table | `id`, `name`, `schema` |
| `Query` | SQL/ORM query | `id`, `sql`, `table` |

## Architecture Nodes

Higher-level domain knowledge added manually or by agents.

| Label | Description | Key properties |
|-------|-------------|----------------|
| `Feature` | Product feature | `id`, `name`, `description` |
| `DomainEntity` | Domain model entity | `id`, `name`, `domain` |
| `BusinessRule` | Business constraint | `id`, `description`, `scope` |
| `Integration` | External service | `id`, `name`, `type` |
| `ConfigFlag` | Feature flag / config | `id`, `name`, `defaultValue` |

## Agent Memory Nodes

Recorded by agents during work sessions via `memory.*` tools.

| Label | Description | Key properties |
|-------|-------------|----------------|
| `Analysis` | Agent analysis session | `id`, `scope`, `findings`, `timestamp` |
| `Plan` | Multi-step execution plan | `id`, `goal`, `status`, `createdAt` |
| `Step` | Individual plan step | `id`, `name`, `description`, `status` |
| `Decision` | Recorded decision | `id`, `context`, `choice`, `rationale`, `timestamp` |
| `Change` | Code change record | `id`, `description`, `affectedFiles`, `timestamp` |
| `Validation` | Test/validation result | `id`, `type`, `passed`, `notes`, `timestamp` |
| `Hypothesis` | Agent hypothesis | `id`, `description`, `confidence`, `timestamp` |
| `Todo` | Pending task | `id`, `description`, `priority`, `status` |
| `Session` | Agent session | `id`, `startedAt`, `endedAt`, `summary` |

## Provenance Nodes

| Label | Description | Key properties |
|-------|-------------|----------------|
| `Commit` | Git commit | `id`, `sha`, `message`, `author`, `timestamp` |
| `PR` | Pull request | `id`, `number`, `title`, `status` |
| `Issue` | Issue / ticket | `id`, `number`, `title`, `status` |
| `Snapshot` | Graph state snapshot | `id`, `path`, `timestamp`, `nodeCount` |
| `Document` | Documentation file | `id`, `path`, `title` |

## Relationships

| Type | From → To | Description |
|------|-----------|-------------|
| `IMPORTS` | Module → Module | Module imports another |
| `CALLS` | Function → Function | Function calls function |
| `USES_TYPE` | Any → Type/Interface | Uses a type definition |
| `READS` | Function → Table | Reads from table/state |
| `WRITES` | Function → Table | Writes to table/state |
| `EXPOSES` | Module → Function/Class/… | Module exports symbol |
| `DEPENDS_ON` | Package → Package | Package dependency |
| `IMPLEMENTS` | Function/Class → Feature | Implements a feature |
| `AFFECTS` | Change/Decision → Any | Change/decision affects entity |
| `BELONGS_TO` | Any → DomainEntity | Entity belongs to domain |
| `CONSTRAINED_BY` | Any → BusinessRule | Constrained by a rule |
| `BASED_ON` | Decision → Analysis | Decision based on analysis |
| `PROPOSES` | Plan → Change | Plan proposes a change |
| `RESULTED_IN` | Change → Validation | Change resulted in validation |
| `SUPERSEDES` | Decision → Decision | Decision supersedes prior |
| `VALIDATED_BY` | Change → Validation | Change validated by test |
| `OBSERVED_IN` | Analysis → Session | Analysis observed in session |
| `DERIVED_FROM` | Snapshot → Snapshot | Snapshot derived from prior |
| `CHANGED_BY` | Any → Commit | Node changed by commit |
| `HAS_STEP` | Plan → Step | Plan contains step |

## Node ID conventions

Code node IDs are derived deterministically from the source location:

```
<label_lower>:<file_path>:<name>

Examples:
  module:src/auth.ts
  function:src/auth.ts:login
  component:src/App.tsx:App
  hook:src/hooks.ts:useAuth
  interface:src/types.ts:User
  type:src/types.ts:AuthStatus
```

Memory and provenance node IDs use UUIDs or human-readable slugs:

```
decision:abc123
analysis:2026-04-18T10:00:00Z
plan:refactor-auth-20260418
```

## Example Cypher queries

```cypher
-- All components using a specific hook
MATCH (c:Component)-[:USES_TYPE]->(h:Hook {name: 'useAuth'})
RETURN c.name, c.path

-- Impact: what calls this function transitively?
MATCH (caller:Function)-[:CALLS*1..3]->(t:Function {name: 'validateUser'})
RETURN caller.name, caller.path

-- Recent decisions affecting auth
MATCH (d:Decision)-[:AFFECTS]->(m:Module)
WHERE m.path CONTAINS 'auth' AND d.timestamp > datetime() - duration('P7D')
RETURN d.choice, d.rationale ORDER BY d.timestamp DESC

-- Open plans
MATCH (p:Plan) WHERE p.status IN ['pending','running'] RETURN p
```
