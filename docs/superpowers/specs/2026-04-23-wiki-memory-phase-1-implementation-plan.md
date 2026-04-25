# Wiki Memory Phase 1 Implementation Plan

## Goal

Implement the smallest end-to-end slice that validates the architecture without collapsing back into an ad hoc wiki tool.

Phase 1 must prove:

- the five-object semantic core works in code
- repo ingest can create stable objects
- query can build a useful context pack
- agent work can crystallize back into the system
- structural lint can validate basic integrity

## Scope

Build only these user-visible capabilities:

1. `wiki.ingest(mode=repo)`
2. `wiki.query(mode=context)`
3. `wiki.query(mode=expand)`
4. `wiki.crystallize(mode=activity)`
5. `wiki.crystallize(mode=knowledge)`
6. `wiki.crystallize(mode=work_item)`
7. `wiki.lint(mode=structure)`
8. `wiki.lint(mode=audit)`

Do not build in phase 1:

- PDF ingest
- web ingest
- vector search
- graph DB
- semantic lint
- UI
- multi-user behavior

## Implementation Strategy

Order matters. Build from semantic core outward.

### Step 1: Core schemas

Implement stable schemas for:

- `Source`
- `Node`
- `Knowledge`
- `Activity`
- `WorkItem`
- `EvidenceRef`
- `ContextPack`
- `WikiPatch`
- `AuditEvent`

Requirements:

- stable `id`
- explicit status fields
- timestamp fields
- typed payloads where required

### Step 2: Repositories

Implement file-backed repositories for:

- objects
- patches
- audit log

Storage rules:

- one object per JSON file
- append-only JSONL for audit
- no markdown as source of truth

### Step 3: Patch and audit

Implement:

- patch model
- patch applier
- audit append on mutation

Required patch operations in phase 1:

- `create_object`
- `update_object`
- `change_status`
- `archive_object`

### Step 4: Repo ingest

Implement repo ingest pipeline:

1. register repo source
2. normalize repo payload
3. extract candidate nodes
4. extract candidate knowledge
5. emit initial activity
6. apply patch

Phase 1 repo ingest may use lightweight heuristics first, with Tree-sitter integration kept behind the repo adapter boundary.

Tree-sitter use in phase 1:

- file language detection
- symbol extraction for supported languages
- basic API/module discovery

Do not overfit early extraction quality. The goal is stable structure, not perfect repo understanding.

### Step 5: Query context and expand

Implement two-step query flow:

- `context`: build a useful starting `ContextPack`
- `expand`: retrieve deeper content around selected objects or sources

Phase 1 query ranking inputs:

- related nodes
- active knowledge
- recent activities
- active work items
- source references

No embedding or graph dependency required in phase 1.

### Step 6: Crystallize

Implement write-back flow:

- record `Activity`
- produce `Knowledge`
- produce `WorkItem`

Crystallization rule:

- only persist reusable outputs
- do not dump raw chain-of-thought or transient chat text into the core

### Step 7: Structural lint

Implement integrity checks for:

- missing referenced object ids
- broken evidence references
- invalid statuses
- duplicate ids
- invalid projection links

### Step 8: Projections

Implement markdown projection for:

- sources
- nodes
- knowledge
- activities
- work items

Projection is derived, so generation can stay simple in phase 1.

## Code Layout

```text
src/wiki_memory/
  domain/
    objects/
    protocols/
    services/
  application/
    ingest/
    query/
    crystallize/
    lint/
  infrastructure/
    repositories/
    storage/
  adapters/
    repo/
  projections/
    markdown/
  interfaces/
    mcp/
```

## Phase 1 Entry Points

### Ingest

- `application.ingest.service`
- `adapters.repo.adapter`

### Query

- `application.query.service`
- `domain.services.context_builder`

### Crystallize

- `application.crystallize.service`
- `domain.services.crystallizer`

### Lint

- `application.lint.service`
- `domain.services.structure_lint`

## Acceptance Criteria

Phase 1 is complete when all of the following are true:

1. A repo path can be ingested into `Source`, `Node`, candidate `Knowledge`, and initial `Activity`.
2. `wiki.query(mode=context)` returns a coherent `ContextPack`.
3. `wiki.query(mode=expand)` can retrieve more detail around a selected object or source.
4. `wiki.crystallize` can write back an `Activity`, `Knowledge`, or `WorkItem`.
5. All mutations go through `WikiPatch` and produce `AuditEvent`.
6. Structural lint detects broken references and invalid core object states.
7. Markdown pages can be regenerated from the object store.

## Recommended Next Step After Phase 1

After this slice is stable, expand in this order:

1. improve repo adapter quality
2. add semantic lint
3. add web ingest
4. add PDF ingest
5. add lexical and vector retrieval enhancements
