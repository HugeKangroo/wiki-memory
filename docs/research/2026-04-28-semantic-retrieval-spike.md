# Semantic Retrieval Spike

Date: 2026-04-28

Status: Completed spike

## Goal

Validate whether a local-first semantic retrieval path can improve Memory Substrate query behavior without making LanceDB canonical storage.

The spike tested:

- LanceDB as a derived vector index
- BGE-M3 as the quality-first embedding model
- FlagEmbedding as the BGE-M3 runtime
- synthetic Chinese/English memory queries
- one real memory object written through Codex MCP dogfood

## Result

BGE-M3 through FlagEmbedding works in the current Python 3.14 environment.

The command used:

```bash
uv run --with lancedb --with FlagEmbedding python experiments/semantic_retrieval_spike.py \
  --provider flagembedding \
  --model BAAI/bge-m3 \
  --eval-cases experiments/semantic_retrieval_eval_cases.json \
  --db-path /tmp/memory-semantic-spike-bge-m3 \
  --clean
```

Observed results:

- synthetic eval cases: 5 passed, 0 failed
- embedding dimension: 1024
- first model download and ready time: about 177 seconds
- post-download model ready time: about 6 seconds
- embedding 6-7 short records: about 0.5 seconds
- 5 eval queries: about 0.1 seconds

Including the current canonical memory root, the probe query `Codex dogfood MCP` retrieved the real MCP dogfood memory object `know:c8e702c662654692898a144a8352b719` at rank 2. The existing lexical search did not retrieve that object for the same query.

## Dependency Finding

FastEmbed in the tested Python environment does not expose `BAAI/bge-m3` through `TextEmbedding`.

FastEmbed's strongest local fallback in this environment is `intfloat/multilingual-e5-large`. It remains a useful fallback, but BGE-M3 currently requires FlagEmbedding.

## Model Comparison

The spike compared four local models against the same five Chinese/English eval cases.

Command:

```bash
uv run --with lancedb --with FlagEmbedding --with fastembed python experiments/semantic_retrieval_spike.py \
  --compare bge-m3 \
  --compare e5-large \
  --compare mpnet-base \
  --compare minilm \
  --eval-cases experiments/semantic_retrieval_eval_cases.json \
  --db-path /tmp/memory-semantic-compare-all \
  --clean
```

Results:

| Preset | Runtime | Vector dim | Passed | Mean rank | Cached ready | Embed 6 records | Query 5 cases | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `bge-m3` | FlagEmbedding | 1024 | 5/5 | 1.4 | 5.9s | 0.44s | 0.11s | Best rank quality; use as default candidate. |
| `mpnet-base` | FastEmbed | 768 | 5/5 | 1.6 | 59.6s first run | 0.06s | 0.06s | Strong lightweight-ish fallback after download. |
| `e5-large` | FastEmbed | 1024 | 5/5 | 2.0 | 78.9s first run | 0.20s | 0.13s | Strong fallback, but rank quality was weaker on these cases. |
| `minilm` | FastEmbed | 384 | 4/5 | 1.75 on hits | 0.4s cached | 0.02s | 0.03s | Fast, but missed the graph-backend query; not suitable as default. |

Interpretation:

- `BAAI/bge-m3` should remain the default semantic quality baseline.
- `paraphrase-multilingual-mpnet-base-v2` is worth keeping as the practical speed fallback candidate.
- `intfloat/multilingual-e5-large` is viable but not clearly better than mpnet-base in this small eval.
- `paraphrase-multilingual-MiniLM-L12-v2` is useful for smoke tests or low-resource fallback, not for core memory retrieval.

The eval set is still small. Before finalizing production defaults, expand it with real user and agent queries collected from dogfood sessions.

## Architecture Decision

Proceed with a quality-first semantic retrieval design:

- default semantic model candidate: `BAAI/bge-m3`
- runtime candidate: FlagEmbedding
- speed fallback candidate: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` through FastEmbed
- vector index: LanceDB
- storage role: derived index only
- canonical memory remains in objects, patches, and audit
- query mode: hybrid lexical + semantic + graph/governance filters

Do not build a generic vector database plugin system now. LanceDB is sufficient for the current local personal-use target. Future replacement should be treated as a deliberate refactor if needed.

## Implementation Implications

The next production slice should add:

- optional `semantic` dependency group with LanceDB and FlagEmbedding
- semantic chunk projection from canonical memory objects
- LanceDB rebuild from `memory_maintain reindex`
- semantic query path behind `memory_query search`
- score fusion with existing lexical results
- tests that prove the `Codex dogfood MCP` style query is recovered by semantic search

The existing lexical normalization and graph retrieval should stay in place. Semantic retrieval improves recall; it does not replace exact matching, scope/status filters, evidence governance, or graph expansion.
