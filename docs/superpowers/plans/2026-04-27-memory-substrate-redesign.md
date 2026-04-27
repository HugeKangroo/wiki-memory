# Memory Substrate Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the public project surface from wiki-centered memory to memory substrate naming while preserving current behavior.

**Architecture:** Keep the existing object store, patch, audit, query, projection, and maintenance behavior. Change the package and MCP contract to `memory_substrate` and `memory_*` tools, with `remember` and `maintain` as the product-level write and lifecycle surfaces.

**Tech Stack:** Python 3.10+, MCP, pytest, hatchling, current filesystem object store.

---

## Files

- Modify: `pyproject.toml`
- Move: `src/wiki_memory/` to `src/memory_substrate/`
- Modify: `src/memory_substrate/interfaces/mcp/server.py`
- Modify: `src/memory_substrate/interfaces/mcp/tools.py`
- Modify: `src/memory_substrate/interfaces/mcp/models.py`
- Move: `src/memory_substrate/application/crystallize/` to `src/memory_substrate/application/remember/`
- Move: `src/memory_substrate/application/lint/` to `src/memory_substrate/application/maintain/`
- Modify: `src/memory_substrate/application/remember/service.py`
- Modify: `src/memory_substrate/application/maintain/service.py`
- Modify: tests under `tests/`
- Modify: `README.md`
- Add: `docs/superpowers/specs/2026-04-27-memory-substrate-redesign.md`

## Task 1: Public MCP Tests

**Files:**
- Modify: `tests/test_mcp_server.py`
- Modify: `tests/test_mcp_tools.py`

- [x] **Step 1: Write failing MCP registration expectations**

Change the expected MCP tool names in `tests/test_mcp_server.py` to:

```python
{"memory_ingest", "memory_query", "memory_remember", "memory_maintain"}
```

Change mode expectations:

```python
memory_ingest: {"repo", "file", "markdown", "web", "pdf", "conversation"}
memory_query: {"context", "expand", "page", "recent", "search", "graph"}
memory_remember: {"activity", "knowledge", "work_item", "promote", "supersede", "contest", "batch"}
memory_maintain: {"structure", "audit", "reindex", "repair", "promote_candidates", "merge_duplicates", "decay_stale", "cycle", "report"}
```

- [x] **Step 2: Write failing MCP dispatch imports**

Change `tests/test_mcp_tools.py` imports from:

```python
from wiki_memory.interfaces.mcp.tools import wiki_crystallize, wiki_dream
```

to:

```python
from memory_substrate.interfaces.mcp.tools import memory_maintain, memory_remember
```

Update calls:

```python
memory_dream_call = memory_maintain(".", "cycle", {"reference_time": "2026-04-24T00:00:00+00:00"})
remember_call = memory_remember(".", "knowledge", {...})
```

- [x] **Step 3: Run tests and verify red**

Run:

```bash
uv run --group dev python -m pytest tests/test_mcp_server.py tests/test_mcp_tools.py
```

Expected: FAIL because `memory_substrate` imports and `memory_*` tools do not exist yet.

## Task 2: Package Rename

**Files:**
- Move: `src/wiki_memory/` to `src/memory_substrate/`
- Modify: all Python imports under `src/` and `tests/`
- Modify: `pyproject.toml`

- [x] **Step 1: Move package directory**

Run:

```bash
mv src/wiki_memory src/memory_substrate
```

- [x] **Step 2: Replace import paths**

Run:

```bash
perl -pi -e 's/wiki_memory/memory_substrate/g' $(find src tests -name '*.py')
```

- [x] **Step 3: Update project metadata**

In `pyproject.toml`, set:

```toml
[project]
name = "memory-substrate"
description = "Graph-backed memory substrate for agents, with derived wiki projections."

[project.scripts]
memory-substrate-mcp = "memory_substrate.interfaces.mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/memory_substrate"]
```

