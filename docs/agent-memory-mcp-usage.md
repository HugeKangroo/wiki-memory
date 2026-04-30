# Agent Memory MCP Usage

This document defines how agents should use the Memory Substrate MCP tools. It is a protocol for agent behavior, not just a set of examples.

For cross-project rules, read [Memory Policy](memory-policy.md). This document is the caller workflow and examples layer; it should not duplicate every policy rule.

MCP hosts can also read the built-in resources:

- `memory://policy`
- `memory://agent-playbook`
- `memory://mcp-api-summary`

The server provides two prompts, `memory_task_start` and `memory_review`, for hosts that support MCP prompts.

Agents must not pass a memory root in tool calls. The MCP server binds to one root per server instance, defaulting to `~/memory-substrate` unless the host sets `MEMORY_SUBSTRATE_ROOT`.

## Current Data Model

The canonical data is a structured object store under `memory/objects/`. Markdown files under `memory/projections/` are derived views and are not the source of truth.

Current canonical object types:

- `source`: durable evidence origin, such as a file, repository, web page, PDF, or conversation.
- `source.segments`: citable evidence slices inside a source, each with a locator, excerpt, hash, line range, and optional heading breadcrumbs.
- `node`: reusable long-lived entity, such as a project, person, file, concept, tool, preference, or decision anchor.
- `knowledge`: a claim the system believes or is evaluating. It carries subject refs, evidence refs, optional structured payload, status, confidence, and validity windows.
- `activity`: completed work or analysis, linked to nodes, work items, sources, produced objects, and artifacts.
- `work_item`: actionable task or issue, linked to owners, nodes, knowledge, sources, dependencies, and children.
- `patch`: governed memory mutation record.
- `audit_event`: accountability record for writes and lifecycle changes.

Derived data:

- `memory/indexes/`: query state derived from canonical objects.
- `memory/projections/wiki/`: Obsidian-friendly reading projection.
- `memory/projections/debug/`: object-level markdown mirror for traceability.
- `memory/projections/doxygen/`: optional API documentation projection.

The current schema is already suitable for an early memory substrate. It should not be replaced by Markdown or a raw graph database model. The next upgrade should harden the memory write contract before changing storage backends.

The memory server should not require agents to configure a separate LLM API key. Agents or humans may perform analysis and extraction, then call `memory_remember` with structured candidates. Backends such as Kuzu, Neo4j, Graphiti, Cognee, or LlamaIndex must remain behind Memory Substrate contracts.

Graph backend usage is explicit. Agents should omit `options.graph_backend` unless they need to override the root default for a specific call. Configure a root default with `memory_maintain` `configure` when the memory root should consistently sync, query, report, and reindex through a graph backend. Allowed values are `file` and `kuzu`.

When remembering unstructured title/summary-only knowledge, omit `payload` or pass `{}`. When remembering structured knowledge, prefer stable object ids in `payload.subject` and `payload.object` when the claim is a relationship. For example, `{"subject": "node:memory", "predicate": "uses", "object": "node:kuzu"}` becomes a graph edge `node:memory -uses-> node:kuzu` while the knowledge object remains the provenance-bearing claim.

Governed `memory_remember` create operations require:

- `reason`: why the memory should survive future sessions.
- `memory_source`: one of `user_declared`, `human_curated`, `agent_inferred`, `system_generated`, or `imported`.
- `scope_refs`: at least one durable scope id, such as a project, user, repo, or topic scope.

Governed knowledge writes normalize `agent_inferred` active claims to `candidate`, reject exact duplicate structured claims with the same `kind`, overlapping `scope_refs`, subject, predicate, and value/object, store same-kind/same-scope subject/predicate conflicts as `contested`, and reject `evidence_refs` that do not point to an existing source segment or whose optional `locator`/`hash` does not match that segment.

Recommended near-term data upgrades:

- Add deterministic query normalization for domain terms such as `待办项`, `todo`, `task`, and `work_item`.
- Add stronger semantic matching for unstructured title/summary-only knowledge.
- Keep Graphiti/Neo4j behind backend interfaces when graph scale, temporal relation queries, or hybrid retrieval become core requirements.

## Tool Responsibilities

Use the four MCP tools with strict boundaries:

- `memory_query`: load existing context, search related memory, expand objects, and check duplicates or conflicts.
- `memory_ingest`: capture source material as evidence. It should not decide what deserves durable memory.
- `memory_remember`: commit durable memory after the user or agent can justify it.
- `memory_maintain`: validate, report, repair, reindex, and run lifecycle consolidation.

