# Wiki Memory System Design

## Goal

Build a wiki-based memory system for a single user that supports:

- coding agent workflows
- project management workflows
- reusable knowledge management across papers, code docs, specs, notes, and repos

This system is not a generic memory backend. It is a wiki-based context substrate for agents:

- ingest external input
- assemble usable context for work
- let the agent continue exploration
- crystallize successful results back into the system
- keep the system healthy over time

## First Principles

1. The system exists to provide durable, usable working context across sessions.
2. Memory is not just storage. It must be traceable, correctable, and evolvable.
3. The semantic core must stay stable even if projections, indexes, or adapters change.
4. Search, graph, embeddings, and markdown pages are derived layers, not the semantic core.
5. Agents should enter through structured context, not through ad hoc search alone.
6. The system should not try to pre-structure every detail in advance.
7. The system should build a navigable knowledge terrain; the agent explores within it.
8. High-value exploration results should be crystallized back into the system.

## Core Loop

```text
Ingest
  -> Query
  -> Agent work
  -> Crystallize
  -> Lint
```

Meaning:

- `Ingest`: bring external input into the system
- `Query`: provide a structured context entrypoint
- `Agent work`: perform task-specific exploration and reasoning
- `Crystallize`: write back reusable results
- `Lint`: detect and repair drift, inconsistency, and decay

## Semantic Core

The system is built around five core domain objects:

- `Source`
- `Node`
- `Knowledge`
- `Activity`
- `WorkItem`

These answer five irreducible questions:

- what has the system seen
- what stable objects exist in the system world
- what does the system currently believe
- what work has happened
- what work needs to be tracked or advanced

## Core Object Model

### Source

Represents stable ingested input from the outside world.

Responsibilities:

- preserve a stable internal representation of input
- support traceability and re-interpretation
- provide locally referenceable segments for evidence

Non-responsibilities:

- not the system's conclusion
- not the definition of a stable object
- not a work process record
- not a task, bug, issue, or requirement

Allowed kinds:

- `repo`
- `file`
- `pdf`
- `web`
- `markdown`
- `note`
- `openapi`
- `office`
- `conversation`
- `meeting_record`

Minimum fields:

- `id`
- `kind`
- `origin`
- `title`
- `fingerprint`
- `content_type`
- `payload`
- `segments`
- `metadata`
- `status`
- `captured_at`
- `updated_at`

Field notes:

- `origin`: path, URL, repo+commit, document identifier, or equivalent
- `fingerprint`: stable content hash
- `content_type`: `text | markdown | structured | repo_map | binary_stub`
- `payload`: normalized content body
- `segments`: local reference units for evidence

Each segment should contain:

- `segment_id`
- `locator`
- `excerpt`
- `hash`

Suggested status:

- `active`
- `invalid`
- `archived`

### Node

Represents a stable object in the system world.

Responsibilities:

- act as the stable center for relationships
- act as the anchor for knowledge, activity, and work items

Non-responsibilities:

- not the fact about an object
- not the process around an object
- not the task around an object
- not raw source content

Allowed kinds:

- `project`
- `repo`
- `module`
- `service`
- `api`
- `document`
- `paper`
- `concept`
- `person`
- `team`
- `component`
- `dataset`
- `spec`

Minimum fields:

- `id`
- `kind`
- `name`
- `slug`
- `aliases`
- `summary`
- `status`
- `created_at`
- `updated_at`

Suggested status:

- `active`
- `merged`
- `archived`

Creation rule:

Create a `Node` only if the object is expected to be reused across multiple knowledge items, activities, or work items. Not every noun becomes a node.

### Knowledge

Represents system-recognized cognition.

Responsibilities:

- hold reusable recognized knowledge
- support updating, contesting, superseding, and aging
- support agent work without forcing re-derivation every time

Non-responsibilities:

- not raw input
- not a full work log
- not a task tracker
- not the object definition itself

Allowed kinds:

- `fact`
- `procedure`
- `decision`
- `constraint`
- `preference`

Minimum fields:

- `id`
- `kind`
- `title`
- `summary`
- `subject_refs`
- `evidence_refs`
- `payload`
- `status`
- `confidence`
- `valid_from`
- `valid_until`
- `last_verified_at`
- `created_at`
- `updated_at`

