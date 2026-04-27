# Knowledge Payload Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add typed payload contracts for decision and procedure knowledge.

**Architecture:** Keep `Decision` and `Procedure` stored as `Knowledge` records with dedicated `kind` values, but add dataclasses that define their structured payload shape for future validation and MCP schema evolution.

**Tech Stack:** Python dataclasses and pytest/unittest.

---

### Task 1: Add DecisionPayload And ProcedurePayload

**Files:**
- Create: `tests/test_knowledge_payload_contracts.py`
- Create: `src/memory_substrate/domain/protocols/knowledge_payloads.py`
- Modify: `src/memory_substrate/domain/protocols/__init__.py`

- [x] **Step 1: Write failing tests**

Add tests that construct `DecisionPayload` and `ProcedurePayload`, assert their defaults, and verify `to_payload()` returns a JSON-ready dictionary.

- [x] **Step 2: Verify red**

Run:

```bash
uv run --group dev python -m pytest tests/test_knowledge_payload_contracts.py
```

Expected: fail with `ModuleNotFoundError` for the new payload module.

- [x] **Step 3: Implement payload dataclasses**

Add `DecisionPayload` and `ProcedurePayload` with `to_payload()` helpers.

- [x] **Step 4: Verify green**

Run:

```bash
uv run --group dev python -m pytest tests/test_knowledge_payload_contracts.py
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
git add docs/superpowers/plans/2026-04-28-knowledge-payload-contracts.md tests/test_knowledge_payload_contracts.py src/memory_substrate/domain/protocols/knowledge_payloads.py src/memory_substrate/domain/protocols/__init__.py
git commit -m "feat: add knowledge payload contracts"
```
