# Compounding Memory Core Design

## Goal

Build an llmwiki-style compounding memory core: a local-first context substrate that turns useful work into durable context assets that can be inspected, corrected, reused, and improved over time.

This system should learn from the second category identified in `argue.md`: context substrates. It should not become a hidden fact database, a chat-history store, a Zep clone, or a raw graph database wrapper.

The product center is:

```text
What context should an agent or human work inside?
How does that context become better after useful work?
```

## Non-Goals

The memory core does not include:

- agent prompt harnesses
- Claude, Codex, VS Code, or OpenClaw plugins
- a managed SaaS product
- dashboard UI
- team permissions
- benchmark infrastructure
- automatic agent compliance logic
- chat application UX

These belong to integration layers. The memory core must work when called by a human, script, MCP host, batch job, or agent runtime.

## Capability Benchmark

The design borrows capabilities from existing systems without inheriting their product boundaries:

- OpenClaw: plain files, long-term memory, daily notes, dream summaries, explicit disk state.
- MemSearch: Markdown source of truth, rebuildable shadow index, hybrid retrieval, progressive disclosure.
- TrustGraph: portable context cores with schema, graph, embeddings, evidence, and retrieval policy.
- Thoth: local knowledge graph, wiki vault, dream cycle, provenance, graph-enhanced recall.
- Letta MemFS: git-backed context repository, rollback, memory as context management.
- Acontext: skill memory from successful runs and operational lessons.
- ContextGraph: coding-agent checkpoints, decisions, failures, changed files, restoration instructions.
- Zep/Graphiti: temporal graph, episodes, entities, facts, validity windows, hybrid retrieval.
- Cognee: local-friendly graph/vector/relational architecture and ontology grounding.

The common requirement is not any one backend. The common requirement is a governable context substrate that compounds.

## Core Lifecycle

The memory core lifecycle is:

```text
capture
-> analyze
-> remember
-> query
-> maintain
-> project
-> reuse
-> refine
```

### Capture

`memory_ingest` captures source material as evidence. It is deterministic and does not decide what deserves durable memory.

Inputs include:

- files
- repositories
- Markdown
- web pages
- PDFs
- conversations
- command output
- meeting records
- task logs

Capture creates `Source`, `Episode`, and `Segment` records with stable provenance.

### Analyze

Analysis extracts candidate entities, relations, claims, procedures, decisions, and work state from captured evidence.

Analysis may be performed by:

- an LLM
- a deterministic parser
- a human
- a batch job
- an agent

Analysis is not the durable write path. It proposes memory candidates.

### Remember

`memory_remember` is the governed durable write path. It commits memory only after validating evidence, scope, status, confidence, and duplicate or conflict risks.

### Query

`memory_query` retrieves work-ready context packs. It should not return only raw search hits.

### Maintain

`memory_maintain` keeps the memory graph and projections healthy through validation, repair, consolidation, decay, conflict detection, and rebuilds.

### Project

Projection creates human-readable and LLM-readable views. Markdown and wiki output are derived views, not the only semantic model.

## Core Objects

### MemoryScope

Defines the boundary where memory applies.

Minimum fields:

- `id`
- `kind`: `project | repo | user | workspace | branch | topic | collection`
- `name`
- `parent_refs`
- `metadata`
- `created_at`
- `updated_at`

Rules:

- Every durable object belongs to at least one scope.
- Scope is composable; a memory can apply to project plus repo plus topic.
- Scope controls retrieval, export, maintenance, and future access policy.

### Source

Durable evidence origin.

Minimum fields:

- `id`
- `kind`
- `origin`
- `title`
- `fingerprint`
- `content_type`
- `payload_ref` or `payload`
- `metadata`
- `status`
- `captured_at`
- `updated_at`
- `scope_refs`

### Episode

One captured event or input occurrence.

Examples:

- one conversation turn group
- one file ingest
- one repo scan
- one command output capture
- one meeting transcript ingest

Minimum fields:

- `id`
- `source_ref`
- `kind`
- `observed_at`
- `ingested_at`
- `actor`
- `summary`
- `scope_refs`
- `metadata`

### Segment

Citable evidence slice inside a source or episode.

Minimum fields:

- `id`
- `source_ref`
- `episode_ref`
- `locator`
- `excerpt`
- `hash`
- `metadata`

### Entity

Stable long-lived object in the memory world.

Examples:

- project
- repo
- file
- module
- concept
- person
- tool
- decision topic
- preference
- workflow

Minimum fields:

- `id`
- `kind`
- `name`
- `aliases`
- `summary`
- `scope_refs`
- `status`
- `created_at`
- `updated_at`

### Relation

Typed edge between entities or memory objects.

Common relation types:

