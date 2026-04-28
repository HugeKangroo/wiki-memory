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
    "root": "/absolute/path/to/memory-substrate",
    "mode": "...",
    "input_data": {},
    "options": {}
  }
}
```

Rules:

- `args` is required.
- `root` is optional and defaults to `~/memory-substrate`.
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
      "path": "/absolute/path/to/repo"
    }
  }
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
      "graph_backend": "file"
    },
    "options": {
      "apply": true
    }
  }
}
```

Supported `graph_backend` values are `file` and `kuzu`.

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
      "apply": true
    }
  }
}
```

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
