# Wiki Memory MCP Server Design

## Goal

Turn the current phase-1 wiki-memory slice into a runnable stdio MCP server with five tools:

- `wiki_ingest`
- `wiki_query`
- `wiki_crystallize`
- `wiki_lint`
- `wiki_dream`

The server must be thin. Domain behavior stays in application and domain services. The MCP layer is responsible for registration, argument validation, transport-safe error handling, and stable tool contracts.

## Scope

This design includes:

- a runnable stdio MCP server
- one new dream application service
- one new MCP tool, `wiki_dream`
- startup and usage documentation
- tests for dream behavior and MCP registration/dispatch

This design does not include:

- new ingestion modes such as web or PDF
- vector search or graph retrieval
- UI
- multi-user coordination
- extra MCP tools such as health, object, or admin

## Tool Surface

The MCP server exposes exactly five tools.

### `wiki_ingest`

Purpose:
- ingest external content into the semantic store

Supported modes:
- `repo`

### `wiki_query`

Purpose:
- retrieve context and object views for agent work

Supported modes:
- `context`
- `expand`
- `page`
- `recent`
- `search`

### `wiki_crystallize`

Purpose:
- write reusable outputs back into the semantic store

Supported modes:
- `activity`
- `knowledge`
- `work_item`
- `promote`
- `supersede`

### `wiki_lint`

Purpose:
- inspect and repair structural health

Supported modes:
- `structure`
- `audit`
- `reindex`
- `repair`

### `wiki_dream`

Purpose:
- consolidate accumulated context into stronger long-lived knowledge

Supported modes:
- `promote_candidates`
- `merge_duplicates`
- `decay_stale`
- `cycle`

`cycle` runs the full dream sequence in deterministic order:

1. promote viable candidates
2. merge duplicate active/candidate knowledge
3. decay stale knowledge that has aged past threshold
4. rebuild markdown projection

## Dream Semantics

`dream` is not lint.

- `lint` checks and repairs structural integrity
- `dream` changes system cognition by consolidating, promoting, merging, and aging knowledge

This keeps health operations separate from consolidation operations.

### `promote_candidates`

Promote `knowledge.status == candidate` to `active` when all of these are true:

- confidence meets threshold
- evidence count meets threshold
- subject refs are present

Defaults:

- `min_confidence = 0.75`
- `min_evidence = 1`

Result:

- updates matching knowledge items to `active`
- sets `last_verified_at`
- records reason `dream_promote_candidates`

### `merge_duplicates`

Merge duplicate knowledge items when they refer to the same subject and predicate.

Phase-1.5 duplicate rule:

- `kind == fact`
- same first `subject_ref`
- same `payload.predicate`
- same normalized `payload.value`
- same normalized `payload.object`

Behavior:

- choose one canonical winner
  rule: prefer stronger lifecycle status, higher confidence, newer verification timestamp, then older creation time for stability
- merge evidence refs and keep unique refs
- keep strongest confidence
- mark loser as `superseded`
- set loser `valid_until`
- set reasons on both sides

This is intentionally conservative. It should only merge pairs that are clearly equivalent.

### `decay_stale`

Mark active or candidate knowledge as `stale` when:

- `last_verified_at` is older than configured age threshold
- item is not already `superseded` or `archived`

Default:

- `stale_after_days = 30`

Result:

- status becomes `stale`
- reason `dream_decay_stale`

### `cycle`

Run all three operations and return a structured summary:

- promoted count
- merged count
- decayed count
- patch ids
- audit event ids
- projection count

`cycle` should be safe to run repeatedly.

## Architecture

### MCP Layer

`src/wiki_memory/interfaces/mcp/server.py`

Responsibilities:

- instantiate the MCP server
- register the five tools
- expose one callable entrypoint for stdio transport
- validate required arguments before dispatch
- convert internal exceptions into MCP-safe tool errors

The server should not know domain rules.

### Application Layer

New file:

- `src/wiki_memory/application/dream/service.py`

Responsibilities:

- orchestrate dream operations
- build patches
- apply patches through `PatchApplier`
- rebuild projection after mutation
- return structured summaries

### Existing Tool Layer

`src/wiki_memory/interfaces/mcp/tools.py`

Responsibilities:

- remain the thin function layer used by the server
- add `wiki_dream(...)`
- keep consistent parameter shape with other tools

## Error Handling

Tool errors should be explicit and stable.

Rules:

- unsupported mode raises a clear `ValueError`
- missing required keys raises a clear `ValueError`
- object-not-found errors keep object id in message
- dream no-op returns success payload with zero counts, not an exception

## Testing

### Dream tests

Add focused tests for:

- candidate promotion above threshold
- duplicate merge chooses canonical winner and supersedes loser
- stale decay marks old knowledge stale
- cycle returns combined counts and leaves lint clean

### MCP interface tests

Add tests for:

- server registers all five tools
- each server tool dispatches to the corresponding tool function
- invalid mode returns stable failure

## Documentation

Add a short usage section describing:

- how to launch the stdio MCP server
- the five tool names
- the supported modes for each tool

## Acceptance Criteria

This task is complete when all of the following are true:

1. `server.py` is no longer a placeholder and can create a runnable stdio MCP server.
2. The server exposes exactly five tools: `wiki_ingest`, `wiki_query`, `wiki_crystallize`, `wiki_lint`, `wiki_dream`.
3. `wiki_dream` supports `promote_candidates`, `merge_duplicates`, `decay_stale`, and `cycle`.
4. Dream operations mutate the store only through `WikiPatch` and emit `AuditEvent`.
5. Dream mutations rebuild markdown projection.
6. Tests cover both dream behavior and MCP registration/dispatch.
7. Project docs include a launch command and tool overview.