- `supports`
- `contradicts`
- `depends_on`
- `part_of`
- `supersedes`
- `derived_from`
- `blocks`
- `produces`
- `uses`
- `owned_by`
- `applies_to`
- `mentions`

Minimum fields:

- `id`
- `source_ref`
- `target_ref`
- `relation_type`
- `evidence_refs`
- `confidence`
- `status`
- `valid_from`
- `valid_until`
- `scope_refs`
- `metadata`

### Knowledge

Reusable cognition the system believes or is evaluating.

Kinds:

- `fact`
- `decision`
- `constraint`
- `preference`
- `procedure`
- `lesson`
- `warning`
- `pattern`

Minimum fields:

- `id`
- `kind`
- `title`
- `summary`
- `subject_refs`
- `relation_refs`
- `evidence_refs`
- `payload`
- `status`
- `confidence`
- `valid_from`
- `valid_until`
- `last_verified_at`
- `scope_refs`
- `created_at`
- `updated_at`

Status values:

- `candidate`
- `active`
- `contested`
- `superseded`
- `stale`
- `archived`

### Decision

Decision can be a `Knowledge` kind, but it must have a structured payload.

Payload fields:

- `question`
- `outcome`
- `rationale`
- `alternatives`
- `constraints`
- `consequences`
- `revisit_conditions`

### Procedure

Procedure can be a `Knowledge` kind, but it must represent reusable operational memory.

Payload fields:

- `goal`
- `preconditions`
- `steps`
- `expected_outcome`
- `failure_modes`
- `examples`

### Activity

Completed work or analysis.

Minimum fields:

- `id`
- `kind`
- `title`
- `summary`
- `status`
- `started_at`
- `ended_at`
- `actor`
- `source_refs`
- `related_entity_refs`
- `related_knowledge_refs`
- `related_work_item_refs`
- `produced_object_refs`
- `artifact_refs`
- `scope_refs`

### WorkItem

Actionable durable work state.

Minimum fields:

- `id`
- `kind`
- `title`
- `summary`
- `status`
- `priority`
- `owner_refs`
- `related_entity_refs`
- `related_knowledge_refs`
- `source_refs`
- `depends_on`
- `blocked_by`
- `parent_ref`
- `child_refs`
- `resolution`
- `due_at`
- `opened_at`
- `scope_refs`

### ContextPack

Query result prepared for work.

Minimum fields:

- `id`
- `task`
- `scope`
- `summary`
- `items`
- `evidence`
- `decisions`
- `procedures`
- `open_work`
- `conflicts`
- `missing_context`
- `recommended_next_reads`
- `freshness`
- `generated_at`
- `expires_at`

### Patch And AuditEvent

Every durable mutation must produce:

- a patch describing object changes
- audit events describing actor, target, reason, before, after, and timestamp

The audit trail must be useful even if the graph backend is rebuilt.

## Governance Rules

`memory_remember` must not blindly write whatever the caller proposes.

Create operations require:

- `reason`: why this should survive future sessions
- `memory_source`: `user_declared | human_curated | agent_inferred | imported | system_maintained`
- `scope_refs`
- `status`
- `confidence`
- `evidence_refs` when status is `active`, unless `memory_source` is `user_declared` or `human_curated`

Write behavior:

- weak or inferred memory defaults to `candidate`
- active knowledge without evidence is rejected or downgraded
- duplicate candidates are merged or linked instead of duplicated
- conflicting claims are marked `contested`
- superseded knowledge keeps history through validity windows
- all writes produce patch and audit records

## Query Behavior

`memory_query` must support:

- `context`: produce a context pack for a task
- `search`: find relevant objects
- `expand`: expand one object into nearby context and evidence
- `page`: return a full object
- `graph`: return graph neighborhood
- `recent`: return recently updated memory

The context pack should combine:

- semantic similarity
- keyword search
- graph neighborhood
- scope filtering
- status filtering
- freshness filtering
- evidence availability
- work-item relevance

Query is not answer generation. Generation may be layered on top, but first-class output is grounded context.

## Progressive Disclosure

Retrieval should expose four levels:

1. ranked context item
2. expanded object or wiki section
3. cited segment
4. original source or raw transcript

This lets agents start cheap and drill down only when necessary.

## Maintain / Dream Behavior

Maintenance is not optional cleanup. It is how memory compounds safely.

Required read-only modes:

- structure validation
- audit read
- maintenance report
- backend health check
- projection freshness check

Required mutating modes:

- repair missing or stale projections
- promote candidates
- merge duplicates
- mark stale knowledge
- contest conflicts
- supersede replaced facts
- infer missing relations
- enrich thin entities or procedures
- prune orphaned derived context
- rebuild indexes
- rebuild projections

