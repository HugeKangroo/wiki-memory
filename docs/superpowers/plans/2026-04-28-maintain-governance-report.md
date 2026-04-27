# Maintain Governance Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only governance violation reporting to `memory_maintain report`.

**Architecture:** Extend `MaintenanceLifecycle.report` with a `governance_violations` list and count. The first rule reports active knowledge that has no evidence and is not explicitly user-declared or human-curated.

**Tech Stack:** Existing maintain lifecycle, file object repository, pytest/unittest.

---

### Task 1: Report Active Knowledge Without Evidence

**Files:**
- Modify: `tests/test_maintain_service.py`
- Modify: `src/memory_substrate/application/maintain/lifecycle.py`

- [x] **Step 1: Write failing test**

Add a test that seeds active agent-inferred knowledge without evidence and expects `memory_maintain report` to return a governance violation, while user-declared active knowledge without evidence is allowed.

- [x] **Step 2: Verify red**

Run:

```bash
uv run --group dev python -m pytest tests/test_maintain_service.py::MaintenanceLifecycleTest::test_report_flags_active_agent_inferred_knowledge_without_evidence
```

Expected: fail because `governance_violations` is absent.

- [x] **Step 3: Implement report rule**

Add a helper in `MaintenanceLifecycle` that detects active knowledge without evidence unless `payload.metadata.memory_source` is `user_declared` or `human_curated`.

- [x] **Step 4: Verify green**

Run:

```bash
uv run --group dev python -m pytest tests/test_maintain_service.py::MaintenanceLifecycleTest::test_report_flags_active_agent_inferred_knowledge_without_evidence
```

Expected: test passes.

- [x] **Step 5: Verify full suite and build**

Run:

```bash
uv run --group dev python -m pytest
uv build
```

Expected: full suite passes and build succeeds.

- [x] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-04-28-maintain-governance-report.md tests/test_maintain_service.py src/memory_substrate/application/maintain/lifecycle.py
git commit -m "feat: report memory governance violations"
```
