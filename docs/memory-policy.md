# Memory Policy

This is the canonical cross-project policy for Memory Substrate behavior. It applies to every MCP host and every project that uses this server.

## Product Boundary

Memory Substrate is a governed memory core. Agents, humans, scripts, and MCP hosts are callers.

The core owns:

- canonical memory objects
- evidence refs and source segments
- scopes
- governed durable writes
- duplicate and conflict rules
- lifecycle state
- audit and patches
- rebuildable projections and indexes

The caller owns:

- natural-language understanding
- task-specific judgment
- query planning
- extraction from ambiguous material
- final answer generation

LLM capability may help callers plan queries, extract candidates, and judge soft duplicate candidates. It must not be a mandatory dependency of the memory core.

## Canonical Data

Canonical data lives under `memory/objects/`. Markdown, wiki pages, debug mirrors, Doxygen output, graph tables, and search indexes are derived projections or indexes.

Durable writes should go through `memory_remember` or controlled `memory_maintain` modes. Direct file edits are only for recovery and must be followed by structure validation, repair when needed, and reindexing.

## Tool Boundaries

- `memory_ingest` captures source material as evidence. It does not decide what should become durable memory.
- `memory_query` retrieves existing context, related records, candidate duplicates, and graph neighborhoods.
- `memory_remember` is the governed durable write path.
- `memory_maintain` validates, repairs, reindexes, reports, and performs lifecycle consolidation.

Ingest and maintain may return advisory `concept_candidates`. These candidates help callers notice repeated ideas that may deserve crystallization, but they are not canonical memory until an agent or human reviews evidence and calls `memory_remember`.

Ingest responses should also return a compact `agent_extraction` protocol block. The protocol is a handoff contract, not an embedded LLM pipeline: ingest captures evidence, the caller analyzes it, and `memory_remember` commits reviewed durable memory. Detailed instructions belong in MCP resources or documentation, not repeated in every ingest result.

Concept candidates may include a `suggested_memory.input_data` skeleton. This skeleton is a review aid, not an instruction to write automatically. Callers must read evidence, query for existing related memory, rewrite the summary, and choose the correct outcome: remember as concept, procedure, decision, merge with existing memory, or skip.

Candidate ranking is advisory. `candidate_type` and `ranking_signals` should help agents prioritize stable concepts, procedures, and decisions above tool names or implementation details, but they must not replace evidence review. `candidate_diagnostics` may expose skipped terms for tuning; skipped terms are not remembered automatically.

## Governance Fields

Governed create operations require:

- `reason`: why this memory should survive future sessions.
- `memory_source`: one of `user_declared`, `human_curated`, `agent_inferred`, `system_generated`, or `imported`.
- `scope_refs`: at least one durable scope id.

Agent-inferred active knowledge is normalized to `candidate`. Active inferred knowledge must be promoted only after evidence and lifecycle checks justify it.

## Evidence Rules

Evidence refs must point to existing source segments. Optional `locator` and `hash` fields must match the referenced segment when provided.

Active knowledge should have evidence unless it is explicit `user_declared` or `human_curated` memory. Evidence-less inferred claims should remain `candidate` or be rejected by policy.

## Scope Rules

Every durable memory item should declare where it applies. Scope controls retrieval, maintenance, export, and future access policy.

Missing scope is treated as broad/global for duplicate and conflict checks. Prefer explicit scopes such as project, repo, user, workspace, or topic.

## Structured Hard Governance

Structured knowledge can be governed strictly when it has clear semantics:

- exact duplicate structured claims may be rejected
- same-kind, same-scope subject/predicate conflicts may be marked `contested`
- superseded knowledge should remain auditable
- duplicate merge should preserve evidence and lineage

Structured duplicate and conflict checks should consider `kind`, overlapping scopes, subject, predicate, value, and object.

## Unstructured Soft Governance

Title/summary-only knowledge must not be hard-rejected by semantic similarity alone.

For unstructured knowledge:

- detect possible duplicates
- return candidate duplicate ids and reasons
- allow the write unless another hard rule fails
- prefer `candidate` status when confidence or evidence is weak
- let `memory_maintain` or a caller review merge/supersession later

