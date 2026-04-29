# MemPalace Design Review

Date: 2026-04-30

Status: Reviewed for Memory Substrate design input

## Review Scope

Reviewed local repository `/home/y9000/GitRepo/mempalace` as a reference implementation for a local-first agent memory system.

This note is research evidence. Current product rules remain in:

- [Memory Policy](../memory-policy.md)
- [Project Development Policy](../project-development-policy.md)
- [Current Todo](../../todo.md)

## Core Difference

MemPalace is strongest as a verbatim-memory and retrieval-hardening system:

- preserve raw conversation/source evidence
- build searchable compact indexes over raw evidence
- use temporal KG records for relationships
- expose many task-specific MCP tools and hooks

Memory Substrate should not copy the palace metaphor or the large tool surface. Its target remains a governed compounding memory core:

- canonical memory objects
- evidence references
- governed durable writes
- scopes and lifecycle state
- derived indexes and projections
- compact MCP tools that agents can learn quickly

## Model Lessons To Borrow

### Evidence Is Not Memory

MemPalace drawers map well to source evidence. The useful pattern is not the name, but the boundary:

- raw source/evidence is preserved with locators and hashes
- durable memory is a curated or governed object derived from evidence
- retrieval results should be able to hydrate nearby source context when exact wording matters

Memory Substrate should keep `Source` and source segments as evidence, and keep `Knowledge`, `WorkItem`, `Activity`, `Node`, `Entity`, and `Relation` as canonical memory objects.

### Derived Indexes Are Ranking Signals

MemPalace closets are compact searchable indexes that point back to drawers. They should not replace raw evidence.

Memory Substrate should keep this rule:

- LanceDB semantic chunks are derived
- graph backend state is derived
- Markdown/wiki projections are derived
- future BM25 or pointer indexes are derived

Derived indexes may boost, rerank, or hydrate canonical objects. They must not become the source of truth.

### Temporal Relations Need Lifecycle Fields

MemPalace's KG uses temporal validity and source pointers. The valuable fields are:

- `valid_from`
- `valid_to` or equivalent expiry
- `confidence`
- source/evidence pointers
- explicit invalidation
- timeline queries

Memory Substrate already has validity, confidence, status, evidence, supersession, and graph contracts. Future relation work should continue making lifecycle explicit instead of treating graph edges as timeless facts.

### Query Hardening Should Follow Observed Misses

MemPalace's hybrid search improvements are practical because they came from failure analysis:

- embeddings underweight exact nouns
- temporal references are easy to miss
- agent prompts can contaminate query text
- index corruption should fall back to deterministic search

Memory Substrate should prefer measured hardening slices over speculative retrieval complexity. Query sanitizer, rank fusion, source locator hydration, and fallback search are appropriate near-term improvements.

### Source Adapters Should Declare Transformations

MemPalace source adapters expose schema, capabilities, transformations, and privacy hints.

Memory Substrate ingest adapters should eventually expose:

- adapter name and version
- supported source modes
- declared transformations
- default privacy class
- item metadata and freshness checks
- source origin classification

This belongs behind `memory_ingest`; it should not change canonical object semantics.

### Layered Context Is A Better Agent Contract Than Flat Search

MemPalace's L0/L1/L2/L3 memory stack is worth adapting as a context-pack design:

- always-on identity and project policy
- compact active task context
- relevant decisions, procedures, evidence, and open work
- deep search only when requested

Memory Substrate should evolve `memory_query context` toward tiered, budgeted context rather than returning a flat search dump.

## Model Lessons Not To Copy

- Do not make `wing`, `room`, `drawer`, or `closet` canonical terminology.
- Do not expand the MCP surface to dozens of narrow tools while four mode-based tools remain learnable.
- Do not adopt verbatim-only memory as the core. Raw evidence is necessary, but compounding memory requires curated decisions, preferences, rules, tasks, and relations.
- Do not switch vector defaults to ChromaDB just because MemPalace uses it. LanceDB remains the current local semantic index.
- Do not copy product-specific hook behavior directly; adapt the principle into optional Codex/Claude capture workflows.

## Executable Follow-Up Projects

### MS-05: MCP Query Sanitizer And Diagnostics

Goal: prevent long agent prompts, system instructions, and scratchpads from polluting retrieval.

Deliverables:

- sanitize long `memory_query search` and `context` text before query planning
- return `query_sanitizer` diagnostics
- add warnings when sanitization occurs
- document response fields and caller behavior

### MS-06: Source Adapter Metadata Contract

Goal: make ingest outputs more self-describing and maintainable across source types.

Deliverables:

- define adapter metadata fields for version, transformations, privacy class, and origin
- attach adapter metadata to ingested sources
- expose freshness/currentness hints where deterministic
- test repo and markdown adapters first

### MS-07: Tiered Context Pack Contract

Goal: make `memory_query context` return budgeted work-ready context instead of a flat item list.

Deliverables:

- define tiers for policy, active task, decisions, procedures, evidence, open work, and deep-search hints
- keep compact defaults
- add tests for token-budget behavior
- update MCP docs and resources

### MS-08: Derived Index Repair And Benchmark Harness

Goal: make semantic/graph indexes auditable, rebuildable, and measurable.

Deliverables:

- add repair checks that compare derived index counts against canonical objects before destructive rebuilds
- add deterministic planted-needle retrieval benchmark cases
- report lexical, semantic, and hybrid recall separately
- keep benchmark data local and small enough for normal development

### MS-09: Memory Fact-Checker And Lifecycle Lint

Goal: detect entity confusion, stale facts, and relationship mismatches without automatic mutation.

Deliverables:

- report similar entity names
- report stale active facts
- report relationship mismatches where structured evidence exists
- keep all outputs advisory until a governed resolve mode exists
