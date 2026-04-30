# Candidate Crystallization Dogfood

Date: 2026-04-30

## Scope

MS-12 tested the candidate review loop with a temporary memory root so the default memory store was not mutated.

Repositories:

- `/home/y9000/Projects/wiki-memory`
- `/home/y9000/GitRepo/llm_wiki`
- `/home/y9000/GitRepo/mempalace`

## MS-12 Result

Each repository was ingested, concept candidates were inspected, the first candidate was temporarily accepted through `memory_remember`, and `memory_query search` was used to verify that the remembered item could be retrieved again.

Observed top candidate titles after noise filtering:

- `wiki-memory`: `BAAI/bge-m3`, `BGE-M3`, `Chinese/English`, `Current Data Model`, `Duplicate Handling`
- `llm_wiki`: `A3B-UD`, `Adamic-Adar`, `Deep Research`, `Graph Insights`, `LLM Wiki`
- `mempalace`: `Claude Code`, `Claude Code JSONL`, `Design Principles`, `Evaluates MemPal`, `Graceful Ctrl`

Temporary accepted candidates all returned from query:

- `wiki-memory`: `BAAI/bge-m3`
- `llm_wiki`: `A3B-UD`
- `mempalace`: `Claude Code`

## MS-13 Result

MS-13 added `candidate_type`, `ranking_signals`, bounded score components, and `candidate_diagnostics`.

Observed top candidate titles after classification and ranking:

- `wiki-memory`: `Memory Policy`, `memory-substrate`, `Current Data Model`, `Duplicate Handling`, `待办项`
- `llm_wiki`: `LLM Wiki`, `Deep Research`, `Graph Insights`, `Real-LLM`, `Adamic-Adar`
- `mempalace`: `Design Principles`, `JSON-RPC`, `Project Structure`, `Niklas Luhmann`, `Knowledge Graph`

The combined maintain report ranked reusable concepts ahead of tool names and implementation details:

- `LLM Wiki`
- `Design Principles`
- `Knowledge Graph`
- `Memory Policy`
- `Project Structure`
- `memory-substrate`

## Adjustments

Dogfood exposed document-structure noise such as `END FILE`, `Content-Type`, `Bug Fixes`, `Agent Memory MCP Usage`, and `Current Todo`.

The candidate extractor now suppresses:

- top-level document title headings
- common document artifact suffixes such as `Usage`, `Todo`, `Examples`, and `Reference`
- generic artifact phrases such as `Bug Fixes`, `Call Examples`, `Content-Type`, and `END FILE`

MS-13 additionally downgraded or suppressed:

- tool and model names such as `BGE-M3`, `BAAI/bge-m3`, `Claude Code`, and `LM Studio`
- command or MCP operation phrases such as `mempalace init` and `memory_query search`
- command phrases with flags such as `mempalace init --llm`
- package/tool names such as `mempalace-mcp`
- schema fragments such as `TEXT NOT NULL`
- locale or format markers such as `pt-br` and `YYYY-MM-DD`
- prompt/document markers such as `MANDATORY OUTPUT LANGUAGE`, `New Features`, and `Written BEFORE`
- feature-style action phrases such as `Evaluates MemPal`
- keyboard shortcut fragments such as `Graceful Ctrl`

## Remaining Judgment Boundary

Candidate discovery is still advisory. Terms such as `Adamic-Adar`, `JSON-RPC`, and `Niklas Luhmann` may be valid concepts or may be too narrow depending on the task. Agents must follow `review_guidance`, inspect evidence, query existing memory, and rewrite summaries before calling `memory_remember`.
