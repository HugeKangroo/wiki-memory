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

By default, MCP tools use `~/memory-substrate` as the memory root on Linux and macOS when the caller does not pass an explicit `root`.

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
    "root": "/absolute/path/to/memory-substrate",
    "mode": "...",
    "input_data": {},
    "options": {}
  }
}
```

Notes:

- `root` is optional and defaults to `~/memory-substrate`.
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

## Host Configuration

Most MCP hosts can run the server with this stdio command:

```json
{
  "memory-substrate": {
    "command": "uv",
    "args": ["run", "--directory", "/absolute/path/to/memory-substrate", "memory-substrate-mcp"]
  }
}
```

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
