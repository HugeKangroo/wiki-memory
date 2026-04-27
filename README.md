# memory-substrate

Graph-backed memory substrate for agents, with derived wiki projections. The project stores semantic objects on disk, derives markdown projections, and exposes the workflow through an MCP server.

By default, the MCP tools use `~/memory-substrate` as the memory root on Linux and macOS when the caller does not pass an explicit `root`.

The MCP server uses a strict argument model with `extra="forbid"`. Older argument layouts or unexpected fields fail fast instead of being accepted silently.

## Storage and Editing Boundary

The memory root contains two different kinds of data:

- `memory/objects/` is the canonical object store. MCP tools read and write this data.
- `memory/projections/wiki/` is a generated Obsidian-friendly reading view. Open this directory as the Obsidian vault.
- `memory/projections/debug/` is a generated object-level markdown mirror for debugging, validation, and traceability.
- `memory/projections/doxygen/` is an optional Doxygen HTML projection for source API documentation.

Treat projections as derived output. They are safe to read, link, and browse, but changes made directly inside `memory/projections/wiki/` can be overwritten by a later projection rebuild and are not the reliable source of truth.

All durable changes should go through the MCP server, whether the caller is a human, an agent, Codex, Claude Code, Gemini CLI, VS Code, or another host. This keeps object IDs, references, indexes, projections, validation checks, and repair behavior consistent.

Direct file edits are possible for emergency recovery or local debugging, but they must preserve object schema and references. After direct edits, run `memory_maintain` with `structure` or `repair`, then `reindex`, before relying on query or maintenance results.

Recommended Obsidian entrypoint:

```text
~/memory-substrate/memory/projections/wiki/Home.md
```

Recommended root layout:

```text
~/memory-substrate/
  memory/
    objects/              # canonical JSON objects
    indexes/              # derived query state
    patches/              # write records
    audit/                # audit log
    projections/
      wiki/               # Obsidian vault for humans
        Home.md
        Projects/
        Knowledge/
        Sources/
        Activities/
        Work_Items/
      debug/              # object-level markdown mirror for tooling/debug
        sources/
        nodes/
        knowledge/
        activities/
        work_items/
      doxygen/            # optional Doxygen config and generated HTML
        Doxyfile
        html/
```

### Optional Doxygen API Docs

`memory-substrate` can generate a Doxygen projection for repository API documentation. Doxygen is an external system tool, not a Python package managed by `uv`.

Install it with your OS package manager:

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y doxygen graphviz

