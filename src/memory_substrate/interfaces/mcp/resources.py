from __future__ import annotations

from mcp.server.fastmcp import FastMCP


MEMORY_POLICY = """# Memory Substrate Policy

## Product Boundary

Memory Substrate owns canonical objects, evidence, scopes, governed writes, lifecycle state, audit, projections, and rebuildable indexes. Agents and humans own natural-language judgment, extraction, query planning, and answer generation.

The memory core must not require a second LLM API key. Hosted LLMs, local LLMs, Graphiti, Cognee, LlamaIndex, vector indexes, and reasoner adapters are optional adapters behind project-owned contracts.

Graph relations are derived index records unless backed by a canonical relation object. Inspect `payload.relation_schema` for version, derivation, origin object, origin field, and endpoint canonical types before treating a relation as reusable knowledge.

External wiki folders are projection targets only. Rendered files are managed through a projection manifest; reconciliation is report-only and canonical writes still go through reviewed ingest, remember, or explicit maintenance modes.

## Structured Hard Governance

Structured knowledge may be governed strictly. Exact duplicate structured claims can be rejected, same-scope subject/predicate conflicts can be marked contested, and supersession must preserve audit history.

Active agent-inferred knowledge requires evidence and is normalized to candidate when evidence is absent. Direct user-declared or human-curated knowledge without evidence refs gets a generated declaration source so the compressed knowledge still has a citeable source layer.

## Unstructured Soft Governance

Title/summary-only knowledge uses soft duplicate detection. Similar text returns advisory `possible_duplicates`; it must not be hard-rejected or automatically merged by semantic similarity alone.

## Query Policy

Callers should use `memory_query` at task start and before durable writes. If a result is empty or weak, perform query expansion and retry before concluding that memory has no answer.

Required domain mappings include todo/work item, decision, preference, procedure, source, and evidence terms.

`memory_query search` and `context` sanitize unusually long prompt-like query text before retrieval and return `query_sanitizer` diagnostics.

## Maintenance Policy

`memory_maintain report` may surface soft duplicate candidates with `review_guidance`, editable `suggested_resolution`, and `next_actions`. `merge_duplicates` is limited to deterministic structured duplicates. Use `memory_maintain resolve_duplicates` with `options.apply=true` after explicit review to supersede a duplicate, keep both with clarified summaries or scopes, or contest the listed items.

Use `memory_maintain archive_source` with `options.apply=true` to retire a bad source without deleting audit history. It archives the source, marks knowledge stale only when all evidence depends on that source, and reports mixed-evidence knowledge for explicit review.

`memory_ingest` and `memory_maintain report` may surface advisory `concept_candidates`. They are review signals for possible LLM Wiki-style crystallization, not automatic durable memory. Ingest candidates are compact triage records; run `memory_maintain report` when the full `suggested_memory.input_data` skeleton is needed. Treat `candidate_type`, `ranking_signals`, and `recommendation.priority` as triage aids. Read evidence, query for existing memory, rewrite summary, and choose concept/procedure/decision/merge/skip. Use `candidate_diagnostics` to understand skipped document artifacts, path fragments, temporary task vocabulary, format markers, action phrases, shortcut fragments, generic terms, long terms, or weak terms.

Temporary, scratch, and evaluation memories must use explicit `status` or `lifecycle_state` such as `temporary`. They are excluded from default query/context results. Use `include_temporary: true` only when reviewing them, then promote durable items or archive obsolete ones with `memory_maintain archive_knowledge`.
"""


