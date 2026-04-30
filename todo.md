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

## P1: LanceDB Semantic Retrieval

- [x] Spike LanceDB + BGE-M3 semantic retrieval against Chinese/English memory queries.
- [x] Confirm LanceDB remains a derived index, not canonical storage.
- [x] Add optional semantic dependencies for LanceDB and FlagEmbedding.
- [x] Project canonical memory objects into semantic chunks.
- [x] Rebuild the semantic index from `memory_maintain reindex`.
- [x] Merge lexical and semantic results in `memory_query search`.
- [x] Keep semantic search active when a graph backend is also configured.
- [x] Add regression coverage for the `Codex dogfood MCP` query miss.

## P1: Repo Parser And Documentation Indexing

- [x] Adopt a single-primary parser stance: require `tree_sitter_language_pack`, then use local fallback parsing only when parser loading fails.
- [x] Index Markdown repository docs as source evidence with headings, excerpts, and line locators.
- [x] Make repo query summaries include documentation sections so theory-to-code questions can find design docs.
- [x] Add a locked parser dependency for `tree-sitter-language-pack==1.6.0` and run a live parser smoke test.

## P1: MCP Context Budget

- [x] Make `memory_query page` compact by default with explicit `options.detail: "full"` for complete stored objects.
- [x] Bound and truncate source segment excerpts returned by `memory_query expand`.
- [x] Shorten repo source summaries and MCP server instructions.

## Active Execution Queue

### MS-01: Retrieval Fusion And Query Matching

Status: `completed`

Goal: make `memory_query search` robust when users and agents do not phrase queries with exact stored keywords.

Boundary: memory-core retrieval only. Do not adopt llm_wiki desktop/wiki UI, web clipper, or knowledge-collection workflows.

Deliverables:
- [x] Replace lexical/semantic score max-merge with rank-based fusion such as Reciprocal Rank Fusion.
- [x] Improve lexical query planning with phrase, title, filename/id, and CJK bigram signals.
- [x] Return matched semantic chunks with source locators, excerpts, and chunk scores in query results.
- [x] Document retrieval scoring behavior in MCP docs.

Verification:
- [x] Add focused unit tests for lexical phrase/title/id/CJK matching.
- [x] Add semantic merge tests using a fake semantic index.
- [x] Run `uv run --group dev python -m pytest tests/test_query_normalization.py tests/test_semantic_index_service.py tests/test_mcp_server.py`.
- [x] Run non-semantic main path: `uv run --group dev python -m pytest -k 'not lance and not semantic'`.

### MS-02: Source Chunking And Evidence Quality

Status: `completed`

Goal: make source segments and semantic chunks preserve document structure and citeable locations.

Boundary: deterministic source/evidence preparation. Do not introduce mandatory LLM extraction or hosted services.

Deliverables:
- [x] Add a Markdown-aware document chunker for ingest and semantic indexing.
- [x] Preserve heading breadcrumbs, code fences, tables, frontmatter boundaries, overlap, and source offsets in chunks.
- [x] Reuse one chunking contract across `memory_ingest`, source segments, and semantic rebuild.
- [x] Include source locators and heading breadcrumbs in semantic chunks.

Verification:
- [x] Add tests for CJK text, code blocks, markdown tables, YAML frontmatter, and oversized sections.
- [x] Add ingest tests proving source segments carry stable locators and hashes.
- [x] Run `uv run --group dev python -m pytest tests/test_phase1_acceptance.py tests/test_semantic_index_service.py`.

### MS-03: Source Robustness From llm_wiki Upstream

Status: `completed`

Goal: absorb upstream llm_wiki source-hardening lessons without shifting Memory Substrate into a desktop knowledge collector.

Boundary: adapters and projections only. Canonical memory objects remain independent of document extraction libraries.

Deliverables:
- [x] Add robust frontmatter parsing/sanitizing for LLM-generated or imported markdown projections.
- [x] Evaluate PDF/DOCX/XLSX extraction dependencies for source capture; keep them behind ingest adapters and not core storage.
- [x] Treat multimodal image extraction/captioning as optional evidence capture for document-heavy knowledge work, not a memory-core prerequisite.
- [x] Add source deletion/cascade cleanup semantics only after source manifests and provenance policies are explicit.

Verification:
- [x] Add projection tests for fenced YAML, misplaced `frontmatter:`, wikilink lists, and malformed frontmatter fallback.
- [x] Add dependency decision notes before adding document extraction packages.
- [x] Run `uv run --group dev python -m pytest tests/test_obsidian_projection.py tests/test_structure_validation.py`.

### MS-04: Graph Maintenance Insights