# macOS
brew install doxygen graphviz
```

After installing Doxygen, rebuild the projection by ingesting the repo again through MCP, or locally:

```bash
uv run --group dev python -c "from pathlib import Path; from memory_substrate.application.ingest.service import IngestService; IngestService(Path.home() / 'memory-substrate').ingest_repo(Path.cwd())"
```

Generated files:

```text
~/memory-substrate/memory/projections/wiki/API_Docs.md
~/memory-substrate/memory/projections/doxygen/Doxyfile
~/memory-substrate/memory/projections/doxygen/html/index.html
```

Open `API_Docs.md` from Obsidian to view the embedded Doxygen HTML page. If `doxygen` is not installed, `API_Docs.md` still gets generated but reports that HTML output was not produced.

`API_Docs.md` is an Obsidian entry page, not the full API document itself. It links to and embeds:

```text
~/memory-substrate/memory/projections/doxygen/html/index.html
```

If Obsidian does not render the embedded frame or relative HTML link in your setup, open the generated `index.html` directly in a browser.

Other documentation generators can be added later:

- `pdoc`: good Python-first API docs, simple setup, understands type annotations and Google-style docstrings, outputs HTML.
- `mkdocs` + `mkdocstrings`: good documentation site workflow from Markdown source pages, supports Python and other handlers, outputs a static HTML site.
- `Sphinx` + `MyST`: strong for large docs and cross references, Markdown-capable through MyST, heavier setup.

The current built-in projections are:

- Obsidian-native Markdown pages for memory browsing.
- Optional Doxygen HTML pages for source API documentation.

## MCP Server

The MCP server exposes exactly four tools:

- `memory_ingest`
- `memory_query`
- `memory_remember`
- `memory_maintain`

Recommended agent workflow:

1. At task start, call `memory_query` to load existing context.
2. For new evidence, call `memory_ingest` to capture files, repos, web pages, PDFs, or conversations as citable evidence.
3. Analyze the evidence outside ingest and decide whether any extracted information should survive future sessions.
4. Before durable writes, call `memory_query` to check related context, duplicates, and conflicts.
5. Call `memory_remember` only for durable memory the user requested or the agent can justify.
6. Call `memory_maintain` read-only modes before mutating maintenance. Mutating maintain modes require `options.apply=true`.

### Supported Modes

- `memory_ingest`: `repo`, `file`, `markdown`, `web`, `pdf`, `conversation`
- `memory_query`: `context`, `expand`, `page`, `recent`, `search`, `graph`
- `memory_remember`: `activity`, `knowledge`, `work_item`, `promote`, `supersede`, `contest`, `batch`
- `memory_maintain`: `structure`, `audit`, `reindex`, `repair`, `promote_candidates`, `merge_duplicates`, `decay_stale`, `cycle`, `report`

### Required MCP Call Shape

Every tool call must include:

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

- `args` is required
- `root` is optional; if omitted, it defaults to `~/memory-substrate`
- `input_data` is required at the MCP boundary even when empty
- `options` is optional
- unexpected extra fields inside `args` are rejected
- mutating `memory_maintain` modes reject the call unless `options.apply` is exactly `true`

### MCP API Reference

The outer envelope is always:

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

What changes per tool is the allowed `mode` set and the required shape of `input_data`.

#### `memory_ingest`

Allowed modes:

- `repo`
- `file`
- `markdown`
- `web`
- `pdf`
- `conversation`

`repo` requires:

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

`file` and `markdown` both require a local path:

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

`file` stores plain text sources. `markdown` stores markdown sources and uses headings as segment boundaries where possible.
`web` stores fetched text from a URL, `pdf` stores extracted text when readable or a binary stub otherwise, and `conversation` stores role/content message lists.

`conversation` messages are structured:

```json
{
  "role": "user",
  "content": "Remember that project X uses Neo4j.",
  "name": "optional-speaker",
  "created_at": "2026-04-27T00:00:00+00:00",
  "metadata": {}
}
```

#### `memory_query`

Allowed modes:

- `context`
- `expand`
- `page`
- `recent`
- `search`
- `graph`

Examples:

`context`

```json
{
  "args": {
    "mode": "context",
    "input_data": {
      "task": "inspect repository structure",
      "scope": {
        "node_ids": ["node:..."]
      }
    },
    "options": {
      "max_items": 12
    }
  }
}
```

`context` also accepts scope filters such as `object_types`, `kind`, `status`, and `node_ids`.

`expand`

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

`page`

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

`recent`

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

`search`

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

`graph` returns a local relationship neighborhood:

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

#### `memory_remember`

Allowed modes:

- `activity`
- `knowledge`
- `work_item`
- `promote`
- `supersede`
- `contest`
- `batch`

Examples:

`activity`

```json
{
  "args": {
    "mode": "activity",
    "input_data": {
      "kind": "research",
      "title": "Repo walkthrough",
      "summary": "Captured reusable findings.",
      "source_refs": ["src:..."],
      "related_node_refs": ["node:..."]
    }
  }
}
```

`contest`

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

`batch` writes multiple `activity`, `knowledge`, and `work_item` entries:

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
            "subject_refs": ["node:..."],
            "evidence_refs": [],
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

`knowledge`

```json
{
  "args": {
    "mode": "knowledge",
    "input_data": {
      "kind": "fact",
      "title": "Repo uses Python",
      "summary": "Primary language is Python.",
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

`evidence_refs` entries are structured as:

```json
{
  "source_id": "src:...",
  "segment_id": "seg-1",
  "locator": {
    "kind": "line",
    "line": 12
  }
}
```

`payload` is a structured claim: `subject`, `predicate`, `value`, `object`, and optional `metadata`.

`work_item`

```json
{
  "args": {
    "mode": "work_item",
    "input_data": {
      "kind": "task",
      "title": "Review repo",
      "summary": "Track next step.",
      "source_refs": ["src:..."]
    }
  }
}
```

`promote`

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

`supersede`

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

#### `memory_maintain` Structural Modes

Allowed modes:

- `structure`
- `audit`
- `reindex`
- `repair`

Examples:

`structure`

```json
{
  "args": {
    "mode": "structure",
    "input_data": {}
  }
}
```

`audit`

```json
{
  "args": {
    "mode": "audit",
    "input_data": {},
    "options": {
      "max_items": 100
    }
  }
}
```

`reindex`

```json
{
  "args": {
    "mode": "reindex",
    "input_data": {}
  }
}
```

`repair`

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

#### `memory_maintain` Lifecycle Modes

Allowed modes:

- `promote_candidates`
- `merge_duplicates`
- `decay_stale`
- `cycle`
- `report`

Examples:

`promote_candidates`

```json
{
  "args": {
    "mode": "promote_candidates",
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

`merge_duplicates`

```json
{
  "args": {
    "mode": "merge_duplicates",
    "input_data": {},
    "options": {
      "apply": true
    }
  }
}
```

`decay_stale`

```json
{
  "args": {
    "mode": "decay_stale",
    "input_data": {
      "reference_time": "2026-04-24T00:00:00+00:00",
      "stale_after_days": 30
    },
    "options": {
      "apply": true
    }
  }
}
```

`cycle`

```json
{
  "args": {
    "mode": "cycle",
    "input_data": {
      "min_confidence": 0.75,
      "min_evidence": 1,
      "reference_time": "2026-04-24T00:00:00+00:00",
      "stale_after_days": 30
    },
    "options": {
      "apply": true
    }
  }
}
```

`report`

```json
{
  "args": {
    "mode": "report",
    "input_data": {
      "min_confidence": 0.75,
      "min_evidence": 1,
      "reference_time": "2026-04-24T00:00:00+00:00",
      "stale_after_days": 30
    }
  }
}
```

`report` is read-only. It returns promotable candidate ids, low-evidence candidate ids, stale candidate ids, duplicate groups, and counts.

### Run

```bash
uv sync --group dev
uv run memory-substrate-mcp
```

The server runs over stdio using the official Python MCP SDK.

### Host Configuration Example

Use the server as a stdio command. Many MCP hosts expect the same shape:

```json
{
  "memory-substrate": {
    "command": "uv",
    "args": ["run", "memory-substrate-mcp"],
    "cwd": "/absolute/path/to/memory-substrate"
  }
}
```

If your host uses a different wrapper format, keep the same command, args, and working directory.

## Host-Specific Setup

Replace `/absolute/path/to/memory-substrate` with your local checkout path.

### Codex

Codex can register the server directly from the CLI:

```bash
codex mcp add memory-substrate -- uv run --directory /absolute/path/to/memory-substrate memory-substrate-mcp
```

If you prefer editing config manually, use the same command and arguments in your Codex MCP server entry.
For non-interactive smoke tests or trusted local use, set the server approval mode:

```toml
[mcp_servers.memory-substrate]
command = "uv"
args = ["run", "--directory", "/absolute/path/to/memory-substrate", "memory-substrate-mcp"]
default_tools_approval_mode = "approve"
```

### Claude Code

For a project-shared setup, add this to `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "memory-substrate": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/memory-substrate",
        "memory-substrate-mcp"
      ],
      "env": {}
    }
  }
}
```

You can also add it from the CLI:

```bash
claude mcp add --transport stdio --scope project memory-substrate -- \
  uv run --directory /absolute/path/to/memory-substrate memory-substrate-mcp
