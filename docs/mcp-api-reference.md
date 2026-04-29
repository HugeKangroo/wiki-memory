# MCP API Reference

The MCP server exposes four tools:

- `memory_ingest`
- `memory_query`
- `memory_remember`
- `memory_maintain`

The server uses strict argument validation. Unexpected fields inside `args` fail instead of being accepted silently.

## Agent Resources And Prompts

The server also exposes MCP resources so hosts can read policy without relying on repository-local `AGENTS.md` files:

- `memory://policy`
- `memory://agent-playbook`
- `memory://mcp-api-summary`

It also exposes prompts:

- `memory_task_start`: guide callers to query memory and retry with query expansion before starting work.
- `memory_review`: guide callers through the end-of-task memory review and `possible_duplicates` handling.

## Call Envelope

Every tool call uses this shape:

```json
{
  "args": {
    "mode": "...",
    "input_data": {},
    "options": {}
  }
}
```

Rules:

- `args` is required.
- `root` is not accepted in tool calls. The server root is configured outside the tool schema, defaulting to `~/memory-substrate` or `MEMORY_SUBSTRATE_ROOT`.
- `mode` is required.
- `input_data` is required even when empty.
- `options` is optional.
- mutating `memory_maintain` modes require `options.apply=true`.

## `memory_ingest`

Allowed modes:

- `repo`
- `file`
- `markdown`
- `web`
- `pdf`
- `conversation`

`repo`:

```json
{
  "args": {
    "mode": "repo",
    "input_data": {
      "path": "/absolute/path/to/repo",
      "exclude_patterns": [".codex", ".worktrees"]
    }
  }
}
```

`repo` ingest always skips common generated directories such as `.git`, `node_modules`, `dist`, `build`, and Rust/Tauri `target`. Agents can pass `include_patterns` and `exclude_patterns` for project-specific scope control. Patterns are matched against relative paths and basename values.

The stored repo source is a lightweight code map. `payload.code_index` records source paths, languages, line counts, and hashes. `payload.code_modules` records parsed module paths, imports, classes, functions, symbols, and line ranges when the parser can extract them. It intentionally does not make full source bodies the canonical data; use `memory_query page` or `expand` to find locators, then read the local files directly for full code.

Before writing memory, `repo` ingest runs a preflight for local or agent state such as `.codex`, `.claude`, `.cursor`, or `.worktrees`. If these entries are present and not excluded, the tool excludes them from the current scan, writes the clean repo view, and returns `status: "completed_with_pending_decisions"`. Agents should use the clean source normally and inspect `pending_decisions` separately.

```json
{
  "result_type": "repo_ingest_result",
  "status": "completed_with_pending_decisions",
  "requires_decision": true,
  "source_id": "src:...",
  "applied_operations": 24,
  "excluded_by_preflight": [".codex", ".worktrees"],
  "pending_decisions": [
    {
      "path": ".codex",
      "kind": "local_agent_state",
      "reason": "Repository contains local/agent state that may not belong in durable memory.",
      "suggested_action": "exclude"
    }
  ],
  "warnings": [
    "Repository contains local/agent state entries that may not belong in memory: .codex, .worktrees. They are excluded from the clean repo ingest unless options.force=true is used."
  ],
  "suggested_exclude_patterns": [".codex", ".worktrees"]
}
```

Use `options.force: true` only when the local or agent state is intentionally part of the evidence and should be written. In normal use, do not re-run just to exclude pending entries; the clean view has already been written.

When repo preflight passes but the computed repo fingerprint is unchanged from the active stored source, the tool returns `status: "noop"` without writing patch, audit, or projection data:

```json
{
  "result_type": "repo_ingest_result",
  "status": "noop",
  "requires_decision": false,
  "patch_id": null,
  "source_id": "src:...",
  "applied_operations": 0,
  "audit_event_ids": [],
  "projection_count": 0,
  "reason": "repo_fingerprint_unchanged"
}
```

`file` and `markdown`:

```json
{
  "args": {
    "mode": "markdown",
    "input_data": {
      "path": "/absolute/path/to/guide.md"
    }
  }
}
```

`web`:

```json
{
  "args": {
    "mode": "web",
    "input_data": {
      "url": "https://example.com/page"
    }
  }
}
```

`conversation`:

```json
{
  "args": {
    "mode": "conversation",
    "input_data": {
      "title": "Memory design discussion",
      "messages": [
        {
          "role": "user",
          "content": "Remember that project X uses Kuzu.",
          "name": "optional-speaker",
          "created_at": "2026-04-28T00:00:00+00:00",
          "metadata": {}
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

`memory_ingest` captures evidence. It does not decide what should become durable memory.

## `memory_query`

Allowed modes:

- `context`
- `expand`
- `page`
- `recent`
- `search`
- `graph`

`context`:

```json
{
  "args": {
    "mode": "context",
    "input_data": {
      "task": "inspect repository structure",
      "scope": {
        "object_types": ["knowledge", "activity", "work_item"]
      }
    },
    "options": {
      "max_items": 12
    }
  }
}
```

`search`:

```json
{
  "args": {
    "mode": "search",
    "input_data": {
      "query": "memory"
    },
    "options": {
      "max_items": 20,
      "filters": {
        "object_types": ["source", "knowledge"]
      }
    }
  }
}
```

Supported query filters:

- `object_type` or `object_types`
- `kind` or `kinds`
- `status` or `statuses`
- `node_id` or `node_ids`
- `source_id` or `source_ids`

`expand`:

```json
{
  "args": {
    "mode": "expand",
    "input_data": {
      "id": "node:..."
    },
    "options": {
      "max_items": 10
    }
  }
}
```

`page`:

```json
{
  "args": {
    "mode": "page",
    "input_data": {
      "id": "know:..."
    }
  }
}
```

`recent`:

```json
{
  "args": {
    "mode": "recent",
    "input_data": {},
    "options": {
      "max_items": 20,
      "filters": {
        "object_type": "knowledge",
        "status": "active"
      }
    }
  }
}
```

`graph`:

```json
{
  "args": {
    "mode": "graph",
    "input_data": {
      "id": "node:..."
    },
    "options": {
      "max_items": 20
    }
  }
}
```

`search` uses deterministic query normalization before lexical matching. It can expand domain terms such as `待办项`, `todo`, `task`, and `work_item`, and returns diagnostic fields:

- `normalized_terms`
- `applied_filters`
- `inferred_filters`
- `suggested_retry_terms`

This is not embedding or semantic vector search. Callers should still retry with expanded terms when a result is weak.

## `memory_remember`

Allowed modes:

- `activity`
- `knowledge`
- `work_item`
- `promote`
- `supersede`
- `contest`
- `batch`

Create modes require governance fields:

- `reason`
- `memory_source`
- `scope_refs`

Allowed `memory_source` values:

- `user_declared`
- `human_curated`
- `agent_inferred`
- `system_generated`
- `imported`

Governed `knowledge` writes:

- normalize `agent_inferred` active claims to `candidate`
- reject exact duplicate structured claims with the same `kind`, overlapping scopes, subject, predicate, and value/object
- mark same-kind, same-scope subject/predicate conflicts as `contested`
- return `possible_duplicates` for similar unstructured title/summary-only knowledge without rejecting the write
- reject evidence refs that point to missing sources or segments
- reject optional evidence `locator` or `hash` mismatches

For unstructured title/summary-only knowledge, omit `payload` or pass `{}`. For structured fact-like knowledge, include `payload.subject`, `payload.predicate`, and `payload.value` or `payload.object` when applicable.

`knowledge`:

```json
{
  "args": {
    "mode": "knowledge",
    "input_data": {
      "kind": "fact",
      "title": "Repo uses Python",
      "summary": "Primary language is Python.",
      "reason": "The detected language changes future repository work.",
      "memory_source": "agent_inferred",
      "scope_refs": ["scope:project"],
      "subject_refs": ["node:..."],
      "evidence_refs": [
        {
          "source_id": "src:...",
          "segment_id": "seg-1"
        }
      ],
      "payload": {
        "subject": "node:...",
        "predicate": "primary_language",
        "value": "python",
        "object": null,
        "metadata": {}
      },
      "confidence": 0.8
    }
  }
}
```

Evidence refs may include optional details:

```json
{
  "source_id": "src:...",
  "segment_id": "seg-1",
  "locator": {
    "kind": "line",
    "line": 12
  },
  "hash": "optional-segment-hash"
}
```

`activity`:

```json
{
  "args": {
    "mode": "activity",
    "input_data": {
      "kind": "research",
      "title": "Repo walkthrough",
      "summary": "Captured reusable findings.",
      "reason": "This walkthrough records reusable project context.",
      "memory_source": "agent_inferred",
      "scope_refs": ["scope:project"],
      "source_refs": ["src:..."],
      "related_node_refs": ["node:..."]
    }
  }
}
```

`knowledge` responses include `possible_duplicates`. This list is empty when no soft duplicate candidates are found. Each item includes:

- `object_id`
- `score`
- `reasons`
- `title`
- `kind`
- `status`

Soft duplicate detection is advisory. It is intended for agent or maintenance review and does not supersede structured duplicate/conflict rules.

`work_item`:

```json
{
  "args": {
    "mode": "work_item",
    "input_data": {
      "kind": "task",
      "title": "Review repo",
      "summary": "Track next step.",
      "reason": "This task should persist beyond the current session.",
      "memory_source": "user_declared",
      "scope_refs": ["scope:project"],
      "source_refs": ["src:..."]
    }
  }
}
```

`batch`:

```json
{
  "args": {
    "mode": "batch",
    "input_data": {
      "entries": [
        {
          "mode": "knowledge",
          "input_data": {
            "kind": "fact",
            "title": "Reusable fact",
            "summary": "Captured by the agent.",
            "reason": "This fact affects future work in this project.",
            "memory_source": "agent_inferred",
            "scope_refs": ["scope:project"],
            "payload": {
              "subject": "node:...",
              "predicate": "observed",
              "value": true,
              "object": null
            },
            "confidence": 0.7
          }
        }
      ]
    }
  }
}
```

Lifecycle writes:

```json
{
  "args": {
    "mode": "promote",
    "input_data": {
      "knowledge_id": "know:...",
      "reason": "verified"
    }
  }
}
```

```json
{
  "args": {
    "mode": "supersede",
    "input_data": {
      "old_knowledge_id": "know:old",
      "new_knowledge_id": "know:new",
      "reason": "new evidence"
    }
  }
}
```

```json
{
  "args": {
    "mode": "contest",
    "input_data": {
      "knowledge_id": "know:...",
      "reason": "conflicting source found"
    }
  }
}
```

## `memory_maintain`

Allowed structural modes:

- `configure`
- `structure`
- `audit`
- `reindex`
- `repair`

Allowed lifecycle modes:

- `promote_candidates`
- `merge_duplicates`
- `decay_stale`
- `cycle`
- `report`

Mutating modes require `options.apply=true`. `report` is read-only.

`configure`:

```json
{
  "args": {
    "mode": "configure",
    "input_data": {
      "graph_backend": "file",
      "semantic_backend": "lancedb"
    },
    "options": {
      "apply": true
    }
  }
}
```

Supported `graph_backend` values are `file` and `kuzu`.
Supported `semantic_backend` values are `lancedb`.
Both fields are optional, but at least one should be supplied for a meaningful configure call.

`structure`:

```json
{
  "args": {
    "mode": "structure",
    "input_data": {}
  }
}
```

`repair`:

```json
{
  "args": {
    "mode": "repair",
    "input_data": {},
    "options": {
      "apply": true
    }
  }
}
```

`reindex`:

```json
{
  "args": {
    "mode": "reindex",
    "input_data": {},
    "options": {
      "graph_backend": "kuzu",
      "semantic_backend": "lancedb"
    }
  }
}
```

`reindex` rebuilds derived projections. When configured or requested, it also rebuilds graph and semantic indexes from canonical memory objects.
When both graph and semantic backends are enabled, `memory_query search` merges graph/lexical results with semantic hits before ranking the final list.
Semantic model loading is lazy and process-local. MCP startup does not load BGE-M3; the first semantic `reindex` or `search` tries cached model files before downloading, then warms the provider cache for the running server process. Hosts may set `HF_HUB_OFFLINE=1` only for hard offline mode.

`report`:

```json
{
  "args": {
    "mode": "report",
    "input_data": {
      "min_confidence": 0.75,
      "min_evidence": 1,
      "reference_time": "2026-04-28T00:00:00+00:00",
      "stale_after_days": 30
    }
  }
}
```

`cycle`:

```json
{
  "args": {
    "mode": "cycle",
    "input_data": {
      "min_confidence": 0.75,
      "min_evidence": 1,
      "reference_time": "2026-04-28T00:00:00+00:00",
      "stale_after_days": 30
    },
    "options": {
      "apply": true
    }
  }
}
```

`report` returns promotable candidates, low-evidence candidates, stale candidates, deterministic duplicate groups, unstructured soft duplicate candidates, counts, and graph health when a graph backend is configured.

Soft duplicate report entries use this shape:

```json
{
  "object_ids": ["know:...", "know:..."],
  "score": 0.72,
  "reasons": ["title_overlap", "summary_overlap", "same_kind"]
}
```

`merge_duplicates` intentionally merges only deterministic structured duplicates. It does not automatically merge soft duplicate candidates.

## Error Behavior

- unsupported modes return a clear `ValueError`
- missing required fields fail at MCP argument validation
- unexpected extra fields inside `args` fail with `Extra inputs are not permitted`
- missing required tool arguments fail through MCP SDK validation
- `memory_maintain` no-op paths return success payloads with zero counts
- domain object lookup failures keep the missing object id in the error message
