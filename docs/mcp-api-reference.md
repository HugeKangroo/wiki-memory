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

The stored repo source is a lightweight repo map. `payload.code_index` records source paths, languages, line counts, and hashes. `payload.code_modules` records parsed module paths, imports, classes, functions, symbols, and line ranges when the parser can extract them. `payload.doc_index` and `payload.document_sections` record Markdown documentation paths, section headings, heading breadcrumbs, short excerpts, chunk kinds, and line locators. It intentionally does not make full source bodies or full documents the canonical data; use `memory_query page` or `expand` to find locators, then read the local files directly for full code or full documents.

Markdown and text source ingest use the shared `document_chunker.v1` contract. Markdown chunks preserve frontmatter as a separate boundary, split on headings outside code fences, keep tables and fenced code inside the surrounding chunk, record `line_start` / `line_end`, and include `heading_path` breadcrumbs in segment locators when present. Oversized sections are split with small line overlap so semantic chunks and evidence segments can remain bounded while still carrying local context.

Ingested sources include adapter metadata under `source.metadata.adapter` and freshness diagnostics under `source.metadata.freshness`. Adapter metadata includes:

- `name`
- `version`
- `mode`
- `supported_modes`
- `declared_transformations`
- `default_privacy_class`
- `origin_classification`

Freshness diagnostics include `checked_at`, `is_current`, and the source `fingerprint` captured during ingest. These fields describe how evidence was captured; they do not turn adapters or derived indexes into canonical memory.

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

Ingest responses include advisory `memory_suggestions`. These suggestions are derived from the current source and are not canonical memory. `concept_candidates` indicate repeated headings or technical terms that may deserve a later `memory_remember` write after agent review:

```json
{
  "memory_suggestions": {
    "concept_candidates": [
      {
        "kind": "concept_candidate",
        "candidate_type": "concept",
        "title": "Context Pack",
        "score": 0.75,
        "occurrences": 2,
        "ranking_signals": {
          "bonuses": ["durable_memory_candidate"],
          "penalties": [],
          "score_adjustment": 0.08
        },
        "evidence_refs": [{"source_id": "src:...", "segment_id": "..."}],
        "suggested_memory": {
          "mode": "knowledge",
          "kind": "concept",
          "status": "candidate",
          "input_data": {
            "kind": "concept",
            "title": "Context Pack",
            "summary": "Candidate concept. Review evidence and replace this summary before writing.",
            "reason": "Agent reviewed candidate concept 'Context Pack' from repeated source evidence and judged it durable.",
            "memory_source": "agent_inferred",
            "scope_refs": ["node:..."],
            "evidence_refs": [{"source_id": "src:...", "segment_id": "..."}],
            "status": "candidate"
          },
          "editable_fields": ["summary", "reason", "scope_refs", "payload"]
        },
        "review_guidance": {
          "required_checks": [
            "read_evidence_refs",
            "query_existing_memory_for_title_and_synonyms",
            "choose_scope_refs_before_write",
            "rewrite_summary_from_evidence"
          ]
        },
        "next_actions": ["review_and_remember", "attach_evidence_refs", "skip_if_project_specific_noise"]
      }
    ],
    "candidate_diagnostics": {
      "skipped": [
        {"title": "Current Todo", "reason": "document_artifact", "occurrences": 1}
      ],
      "counts": {"skipped": 1, "returned": 1}
    },
    "next_actions": [
      "review_concept_candidates",
      "run_memory_maintain_report_for_cross_source_candidates",
      "call_memory_remember_if_durable"
    ]
  }
}
```

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

`page` returns compact objects by default. Compact source pages include bounded index lists, locators, and short snippets rather than full payloads and all source segments. Request full objects only when needed:

```json
{
  "args": {
    "mode": "page",
    "input_data": {
      "id": "src:..."
    },
    "options": {
      "detail": "full"
    }
  }
}
```

Compact query options:

- `page.max_items`: list cap for each compact page index list.
- `page.include_segments`: include bounded source segment snippets; default is `false`.
- `page.snippet_chars`: maximum compact excerpt length.
- `expand.include_segments`: include bounded source segment snippets; default is `true`.
- `expand.snippet_chars`: maximum expanded segment excerpt length.

Query options are mode-specific. For example, `detail` is accepted only by `page`, and `snippet_chars` is accepted only by `page` and `expand`.

`context` returns work-ready sections and tier diagnostics:

- `context_tiers.policy`: reserved for always-on policy snippets.
- `context_tiers.active_task`: effective task and scope.
- `context_tiers.decisions`, `procedures`, `evidence`, and `open_work`: compact directory metadata with `field`, `count`, and `ids`.
- `context_tiers.deep_search_hints`: bounded follow-up `memory_query expand` hints.
- `context_budget`: compact budget metadata such as `max_items`, `returned_items`, and `detail`.

To reduce context consumption, `items` is the only default field carrying compact item summaries. `decisions`, `procedures`, and `open_work` are section references with ids that point back into `items`; use `expand` or `page` only when more detail is required.

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

`search` uses deterministic query normalization before matching. It can expand domain terms such as `待办项`, `todo`, `task`, and `work_item`, and returns diagnostic fields:

- `normalized_terms`
- `applied_filters`
- `inferred_filters`
- `suggested_retry_terms`
- `semantic_backend`
- `query_sanitizer`

Lexical matching keeps the full phrase as a strong signal and also checks tokenized terms, object ids, metadata, source locators, and CJK bigrams. Title matches score higher than summaries, payloads, source segments, and metadata.

`search` and `context` sanitize unusually long query text before planning terms. This protects retrieval when an agent accidentally passes a full prompt, scratchpad, or system instructions instead of the actual question. The response keeps the effective `query` or `task` and returns `query_sanitizer` diagnostics:

- `was_sanitized`
- `method`: `passthrough`, `labeled_line`, `question_sentence`, or `tail_truncation`
- `original_length`
- `clean_length`

When a semantic backend is configured, `search` fuses lexical or graph results with semantic hits using Reciprocal Rank Fusion. Returned items may include:

- `retrieval_sources`: streams that found the item, such as `lexical`, `graph`, or `semantic`.
- `retrieval_ranks`: rank per retrieval stream.
- `rank_score`: fused rank score used for final ordering.
- `lexical_score` and `semantic_score`: stream-local scores for diagnostics.
- `matched_chunks`: semantic source chunks with `chunk_id`, `segment_id`, `locator`, `excerpt`, `hash`, `distance`, and `semantic_score` when the hit maps to a stored source segment.

Callers should still retry with expanded terms when a result is weak, because semantic retrieval improves recall but does not replace scope, status, evidence, or graph-aware filtering.

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
- `resolve_duplicates`
- `archive_source`
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

`resolve_duplicates`:

```json
{
  "args": {
    "mode": "resolve_duplicates",
    "input_data": {
      "outcome": "supersede",
      "knowledge_ids": ["know:older", "know:newer"],
      "canonical_knowledge_id": "know:newer",
      "reason": "Reviewed the soft duplicate candidate and selected the newer scoped decision."
    },
    "options": {
      "apply": true
    }
  }
}
```

Use `outcome: "keep_both"` when the items are distinct but need clarified summaries or scopes:

```json
{
  "args": {
    "mode": "resolve_duplicates",
    "input_data": {
      "outcome": "keep_both",
      "knowledge_ids": ["know:a", "know:b"],
      "reason": "Same phrasing, but different project scopes.",
      "updates": [
        {"knowledge_id": "know:a", "scope_refs": ["scope:project-a"]},
        {"knowledge_id": "know:b", "scope_refs": ["scope:project-b"]}
      ]
    },
    "options": {
      "apply": true
    }
  }
}
```

Use `outcome: "contest"` when the relationship is unclear or conflicting and the items should not be treated as clean active memories.

`archive_source`:

```json
{
  "args": {
    "mode": "archive_source",
    "input_data": {
      "source_id": "src:retired",
      "reason": "Retired because the import captured local agent state."
    },
    "options": {
      "apply": true
    }
  }
}
```

`archive_source` marks the source archived, marks knowledge as `stale` when all of its evidence refs point to that source, and reports mixed-evidence knowledge in `partially_affected_knowledge_ids` without automatically downgrading it.

`repair` returns safe missing-reference repair results. When semantic or graph backends are configured, it also returns `derived_indexes` diagnostics so callers can detect stale indexes before choosing a mutating `reindex`.

`report` returns promotable candidates, low-evidence candidates, stale candidates, deterministic duplicate groups, unstructured soft duplicate candidates, concept candidates, candidate diagnostics, fact-check issues, counts, and graph health when a graph backend is configured. Concept candidates are advisory repeated terms or headings that may deserve a `memory_remember` write after review; they are not persisted automatically. Each candidate includes `candidate_type`, `ranking_signals`, `review_guidance`, and a `suggested_memory.input_data` skeleton with inferred `scope_refs`, evidence refs, `reason`, `memory_source`, `status`, and confidence. Agents must review evidence and rewrite the summary before using it. Candidate diagnostics list skipped terms with reasons such as `document_artifact`, `format_marker`, `action_phrase`, `shortcut_marker`, `generic_term`, `too_long`, or `weak_term`. Fact-check issues are advisory and currently include:

- `similar_entity_name`: multiple nodes normalize to the same name key.
- `stale_fact`: active facts past their validity window.
- `relationship_mismatch`: structured facts with the same subject and predicate but different value/object assertions.

Graph health includes backend/canonical count comparisons, missing backend counts, stub node counts, and deterministic `insights`:

- `isolated_nodes`: graph records with no relations.
- `sparse_clusters`: low-density connected components that may need more typed relations or consolidation.
- `bridge_nodes`: high-leverage records whose removal disconnects an existing component.
- `weakly_connected_scopes`: scopes with multiple records but too few internal relations.

Soft duplicate report entries use this shape:

```json
{
  "object_ids": ["know:...", "know:..."],
  "score": 0.72,
  "reasons": ["title_overlap", "summary_overlap", "same_kind"],
  "review_guidance": {
    "required_checks": [
      "read_both_knowledge_items",
      "compare_scope_refs",
      "compare_evidence_refs",
      "decide_whether_meaning_is_same_distinct_or_conflicting"
    ],
    "outcomes": [
      {"action": "supersede", "tool": "memory_maintain", "mode": "resolve_duplicates"},
      {"action": "keep_both", "tool": "memory_maintain", "mode": "resolve_duplicates"},
      {"action": "contest", "tool": "memory_maintain", "mode": "resolve_duplicates"}
    ]
  },
  "suggested_resolution": {
    "tool": "memory_maintain",
    "mode": "resolve_duplicates",
    "input_data": {
      "outcome": "supersede",
      "knowledge_ids": ["know:...", "know:..."],
      "canonical_knowledge_id": "know:...",
      "reason": "Reviewed soft duplicate candidate and selected the canonical memory."
    },
    "options": {"apply": true}
  },
  "next_actions": [
    "review_duplicate_pair",
    "choose_supersede_keep_both_or_contest",
    "call_memory_maintain_resolve_duplicates_if_actionable"
  ]
}
```

`merge_duplicates` intentionally merges only deterministic structured duplicates. It does not automatically merge soft duplicate candidates. `resolve_duplicates` only accepts ids that are still reported as current soft duplicate candidates, requires a non-empty reason, and records the chosen outcome through normal patch/audit/projection updates.

## Error Behavior

- unsupported modes return a clear `ValueError`
- missing required fields fail at MCP argument validation
- unexpected extra fields inside `args` fail with `Extra inputs are not permitted`
- missing required tool arguments fail through MCP SDK validation
- `memory_maintain` no-op paths return success payloads with zero counts
- domain object lookup failures keep the missing object id in the error message
