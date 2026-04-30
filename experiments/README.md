# Experiments

This directory contains runnable spikes that are not part of the default package runtime.

## Semantic Retrieval Spike

Run the LanceDB + FlagEmbedding/BGE-M3 spike without adding optional dependencies to the project:

```bash
uv run --with lancedb --with FlagEmbedding python experiments/semantic_retrieval_spike.py \
  --eval-cases experiments/semantic_retrieval_eval_cases.json
```

FastEmbed does not expose `BAAI/bge-m3` in the tested Python environment. Use multilingual E5-large as the strong FastEmbed fallback:

```bash
uv run --with lancedb --with fastembed python experiments/semantic_retrieval_spike.py \
  --provider fastembed \
  --model intfloat/multilingual-e5-large \
  --eval-cases experiments/semantic_retrieval_eval_cases.json
```

To include the current canonical memory root in the temporary index:

```bash
uv run --with lancedb --with FlagEmbedding python experiments/semantic_retrieval_spike.py \
  --include-memory-root \
  --probe-query "Codex dogfood MCP" \
  --eval-cases experiments/semantic_retrieval_eval_cases.json
```

The spike stores only derived chunks and vectors in LanceDB. Canonical memory objects remain under the memory root and can rebuild the semantic index.

Compare the quality baseline, strong FastEmbed fallback, and lightweight fallbacks:

```bash
uv run --with lancedb --with FlagEmbedding --with fastembed python experiments/semantic_retrieval_spike.py \
  --compare bge-m3 \
  --compare e5-large \
  --compare mpnet-base \
  --compare minilm \
  --eval-cases experiments/semantic_retrieval_eval_cases.json
```

## MCP Semantic Demo

Run the real MCP server path after semantic or MCP schema changes:

```bash
uv run --extra semantic python experiments/mcp_semantic_demo.py
```

The demo uses a temporary `MEMORY_SUBSTRATE_ROOT`, intentionally does not pass `root` in normal tool calls, verifies that rogue `root` arguments are rejected, writes one knowledge object, rebuilds the LanceDB semantic index, and confirms semantic search retrieves the object.

The semantic loader tries cached BGE-M3 files first and downloads only when the cache is missing. Add `HF_HUB_OFFLINE=1` and `--offline` when you want the demo to fail fast if the model is not already cached.

## Retrieval Benchmark Harness

The packaged benchmark helper seeds a temporary/local memory root with small planted-needle records and reports recall per retrieval stream without network access:

```bash
uv run --group dev python -m pytest tests/test_retrieval_benchmark.py
```

Programmatic entrypoint:

```python
from memory_substrate.experiments.retrieval_benchmark import run_planted_needle_benchmark

result = run_planted_needle_benchmark("/tmp/memory-benchmark")
```

The default smoke path reports lexical recall and marks semantic/hybrid streams as `not_configured`. Pass a configured semantic service only when intentionally evaluating hybrid retrieval.

## Maintenance Dogfood Benchmark

The maintenance benchmark helper seeds a temporary/local memory root with deterministic lifecycle cases and runs read-only `memory_maintain report` logic. It checks promotable candidates, low-evidence candidates, stale candidates, structured duplicate groups, and soft duplicate candidates without network access or optional semantic models:

```python
from memory_substrate.experiments.maintenance_benchmark import run_maintenance_dogfood_benchmark

result = run_maintenance_dogfood_benchmark("/tmp/memory-maintenance-benchmark")
```

The helper does not mutate maintenance state beyond seeding the benchmark root. Use it as a local regression signal when changing lifecycle, duplicate, or report logic.

## End-To-End Dogfood Acceptance

The end-to-end dogfood helper seeds a small repo and exercises the MCP dispatch loop: `memory_ingest`, `memory_query`, `memory_remember`, `memory_maintain report`, `memory_maintain reindex`, then `memory_query context`.

```python
from memory_substrate.experiments.end_to_end_dogfood import run_end_to_end_dogfood_acceptance

result = run_end_to_end_dogfood_acceptance("/tmp/memory-e2e-dogfood")
```

Use it as a deterministic local acceptance signal when changing MCP schemas, compact response policies, ingest suggestions, durable write governance, maintenance reports, or context assembly. The helper mutates only the supplied temporary/local root and does not require network access or optional semantic models.
