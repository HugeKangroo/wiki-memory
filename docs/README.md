# Documentation Map

This repository has three kinds of documentation. Keep them separate so the current product rules stay clear.

## Current Canonical Docs

- [Memory Policy](memory-policy.md): cross-project rules for Memory Substrate behavior and MCP tool semantics.
- [Agent Memory MCP Usage](agent-memory-mcp-usage.md): how agents and humans should call the four MCP tools.
- [MCP API Reference](mcp-api-reference.md): supported modes, required call shape, and examples.
- [Project Development Policy](project-development-policy.md): development strategy for this repository only.
- [Current Todo](../todo.md): active execution queue and near-term priorities.

## Research Notes

- [Context Substrate Memory Core Research](research/2026-04-28-context-substrate-memory-core-research.md)
- [Memory Backend Library Spike](research/2026-04-28-memory-backend-library-spike.md)
- [Semantic Retrieval And Reasoner Evaluation](research/2026-04-28-semantic-retrieval-and-reasoner-evaluation.md)
- [Semantic Retrieval Spike](research/2026-04-28-semantic-retrieval-spike.md)
- [Source Notes](research/source-notes/): imported source material such as `argue.md` and `llmwiki.md`.

Research notes are evidence and reasoning history. They are not the current product contract unless a current canonical doc cites a decision from them.

## Design And Execution History

- [Superpowers Docs](superpowers/README.md)
- [Specs](superpowers/specs/)
- [Plans](superpowers/plans/)

Specs and plans capture design decisions and implementation slices. Historical wiki-centered specs remain useful as archaeology, but current work should follow the memory-substrate policy and project development policy.

## Maintenance Rules

- Keep `README.md` short and navigational.
- Put MCP parameter details in `mcp-api-reference.md`.
- Put cross-project memory rules in `memory-policy.md`.
- Put repository-specific strategy in `project-development-policy.md`.
- Update `todo.md` whenever active priorities change.
- Add a historical note instead of deleting old design docs unless the file is actively misleading and no longer useful.
