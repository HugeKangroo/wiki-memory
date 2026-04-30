# Candidate Crystallization Dogfood

Date: 2026-04-30

## Scope

MS-12 tested the candidate review loop with a temporary memory root so the default memory store was not mutated.

Repositories:

- `/home/y9000/Projects/wiki-memory`
- `/home/y9000/GitRepo/llm_wiki`
- `/home/y9000/GitRepo/mempalace`

## Result

Each repository was ingested, concept candidates were inspected, the first candidate was temporarily accepted through `memory_remember`, and `memory_query search` was used to verify that the remembered item could be retrieved again.

Observed top candidate titles after noise filtering:

- `wiki-memory`: `BAAI/bge-m3`, `BGE-M3`, `Chinese/English`, `Current Data Model`, `Duplicate Handling`
- `llm_wiki`: `A3B-UD`, `Adamic-Adar`, `Deep Research`, `Graph Insights`, `LLM Wiki`
- `mempalace`: `Claude Code`, `Claude Code JSONL`, `Design Principles`, `Evaluates MemPal`, `Graceful Ctrl`

Temporary accepted candidates all returned from query:

- `wiki-memory`: `BAAI/bge-m3`
- `llm_wiki`: `A3B-UD`
- `mempalace`: `Claude Code`

## Adjustments

Dogfood exposed document-structure noise such as `END FILE`, `Content-Type`, `Bug Fixes`, `Agent Memory MCP Usage`, and `Current Todo`.

The candidate extractor now suppresses:

- top-level document title headings
- common document artifact suffixes such as `Usage`, `Todo`, `Examples`, and `Reference`
- generic artifact phrases such as `Bug Fixes`, `Call Examples`, `Content-Type`, and `END FILE`

## Remaining Judgment Boundary

Candidate discovery is still advisory. Terms such as `BAAI/bge-m3`, `A3B-UD`, and `Claude Code JSONL` may be valid technical concepts or may be implementation details depending on the task. Agents must follow `review_guidance`, inspect evidence, query existing memory, and rewrite summaries before calling `memory_remember`.
