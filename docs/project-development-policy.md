# Project Development Policy

This document applies to this repository only. It should not become cross-project Memory Substrate policy.

## Product Direction

The project is `memory-substrate`, not a wiki-first tool.

Current priorities:

- local-first memory system
- no mandatory second LLM API key
- governed durable writes
- evidence-backed memory
- query normalization before heavier semantic infrastructure
- Kuzu/local graph backend for lightweight prototypes
- Neo4j as an optional production backend later
- Markdown/wiki as projection, not canonical storage

## Backend Strategy

Keep `GraphBackend` as the integration boundary.

Current backend stance:

- `file` backend is the deterministic contract and test backend.
- direct `KuzuGraphBackend` is the local-first graph prototype.
- Graphiti remains a temporal graph reference and possible low-level adapter, not the canonical high-level ingest path.
- Cognee and LlamaIndex are future adapter candidates only if they fit behind Memory Substrate governance.
- Neo4j should remain optional until local contracts, migration, and lifecycle semantics are stable.

## Retrieval Strategy

Do not jump directly to vector search to solve known domain vocabulary gaps.

Near-term order:

1. query normalization and synonym expansion
2. type/status/scope-aware retrieval
3. unstructured soft duplicate candidates
4. maintain report/review support
5. graph-backed expansion
6. embedding/vector/hybrid retrieval only after deterministic gaps are clear

## Agent And MCP Strategy

The MCP tool schema, service layer, and tool responses should carry the rules. `AGENTS.md`, `CLAUDE.md`, and host-specific notes are adapters, not policy sources.

When MCP behavior changes:

- update service tests
- update MCP boundary tests
- update `docs/mcp-api-reference.md`
- update `docs/agent-memory-mcp-usage.md` if caller behavior changes
- update `todo.md` if priorities change

## Documentation Strategy

Keep docs layered:

- `README.md`: short entrypoint
- `docs/README.md`: documentation map
- `docs/memory-policy.md`: cross-project rules
- `docs/project-development-policy.md`: repository strategy
- `docs/agent-memory-mcp-usage.md`: caller workflow
- `docs/mcp-api-reference.md`: tool reference
- `todo.md`: active execution queue

Historical specs and plans should be preserved unless they actively mislead current work. Mark them as historical and link to current canonical docs.

## Development Discipline

Prefer small, testable slices.

For code changes:

- write or update tests before implementation when behavior changes
- keep canonical data and derived projections separated
- use service-layer validation as the final guard
- avoid broad refactors unrelated to the current slice
- do not require optional dependencies for default tests
- verify full tests before claiming completion when behavior changes

For docs-only changes:

- verify Markdown links where practical
- avoid duplicating canonical policy across multiple files
- point to canonical docs instead of copying long sections
