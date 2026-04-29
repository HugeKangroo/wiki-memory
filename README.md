# memory-substrate

`memory-substrate` is a local-first memory substrate for agents. It stores canonical memory objects on disk, derives human-readable wiki projections, and exposes the workflow through an MCP server.

The current product center is memory, not wiki pages. Markdown and Obsidian views are projections. The durable model is the structured object store plus patches, audit events, evidence, lifecycle state, and optional graph indexes.

## Read First

- [Documentation Map](docs/README.md)
- [Memory Policy](docs/memory-policy.md)
- [Agent Memory MCP Usage](docs/agent-memory-mcp-usage.md)
- [MCP API Reference](docs/mcp-api-reference.md)
- [Project Development Policy](docs/project-development-policy.md)
- [Current Todo](todo.md)

Research and design history:

- [Compounding Memory Core Design](docs/superpowers/specs/2026-04-28-compounding-memory-core-design.md)
- [Context Substrate Memory Core Research](docs/research/2026-04-28-context-substrate-memory-core-research.md)
- [Memory Backend Library Spike](docs/research/2026-04-28-memory-backend-library-spike.md)
- [Semantic Retrieval And Reasoner Evaluation](docs/research/2026-04-28-semantic-retrieval-and-reasoner-evaluation.md)
- [Source Notes](docs/research/source-notes/)

## Quick Start

```bash
uv sync --group dev
uv run memory-substrate-mcp
```

The server runs over stdio using the official Python MCP SDK.

By default, the MCP server uses `~/memory-substrate` as the memory root on Linux and macOS. Tool calls do not expose a `root` argument to agents; set `MEMORY_SUBSTRATE_ROOT` in the MCP host environment when a server instance should use a different root.

## MCP Tools

The MCP server exposes exactly four tools:

- `memory_ingest`: capture source material as citable evidence.
- `memory_query`: search, expand, retrieve context packs, and inspect graph neighborhoods.
- `memory_remember`: commit governed durable memory.
- `memory_maintain`: validate, repair, reindex, report, and run lifecycle consolidation.

Every tool call uses this envelope:

```json
{
  "args": {
    "mode": "...",
    "input_data": {},
    "options": {}
  }
}
```

Notes:

- `input_data` is required at the MCP boundary even when empty.
- unexpected extra fields inside `args` are rejected.
- mutating `memory_maintain` modes require `options.apply=true`.

See [MCP API Reference](docs/mcp-api-reference.md) for supported modes and examples.

## Storage Boundary

The memory root contains canonical data and derived data:

```text
~/memory-substrate/
  memory/
    objects/              # canonical JSON objects
    indexes/              # derived query and graph state
    patches/              # governed write records
    audit/                # accountability records
    projections/
      wiki/               # Obsidian-friendly reading projection
      debug/              # object-level markdown mirror
      doxygen/            # optional generated API docs
```

Treat projections as read-only derived output. All durable changes should go through the MCP server so object IDs, references, indexes, projections, validation checks, and repair behavior stay consistent.

Direct file edits are reserved for emergency recovery or local debugging. After direct edits, run `memory_maintain` with `structure` or `repair`, then `reindex`, before relying on query or maintenance results.

## Optional Kuzu Graph Backend

The core package does not require a graph database or a separate LLM API key. For local graph-backed prototypes, install the optional Kuzu extra:

```bash
uv sync --extra kuzu
```

`KuzuGraphBackend` stores Memory Substrate objects directly in local Kuzu tables under `memory/indexes/kuzu_graph`. It is an adapter behind the project-owned graph contract, not a replacement for `memory_ingest`, `memory_remember`, `memory_query`, or `memory_maintain`.

Configure a root-level default graph backend with:

```json
{
  "args": {
    "mode": "configure",
    "input_data": {
      "graph_backend": "kuzu"
    },
    "options": {
      "apply": true
    }
  }
}
```

Supported graph backend values are `file` and `kuzu`.

## Repo Parser Backend

Repository ingest uses `tree-sitter-language-pack` as the primary parser for code symbols and Markdown documentation sections. Python parsing also uses the stdlib AST to enrich interface signatures and docstrings. Local fallback parsing remains in code only as a defensive path if parser loading fails.

## Optional LanceDB Semantic Index

Semantic retrieval is optional and local-first. It uses BGE-M3 through FlagEmbedding and stores derived chunks in LanceDB under `memory/indexes/semantic_lancedb`.

```bash
uv sync --extra semantic
```

Configure a root-level default semantic backend with:

```json
{
  "args": {
    "mode": "configure",
    "input_data": {
      "semantic_backend": "lancedb"
    },
    "options": {
      "apply": true
    }
  }
}
```

Then rebuild the semantic index from canonical objects:

```json
{
  "args": {
    "mode": "reindex",
    "input_data": {},
    "options": {
      "semantic_backend": "lancedb"
    }
  }
}
```

The semantic index is not canonical storage. If it is deleted or the embedding model changes, run `memory_maintain reindex` to rebuild it.
If a graph backend is also configured, `memory_query search` merges graph/lexical results with semantic hits and keeps canonical objects as the source of truth.
The MCP server does not load the embedding model during startup. The first semantic `reindex` or `search` loads the model lazily, tries the local Hugging Face cache first, falls back to download when the cache is missing, then reuses the same in-process provider for later calls with the same model.

## Host Configuration

Most MCP hosts can run the server with this stdio command:

```json
{
  "memory-substrate": {
    "command": "uv",
    "args": ["run", "--directory", "/absolute/path/to/memory-substrate", "memory-substrate-mcp"],
    "env": {
      "MEMORY_SUBSTRATE_ROOT": "/absolute/path/to/memory-root"
    }
  }
}
```

Omit `MEMORY_SUBSTRATE_ROOT` to use the default `~/memory-substrate` root.
Set `HF_HUB_OFFLINE=1` only when you intentionally want hard offline mode; the default semantic loader already tries cached files before downloading.

Codex CLI:

```bash
# Only needed when migrating from the old wiki-memory server name.
codex mcp remove wiki-memory

codex mcp add memory-substrate -- uv run --directory /absolute/path/to/memory-substrate memory-substrate-mcp
codex mcp list
```

The configured command must use `memory-substrate-mcp`. The old `wiki-memory-mcp` entrypoint is obsolete.

Claude Code:

```bash
claude mcp add --transport stdio --scope project memory-substrate -- \
  uv run --directory /absolute/path/to/memory-substrate memory-substrate-mcp
```

## Release

Build locally:

```bash
uv build
```

Create a GitHub release by pushing a semver tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```
