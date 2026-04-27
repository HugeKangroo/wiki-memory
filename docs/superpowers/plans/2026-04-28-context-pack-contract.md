# Context Pack Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the context pack contract to carry work-ready memory context without breaking existing query behavior.

**Architecture:** Add optional/defaulted fields to the `ContextPack` dataclass, populate them in `ContextBuilder`, and expose them through `QueryService.context`. Keep existing `citations` output for compatibility while adding `evidence` as the memory-core field.

**Tech Stack:** Python dataclasses, existing query service, pytest/unittest.

---

### Task 1: Extend ContextPack And Query Output

**Files:**
- Create: `tests/test_context_pack_contract.py`
- Modify: `src/memory_substrate/domain/protocols/context_pack.py`
- Modify: `src/memory_substrate/domain/services/context_builder.py`
- Modify: `src/memory_substrate/application/query/service.py`

- [x] **Step 1: Write failing tests**

Create tests showing default fields exist and `memory_query context` returns evidence, decisions, procedures, open work, and freshness.

- [x] **Step 2: Verify red**

Run:

```bash
uv run --group dev python -m pytest tests/test_context_pack_contract.py
```

Expected: fail because the new context pack keys are absent.

- [x] **Step 3: Add minimal implementation**

Add default fields to `ContextPack`, derive typed sections in `ContextBuilder`, and include them in `QueryService.context`.

- [x] **Step 4: Verify green**

Run:

```bash
uv run --group dev python -m pytest tests/test_context_pack_contract.py
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
git add docs/superpowers/plans/2026-04-28-context-pack-contract.md tests/test_context_pack_contract.py src/memory_substrate/domain/protocols/context_pack.py src/memory_substrate/domain/services/context_builder.py src/memory_substrate/application/query/service.py
git commit -m "feat: expand context pack contract"
```
