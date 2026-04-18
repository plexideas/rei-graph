# Examples

Step-by-step examples of using dev-graph-kit with the demo projects.

## Prerequisites

Services running:
```bash
docker compose up -d      # Neo4j
uv run dgk doctor          # Verify all healthy
```

---

## Example 1: Scan react_ts_app

### Step 1: Scan the project

```bash
uv run dgk scan examples/react_ts_app
```

Output:
```
Scanning 5 file(s)...
Done: 14 nodes, 18 relationships from 5 files
```

### Step 2: Query the graph

```bash
uv run dgk query "useAuth"
```

Output:
```
hook:src/hooks.ts:useAuth  (Hook)  hooks.ts:7
```

```bash
uv run dgk query "LoginForm"
```

Output:
```
component:src/components.tsx:LoginForm  (Component)  components.tsx:11
```

### Step 3: Run impact analysis

```bash
uv run dgk impact examples/react_ts_app/src/hooks.ts
```

Output:
```
Impact analysis for: examples/react_ts_app/src/hooks.ts
  Directly affected (1):
    - component:src/components.tsx:LoginForm
  Transitively affected (1):
    - module:src/App.tsx
  Risk score: 0.2
  Recommendations:
    - Review LoginForm before modifying hooks.ts
```

### Step 4: Snapshot the graph

```bash
uv run dgk snapshot --project-id react-demo
```

Output:
```
Snapshot saved: ~/.dev-graph-kit/snapshots/react-demo/snapshots/snap_20260418T100000Z.json
```

---

## Example 2: Scan express_api

```bash
uv run dgk scan examples/express_api
```

Output:
```
Scanning 4 file(s)...
Done: 18 nodes, 22 relationships from 4 files
```

Query the API routes:
```bash
uv run dgk query "userRouter"
```

---

## Example 3: Incremental scan after a change

```bash
# Edit a file
echo "// a new comment" >> examples/react_ts_app/src/utils.ts
git add -A

# Scan only changed files
uv run dgk scan examples/react_ts_app --changed
```

Output:
```
Scanning 1 changed file(s)...
Done: 3 nodes, 2 relationships from 1 changed files
```

---

## Example 4: Using MCP tools with Claude Code

Start the MCP server (Claude Code manages this via config, but you can test manually):

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' | uv run dgk mcp
```

### Agent session example

In Claude Code with MCP connected:

**You:** "What does the auth flow look like in this project?"

**Agent calls:**
```
graph.get_context({"query": "auth"})
→ nodes: [LoginForm, useAuth, validateEmail, ...], relationships: [IMPORTS, CALLS, ...]
→ summary: "Found 6 nodes related to auth: 1 Component, 1 Hook, 2 Functions..."
```

**You:** "Refactor the auth to extract shared logic"

**Agent calls:**
```
memory.get_recent_context({"query": "auth"})
→ no prior decisions

dag.create_plan({
  "goal": "Extract shared auth logic",
  "steps": [
    {"name": "analyze", "description": "Find duplicated auth code"},
    {"name": "extract", "description": "Move to shared/auth.ts"},
    {"name": "update_imports", "description": "Update all import paths"},
    {"name": "validate", "description": "Run tests"}
  ]
})
→ planId: "plan:abc123"

dag.run_plan({"planId": "plan:abc123"})
→ status: "running"

# ... agent works through steps ...

memory.record_decision({
  "context": "auth refactor",
  "choice": "Extract validateEmail and fetchUser to shared/auth.ts",
  "rationale": "Used by both LoginForm and UserProfile components"
})

memory.record_change({
  "description": "Extracted shared auth utilities",
  "affectedFiles": ["src/utils.ts", "shared/auth.ts"]
})
```

---

## Example 5: Record and retrieve agent memory

```bash
# Start MCP server manually to test
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory.record_decision","arguments":{"context":"auth","choice":"use JWT","rationale":"stateless sessions"}}}' | uv run dgk mcp
```

Retrieve in next session:
```bash
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"memory.get_recent_context","arguments":{"query":"auth","limit":5}}}' | uv run dgk mcp
```

---

## Example 6: Create and track a plan from CLI

```bash
# Create a plan
uv run dgk plan "Add user profile page"

# List open plans
uv run dgk plans
```

Output:
```
Open plans (1):
  plan:abc123  Add user profile page  [pending]
```
