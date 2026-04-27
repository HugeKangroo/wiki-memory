# Graph Backend Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-owned `GraphBackend` contract plus a file-backed implementation for tests and local contract development.

**Architecture:** The new protocol lives in the domain layer and uses Memory Substrate records, not vendor API objects. The file-backed implementation stores a deterministic JSON graph under `memory/indexes/file_graph.json` and is only a contract backend, not a production graph memory engine.

**Tech Stack:** Python dataclasses/typing protocols, existing JSON storage helpers, unittest/pytest.

---

### Task 1: Define Graph Backend Contract And Tests

**Files:**
- Create: `tests/test_graph_backend.py`
- Create: `src/memory_substrate/domain/protocols/graph_backend.py`
- Create: `src/memory_substrate/infrastructure/graph/__init__.py`
- Create: `src/memory_substrate/infrastructure/graph/file_graph_backend.py`

- [x] **Step 1: Write failing tests**

Create tests that import `FileGraphBackend` and verify persistence, search, neighborhood traversal, temporal lookup, evidence linking, health, rebuild, and scope export.

- [x] **Step 2: Verify red**

Run:

```bash
uv run --group dev python -m pytest tests/test_graph_backend.py
```

Expected: fail with `ModuleNotFoundError` for the new graph backend module.

- [x] **Step 3: Add protocol and file-backed implementation**

Implement `GraphBackend` in `src/memory_substrate/domain/protocols/graph_backend.py`.

Implement `FileGraphBackend` in `src/memory_substrate/infrastructure/graph/file_graph_backend.py`.

The backend stores:

```json
{
  "episodes": {},
  "entities": {},
  "relations": {},
  "knowledge": {}
}
```

Required methods:

- `upsert_episode`
- `upsert_entity`
- `upsert_relation`
- `upsert_knowledge`
- `link_evidence`
- `search`
- `neighborhood`
- `temporal_lookup`
- `health`
- `rebuild`
- `export_scope`

- [x] **Step 4: Verify green**

Run:

```bash
uv run --group dev python -m pytest tests/test_graph_backend.py
```

Expected: all new tests pass.

- [x] **Step 5: Verify full suite and build**

Run:

```bash
uv run --group dev python -m pytest
uv build
```

Expected: existing suite remains green and package builds.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-04-28-graph-backend-contract.md tests/test_graph_backend.py src/memory_substrate/domain/protocols/graph_backend.py src/memory_substrate/infrastructure/graph/__init__.py src/memory_substrate/infrastructure/graph/file_graph_backend.py
git commit -m "feat: add graph backend contract"
```
