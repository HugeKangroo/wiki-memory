# Superpowers Design And Plan History

This directory stores design specs and implementation plans created during development.

Current implementation should follow:

- [Memory Policy](../memory-policy.md)
- [Project Development Policy](../project-development-policy.md)
- [Current Todo](../../todo.md)

## Directories

- `specs/`: design snapshots and architecture proposals.
- `plans/`: executable implementation plans for specific slices.

## Historical Documents

Some early files use `wiki_memory`, `wiki_*`, `crystallize`, `lint`, or `dream` terminology. Those files are historical snapshots unless they explicitly say they define the current memory-substrate surface.

Current public names are:

- package: `memory_substrate`
- MCP tools: `memory_ingest`, `memory_query`, `memory_remember`, `memory_maintain`
- product center: governed memory substrate
- wiki: derived projection

Do not implement new work from an old plan without checking `todo.md` and the current policy docs first.