Suggested status:

- `candidate`
- `active`
- `contested`
- `superseded`
- `stale`
- `archived`

Payload rules by kind:

`fact`

- `subject`
- `predicate`
- `object` or `value`

`procedure`

- `steps`
- `preconditions`
- `expected_outcome`

`decision`

- `question`
- `outcome`
- `rationale`
- `alternatives`

`constraint`

- `rule`
- `scope`
- `violation_impact`

`preference`

- `statement`
- `scope`

Design constraints:

- knowledge must be able to become invalid, stale, contested, or superseded
- knowledge must not degrade into an unstructured text bucket

### Activity

Represents work that has already happened.

Responsibilities:

- record completed or completed-enough work processes
- provide the main basis for reports, retrospectives, and crystallization

Non-responsibilities:

- not long-term knowledge itself
- not the work item itself
- not raw source storage

Allowed kinds:

- `episode`
- `debug`
- `review`
- `research`
- `implementation`
- `meeting`
- `reading`

Minimum fields:

- `id`
- `kind`
- `title`
- `summary`
- `status`
- `started_at`
- `ended_at`
- `related_node_refs`
- `related_work_item_refs`
- `source_refs`
- `produced_object_refs`
- `artifact_refs`
- `created_at`
- `updated_at`

Suggested status:

- `draft`
- `finalized`
- `archived`

Field notes:

- `produced_object_refs`: knowledge, node, or work item outputs
- `artifact_refs`: PRs, docs, reports, file paths, or other external artifacts

### WorkItem

Represents a tracked unit of work that needs to be advanced, resolved, or closed.

Responsibilities:

- unify tasks, requirements, issues, bugs, and investigations
- support tracking, blocking, dependency, and closure

Non-responsibilities:

- not long-term recognized knowledge
- not raw source content
- not a complete work process log

Allowed kinds:

- `task`
- `requirement`
- `issue`
- `bug`
- `improvement`
- `question`
- `investigation`

Minimum fields:

- `id`
- `kind`
- `title`
- `summary`
- `status`
- `lifecycle_state`
- `priority`
- `owner_refs`
- `related_node_refs`
- `related_knowledge_refs`
- `source_refs`
- `depends_on`
- `blocked_by`
- `parent_ref`
- `child_refs`
- `resolution`
- `due_at`
- `opened_at`
- `updated_at`

Suggested work status:

- `open`
- `in_progress`
- `blocked`
- `resolved`
- `closed`
- `cancelled`

Suggested lifecycle state:

- `active`
- `archived`

## Protocol Objects

These are important, but they are not part of the semantic core object set.

### EvidenceRef

Purpose:

- connect `Knowledge` back to concrete `Source` segments

Minimum fields:

- `source_id`
- `segment_id`

### ContextPack

Purpose:

- provide structured working context to an agent

Minimum fields:

- `id`
- `task`
- `summary`
- `scope`
- `items`
- `conflicts`
- `missing_context`
- `recommended_next_reads`
- `citations`
- `generated_at`
- `expires_at`

### WikiPatch

Purpose:

- express mutations before they are applied

Minimum fields:

- `id`
- `source`
- `operations`
- `created_at`

### AuditEvent

Purpose:

- append-only record of meaningful system mutations

Minimum fields:

- `id`
- `event_type`
- `actor`
- `target`
- `before`
- `after`
- `reason`
- `timestamp`

## Object Boundaries

### Source vs Knowledge

- `Source` is what the system saw
- `Knowledge` is what the system currently recognizes from what it saw

### Node vs Knowledge

- `Node` is the object
- `Knowledge` is what is known about the object

### Activity vs WorkItem

- `Activity` is work that already happened
- `WorkItem` is work that needs tracking or advancement

### Activity vs Knowledge

- `Activity` is the process
- `Knowledge` is the durable result that may be extracted from that process

## Identity Model

Identity must not depend on path, filename, or page title.

Rules:

1. All internal references use stable `id`.
2. Page names and file paths are projections.
3. External references may break; internal references must not.
4. Merge and supersede are different operations.

Recommended ID prefixes:

- `src:`
- `node:`
- `know:`
- `act:`
- `work:`
- `ctx:`
- `patch:`
- `aud:`

