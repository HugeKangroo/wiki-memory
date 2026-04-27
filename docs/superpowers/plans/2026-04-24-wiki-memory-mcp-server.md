# Wiki Memory MCP Server Implementation Plan

> Historical snapshot: this plan implemented the previous wiki-centered MCP surface. The current implementation plan is `2026-04-27-memory-substrate-redesign.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable stdio MCP server for wiki-memory with five tools, including a full `wiki_dream` consolidation tool.

**Architecture:** Keep the MCP layer thin by registering five tools in `server.py` and dispatching into the existing tool functions in `tools.py`. Add a new `application.dream.service` that owns promotion, duplicate merge, stale decay, and cycle orchestration through `WikiPatch`, then cover the behavior with application and interface tests.

**Tech Stack:** Python 3.10+, official MCP Python SDK (`mcp.server.fastmcp.FastMCP`), `pytest`, file-backed repositories.

---

### Task 1: Add Failing Dream Service Tests

**Files:**
- Create: `tests/test_dream_service.py`
- Test: `tests/test_dream_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_promote_candidates_activates_eligible_knowledge():
    ...

def test_merge_duplicates_supersedes_loser_and_merges_evidence():
    ...

def test_decay_stale_marks_old_knowledge_stale():
    ...

def test_cycle_runs_all_dream_steps_and_rebuilds_projection():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --group dev python -m pytest tests/test_dream_service.py -q`
Expected: FAIL because `wiki_memory.application.dream.service` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
class DreamService:
    def promote_candidates(...): ...
    def merge_duplicates(...): ...
    def decay_stale(...): ...
    def cycle(...): ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --group dev python -m pytest tests/test_dream_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_dream_service.py src/wiki_memory/application/dream/service.py
git commit -m "feat: add dream consolidation service"
```

### Task 2: Add MCP Tool and Dispatch Coverage

**Files:**
- Modify: `src/wiki_memory/interfaces/mcp/tools.py`
- Create: `tests/test_mcp_tools.py`
- Test: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_wiki_dream_dispatches_to_supported_modes():
    ...

def test_wiki_dream_rejects_unsupported_modes():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --group dev python -m pytest tests/test_mcp_tools.py -q`
Expected: FAIL because `wiki_dream` is not defined

- [ ] **Step 3: Write minimal implementation**

```python
def wiki_dream(root, mode, input_data=None, options=None):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --group dev python -m pytest tests/test_mcp_tools.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wiki_memory/interfaces/mcp/tools.py tests/test_mcp_tools.py
git commit -m "feat: expose wiki dream tool dispatch"
```

### Task 3: Add Failing MCP Server Tests

**Files:**
- Modify: `src/wiki_memory/interfaces/mcp/server.py`
- Create: `tests/test_mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_create_server_registers_exactly_five_tools():
    ...

def test_server_entrypoint_is_runnable():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --group dev python -m pytest tests/test_mcp_server.py -q`
Expected: FAIL because `server.py` is still a placeholder

- [ ] **Step 3: Write minimal implementation**

```python
def create_server():
    mcp = FastMCP(...)
    @mcp.tool()
    def wiki_ingest(...): ...
    ...
    return mcp

def main():
    create_server().run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --group dev python -m pytest tests/test_mcp_server.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wiki_memory/interfaces/mcp/server.py tests/test_mcp_server.py
git commit -m "feat: add runnable wiki memory mcp server"
```

### Task 4: Add Documentation and Final Verification

**Files:**
- Modify: `pyproject.toml`
- Create: `README.md`
- Test: `tests/test_phase1_acceptance.py`

- [ ] **Step 1: Write the failing documentation assertions if needed**

```python
def test_readme_mentions_five_mcp_tools():
    ...
```

- [ ] **Step 2: Run targeted tests to verify the gap**

Run: `uv run --group dev python -m pytest tests/test_mcp_server.py tests/test_mcp_tools.py tests/test_dream_service.py -q`
Expected: PASS before docs update, then add docs manually

- [ ] **Step 3: Write minimal documentation and packaging updates**

```toml
[project.scripts]
wiki-memory-mcp = "wiki_memory.interfaces.mcp.server:main"
```

```markdown
# wiki-memory

## MCP Server

Run:
`uv run wiki-memory-mcp`
```

- [ ] **Step 4: Run full verification**

Run: `uv run --group dev python -m pytest -q`
Expected: PASS

Run: `python3 -m wiki_memory.interfaces.mcp.server --help`
Expected: exits successfully or starts without import error

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/wiki_memory/interfaces/mcp/server.py src/wiki_memory/interfaces/mcp/tools.py src/wiki_memory/application/dream/service.py tests
git commit -m "feat: ship wiki memory mcp server"
```