AGENT_PLAYBOOK = """# Agent Memory Playbook

## Tool Discovery

Some hosts expose MCP tools through deferred tool search to reduce initial context. If `memory_query`, `memory_ingest`, `memory_remember`, or `memory_maintain` are not active tools, search for `memory-substrate`, `agent memory`, `persistent memory`, `memory_query`, `context`, `remember`, `ingest`, or `maintain` and then use the loaded tools directly. Do not fall back to shell or internal Python dispatch unless MCP discovery or MCP calls fail.

## Task Start

1. Call `memory_query` with `mode: "context"` or `mode: "search"`.
2. If results are weak, apply query expansion. Examples: `待办项` -> `work_item`, `todo`, `task`; `决策` -> decision knowledge.
3. Use returned citations, open work, decisions, procedures, conflicts, and missing context to plan the task.
4. Pass the actual task or question, not the full system prompt or scratchpad. If `query_sanitizer.was_sanitized` is true, tighten the next query.
5. When several returned ids need hydration, call `memory_query` `mode: "expand"` with `input_data.ids` and bounded `options.max_items` / `options.per_id_max_items`.

## New Evidence

1. Use `memory_ingest` to capture files, repos, web pages, PDFs, or conversations as evidence.
2. For repo ingest, use compact `memory_query page` results (`code_index`, `code_modules`, `api_inventory`, `code_intelligence`, `module_dependencies`, `inheritance_graph`, `call_index`, `framework_entries`, `doc_index`, `document_sections`, symbols, excerpts, and line locators) to find files, callable surfaces, and stable code structure, then use `memory_query` `mode: "source_slice"` for exact bounded code or document text.
3. Inspect `metadata.adapter` and `metadata.freshness` to understand capture mode, transformations, privacy class, currentness, and fingerprint.
4. For repo ingest, handle `status: "completed_with_pending_decisions"` by using the clean source and deciding separately whether pending entries ever need `options.force: true`.
5. Treat repo `status: "noop"` as a clean unchanged result and use the existing `source_id`.
6. Follow compact `memory_suggestions.agent_extraction` to inspect source evidence, query existing memory, prepare durable candidates outside ingest, and call `memory_remember` only after review.
7. Inspect compact `memory_suggestions.concept_candidates`; prefer candidates with `recommendation.recommended=true` and high or medium priority, follow `review_guidance`, review cited evidence, query for existing memory, then decide whether to remember as concept/procedure/decision, merge, or skip. Run `memory_maintain report` when you need the full `suggested_memory.input_data` skeleton.
8. Analyze outside ingest.
9. Before durable writes, call `memory_query` again to check related context, duplicates, and conflicts.

## Durable Writes

Use `memory_remember` only when the item should survive future sessions. Create writes need `reason`, `memory_source`, and `scope_refs`.

Use direct `memory_remember knowledge` without `evidence_refs` only for bounded user-declared or human-curated statements. The server creates a `declaration` source and returns `evidence_contract.provenance: "declaration_source_created"`. For longer direct statements or explicit long remember inputs, pass `source_text` so the raw input is preserved as source evidence. Agent-inferred active claims still normalize to candidate. Use `memory_ingest` first for repos, files, web pages, PDFs, conversations, and external material.

When completed work satisfies an existing `work_item`, create or link the activity with `related_work_item_refs`, then call `memory_remember` `mode: "work_item_status"` to set the work item to `resolved`, `closed`, `blocked`, or another explicit status. Do not leave completed activity records with related open todos.

For concept candidates from `memory_maintain report`, edit `suggested_memory.input_data` before writing. At minimum, replace the generated summary with a bounded definition grounded in evidence and verify the suggested `scope_refs`.

Inspect `possible_duplicates` after knowledge writes. Similar unstructured items are advisory candidates, not automatic merge decisions.

## Maintenance

Use `memory_maintain report` for read-only review. Mutating maintenance requires `options.apply=true`.

Treat graph health, derived index diagnostics, soft duplicate candidates, `concept_candidates`, and `fact_check_issues` as review signals. They should guide explicit remember/maintain actions, not automatic mutation.

Use `memory_maintain archive_source` only for bad imports or untrusted evidence sources. Review `partially_affected_knowledge_ids` before changing mixed-evidence memories.

Use `memory_maintain archive_knowledge` with `options.apply=true` after reviewing a temporary, stale, or incorrect knowledge item that should be retained for history but excluded from normal retrieval.

Temporary memories are excluded from default query/context results. Pass `include_temporary: true` only when intentionally reviewing temporary, scratch, or evaluation memory.

Use external wiki projection only as a low-frequency maintenance flow. Configure `wiki_projection.path` and `wiki_projection.format`, call `render_projection` with `options.apply=true` to write manifest-bound generated files, and call `reconcile_projection` to review local wiki edits. Reconcile returns conflicts and `remember_candidates`; it does not mutate canonical memory.

When reading graph neighborhoods, check each relation's `payload.relation_schema` and then inspect the origin object when exact provenance matters.
"""


