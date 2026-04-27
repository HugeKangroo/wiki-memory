# Memory Backend Library Spike

Date: 2026-04-28

Status: Proposed

## Decision Context

The compounding memory core needs a graph-native backend, but the project should not overfit to Zep, Graphiti, Neo4j, Kuzu, or any single library.

The core product semantics are owned by Memory Substrate:

- evidence capture
- governed durable writes
- memory scopes
- provenance and audit
- context packs
- progressive disclosure
- projection
- maintenance and dream lifecycle

Backend libraries should provide graph, retrieval, and extraction capabilities behind a project-owned `GraphBackend` interface.

## Current Decision

Do not treat Graphiti as the only option yet.

Run a focused backend/library spike with these candidates:

1. `Graphiti` with Kuzu and Neo4j/FalkorDB as graph backends.
2. `Cognee` with its local defaults, especially Kuzu.
3. `LlamaIndex PropertyGraphIndex` with Kuzu.
4. `file-backed test graph` as the non-production contract baseline.

Do not include Microsoft GraphRAG in the implementation spike. It is useful as a reference for graph-based retrieval over static corpora, but it is batch-oriented and not a strong fit for continuously evolving memory.

## Candidate Summary

### Graphiti

Why evaluate:

- Purpose-built temporal context graph for agents.
- Supports entities, facts/relationships, episodes, provenance, temporal validity, and hybrid retrieval.
- Supports custom entity and edge types through Pydantic models.
- Designed for incremental updates without full graph recomputation.
- Has MCP server direction already, but Memory Substrate should not expose Graphiti directly.

Risks:

- Defaults to OpenAI for LLM inference and embeddings.
- Works best with structured-output-capable LLMs.
- Full value depends on graph backend quality.
- Project semantics may leak if integration is too direct.

Backend notes:

- Current Graphiti docs list Neo4j 5.26, FalkorDB 1.1.2, Kuzu 0.11.2, and Amazon Neptune support.
- Kuzu support exists through `graphiti-core[kuzu]`.
- Neo4j remains the strongest production candidate.

Primary spike question:

Can Graphiti represent `Source/Episode/Segment`, `Entity/Relation/Knowledge`, validity windows, evidence, and context retrieval without forcing Memory Substrate to adopt Graphiti's public API as its own domain model?

Sources:

- https://github.com/getzep/graphiti
- https://www.getzep.com/product/open-source/

### Cognee

Why evaluate:

- Presents itself as an AI memory engine, not only a graph index.
- Uses three complementary stores: relational for documents/provenance, vector for embeddings, graph for entities/relationships.
- Local defaults are file-based: SQLite, LanceDB, and Kuzu.
- Supports production graph backends such as Neo4j and Neptune.
- Kuzu is the documented default graph store for local development.

Risks:

- Larger opinionated engine may overlap with Memory Substrate's own governance layer.
- Its pipeline concepts may be harder to wrap cleanly than Graphiti's graph engine.
- Need to verify whether temporal validity, supersession, and conflict lifecycle can be controlled externally.

Primary spike question:

Can Cognee act as a local-first memory engine underneath Memory Substrate without taking over our `ingest/remember/query/maintain` semantics?

Sources:

- https://docs.cognee.ai/core-concepts/architecture
- https://docs.cognee.ai/setup-configuration/graph-stores
- https://github.com/topoteretes/cognee
- https://www.cognee.ai/blog/fundamentals/how-cognee-builds-ai-memory

### LlamaIndex PropertyGraphIndex

Why evaluate:

- Flexible property graph orchestration.
- Supports graph construction and querying.
- Supports Kuzu and Neo4j graph stores.
- Kuzu mode supports structured schemas and vector index usage.
- Good lower-level fallback if memory-specific engines are too opinionated.

Risks:

- More of a graph/RAG index than a durable memory lifecycle.
- Temporal validity, invalidation, conflict lifecycle, provenance governance, and dream behavior would likely remain our responsibility.
- May encourage treating memory as an index rather than as a governed context substrate.

Primary spike question:

Is LlamaIndex a useful low-level property graph adapter for our `GraphBackend`, or would it leave too much memory-system behavior for us to build?

Sources:

- https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/
- https://docs.llamaindex.ai/en/stable/examples/property_graph/property_graph_kuzu/
- https://docs.llamaindex.ai/en/stable/examples/property_graph/property_graph_neo4j/

### File-Backed Test Graph

Why include:

- Required for fast unit tests and CI.
- Avoids Neo4j, Kuzu, LLM, and embedding dependencies in core tests.
- Lets Memory Substrate define its own `GraphBackend` contract first.

Non-goal:

The file-backed graph is not a production memory backend. It should not grow into a hand-rolled replacement for temporal graph memory.

Primary spike question:

Can the contract backend validate all memory-core semantics without pretending to solve hybrid retrieval or temporal graph reasoning?

### Microsoft GraphRAG

Why exclude from implementation spike:

- Designed as a modular graph-based RAG pipeline for extracting structured data from unstructured text and answering over private datasets.
- Strong fit for static or batch-processed corpora.
- Weak fit for continuously updated, agent-operational memory where facts evolve and writes happen through governed memory operations.