Status: `completed`

Goal: make `memory_maintain report` surface graph-health issues that agents can act on.

Boundary: maintain/report output first. Defer visualization and UI concerns to product layers.

Deliverables:
- [x] Add deterministic graph health insights to `memory_maintain report`: isolated nodes, sparse clusters, bridge nodes, and weakly connected scopes.
- [x] Evaluate a local Python graph analysis library, such as `networkx`, before considering UI-oriented graphology/sigma dependencies.
- [x] Keep graph insights as maintain/report output for agents first; defer visualization to a separate product layer.

Verification:
- [x] Add graph-health report tests with a small synthetic memory graph.
- [x] Run `uv run --group dev python -m pytest tests/test_maintain_service.py tests/test_graph_health_report.py`.

### MS-05: MCP Query Sanitizer And Diagnostics

Status: `completed`

Goal: prevent long agent prompts, system instructions, and scratchpads from polluting `memory_query` retrieval.

Boundary: query-service hardening only. Do not add LLM query rewriting or a new retrieval library for this slice.

Deliverables:
- [x] Review MemPalace design lessons and capture them in `docs/research/2026-04-30-mempalace-design-review.md`.
- [x] Sanitize long `memory_query search` text before query planning.
- [x] Sanitize long `memory_query context` task text before context building.
- [x] Return `query_sanitizer` diagnostics and warnings when sanitization occurs.
- [x] Update MCP usage and API docs.

Verification:
- [x] Add focused tests for labeled long-prompt sanitization in search and context.
- [x] Run `uv run --group dev python -m pytest tests/test_query_normalization.py::QueryNormalizationTest::test_search_sanitizes_long_agent_prompt_before_planning_terms tests/test_query_normalization.py::QueryNormalizationTest::test_context_sanitizes_long_agent_prompt_and_reports_diagnostics`.

### MS-06: Source Adapter Metadata Contract

Status: `completed`

Goal: make `memory_ingest` outputs self-describing across repos, markdown, conversations, and future source adapters.

Boundary: adapter metadata and source payloads only. Do not add heavy document extraction dependencies in this slice.

Deliverables:
- [x] Define adapter metadata fields: adapter name, adapter version, supported mode, declared transformations, privacy class, and origin classification.
- [x] Attach adapter metadata to repo and markdown ingested sources.
- [x] Add deterministic freshness/currentness hints where available.
- [x] Update `docs/mcp-api-reference.md` and `docs/agent-memory-mcp-usage.md`.

Verification:
- [x] Add source ingest tests for repo and markdown adapter metadata.
- [x] Run focused source metadata tests in `tests/test_phase1_acceptance.py`.

### MS-07: Tiered Context Pack Contract

Status: `completed`

Goal: evolve `memory_query context` into budgeted work-ready context instead of a flat item list.

Boundary: context pack contract and query output shape. Do not add UI or visualization.

Deliverables:
- [x] Define context tiers for policy, active task, decisions, procedures, evidence, open work, and deep-search hints.
- [x] Keep compact defaults and bounded excerpts.
- [x] Preserve existing fields during the transition where practical.
- [x] Update MCP resources so an agent with no repo context can still use the tiers correctly.

Verification:
- [x] Add context budget and tier-order tests.
- [x] Run focused context pack contract tests.

### MS-08: Derived Index Repair And Retrieval Benchmark Harness

Status: `completed`

Goal: make semantic and graph indexes auditable, rebuildable, and measurable.

Boundary: local diagnostics and small deterministic benchmark data. Do not introduce hosted services.

Deliverables:
- [x] Add derived-index repair checks that compare index counts against canonical objects before destructive rebuilds.
- [x] Add planted-needle retrieval benchmark cases for lexical, semantic, and hybrid retrieval.
- [x] Report recall and latency separately per retrieval stream.
- [x] Document when to run benchmarks and how to interpret regressions.

Verification:
- [x] Add repair-safety tests for missing or stale semantic index entries.
- [x] Add a small benchmark smoke test that runs without network access.

### MS-09: Memory Fact-Checker And Lifecycle Lint

Status: `completed`

Goal: surface entity confusion, stale facts, and relationship mismatches without automatic mutation.

Boundary: advisory `memory_maintain report` output only. Do not auto-contest, supersede, or merge facts.

Deliverables:
- [x] Report similar entity names that may cause incorrect recall.
- [x] Report stale active facts using `valid_until`, `last_verified_at`, status, and evidence age where available.
- [x] Report relationship mismatches for structured claims with clear subject/predicate/object conflicts.
- [x] Add next-action guidance for promote, contest, supersede, or keep-both review.

