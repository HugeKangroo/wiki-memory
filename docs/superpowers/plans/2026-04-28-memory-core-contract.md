# Memory Core Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add graph-ready memory core domain contracts without changing MCP runtime behavior.

**Architecture:** New dataclasses live in `domain/objects` and governed request protocols live in `domain/protocols`. Existing file repositories gain object-directory support for the new domain objects so later services can persist them through the same storage boundary.

**Tech Stack:** Python dataclasses, existing file repository helpers, pytest/unittest.

---

### Task 1: Add Memory Core Domain Models

**Files:**
- Create: `tests/test_memory_core_contract.py`
- Create: `src/memory_substrate/domain/objects/memory_scope.py`
- Create: `src/memory_substrate/domain/objects/episode.py`
- Create: `src/memory_substrate/domain/objects/entity.py`
- Create: `src/memory_substrate/domain/objects/relation.py`
- Create: `src/memory_substrate/domain/protocols/remember_request.py`
- Modify: `src/memory_substrate/domain/objects/__init__.py`
- Modify: `src/memory_substrate/domain/protocols/__init__.py`
- Modify: `src/memory_substrate/infrastructure/storage/paths.py`

- [x] **Step 1: Write failing tests**

Create tests for dataclass defaults, repository persistence for new object types, and governed `RememberRequest` validation.

- [x] **Step 2: Verify red**

Run:

```bash
uv run --group dev python -m pytest tests/test_memory_core_contract.py
```

Expected: fail with `ModuleNotFoundError` for new object modules.

- [x] **Step 3: Add minimal implementation**

Implement the dataclasses and storage path support needed for the tests.

- [x] **Step 4: Verify green**

Run:

```bash
uv run --group dev python -m pytest tests/test_memory_core_contract.py
```

Expected: all new tests pass.

- [x] **Step 5: Verify full suite and build**

Run:

```bash
uv run --group dev python -m pytest
uv build
```

Expected: full suite passes and build succeeds.

- [x] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-04-28-memory-core-contract.md tests/test_memory_core_contract.py src/memory_substrate/domain/objects/memory_scope.py src/memory_substrate/domain/objects/episode.py src/memory_substrate/domain/objects/entity.py src/memory_substrate/domain/objects/relation.py src/memory_substrate/domain/protocols/remember_request.py src/memory_substrate/domain/objects/__init__.py src/memory_substrate/domain/protocols/__init__.py src/memory_substrate/infrastructure/storage/paths.py
git commit -m "feat: add memory core contracts"
```