This avoids corrupting memory when two similar descriptions are actually a decision, a background fact, a narrower rule, or a newer conclusion.

Soft duplicate candidates are advisory response data. They should be recomputable by maintenance flows instead of treated as permanent truth.

Maintenance may report soft duplicate candidates, but automatic merge must stay limited to deterministic structured duplicates. Soft duplicate mutation must go through an explicit review/resolve flow such as `memory_maintain resolve_duplicates`, using one of these explicit outcomes:

- mark one item superseded by another
- keep both with clarified scopes or summaries
- contest one or both items
- promote a curated replacement and supersede the originals through an explicit replacement write followed by `memory_remember supersede`

Source retirement must preserve audit history. Use `memory_maintain archive_source`, not physical deletion, when a source was imported incorrectly or should no longer support claims. Only knowledge whose evidence depends entirely on the archived source should be marked `stale` automatically; mixed-evidence knowledge requires explicit review.

## Query Policy

Query should return work-ready context, not just raw string matches.

Near-term deterministic query behavior should include:

- query normalization for domain terms
- long agent-prompt sanitization before query planning
- type and status aware retrieval
- scope-aware filtering
- graph expansion when configured
- clear no-match diagnostics and retry hints

Graph relations are derived index records unless they are backed by a canonical `relation` object. Every derived relation should carry `payload.relation_schema` so callers can trace the origin object, origin field, derivation kind, and endpoint canonical types before trusting the edge.

Required domain mappings include:

- `待办`, `待办项`, `todo`, `task`, `任务` -> `work_item`
- `决策`, `decision` -> `knowledge` with decision-like kinds
- `偏好`, `preference` -> preference knowledge
- `流程`, `procedure` -> procedure knowledge
- `证据`, `source`, `evidence` -> source and evidence records

When a query returns no useful results, callers should expand terms and retry before concluding that memory has no answer.

Context responses should be tiered and budgeted. Agents should be able to distinguish active task, decisions, procedures, evidence, open work, and deep-search hints without reading all returned items as one flat list. Tier fields should avoid duplicating full item details; they should point to compact item ids whenever possible.

## Source Adapter Policy

Ingest adapters should record how evidence was captured. Source metadata should include adapter name, version, mode, declared transformations, privacy class, origin classification, and freshness diagnostics.

Adapter metadata describes evidence capture. It is not a durable conclusion about the world and should not replace `memory_remember`.

## LLM And Embedding Policy

Embedding, rerankers, hosted LLMs, local LLMs, Graphiti, Cognee, LlamaIndex, Neo4j, or vector databases may be adapters. They must stay behind project-owned contracts.

Do not make the core require a second API key. Codex, Claude Code, humans, scripts, or optional reasoner adapters may supply LLM judgment from outside the core.

The preferred progression is:

1. deterministic query normalization
2. deterministic soft duplicate candidates
3. graph-backed retrieval
4. optional embedding/vector/hybrid retrieval
5. optional reasoner adapter

## Tool Response Guidance

Tool responses should guide callers even if they have not read the docs. Prefer fields such as:

- `normalized_terms`
- `query_sanitizer`
- `context_tiers`
- `context_budget`
- `applied_filters`
- `code_index`
- `code_modules`
- `adapter`
- `freshness`
- `possible_duplicates`
- `concept_candidates`
- `memory_suggestions`
- `fact_check_issues`
- `conflicts_with`
- `requires_decision`
- `pending_decisions`
- `suggested_retry_terms`
- `suggested_exclude_patterns`
- `excluded_by_preflight`
- `warnings`
- `next_actions`

These fields should be test-covered when added.

Query responses should be compact by default. Full stored objects, long source segments, and large audit/report payloads should require explicit caller options such as `detail: "full"` or bounded `max_items` / snippet controls. Repo source pages should block full detail because full repo maps are too large for normal agent context; callers should use compact locators and local file reads.

The MCP server should also expose compact policy and playbook resources for hosts that can read MCP resources directly. Repository-local `AGENTS.md` or `CLAUDE.md` files are adapters, not the policy source of truth.