For repository ingest, pass `exclude_patterns` for project-local or agent-local state such as `.codex` and `.worktrees`. Common generated directories such as `.git`, `node_modules`, `dist`, `build`, and Rust/Tauri `target` are skipped by default.

Repository ingest stores a lightweight repo map, not full source as canonical memory. Repo sources include `payload.code_index` with path, language, line count, and content hash; `payload.code_modules` with parsed module paths, classes, functions, imports, symbols, and line locators when available; and `payload.doc_index` / `payload.document_sections` for Markdown design docs, READMEs, and other repository documentation. Markdown/document source segments follow `document_chunker.v1`: frontmatter, heading sections, fenced code, tables, line ranges, and heading breadcrumbs are preserved in bounded chunks. Source segments may include short excerpts for evidence, but agents should use the returned paths and line ranges to read local source files directly when they need full code or full documents.

Source objects include `metadata.adapter` and `metadata.freshness`. Use these fields to understand how evidence was captured: adapter version, mode, declared transformations, privacy class, origin classification, currentness, and fingerprint. Do not treat adapter metadata as extracted durable knowledge; use `memory_remember` for durable conclusions.

Repository ingest runs a preflight before writing memory. If it detects local or agent state that was not excluded, it excludes those entries from the current scan, writes the clean repo view, and returns `status: "completed_with_pending_decisions"`, `requires_decision: true`, `pending_decisions`, `excluded_by_preflight`, `warnings`, and `suggested_exclude_patterns`. Treat this as a decision point for the pending entries, not as a failed ingest. Use `options.force: true` only when those entries are intentionally part of the evidence.

If a repo was already ingested and its computed fingerprint is unchanged, repository ingest returns `status: "noop"` and `applied_operations: 0` without writing patch, audit, or projection data. Treat `noop` as a clean result, not a failure.

## Required Agent Workflow

At task start:

1. Call `memory_query` with `mode: "context"` or `mode: "search"` to load existing context.
2. Use the returned context to avoid repeating known work and to identify relevant memory IDs.
3. If the result is empty or weak, expand the query terms and retry before concluding that memory has no useful answer.

When new material appears:

1. Call `memory_ingest` to capture the material as evidence.
2. Inspect returned `status`, `warnings`, and `pending_decisions`. If `status` is `completed_with_pending_decisions`, use the clean ingested source normally and decide separately whether any pending entry deserves a later explicit `options.force: true` ingest.
3. If `status` is `noop`, use the existing `source_id` and avoid repeating ingest.
4. Inspect `memory_suggestions.concept_candidates`. These are repeated source terms or headings that may deserve a durable `kind: "concept"` memory after review.
5. Analyze the ingested evidence outside ingest.
6. Decide whether anything should become durable memory.
7. Before writing, call `memory_query` again to check related context, duplicates, and conflicts.
8. Call `memory_remember` only for information that should survive future sessions.
9. Inspect `possible_duplicates` on knowledge write responses before treating a new unstructured item as distinct.

Before ending substantial work:

1. Perform a memory review.
2. If there is durable information, call `memory_remember`.
3. If there is nothing durable, state that nothing should be remembered and why.

## Query Retry Discipline

Current search behavior includes deterministic query normalization, lexical matching, optional graph-backed retrieval, and optional semantic retrieval when the root is configured for it. Agents should still use query planning:

- map user vocabulary to memory object types, kinds, statuses, and scopes
- expand common domain terms before retrying
- pass the actual user task or question, not the full system prompt, scratchpad, or transcript
- search for both natural-language terms and canonical memory terms
- prefer `context` when answering a task and `search` when checking existence
- for codebase questions, query repo/module/path/symbol terms first, then use compact `page` on the repo source to inspect bounded `code_index`, `code_modules`, `doc_index`, and `document_sections`; read local files by locator when needed
- use `options.detail: "full"` on `memory_query page` only when compact locators are insufficient, because full repo pages can be large
- query options are mode-specific: `detail` is only for `page`; `include_segments` and `snippet_chars` are only for `page` and `expand`

Examples:

- `待办项`, `todo`, `task`, `任务` -> search `work_item` records and open/pending statuses
- `决策`, `decision` -> search decision-like knowledge
- `偏好`, `preference` -> search preference knowledge
- `流程`, `procedure` -> search procedure knowledge
- `证据`, `source`, `evidence` -> search sources and evidence-linked knowledge

Do not answer "there is no memory" from a single failed keyword query when a reasonable expansion exists.