Use as reference only.

Source:

- https://github.com/microsoft/graphrag

## Evaluation Criteria

Each candidate should be evaluated against these requirements.

### Local-First Operation

Must answer:

- Can it run fully local except optional LLM or embedding calls?
- Does it require a long-running service?
- Does it store data in a predictable project-controlled path?
- Can it be reset and isolated per test?

### Memory Model Fit

Must support or be adaptable to:

- source
- episode
- segment
- entity
- relation
- knowledge
- decision
- procedure
- activity
- work item
- memory scope

### Temporal Behavior

Must support or allow us to implement:

- observed time
- ingested time
- valid from
- valid until
- supersession
- stale state
- historical lookup

### Evidence And Provenance

Must support:

- derived facts traceable to source episodes or segments
- evidence refs usable in context packs
- source lineage exposed through API
- rebuild or audit story independent of opaque state

### Retrieval

Must support or compose:

- keyword search
- semantic search
- graph neighborhood traversal
- hybrid retrieval
- scope filtering
- status/freshness filtering
- progressive disclosure

### Governance Boundary

Must allow Memory Substrate to own:

- `memory_ingest`
- `memory_remember`
- `memory_query`
- `memory_maintain`
- write reason
- memory source
- scope
- evidence policy
- patch and audit
- projection

If a candidate forces its own memory lifecycle onto callers, it should be treated as a reference or adapter only.

### Maintainability

Must evaluate:

- package health
- Python version support
- backend support
- data migration path
- testability
- dependency size
- operational burden
- ability to replace later

## Spike Tasks

### Task 1: Define `GraphBackend` Contract

Draft the project-owned interface before integrating any library.

Required operations:

- `upsert_episode`
- `upsert_entity`
- `upsert_relation`
- `upsert_knowledge`
- `link_evidence`
- `search`
- `neighborhood`
- `temporal_lookup`
- `health`
- `rebuild`
- `export_scope`

The contract should use Memory Substrate domain objects, not vendor objects.

### Task 2: Implement File-Backed Test Graph

Goal:

- prove the contract
- support unit tests
- avoid external services

Acceptance:

- can store entities and relations
- can return deterministic search results
- can return one-hop neighborhoods
- can preserve evidence refs
- can simulate temporal lookup enough for contract tests

### Task 3: Graphiti Spike

Goal:

- verify Graphiti maps naturally to the memory core.

Minimal test:

- initialize an isolated graph backend
- add an episode
- derive or upsert entities and facts
- preserve provenance
- run hybrid search
- retrieve graph neighborhood
- represent an outdated fact with validity window or invalidation
- close and reopen persisted data

Backends to try:

- Kuzu first if setup is reliable
- Neo4j or FalkorDB if Kuzu support blocks the spike

### Task 4: Cognee Spike

Goal:

- verify whether Cognee can serve as a local-first memory engine.

Minimal test:

- configure local SQLite/LanceDB/Kuzu storage paths
- add a small source
- run its processing pipeline
- inspect provenance
- retrieve graph and semantic results
- verify whether we can control schema and memory lifecycle externally

### Task 5: LlamaIndex PropertyGraphIndex Spike

Goal:

- evaluate it as a lower-level property graph adapter.

Minimal test:

- create Kuzu property graph store
- enforce a small schema
- insert a source-derived graph
- run graph retrieval
- run vector retrieval if available
- check whether temporal and evidence semantics can be expressed as properties

## Decision Matrix

Score each candidate 1 to 5.

| Criterion | Weight | Graphiti | Cognee | LlamaIndex PG | File Test Graph |
|---|---:|---:|---:|---:|---:|
| Local-first setup | 5 | TBD | TBD | TBD | 5 |
| Temporal memory fit | 5 | TBD | TBD | TBD | 1 |
| Evidence/provenance fit | 5 | TBD | TBD | TBD | 3 |
| Graph + semantic retrieval | 5 | TBD | TBD | TBD | 1 |
| Governance boundary | 5 | TBD | TBD | TBD | 5 |
| Schema control | 4 | TBD | TBD | TBD | 4 |
| Testability | 4 | TBD | TBD | TBD | 5 |
| Operational burden | 4 | TBD | TBD | TBD | 5 |
| Migration/rebuild story | 4 | TBD | TBD | TBD | 4 |
| Dependency risk | 3 | TBD | TBD | TBD | 5 |

The `TBD` values should be filled by implementation spike results, not by reading docs alone.

## Initial Hypothesis

Expected outcome before implementation:

1. `Graphiti` is the preferred semantic graph engine if it preserves Memory Substrate's governance boundary.
2. `Cognee` is the strongest alternative because it is local-first by default and already combines relational, vector, and graph stores.
3. `LlamaIndex PropertyGraphIndex` is likely a useful fallback adapter, not the memory engine.
4. `file-backed test graph` is mandatory for core tests but not sufficient for real memory.
5. `Neo4j` should remain optional production backend, not required for the first local prototype.

## Next Step

Do not choose a production backend from documentation alone.

Implement the `GraphBackend` contract and file-backed test graph first. Then run the three library spikes behind the same contract and update the decision matrix with real results.
