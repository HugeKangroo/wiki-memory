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
