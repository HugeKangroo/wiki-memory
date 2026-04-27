# Context Substrate Memory Core Research

Date: 2026-04-28

## Purpose

This note captures the research used to define the memory core without overfitting to Zep, Graphiti, Neo4j, or any single implementation. The goal is to preserve the reasoning before turning it into a formal memory-core design.

The intended product direction is an llmwiki-style compounding memory system:

- local-first
- agent-agnostic
- human-inspectable
- graph-native
- evidence-grounded
- maintainable over time
- able to make each useful session improve future work

## Local Source: `argue.md`

The local `argue.md` frames the current memory-tool landscape as two different camps:

- Camp 1: memory backends.
- Camp 2: context substrates.

Camp 1 asks what the AI should remember. These tools usually extract or store facts, put them in a vector or graph store, and retrieve relevant facts later.

Camp 2 asks what context the AI should work inside. These tools maintain structured, inspectable context that accumulates across sessions. The agent reads it, works within it, writes back to it, and the context becomes richer over time.

The important conclusion for this project:

```text
Memory backends optimize recall.
Context substrates optimize compounding.
```

This project should align with Camp 2. It can reuse Camp 1 retrieval and extraction techniques, but the product center should be a context substrate, not a hidden fact store.

## Tools Reviewed

### OpenClaw

Useful ideas:

- Plain Markdown workspace memory.
- `MEMORY.md` for durable facts, preferences, and decisions.
- Daily notes for running context.
- `DREAMS.md` for consolidation summaries.
- The model only remembers what is saved to disk.
- Memory tools include search and direct file/range reads.
- Optional memory-wiki compiles durable knowledge into structured pages with claims and evidence.

Implication:

Human-readable memory is not a convenience layer; it is part of trust, inspection, correction, and compounding.

Source:

- https://docs.openclaw.ai/concepts/memory

### MemSearch

Useful ideas:

- Markdown is the source of truth.
- Milvus is a rebuildable shadow index.
- Hybrid search combines dense vectors, BM25, and RRF reranking.
- Smart dedup via content hashes.
- Live sync watches changed files.
- Progressive disclosure: search chunk, expand section, inspect raw transcript.
- Cross-agent memory sharing through one backend.

Implication:

Indexes should be derived. The system should support progressive disclosure instead of forcing every query to return either tiny chunks or full raw documents.

Source:

- https://github.com/zilliztech/memsearch
- https://zilliztech.github.io/memsearch/

### TrustGraph

Useful ideas:

- Context Cores package domain context as portable artifacts.
- A core includes graph edges, schema, embeddings, evidence, and retrieval policies.
- Cores can be offline, online, or loaded for retrieval.
- Context can be versioned, shared, promoted, and rolled back.
- Context graph means knowledge plus provenance and explainability.

Implication:

Memory scopes should be portable and versionable. A memory system should be able to export and import a coherent context unit, not just dump raw records.

Source:

- https://docs.trustgraph.ai/guides/context-cores/
- https://github.com/trustgraph-ai/trustgraph
- https://docs.trustgraph.ai/overview/retrieval.html

### Thoth

Useful ideas:

- Local-first personal knowledge graph.
- Entity and relation vocabulary.
- Graph-enhanced recall with semantic search plus one-hop expansion.
- Wiki vault projection.
- Dream cycle for duplicate merge, description enrichment, relationship inference, stale decay, and orphan pruning.
- Document extraction with provenance.
- Local-first privacy and inspectability.

Implication:

Graph memory needs lifecycle maintenance. Entity extraction alone is not enough; the graph must be cleaned, enriched, decayed, and kept inspectable.

Source:

- https://siddsachar.github.io/Thoth/

### Letta / MemFS

Useful ideas:

- Memory is context management, not only retrieval.
- Core memory stays in context; recall and archival memory live outside context.
- Agents can manage memory through tools.
- Letta Code MemFS stores agent memory as a git-backed context repository.
- Markdown files carry frontmatter and can be edited through ordinary filesystem operations.
- Git enables rollback, changelogs, and parallel coordination.

Implication:

Versioned filesystem semantics are valuable even when the semantic backend is a graph. The memory layer should preserve inspectable, diffable, recoverable projections.

Sources:

- https://docs.letta.com/guides/agents/architectures/memgpt
- https://docs.letta.com/letta-code/memory/

### Acontext

Useful ideas:

- Agent skills as a memory layer.
- Captures what the agent did and the outcome, then distills reusable procedures, preferences, and warnings.
- Stores learned skills as Markdown files.
- Skills can be read, edited, shared, and mounted across agents.

Implication:

The memory core must store procedures and reusable operational lessons, not only user facts or conversation summaries.

Source:

- https://docs.acontext.io/
- https://github.com/memodb-io/Acontext

### ContextGraph

Useful ideas:

- Coding-agent memory should preserve durable working state under compaction pressure.
- Stores decisions, open tasks, failures, changed files, and restoration instructions.
- Repo-local `.contextgraph/` makes state visible to both humans and agents.
- Branch-aware checkpoints and context cache.

Implication:

For coding/project use, memory needs explicit working-state objects: decisions, blockers, changed files, failed attempts, restoration instructions, and branch scope.

Source:

- https://allenmaxi.github.io/ContextGraph/

### Agent Context System

Useful ideas:

- Append-only daily logs capture raw signal.
- Periodic consolidation compresses logs into curated topic files.
- A small index injects relevant memories on each turn.
- No vector database is required for the core pattern.

Implication:

The compounding loop can be implemented with simple files, but the important requirement is lifecycle: capture, consolidate, curate, retrieve.

Source:

- https://agents.mainbranch.dev/

### Agent Memory Protocol

Useful ideas:

- File-based, Markdown-first memory format.
- Memory nodes use structured frontmatter.
- Wiki-style links connect nodes into a graph.
- Designed for portability, git friendliness, and agent agnosticism.
- Includes store structure, node types, link semantics, daily notes, indexing, MCP integration, import/export, and versioning.

Implication:

Portability and standard operations should be considered early, even if the internal backend is not Markdown-only.

Source:

- https://agentmemoryprotocol.io/

### SwarmVault

Useful ideas:

- Local-first knowledge compiler inspired by the LLM Wiki pattern.
- Turns raw sources into a persistent Markdown wiki, knowledge graph, and hybrid search.
- Emphasizes that LLM work should not be thrown away after one answer.

Implication:

This project should preserve the llmwiki idea: every high-value investigation can produce a durable knowledge asset.

Source:

- https://github.com/swarmclawai/swarmvault

### Zep / Graphiti

Useful ideas:

- Temporal knowledge graph.
- Episodes, entities, facts/relationships, provenance.
- Fact invalidation through validity windows.
- Hybrid semantic, keyword, and graph search.
- Context block assembly for agents.
- Graphiti is the open-source graph engine; Zep is the managed context platform.

Implication:

Graphiti is a strong candidate for the graph memory engine, but this project should not become a Zep clone. Zep is a capability benchmark; Graphiti/Neo4j are implementation candidates.

Sources:

- https://help.getzep.com/docs/faq/zep-vs-graphiti
- https://help.getzep.com/v2/memory
- https://help.getzep.com/v2/understanding-the-graph
- https://github.com/getzep/graphiti

### Cognee

Useful ideas:

- Graph-vector hybrid memory engine.
- Combines graph store, vector store, and relational store.
- Defaults can be file-based: SQLite, LanceDB, Kuzu.
- Supports ontology grounding, multimodal data, traceability, and audit traits.

Implication:

Graph plus vector plus provenance is a common shape. Neo4j is not the only possible graph backend; Kuzu or similar local-first graph backends may reduce operational cost.

Sources:

- https://github.com/topoteretes/cognee
- https://www.cognee.ai/blog/fundamentals/how-cognee-builds-ai-memory

## Common Capabilities Across Context Substrates

The reviewed Camp 2 tools converge on a common capability set.

### 1. Evidence Capture

The system must capture raw or normalized source material:

- files
- repositories
- web pages
- PDFs
- conversations
- command output
- meetings
- task logs
- documents

Each source needs provenance:

- origin
- locator
- content hash
- captured time
- source type
- stable segment IDs

### 2. Structured Memory Objects

The core should not be raw text only. It needs typed objects:

- `Source`
- `Episode`
- `Segment`
- `Entity`
- `Relation`
- `Knowledge`
- `Decision`
- `Procedure`
- `Activity`
- `WorkItem`
- `ContextPack`
- `Patch`
- `AuditEvent`
- `Projection`
- `MemoryScope`

### 3. Graph-Native Context

The memory must express relationships:

- supports
- contradicts
- depends_on
- part_of
- supersedes
- derived_from
- related_to
- blocks
- produces
- uses
- owned_by
- applies_to

Graph logic is core to the memory model. The graph database choice is an implementation decision, but relation-first modeling is not optional.

### 4. Temporal State

The system needs time semantics:

- observed time
- ingested time
- valid from
- valid until
- last verified time
- stale threshold
- supersession history

Without temporal state, memory cannot distinguish current truth from historical truth.

### 5. Provenance And Governance

Every durable memory should answer:

- Where did this come from?
- Who or what wrote it?
- Why was it written?
- What evidence supports it?
- What confidence does it have?
- Is it active, candidate, contested, stale, superseded, or archived?
- How can it be rolled back or corrected?

### 6. Context Pack Retrieval

Query should return work-ready context, not just search hits:

- relevant knowledge
- relevant entities
- evidence and citations
- decisions
- procedures
- open work items
- conflicts
- missing context
- recommended next reads
- freshness warnings