Verification:
- [x] Add maintain report tests with synthetic entity-confusion and stale-fact fixtures.
- [x] Run focused maintain report fact-check test.

### MS-10: Context Payload Compression

Status: `completed`

Goal: reduce `memory_query context` response size so MCP callers spend less context on duplicated section data.

Boundary: response shape and documentation only. Do not remove compact item details or require an LLM summarizer.

Deliverables:
- [x] Measure context response field sizes and identify duplicated section payloads.
- [x] Convert `context_tiers` from copied section lists into compact directory metadata.
- [x] Convert top-level `decisions`, `procedures`, and `open_work` into id directories back into `items`.
- [x] Clip context item summaries to keep default context compact.
- [x] Update MCP docs and agent resources.

Verification:
- [x] Add regression coverage that context tiers do not duplicate section summaries.
- [x] Add payload budget coverage for large context responses.
- [x] Measure sample context payload reduction from about 16.2 KB to about 7.2 KB.

### MS-11: Advisory Concept Candidate Discovery

Status: `completed`

Goal: reconnect the LLM Wiki crystallization loop by surfacing repeated source concepts without automatically mutating durable memory.

Boundary: deterministic advisory discovery only. Do not add a required LLM API key and do not auto-promote candidates into canonical memory.

Deliverables:
- [x] Add reusable concept candidate discovery over source segments, headings, and existing memory text.
- [x] Surface global `concept_candidates` from `memory_maintain report`.
- [x] Surface current-source `memory_suggestions.concept_candidates` from `memory_ingest`.
- [x] Suppress candidates already represented by concept knowledge or concept nodes.
- [x] Document that candidates require agent/human review before `memory_remember`.

Verification:
- [x] Add maintain report tests for repeated uncrystallized concepts and existing concept suppression.
- [x] Add repo ingest test proving source-local advisory concept candidates are returned.
- [x] Run focused red-green tests for the new behavior.

### MS-12: Candidate Review And Crystallization Flow

Status: `completed`

Goal: make advisory candidates actionable for agents without letting candidates become automatic canonical memory.

Boundary: response guidance and agent workflow only. Do not add an automatic write path, mandatory LLM key, or background agent.

Deliverables:
- [x] Add `review_guidance` outcomes for concept, procedure, decision, merge, and skip.
- [x] Add `suggested_memory.input_data` with reason, memory source, scope refs, evidence refs, status, confidence, and editable fields.
- [x] Infer candidate scope refs from repo/document nodes when available and fall back to source ids.
- [x] Document the candidate review flow in MCP docs, agent resources, and memory policy.
- [x] Dogfood candidate discovery on `wiki-memory`, `llm_wiki`, and `mempalace` using a temporary memory root.

Verification:
- [x] Add regression coverage for executable candidate review payloads.
- [x] Run focused red-green tests for candidate review payloads.

### MS-13: Candidate Quality And Ranking

Status: `completed`

Goal: make candidate discovery more stable and useful by classifying, ranking, and diagnosing candidate quality.

Boundary: deterministic candidate quality only. Do not add a required LLM classifier or automatic durable writes.

Deliverables:
- [x] Add `candidate_type` hints for concept, procedure, decision, tool/library, and implementation detail candidates.
- [x] Add `ranking_signals` with score bonuses and penalties.
- [x] Rank stable concepts/procedures/decisions ahead of tool/library and version/package details.
- [x] Add `candidate_diagnostics.skipped` so filtered phrases are explainable.
- [x] Update MCP docs and agent resources.

Verification:
- [x] Add tests for classification, ranking, diagnostics, and ingest response shape.
- [x] Dogfood against `wiki-memory`, `llm_wiki`, and `mempalace`.

### MS-14: Soft Duplicate Review Resolve

Status: `completed`

Goal: turn advisory soft duplicate candidates into an explicit reviewed maintenance workflow.

Boundary: explicit review outcomes only. Do not let `merge_duplicates` auto-merge unstructured soft duplicates.

Deliverables:
- [x] Add `memory_maintain resolve_duplicates` for reviewed soft duplicate candidates.
- [x] Support `supersede`, `keep_both`, and `contest` outcomes.
- [x] Require non-empty review reasons and current soft duplicate candidate ids.
- [x] Keep curated replacement as an explicit `memory_remember knowledge` write followed by `memory_remember supersede`.
- [x] Update MCP docs, agent usage docs, and built-in resources.

Verification:
- [x] Add lifecycle tests for supersede, keep_both, and rejecting non-candidate pairs.
- [x] Add MCP dispatch/schema/apply guard tests.