```

### Gemini CLI

Add this to `.gemini/settings.json` or `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "memory-substrate": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/memory-substrate",
        "memory-substrate-mcp"
      ],
      "cwd": "/absolute/path/to/memory-substrate",
      "timeout": 30000,
      "trust": true
    }
  }
}
```

### VS Code

Add this to `.vscode/mcp.json` in the workspace or your user `mcp.json`:

```json
{
  "servers": {
    "memorySubstrate": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/memory-substrate",
        "memory-substrate-mcp"
      ]
    }
  }
}
```

### Error Behavior

- unsupported modes return a clear `ValueError`
- missing required fields such as `mode` or `input_data` fail at MCP argument validation
- unexpected extra fields inside `args` fail with `Extra inputs are not permitted`
- missing required tool arguments fail through the MCP SDK argument validation layer
- `memory_maintain` no-op paths return success payloads with zero counts instead of raising
- domain object lookup failures keep the missing object id in the error message

## Notes

- `memory-substrate-mcp` is installed by `uv sync --group dev`
- all four host examples above use stdio transport
- `uv run --directory ... memory-substrate-mcp` avoids relying on the caller's current working directory
- if a tool call omits `root`, the server resolves it to `~/memory-substrate`

## Release

Build locally:

```bash
uv build
```

Create a GitHub release by pushing a semver tag:

```bash
git tag v0.3.0
git push origin v0.3.0
```

The release workflow builds the package and attaches `dist/*` artifacts to the GitHub release.