### 7. Progressive Disclosure

The retrieval path should support levels:

1. summary or ranked item
2. expanded object or section
3. source segment
4. raw transcript or original source

This keeps context efficient while preserving traceability.

### 8. Dream / Consolidation

Background maintenance is a core capability:

- merge duplicates
- promote candidates
- infer missing relationships
- enrich thin descriptions
- decay stale facts
- detect conflicts
- prune orphaned context
- compact verbose logs
- rebuild projections and indexes

### 9. Human-Readable Projection

The core store may be graph-backed, but it must produce readable projections:

- wiki pages
- debug object mirrors
- daily notes or activity logs
- decision records
- task views
- source views

These projections support inspection, correction, trust, and LLM-readable context.

### 10. Portability And Versioning

Memory scopes should be exportable and recoverable:

- snapshot a scope
- import a scope
- version memory changes
- roll back bad writes
- fork an experiment
- rebuild derived indexes from canonical data

### 11. Local-First Runtime

The system should run locally by default:

- local storage
- local inspectability
- optional local embeddings/LLMs
- no mandatory SaaS
- no opaque hidden state

Cloud services can be optional adapters, not product requirements.

### 12. Skill / Procedure Memory

The system must store reusable procedures:

- successful workflows
- project conventions
- tool usage recipes
- failure patterns
- warnings
- recovery steps
- coding standards

This is a major difference between a compounding context substrate and a simple user-fact memory backend.

## What Is Not Memory Core

These are important, but they belong to integration or product layers:

- agent prompt harness
- Claude/Codex/VS Code plugins
- dashboard
- multi-user SaaS
- chat UI
- benchmark harness
- automatic agent compliance
- managed hosting
- team permissions

The memory core should work even if the caller is a human, script, local agent, MCP host, or batch job.

## Proposed Memory Core Definition

```text
Memory Core is a local-first, graph-native, evidence-grounded,
human-inspectable, governable context substrate.

Its job is not to save chat history.
Its job is to convert useful work into durable context assets
that compound across sessions.
```

The core lifecycle:

```text
capture source
-> extract entities, relations, claims, procedures, decisions, and work state
-> remember through a governed write path
-> retrieve context packs for future work
-> consolidate and repair memory health
-> project memory into human-readable and LLM-readable views
-> reuse and refine
```

## Positioning Against Camp 1

Camp 1 memory backends are still useful. They provide:

- extraction
- embeddings
- vector search
- graph retrieval
- low-latency recall
- user/session scoping

This project can borrow those techniques. It should not adopt their product center.

The product center should be:

```text
What context should this agent or human work inside?
How does that context improve after useful work?
```

not:

```text
What facts should be injected into the next chat?
```

## Backend Implications

Graphiti/Neo4j remains a strong candidate for the temporal graph backend because it already addresses:

- episodes
- entities
- facts and relationships
- provenance
- temporal validity
- hybrid retrieval
- incremental update

But the backend should sit behind a project-owned interface. The memory core should own:

- object semantics
- write governance
- evidence policy
- scope model
- audit model
- projection model
- MCP surface
- context pack contract

Candidate backend strategy:

```text
Memory Substrate API and MCP
-> governance layer
-> GraphBackend interface
-> GraphitiBackend initially
-> Neo4j or local graph backend underneath
-> projections and audit generated from governed memory events
```

## Open Design Questions

1. Should the canonical semantic store be Graphiti/Neo4j, or should Graphiti be a rebuildable derived index from governed memory events?
2. Should Markdown/wiki be strictly projection, or can human edits become source events that are re-ingested?
3. What is the minimum local-first backend for development: Neo4j, Kuzu, FalkorDB, or file-backed test graph?
4. How should `MemoryScope` be represented: project, user, repo, workspace, branch, topic, or a composable set?
5. Which memory objects should be first-class in the first implementation slice: source, episode, entity, relation, knowledge, decision, procedure, activity, work item?
6. How much extraction belongs in memory core versus an analysis service?
7. What is the minimum context pack format that is useful before agent integration exists?
8. What maintenance operations must exist before the system is safe for long-term use?

## Initial Recommendation

Use the reviewed tools as capability benchmarks, not as product templates.

The memory core should be defined by the Camp 2 context-substrate requirements:

- compounding context
- local inspectability
- provenance
- graph-native relations
- temporal lifecycle
- progressive retrieval
- readable projections
- portability
- maintenance
- skill/procedure reuse

Graphiti/Neo4j can implement a large part of the graph and retrieval engine, but the llmwiki-style lifecycle must remain owned by this project.

The next formal spec should be:

```text
docs/superpowers/specs/2026-04-28-compounding-memory-core-design.md
```

It should turn this research note into concrete architecture and implementation slices.
