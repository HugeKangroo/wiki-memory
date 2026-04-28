# Agent Memory MCP Usage

This document defines how agents should use the Memory Substrate MCP tools. It is a protocol for agent behavior, not just a set of examples.

For cross-project rules, read [Memory Policy](memory-policy.md). This document is the caller workflow and examples layer; it should not duplicate every policy rule.

MCP hosts can also read the built-in resources:

- `memory://policy`
- `memory://agent-playbook`
- `memory://mcp-api-summary`

The server provides two prompts, `memory_task_start` and `memory_review`, for hosts that support MCP prompts.

## Current Data Model

The canonical data is a structured object store under `memory/objects/`. Markdown files under `memory/projections/` are derived views and are not the source of truth.

Current canonical object types:

- `source`: durable evidence origin, such as a file, repository, web page, PDF, or conversation.
- `source.segments`: citable evidence slices inside a source, each with a locator, excerpt, and hash.
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

## Required Agent Workflow

At task start:

1. Call `memory_query` with `mode: "context"` or `mode: "search"` to load existing context.
2. Use the returned context to avoid repeating known work and to identify relevant memory IDs.
3. If the result is empty or weak, expand the query terms and retry before concluding that memory has no useful answer.

When new material appears:

1. Call `memory_ingest` to capture the material as evidence.
2. Analyze the ingested evidence outside ingest.
3. Decide whether anything should become durable memory.
4. Before writing, call `memory_query` again to check related context, duplicates, and conflicts.
5. Call `memory_remember` only for information that should survive future sessions.
6. Inspect `possible_duplicates` on knowledge write responses before treating a new unstructured item as distinct.

Before ending substantial work:

1. Perform a memory review.
2. If there is durable information, call `memory_remember`.
3. If there is nothing durable, state that nothing should be remembered and why.

## Query Retry Discipline

Current search behavior includes deterministic query normalization, but it is still primarily lexical with graph-backed retrieval when configured. Agents should compensate with query planning:

- map user vocabulary to memory object types, kinds, statuses, and scopes
- expand common domain terms before retrying
- search for both natural-language terms and canonical memory terms
- prefer `context` when answering a task and `search` when checking existence

Examples:

- `待办项`, `todo`, `task`, `任务` -> search `work_item` records and open/pending statuses
- `决策`, `decision` -> search decision-like knowledge
- `偏好`, `preference` -> search preference knowledge
- `流程`, `procedure` -> search procedure knowledge
- `证据`, `source`, `evidence` -> search sources and evidence-linked knowledge

Do not answer "there is no memory" from a single failed keyword query when a reasonable expansion exists.

## Duplicate Handling

Structured fact-like knowledge has hard duplicate and conflict checks. If the same structured claim already exists in an overlapping scope, `memory_remember` may reject it. If the same subject and predicate conflict in the same scope, the new knowledge may become `contested`.

Unstructured title/summary-only knowledge uses soft duplicate detection. `memory_remember` returns `possible_duplicates` with scores and reasons, but it does not reject the write just because the text is similar. Agents should treat those candidates as review material:

- if it is the same memory, avoid relying on the new item as a separate fact
- if it is a refinement, consider superseding or updating in a later maintenance step
- if it is genuinely distinct, keep it and preserve the scope/reason that explains why

`memory_maintain report` also surfaces soft duplicate candidates. `memory_maintain merge_duplicates` does not merge them automatically; use explicit review, supersession, or contesting once the relationship is clear.

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
