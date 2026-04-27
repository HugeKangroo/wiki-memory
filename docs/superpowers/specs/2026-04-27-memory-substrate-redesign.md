# Memory Substrate Redesign

## Goal

Reframe the project from a wiki-centered context store into a general agent memory substrate. The memory system is the product core. Wiki pages are derived projections, coding is a domain adapter, Neo4j/Graphiti is the graph memory backend direction, and RAG is a retrieval/answer adapter rather than the product center.

## First Principles

The system stores long-lived operational state for agents:

- what happened
- what the system believes
- what evidence supports each belief
- when a belief is valid
- what has been superseded, contested, or decayed
- what context an agent must load before work
- what new observations should be remembered after work

This requires a stable memory lifecycle more than a readable wiki. Human-readable projections remain useful, but they must not drive the canonical model.

## External MCP Surface

Expose four product-level tools:

- `memory_ingest`
- `memory_remember`
- `memory_query`
- `memory_maintain`

Do not preserve `wiki_*` compatibility. The project is early enough that old names should be removed instead of carried as a compatibility burden.

### `memory_ingest`

Captures evidence. It should be deterministic and source-oriented.

Responsibilities:

- read files, repos, web pages, PDFs, conversations, command output, or session notes
- normalize input into sources, episodes, and segments
- calculate fingerprints and stable evidence refs
- preserve origin metadata

It should not decide what deserves long-term memory.

### `memory_remember`

Commits durable memory through a governed write path.

Responsibilities:

- accept explicit user instructions such as "remember X"
- accept agent extraction proposals from ingested evidence
- validate schemas
- check duplicates and contradictions
- assign status, confidence, and validity windows
- write patches and audit events
- sync graph/index backends
- rebuild projections

`memory_remember` replaces the old `wiki_crystallize` tool name. Internally, the service should become `RememberService`.

### `memory_query`

Retrieves usable context for agents and humans.

Responsibilities:

- context packs
- page/object lookup
- search
- graph neighborhood traversal
- expansion from one object into evidence and related objects
- answer-ready evidence packs

Generation is optional. The first-class output is grounded context.

### `memory_maintain`

Keeps the memory system healthy.

Responsibilities:

- structure validation
- audit reads
- repair
- reindex
- promote candidates
- merge duplicates
- decay stale knowledge
- detect conflicts
- consolidation cycle
- maintenance reports

This combines the old top-level `wiki_lint` and `wiki_dream` tool surfaces.

## Internal Architecture

Use product naming internally:

- `IngestService`
- `AnalyzeService`
- `RememberService`
- `QueryService`
- `MaintainService`
- `ProjectionService`
- `GraphBackend`

Current implementation can keep the existing object model while renaming the public package and MCP surface. Larger Graphiti/Neo4j integration should land behind a backend interface.

## Core Data Abstractions

Keep the model generic rather than coding-specific:

- `Episode`: one captured input event
- `Source`: durable origin object
- `Segment`: citeable evidence slice
- `Entity`: long-lived object such as a person, project, file, concept, decision, tool, or preference
- `Relation`: typed edge between entities
- `Knowledge`: claim the system currently believes or is evaluating
- `Activity`: completed work or analysis
- `WorkItem`: actionable task
- `ContextPack`: query result prepared for agent use
- `Patch`: governed memory mutation
- `AuditEvent`: accountability record
- `Projection`: derived human or machine view

Coding concepts such as repo, module, file, function, test, and PR are entity types in a domain adapter, not memory-core primitives.

## Backend Direction

Graphiti plus Neo4j is the preferred mature graph-memory path:

- Graphiti provides temporal context graph behavior for episodes, entities, facts, and hybrid retrieval.
- Neo4j provides the graph database backend, query engine, and visualization ecosystem.
- The project must wrap this behind its own memory/graph interfaces to avoid locking the domain model to one library.

Do not start with raw Neo4j as the whole memory system. Do not let `neo4j-graphrag` define the core model. RAG libraries can be adapters for retrieval and answering.

## Initial Implementation Slice

The first implementation slice should be a naming and boundary refactor:

- rename package from `wiki_memory` to `memory_substrate`
- update project metadata from wiki-centered wording to memory-substrate wording
- expose MCP tools as `memory_ingest`, `memory_remember`, `memory_query`, and `memory_maintain`
- rename `CrystallizeService` to `RememberService`
- rename `DreamService` and `LintService` external dispatch under `MaintainService`
- keep wiki projection paths as derived projection output
- update tests and docs to the new names

This slice deliberately does not add Graphiti/Neo4j yet. It creates the correct public contract and prevents further work from building on the wrong naming center.

## Review

The design aligns with the desired direction:

- memory core is the product
- ingest captures evidence without pretending to understand it
- remember is the only durable write path
- query returns grounded context, not just generated text
- maintain owns lifecycle and health
- wiki is a projection
- coding is a domain adapter
- graph/RAG libraries are backend or adapter concerns

Main risks:

- broad rename churn can hide behavior regressions
- internal service names can be changed before their responsibilities are fully split
- Graphiti integration may require model adjustments after this rename

Mitigation:

- make the first slice mostly naming plus public boundary tests
- preserve current behavior while changing names
- run the full test suite after the rename
- introduce GraphBackend and Graphiti/Neo4j in a later focused slice