Mutating modes require explicit apply confirmation.

## Projection Behavior

Projections are derived but important.

Required projections:

- wiki home
- source pages
- entity pages
- knowledge pages
- decision pages
- procedure pages
- activity pages
- work item pages
- debug object mirrors

Projection requirements:

- human-readable
- stable links
- evidence links
- status markers
- scope-aware navigation
- rebuildable from canonical memory

Human edits to projections are not canonical writes. If human-edited projection workflows are added later, edits should become source events and flow back through ingest/analyze/remember.

## Backend Strategy

The memory model is graph-native. The backend must not define the product semantics.

### Options

#### A. File-Backed Graph Only

Benefits:

- simplest local setup
- easiest to inspect
- no external services

Costs:

- self-built graph traversal
- weak hybrid retrieval
- poor temporal relation support
- high chance of rebuilding Graphiti-like behavior poorly

Use only as a test backend or emergency fallback.

#### B. Graphiti + Neo4j As Core

Benefits:

- mature temporal graph behavior
- strong graph backend
- good fit for entities, episodes, facts, provenance, and hybrid search

Costs:

- heavier local setup
- Neo4j service dependency
- harder tests
- lock-in risk if project semantics leak into backend API

Use as the preferred full graph backend once the interface is stable.

#### C. Graphiti + Local Graph Backend

Benefits:

- more local-first
- lower operational burden
- useful for development and personal use

Costs:

- backend maturity may vary
- feature parity with Neo4j must be verified
- migration path must be tested

Use as the preferred development path if Graphiti supports the needed local backend reliably.

#### D. Governed Event Store + Rebuildable Graph Index

Benefits:

- strongest audit and rebuild story
- backend can be replaced
- aligns with projections and portability

Costs:

- more architecture up front
- sync and rebuild complexity
- slower to prototype

Use as the long-term architecture target if graph backend mutability makes audit or portability weak.

### Recommendation

Adopt a two-layer backend design:

```text
governed memory event/object layer
-> GraphBackend interface
-> Graphiti-backed implementation
-> Neo4j or local graph backend underneath
```

For the first implementation slice:

- define the `GraphBackend` interface
- keep a file-backed fake backend for tests
- run a Graphiti backend spike
- decide between Neo4j and local graph backend after the spike

Do not hardwire MCP tools directly to Graphiti APIs.

## MCP Surface

The existing four-tool surface remains correct:

- `memory_ingest`
- `memory_remember`
- `memory_query`
- `memory_maintain`

The tools should evolve internally to support the memory core model.

Public names should not expose backend choices.

## First Implementation Slice

The first slice should avoid a full backend migration. It should establish the correct memory core contract.

Deliverables:

1. Add `MemoryScope`, `Episode`, `Entity`, and `Relation` domain models.
2. Add `Decision` and `Procedure` as first-class typed knowledge payloads; they may initially be stored as `Knowledge` records with dedicated `kind` values.
3. Add governed `RememberRequest` shape with `reason`, `memory_source`, `scope_refs`, status, confidence, and evidence policy.
4. Add `GraphBackend` protocol with methods for upsert, link, search, neighborhood, temporal lookup, health, and rebuild.
5. Add file-backed test implementation of `GraphBackend`.
6. Upgrade `ContextPack` schema to include evidence, decisions, procedures, open work, conflicts, missing context, next reads, and freshness.
7. Add maintain report checks for governance violations.
8. Keep existing object store and projections working during the transition.
9. Add tests for the memory core contract without requiring Neo4j.

This slice should make the system graph-ready and governance-ready before binding to Graphiti.

## Second Implementation Slice

The second slice should test Graphiti integration:

1. Add optional Graphiti dependency group or extra.
2. Implement `GraphitiBackend`.
3. Map `Source/Episode/Segment` to Graphiti episodes and provenance.
4. Map `Entity/Relation/Knowledge` to graph entities and facts.
5. Implement hybrid retrieval through `GraphBackend`.
6. Add local backend and Neo4j setup documentation.
7. Add integration tests gated behind environment variables.

## Review

This design keeps the project aligned with llmwiki:

- memory is context that compounds
- source evidence remains traceable
- graph relations are core
- backend choices are adapters
- projections remain human-readable and rebuildable
- agent integration is deliberately outside the first memory-core slice

Main risks:

- the first slice may feel slower than directly wiring Graphiti
- dual object plus graph abstractions can become redundant if not kept disciplined
- local backend capability may lag Neo4j
- governance fields may make `remember` calls more verbose

Mitigations:

- keep first slice focused on contracts and tests
- keep backend API narrow
- use generated projections to preserve inspectability
- treat Graphiti integration as a spike before committing to a production backend
- keep agent workflow docs separate from memory core design