`memory_query search` and `memory_query context` sanitize unusually long query text before retrieval and return `query_sanitizer` diagnostics. Treat `was_sanitized: true` as a hint to tighten future calls; the effective `query` or `task` in the response is what retrieval used.

`memory_query context` also returns `context_tiers` and `context_budget`. To keep context small, `items` carries compact item details while `decisions`, `procedures`, and `open_work` are id directories back into `items`. Use tier directories for planning, then use `deep_search_hints`, `expand`, or `page` only when the compact context is insufficient.

When semantic retrieval is configured, `memory_query search` fuses lexical or graph hits with semantic hits using Reciprocal Rank Fusion. Prefer items found by multiple streams, but inspect `retrieval_sources`, `retrieval_ranks`, `matched_chunks`, and source locators before treating a hit as evidence. Semantic source hits can point to the matched chunk; use `page`, `expand`, or local file reads to inspect the surrounding context when the answer depends on exact wording.

## Duplicate Handling

Structured fact-like knowledge has hard duplicate and conflict checks. If the same structured claim already exists in an overlapping scope, `memory_remember` may reject it. If the same subject and predicate conflict in the same scope, the new knowledge may become `contested`.

Unstructured title/summary-only knowledge uses soft duplicate detection. `memory_remember` returns `possible_duplicates` with scores and reasons, but it does not reject the write just because the text is similar. Agents should treat those candidates as review material:

- if it is the same memory, avoid relying on the new item as a separate fact
- if it is a refinement, consider superseding or updating in a later maintenance step
- if it is genuinely distinct, keep it and preserve the scope/reason that explains why

`memory_maintain report` also surfaces soft duplicate candidates. `memory_maintain merge_duplicates` does not merge them automatically; use explicit review, supersession, or contesting once the relationship is clear.

`memory_maintain report` also surfaces advisory `concept_candidates`. These are not canonical memory. If a candidate is useful, review the cited evidence, choose a scope, then call `memory_remember` with `kind: "concept"`, `status: "candidate"`, a bounded summary, and evidence refs. Skip candidates that are merely project names, generic headings, or temporary task vocabulary.

When a graph backend is configured, `memory_maintain report` also returns graph-health insights. Treat `isolated_nodes`, `sparse_clusters`, `bridge_nodes`, and `weakly_connected_scopes` as maintenance signals: they suggest where memory may need typed relations, consolidation, evidence review, or scope cleanup, not automatic mutation instructions.

`memory_maintain report` also returns advisory `fact_check_issues` for similar entity names, stale active facts, and structured relationship mismatches. These are review cues only. Use the listed `next_actions` to decide whether to verify, contest, supersede, clarify scope, or keep both records.

`memory_maintain repair` may return `derived_indexes` diagnostics when semantic or graph backends are configured. Treat missing or stale derived-index counts as a reason to run `memory_maintain reindex` with explicit apply/configuration controls, not as canonical data loss.

## Memory Review Gate

Agents should run this review before calling `memory_remember`:

```json
{
  "should_remember": true,
  "reason": "This decision changes future implementation work.",
  "source": "agent_inferred",
  "scope": {
    "project": "memory-substrate",
    "topic": "agent memory protocol"
  },
  "evidence_refs": [
    {
      "source_id": "src:example",
      "segment_id": "seg:example"
    }
  ],
  "items": [
    {
      "type": "knowledge",
      "status": "candidate",
      "confidence": 0.76,
      "title": "Agents must review memory before ending substantial work"
    }
  ]
}
```

Use `should_remember: true` when at least one item is durable and future-useful.

Use `should_remember: false` when the information is transient, duplicated, low confidence, unsupported, or not useful beyond the current turn.

## What Should Be Remembered

Remember information when it is likely to be reused and can be grounded:

- Explicit user instructions, preferences, or principles.
- Architecture decisions and their reasons.
- Stable project facts.
- Reusable domain knowledge.
- Important task outcomes.
- Work items that should persist beyond the current interaction.
- Evidence-backed conclusions that affect future work.

Do not remember:

- One-off reasoning steps.
- Generic summaries of the current answer.
- Transient status updates.
- Unsupported guesses, unless they are stored as `candidate` and clearly marked as inferred.
- Duplicate facts already present in memory.
- Sensitive or private data unless the user explicitly requested durable retention and the host policy allows it.

## Status Rules

Use status deliberately:

- `candidate`: plausible but not fully confirmed, agent-inferred, weakly evidenced, or pending review.
- `active`: confirmed, durable, and evidence-backed. Active knowledge should have evidence refs unless it is explicit user-declared memory.
- `contested`: conflicting evidence exists or the claim is disputed.
- `superseded`: replaced by newer knowledge.
- `stale`: likely outdated due to age or changed context.
- `archived`: retained for history but not used as current context.

