# Todo

This file tracks the active execution queue for this repository. Keep it current when starting, finishing, or reprioritizing work.

## P0: Documentation And Policy Cleanup

- [x] Move root research source notes into `docs/research/source-notes/`.
- [x] Add a documentation map in `docs/README.md`.
- [x] Split cross-project memory rules into `docs/memory-policy.md`.
- [x] Split repository-specific strategy into `docs/project-development-policy.md`.
- [x] Move detailed MCP API reference out of `README.md`.
- [x] Add `AGENTS.md` as a short agent entrypoint.

## P1: Query Normalization

- [x] Add deterministic query normalization for domain terms.
- [x] Make `待办`, `待办项`, `todo`, `task`, and `任务` retrieve `work_item` records.
- [x] Make decision/preference/procedure/evidence terms retrieve the matching object types or knowledge kinds.
- [x] Return `normalized_terms`, `applied_filters`, and useful no-match retry hints where practical.
- [x] Add tests for search and context behavior.
- [x] Update `docs/mcp-api-reference.md` and `docs/agent-memory-mcp-usage.md` after behavior lands.

## P1: Unstructured Soft Duplicate Candidates

- [x] Add soft duplicate detection for title/summary-only knowledge.
- [x] Return `possible_duplicates` with reasons and scores.
- [x] Do not hard-reject unstructured semantic duplicates.
- [x] Preserve current hard duplicate/conflict behavior for structured facts.
- [x] Add tests for similar unstructured knowledge that should be flagged but still writable.

## P1: Maintain Duplicate Review

- [x] Extend `memory_maintain report` to surface soft duplicate candidates.
- [x] Keep `merge_duplicates` limited to deterministic structured duplicates until review semantics are explicit.
- [x] Design a safe resolve/review path for soft duplicates.

## P2: Agent Query Planning Guidance

- [x] Update agent usage docs so callers retry with expanded terms before concluding there is no memory.
- [x] Add response guidance fields to MCP docs after implementation.
- [x] Add MCP resources/prompts for policy and examples.

## P3: Semantic Retrieval And Reasoner Adapter Evaluation

- [x] Re-evaluate embedding/vector/hybrid retrieval after deterministic query normalization is in place.
- [x] Continue Cognee and LlamaIndex spikes only if they fit behind Memory Substrate governance.
- [x] Keep hosted LLMs, local LLMs, Graphiti, and reasoner adapters optional.
- [x] Treat Neo4j as an optional production backend after local contracts and migrations are stable.