- [x] **Step 4: Run import tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_api_docstrings.py
```

Expected: PASS after package imports are updated.

## Task 3: MCP Tool Rename

**Files:**
- Modify: `src/memory_substrate/interfaces/mcp/server.py`
- Modify: `src/memory_substrate/interfaces/mcp/tools.py`
- Modify: `src/memory_substrate/interfaces/mcp/models.py`

- [x] **Step 1: Rename dispatch functions**

In `tools.py`, rename:

```python
wiki_ingest -> memory_ingest
wiki_query -> memory_query
wiki_crystallize -> memory_remember
wiki_lint -> memory_maintain
wiki_dream -> remove as top-level dispatch
```

Route `memory_maintain` modes:

```python
structure, audit, reindex, repair -> MaintainService lint/repair behavior
promote_candidates, merge_duplicates, decay_stale, cycle, report -> MaintainService lifecycle behavior
```

- [x] **Step 2: Rename registered MCP tools**

In `server.py`, register exactly:

```python
memory_ingest
memory_query
memory_remember
memory_maintain
```

- [x] **Step 3: Rename MCP model classes and mode unions**

In `models.py`, expose argument models for the four memory tools and remove top-level wiki/crystallize/lint/dream naming from public class names and tool selection.

- [x] **Step 4: Run MCP tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_mcp_server.py tests/test_mcp_tools.py
```

Expected: PASS.

## Task 4: Remember and Maintain Service Names

**Files:**
- Move: `src/memory_substrate/application/crystallize/` to `src/memory_substrate/application/remember/`
- Move: `src/memory_substrate/application/lint/` to `src/memory_substrate/application/maintain/`
- Modify: `src/memory_substrate/application/remember/service.py`
- Modify: `src/memory_substrate/application/maintain/service.py`
- Modify: imports under `src/` and `tests/`

- [x] **Step 1: Rename directories**

Run:

```bash
mv src/memory_substrate/application/crystallize src/memory_substrate/application/remember
mv src/memory_substrate/application/lint src/memory_substrate/application/maintain
```

- [x] **Step 2: Rename service classes**

In `remember/service.py`, rename:

```python
class CrystallizeService -> class RememberService
```

In `maintain/service.py`, include lifecycle methods by composing or moving current `DreamService` behavior into the public maintain surface.

- [x] **Step 3: Replace import paths and class references**

Run:

```bash
perl -pi -e 's/application\.crystallize/application.remember/g; s/CrystallizeService/RememberService/g; s/application\.lint/application.maintain/g; s/LintService/MaintainService/g' $(find src tests -name '*.py')
```

- [x] **Step 4: Run service tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_crystallize_projection.py tests/test_dream_service.py tests/test_lint_enhanced.py tests/test_repair_missing_references.py
```

Expected: PASS after import and class names are updated.

## Task 5: Documentation Rename

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-04-24-wiki-memory-mcp-server-design.md`
- Modify: `docs/superpowers/plans/2026-04-24-wiki-memory-mcp-server.md`

- [x] **Step 1: Update README product framing**

Change the first paragraph to:

```markdown
# memory-substrate

Graph-backed memory substrate for agents, with derived wiki projections.
```

Document the four tools:

```text
memory_ingest
memory_remember
memory_query
memory_maintain
```

- [x] **Step 2: Update old design docs as historical notes**

Mark older wiki-memory specs as historical snapshots so they do not define the current product surface.

- [x] **Step 3: Run docs-sensitive tests**

Run:

```bash
uv run --group dev python -m pytest tests/test_obsidian_projection.py tests/test_phase1_acceptance.py
```

Expected: PASS.

## Task 6: Full Verification

**Files:**
- All changed files

- [x] **Step 1: Run full test suite**

Run:

```bash
uv run --group dev python -m pytest
```

Expected: all tests pass.

- [x] **Step 2: Inspect diff**

Run:

```bash
git diff --stat
git diff -- README.md pyproject.toml src/memory_substrate/interfaces/mcp/tools.py src/memory_substrate/interfaces/mcp/server.py
```

Expected: diff shows naming and boundary refactor only, no unrelated behavior changes.

## Plan Review

Coverage:

- MCP naming is covered by Tasks 1 and 3.
- Package naming is covered by Task 2.
- Remember/Maintain service naming is covered by Task 4.
- README and historical docs are covered by Task 5.
- Verification is covered by Task 6.

This plan intentionally does not implement Graphiti or Neo4j. That requires a separate backend design and test plan after the memory surface is correctly named.