MCP_API_SUMMARY = """# Memory Substrate MCP API Summary

The server exposes four tools:

- `memory_ingest`: capture source material as citable evidence.
- `memory_query`: retrieve context, search memory, expand objects, hydrate bounded source slices, and inspect graph neighborhoods.
- `memory_remember`: commit governed durable activities, knowledge, work items, and work item status updates.
- `memory_maintain`: validate, repair, reindex, report, and consolidate memory.

All tool calls use:

```json
{
  "args": {
    "mode": "...",
    "input_data": {},
    "options": {}
  }
}
```

The server root is configured outside tool calls and defaults to `~/memory-substrate` unless `MEMORY_SUBSTRATE_ROOT` is set. `input_data` is required even when empty. Mutating maintain modes require `options.apply=true`.

Repo ingest statuses:

- `completed_with_pending_decisions`: preflight excluded local or agent state, wrote the clean repo view, and returned pending decisions.
- `noop`: repo fingerprint is unchanged from the active stored source; no patch, audit, or projection data is written.
- `completed`: source material was written or updated.

Repo sources store a lightweight repo map, API inventory, and deterministic code intelligence indexes rather than full source bodies, full documents, runtime call graphs, or architecture conclusions as canonical memory. `memory_query page` is compact by default; repo source pages with `options.detail: "full"` return `result_type: "page_unavailable"` and `status: "unsupported"` because complete repo content should be read through bounded locators. Use `memory_query` `mode: "source_slice"` with a source id, relative path, and line range for exact source text. Query options are mode-specific: `detail` is only for `page`; `include_segments` is only for `page` and `expand`; `snippet_chars` is for `page`, `expand`, and `source_slice`.

`memory_query search` and `context` return `query_sanitizer` diagnostics when prompt-like query text is shortened before retrieval.

`memory_query context` returns `context_tiers` and `context_budget`; tier sections are compact id directories back into `items`, so use them before deep expansion.

`memory_query expand` accepts either `input_data.id` for one object or `input_data.ids` for several objects. Multi-id expansion returns `expanded_context_many` with groups keyed by root id, missing-id warnings, a shared deduplicated `source_segments` list, and a global context budget.

`memory_remember knowledge` returns `evidence_contract`. `declaration_source_created` means a direct user/human declaration was preserved as a source and attached as evidence. `remember_input_source_created` means explicit `source_text` was preserved for a non-user-curated write. `caller_evidence_refs` means the caller supplied existing source evidence. `evidence_absent` means the memory remains unevidenced and should normally be candidate or review-only.

Temporary memory is excluded from default query/context results. Use query filters with `include_temporary: true` only for review, then promote reviewed durable knowledge or archive it with `memory_maintain archive_knowledge`.

External wiki projection is configured under `memory/config.json` with `wiki_projection.path` and `wiki_projection.format`. Use `memory_maintain render_projection` with `options.apply=true` to write the configured external Obsidian view. Use `memory_maintain reconcile_projection` for report-only review of local wiki edits and unmanaged Markdown notes.
"""


def register_agent_resources(mcp: FastMCP) -> None:
    @mcp.resource(
        "memory://policy",
        name="memory_policy",
        description="Canonical Memory Substrate policy for MCP callers.",
        mime_type="text/markdown",
    )
    def memory_policy() -> str:
        return MEMORY_POLICY

    @mcp.resource(
        "memory://agent-playbook",
        name="memory_agent_playbook",
        description="Agent workflow for querying, ingesting, remembering, and maintaining memory.",
        mime_type="text/markdown",
    )
    def memory_agent_playbook() -> str:
        return AGENT_PLAYBOOK

    @mcp.resource(
        "memory://mcp-api-summary",
        name="memory_mcp_api_summary",
        description="Short summary of Memory Substrate MCP tools and call envelope.",
        mime_type="text/markdown",
    )
    def memory_mcp_api_summary() -> str:
        return MCP_API_SUMMARY

    @mcp.prompt(
        name="memory_task_start",
        description="Plan the required memory query workflow before starting a task.",
    )
    def memory_task_start(task: str = "") -> str:
        return (
            "Start by calling memory_query with mode=context or mode=search. "
            "If the result is empty or weak, perform query expansion and retry before concluding "
            f"there is no memory. Task: {task}"
        )

    @mcp.prompt(
        name="memory_review",
        description="Review whether completed work should be committed to durable memory.",
    )
    def memory_review(outcome: str = "") -> str:
        return (
            "Before ending substantial work, decide whether any result should survive future sessions. "
            "If yes, use memory_remember with reason, memory_source, scope_refs, and evidence refs when available. "
            "Inspect possible_duplicates before relying on a new unstructured knowledge item as distinct. "
            f"Outcome to review: {outcome}"
        )
