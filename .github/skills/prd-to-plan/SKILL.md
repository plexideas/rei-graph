---
name: prd-to-plan
description: "Turn a PRD into a multi-phase implementation plan using tracer-bullet vertical slices, saved as a local Markdown file in ./plans/. Use when: user wants to break down a PRD, create an implementation plan, plan phases from a PRD, mentions 'tracer bullets', asks for vertical slices, or says 'plan this PRD'."
argument-hint: "Optionally specify the PRD file path or feature name"
---

# PRD to Plan

Break a PRD into a phased implementation plan using vertical slices (tracer bullets). Output is a Markdown file in `./plans/`.

## Process

### 1. Confirm the PRD is in context

The PRD should already be in the conversation (attached file, pasted content, or referenced path). If it isn't, ask the user to paste it or point you to the file. Read it fully before proceeding.

### 2. Explore the codebase

If you have not already explored the codebase, do so to understand the current architecture, existing patterns, and integration layers. Use a read-only subagent if the codebase is large. Skip this step if the project has no code yet.

### 3. Identify durable architectural decisions

Before slicing, extract high-level decisions from the PRD that are unlikely to change throughout implementation:

- Route structures / URL patterns
- Database schema shape
- Key data models and ontology
- Authentication / authorization approach
- Third-party service boundaries
- Technology choices (languages, frameworks, databases)

These go in the plan header so every phase can reference them.

### 4. Draft vertical slices

Break the PRD into **tracer bullet** phases. Each phase is a thin vertical slice that cuts through ALL integration layers end-to-end.

**Rules for slicing:**

- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones
- Earlier phases establish foundations that later phases build on
- Do NOT include specific file names, function names, or implementation details that are likely to change as later phases are built
- DO include durable decisions: route paths, schema shapes, data model names, technology choices

**What makes a good slice:**

- Has clear entry and exit points
- Touches every integration layer the feature requires
- Can be tested or demonstrated independently
- Is small enough to complete in a focused session

**What is NOT a vertical slice:**

- "Set up the database schema" (horizontal — one layer only)
- "Build all the API endpoints" (horizontal — one layer only)
- "Write all the tests" (horizontal — one layer only)

### 5. Quiz the user

Present the proposed breakdown as a numbered list. For each phase show:

- **Title**: short descriptive name
- **User stories covered**: which user stories or goals from the PRD this addresses

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Should any phases be merged or split further?
- Are the durable architectural decisions correct?

Iterate until the user approves the breakdown.

### 6. Write the plan file

Create `./plans/` if it doesn't exist. Write the plan as a Markdown file named after the feature (e.g., `./plans/user-onboarding.md`). Use the template below.

## Plan Template

```markdown
# Plan: <Feature Name>

> Source PRD: <brief identifier or link>

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: ...
- **Schema**: ...
- **Key models**: ...
- **Tech stack**: ...
- (add/remove sections as appropriate)

---

## Phase 1: <Title>

**User stories**: <list from PRD>

### What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

### Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

---

## Phase 2: <Title>

**User stories**: <list from PRD>

### What to build

...

### Acceptance criteria

- [ ] ...

<!-- Repeat for each phase -->
```
