# Agent Development Entry

Before changing this repository, read:

- [Current Todo](todo.md)
- [Memory Policy](docs/memory-policy.md)
- [Project Development Policy](docs/project-development-policy.md)
- [Agent Memory MCP Usage](docs/agent-memory-mcp-usage.md)

## Working Rules

- Treat `docs/memory-policy.md` as the cross-project memory policy source.
- Treat `docs/project-development-policy.md` as the repo-specific strategy source.
- Keep `README.md` short and navigational.
- Keep active work in `todo.md`.
- Update tests and docs together when MCP behavior, schemas, service validation, or tool responses change.
- Do not make optional backends or LLM providers mandatory for the default package.
- Do not edit generated memory projections as canonical data.

## Current Focus

The near-term implementation sequence is:

1. query normalization and retry hints
2. unstructured soft duplicate candidates
3. maintain duplicate review/report support
4. optional semantic retrieval evaluation

Use `todo.md` as the source of truth for current status.