## Call Examples

Task-start query:

```json
{
  "args": {
    "mode": "context",
    "input_data": {
      "task": "Design how agents should use memory MCP",
      "scope": {
        "object_types": ["knowledge", "activity", "work_item"]
      }
    },
    "options": {
      "max_items": 10
    }
  }
}
```

Ingest a conversation as evidence:

```json
{
  "args": {
    "mode": "conversation",
    "input_data": {
      "title": "Memory protocol design discussion",
      "messages": [
        {
          "role": "user",
          "content": "How can we make agents follow the memory recording logic?"
        },
        {
          "role": "assistant",
          "content": "Use protocol, validation, and lifecycle checks instead of relying on agent discipline."
        }
      ],
      "origin": {
        "host": "codex",
        "project": "memory-substrate"
      }
    }
  }
}
```

Remember a durable knowledge item:

```json
{
  "args": {
    "mode": "knowledge",
    "input_data": {
      "kind": "agent_memory_policy",
      "title": "Remember is the governed durable write path",
      "summary": "Agents may propose memory, but memory_remember governs durable writes and should validate evidence, scope, confidence, and lifecycle status.",
      "reason": "Prevents agent mistakes from polluting durable memory.",
      "memory_source": "agent_inferred",
      "scope_refs": ["scope:memory-substrate"],
      "actor": {
        "type": "agent",
        "id": "codex"
      },
      "evidence_refs": [
        {
          "source_id": "src:example",
          "segment_id": "seg:example"
        }
      ],
      "payload": {
        "subject": "memory_remember",
        "predicate": "role",
        "value": "governed durable write path",
        "metadata": {}
      },
      "status": "candidate",
      "confidence": 0.8
    }
  }
}
```

Run a read-only maintenance report:

```json
{
  "args": {
    "mode": "report",
    "input_data": {
      "min_confidence": 0.75,
      "min_evidence": 1
    }
  }
}
```

Configure a default graph backend for the memory root:

```json
{
  "args": {
    "mode": "configure",
    "input_data": {
      "graph_backend": "file"
    },
    "options": {
      "apply": true
    }
  }
}
```

After configuration, omit `options.graph_backend` for normal `memory_remember`, `memory_query`, `memory_maintain report`, and `memory_maintain reindex` calls. Use per-call `options.graph_backend` only when intentionally overriding the root default.

Semantic retrieval is configured the same way, but it only affects query/reindex paths. Configure it with `memory_maintain configure` and `semantic_backend: "lancedb"`, then run `memory_maintain reindex` to build `memory/indexes/semantic_lancedb` from canonical objects. When graph and semantic backends are both configured, `memory_query search` merges their results. Agents may use per-call `options.semantic_backend` when intentionally testing or overriding the root default.

Semantic model loading is lazy. Starting the MCP server only registers tools; the first semantic `reindex` or `search` tries cached BGE-M3 files first, falls back to download when missing, warms the embedding model cache in that MCP process, and later calls with the same model reuse it. Hosts should set `HF_HUB_OFFLINE=1` only when they intentionally want hard offline mode.

Run a graph-aware maintenance report:

```json
{
  "args": {
    "mode": "report",
    "input_data": {},
    "options": {
      "graph_backend": "kuzu"
    }
  }
}
```

Rebuild a local Kuzu graph index from canonical memory objects:

```json
{
  "args": {
    "mode": "reindex",
    "input_data": {},
    "options": {
      "graph_backend": "kuzu"
    }
  }
}
```

Read context, search results, or a graph neighborhood from a selected backend:

```json
{
  "args": {
    "mode": "graph",
    "input_data": {
      "id": "know:example"
    },
    "options": {
      "graph_backend": "kuzu",
      "max_items": 20
    }
  }
}
```

Run mutating maintenance only with explicit apply:

```json
{
  "args": {
    "mode": "cycle",
    "input_data": {
      "min_confidence": 0.75,
      "min_evidence": 1
    },
    "options": {
      "apply": true
    }
  }
}
```

## Failure Handling

If `memory_remember` is rejected:

1. Do not bypass it by editing projection files.
2. Query for related context.
3. Ingest missing evidence if needed.
4. Lower the status to `candidate` when evidence is weak.
5. Mark conflicts as `contested` instead of overwriting older memory.

If an agent is unsure whether to remember something, prefer no write or `candidate` with a clear reason. Durable memory should optimize for future usefulness and traceability, not maximum recall of every conversation detail.
