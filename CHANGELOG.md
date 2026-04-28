# Changelog

## 0.4.0 - Unreleased

- Renamed the public product surface to `memory-substrate` and the MCP tools to `memory_ingest`, `memory_query`, `memory_remember`, and `memory_maintain`.
- Added governed memory write rules for reason, memory source, scope refs, duplicate detection, conflict detection, and evidence validation.
- Added optional graph backend configuration with file and Kuzu backends behind the project-owned graph contract.
- Added optional LanceDB semantic retrieval with BGE-M3 embeddings as a rebuildable derived index.
- Added deterministic query normalization for domain terms such as todo/work-item and decision/preference/procedure/evidence queries, including graph backend metadata matching.
- Added advisory `possible_duplicates` responses for similar unstructured title/summary-only knowledge.
- Allowed MCP knowledge writes to omit `payload` for unstructured title/summary-only knowledge.
- Added unstructured soft duplicate candidates to maintenance reports while keeping automatic duplicate merge limited to structured duplicates.
- Added MCP resources and prompts for agent policy, task-start query workflow, and memory review guidance.
- Recorded the current semantic retrieval decision: defer embedding/vector/reasoner infrastructure until deterministic retrieval gaps are proven.
- Reorganized documentation around canonical policy, project policy, MCP usage, and API reference.

## 0.3.0 - 2026-04-26

Historical wiki-centered release:

- Expanded `wiki_ingest` with `web`, `pdf`, and `conversation` modes.
- Expanded `wiki_query` with `graph` mode for local relationship neighborhoods.
- Expanded `wiki_crystallize` with `batch` and `contest` modes.
- Expanded `wiki_lint` with duplicate identity, orphan source, active knowledge evidence, and projection consistency checks.
- Added tag-driven GitHub release workflow and package build verification in CI.

## 0.2.0 - 2026-04-26

Historical wiki-centered release:

- Added `file` and `markdown` ingest modes.
- Added query filters and context citations.
- Added read-only `wiki_dream.report`.

## 0.1.0 - 2026-04-25

Historical wiki-centered release:

- Initial file-backed wiki memory semantic store.
- Added MCP server with ingest, query, crystallize, lint, and dream tools.