## Lifecycle Model

The system is stateful. Objects do not become durable merely by being written.

### Source

Suggested status:

- `active`
- `invalid`
- `archived`

### Node

Suggested status:

- `active`
- `merged`
- `archived`

### Knowledge

Suggested status:

- `candidate`
- `active`
- `contested`
- `superseded`
- `stale`
- `archived`

### Activity

Suggested status:

- `draft`
- `finalized`
- `archived`

### WorkItem

Work status:

- `open`
- `in_progress`
- `blocked`
- `resolved`
- `closed`
- `cancelled`

Lifecycle state:

- `active`
- `archived`

## Query Model

The system should not try to fully pre-structure all possible future questions.

Instead, query should work in two steps:

1. provide a structured starting context
2. allow deeper expansion around relevant objects and sources

That means:

- the system builds a navigable knowledge terrain
- the agent continues task-specific exploration inside that terrain
- high-value findings can later be crystallized back into the system

## Adapter Model

Adapters isolate source-specific parsing from the semantic core.

All adapters should follow the same broad pattern:

```text
identify
read
normalize
segment
propose
```

Adapters may produce:

- `Source`
- candidate `Node`
- candidate `Knowledge`
- initial `Activity`
- initial `WorkItem`

Adapters do not:

- define final semantic truth
- bypass lifecycle rules
- bypass patch application

### Repo Adapter

Primary first-stage adapter for coding workflows.

Internal implementation may use:

- Tree-sitter
- file classification
- symbol extraction
- dependency extraction
- config parsing

The repo adapter should create a useful knowledge terrain, not an exhaustive final answer database.

## Architecture

The architecture should be grouped into three stability zones.

### 1. Core

Most stable. Should change rarely.

Contains:

- five core domain objects
- identity rules
- lifecycle rules
- context, patch, and audit contracts
- patch apply
- audit append

### 2. Derived

Fully rebuildable.

Contains:

- markdown/wiki projections
- indexes
- graphs
- embeddings
- overview and index pages

These are not the source of truth.

### 3. Edge

Most changeable.

Contains:

- adapters
- MCP
- CLI/UI
- jobs
- automation hooks

## MCP Interface

Expose exactly four top-level tools:

- `wiki.ingest`
- `wiki.query`
- `wiki.crystallize`
- `wiki.lint`

All expansion should happen through `mode`, not new top-level tools.

### wiki.ingest

Purpose:

- bring external input into the system

Typical modes:

- `source`
- `path`
- `repo`
- `url`
- `status`

### wiki.query

Purpose:

- provide usable context, then allow deeper expansion

Typical modes:

- `context`
- `search`
- `page`
- `related`
- `recent`
- `expand`

Default preference:

- start with `context`
- then use `expand` or targeted retrieval

### wiki.crystallize

Purpose:

- turn successful work into reusable system state

Typical modes:

- `activity`
- `knowledge`
- `work_item`
- `promote`
- `supersede`

### wiki.lint

Purpose:

- detect drift, inconsistency, and repairable problems

Typical modes:

- `structure`
- `semantic`
- `repair`
- `reindex`
- `audit`

## Unified Tool Shape

All top-level tools should follow the same outer request shape:

```json
{
  "mode": "...",
  "scope": {},
  "input": {},
  "options": {}
}
```

## Phase 1

Phase 1 should prioritize semantic stability over breadth.

Build only:

- repo ingest
- query context
- activity crystallization
- structural lint

Closed loop:

```text
repo
  -> ingest into Source / Node / candidate Knowledge
  -> query context
  -> agent work
  -> crystallize Activity and reusable results
  -> lint and audit
```

## Non-Goals for Phase 1

Do not prioritize:

- vector DB first
- graph DB first
- multi-user collaboration
- rich UI
- full source-type coverage
- full ahead-of-time structure extraction

These are expansion concerns and should not reshape the core.

## Design Summary

The final architecture is:

- five stable semantic core objects
- four stable top-level MCP tools
- query as context-first, then expand
- crystallization as the main compounding mechanism
- projections and indexes as derived layers
- adapters as replaceable edge logic

This keeps the kernel stable while preserving enough flexibility to support coding, project management, knowledge reuse, time-window reporting, issue tracking, and source-driven exploration.
