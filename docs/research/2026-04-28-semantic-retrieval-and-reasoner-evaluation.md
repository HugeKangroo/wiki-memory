# Semantic Retrieval And Reasoner Evaluation

Date: 2026-04-28

Status: Current local decision

## Context

After documentation cleanup, query normalization, unstructured soft duplicates, and maintain duplicate reporting, the memory system has a clearer split:

- Memory core owns deterministic storage, governance, query, lifecycle, audit, and indexes.
- Agents own natural-language judgment, extraction, query planning, and answer generation.
- Optional backends may improve retrieval, but they must not take over memory governance.

The question is whether to add embedding, vector search, hybrid retrieval, hosted LLM reasoners, local LLM reasoners, Cognee, LlamaIndex, Graphiti, or Neo4j now.

## Current Retrieval Capability

Implemented:

- lexical search over title, summary, payload, source segments, and metadata
- deterministic query normalization for todo/work item, decision, preference, procedure, source, and evidence terms
- context packs with decisions, procedures, open work, citations, freshness, and missing context
- optional file and Kuzu graph backend search
- graph backend metadata matching
- soft duplicate detection for unstructured title/summary-only knowledge
- maintain reports for deterministic duplicate groups and soft duplicate candidates

Not implemented:

- embedding generation
- vector index
- cross-encoder reranking
- hybrid lexical/vector/graph retrieval
- hosted or local LLM reasoner inside the memory core

## Decision

Do not add embedding/vector/reasoner infrastructure yet.

Reason:

1. The current highest-value gap was deterministic vocabulary mismatch, not generic semantic similarity.
2. Query normalization now handles the known domain mismatch cases without new dependencies.
3. Soft duplicate detection now covers the most dangerous unstructured-memory duplication case without false hard merges.
4. A mandatory LLM or embedding runtime would violate the local-first, no-second-API-key constraint.
5. The memory policy and MCP contract need to remain stable before adding heavier retrieval layers.

## When To Reopen Embedding Or Hybrid Search

Reopen this decision when at least one of these becomes true:

- deterministic query normalization cannot cover repeated real user queries
- users ask natural-language questions that require fuzzy concept matching across many unrelated terms
- memory grows large enough that lexical filtering produces too many candidates
- graph traversal finds related nodes but not semantically similar unlinked records
- soft duplicate detection produces too many false negatives on title/summary-only knowledge
- a local embedding backend can be added without making default installs heavy or brittle

## Adapter Policy

Any semantic retrieval or reasoner integration must stay behind Memory Substrate contracts.

Allowed future adapters:

- local embedding index
- vector database
- hybrid lexical/vector/graph retriever
- reranker
- local LLM reasoner
- hosted LLM reasoner
- Cognee adapter
- LlamaIndex PropertyGraphIndex adapter
- Graphiti low-level graph adapter
- Neo4j production graph backend

Not allowed as core defaults:

- mandatory hosted LLM API key
- mandatory embedding provider
- high-level ingestion pipeline that decides durable memory outside `memory_remember`
- backend-native schema replacing canonical Memory Substrate objects
- automatic unstructured duplicate merge based only on semantic similarity

## Cognee And LlamaIndex Gate

Do not continue Cognee or LlamaIndex spikes until the project has a concrete retrieval failure that direct Memory Substrate + Kuzu cannot solve.

If reopened, the spike must answer:

- Can it ingest already-structured Memory Substrate objects without running its own mandatory extraction pipeline?
- Can it preserve evidence refs, scope refs, status, confidence, validity windows, and audit lineage?
- Can it run locally without a mandatory hosted LLM key?
- Can indexes be rebuilt from canonical objects?
- Can it be removed without migrating canonical data?

## Neo4j Gate

Keep Neo4j as an optional production backend candidate.

Do not make it the default until:

- local Kuzu/file backend contracts are stable
- graph schema migration is explicit
- rebuild-from-canonical behavior is reliable
- operational burden is justified by graph size, query complexity, visualization needs, or production deployment requirements

## Reasoner Gate

A reasoner adapter may be useful later for query planning, extraction, duplicate review, and maintenance suggestions.

It should be optional and callable through a narrow interface. It should not be required for:

- ingest
- remember
- query
- maintain report
- repair
- projection rebuild
- default tests

## Next Practical Step

The next practical implementation area is not embedding. It is improving agent and MCP ergonomics around the deterministic features already added:

- make tool responses more consistently include guidance fields
- consider an explicit soft duplicate resolve mode
- consider query diagnostics for no-match cases
- gather real failed queries before adding vector infrastructure
