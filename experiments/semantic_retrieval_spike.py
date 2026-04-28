from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


DEFAULT_PROVIDER = "flagembedding"
DEFAULT_MODEL = "BAAI/bge-m3"
FASTEMBED_STRONG_MODEL = "intfloat/multilingual-e5-large"
DEFAULT_TABLE = "semantic_chunks"
PRESET_MODELS = {
    "bge-m3": ("flagembedding", "BAAI/bge-m3"),
    "e5-large": ("fastembed", "intfloat/multilingual-e5-large"),
    "mpnet-base": ("fastembed", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"),
    "minilm": ("fastembed", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
}

SYNTHETIC_RECORDS = [
    {
        "object_id": "synthetic:local-first",
        "chunk_id": "synthetic:local-first#summary",
        "object_type": "knowledge",
        "kind": "decision",
        "status": "active",
        "scope_refs": ["scope:memory-substrate"],
        "title": "Memory Substrate is local-first",
        "text": "Memory Substrate is local-first and should not require a second hosted LLM API key.",
    },
    {
        "object_id": "synthetic:codex-dogfood",
        "chunk_id": "synthetic:codex-dogfood#summary",
        "object_type": "knowledge",
        "kind": "dogfood",
        "status": "candidate",
        "scope_refs": ["scope:memory-substrate", "scope:dogfood"],
        "title": "Codex can call memory-substrate MCP",
        "text": "Codex dogfood can call memory-substrate MCP from a separate Projects test workspace.",
    },
    {
        "object_id": "synthetic:kuzu",
        "chunk_id": "synthetic:kuzu#summary",
        "object_type": "knowledge",
        "kind": "decision",
        "status": "active",
        "scope_refs": ["scope:memory-substrate"],
        "title": "Kuzu is the local graph backend",
        "text": "Kuzu is the selected lightweight local graph backend for prototypes; Neo4j remains optional for production.",
    },
    {
        "object_id": "synthetic:semantic-index",
        "chunk_id": "synthetic:semantic-index#summary",
        "object_type": "knowledge",
        "kind": "architecture",
        "status": "active",
        "scope_refs": ["scope:memory-substrate"],
        "title": "LanceDB stores derived semantic vectors",
        "text": "LanceDB should store derived semantic chunks and embeddings, not canonical memory objects or audit history.",
    },
    {
        "object_id": "synthetic:canonical-storage",
        "chunk_id": "synthetic:canonical-storage#summary",
        "object_type": "knowledge",
        "kind": "architecture",
        "status": "active",
        "scope_refs": ["scope:memory-substrate"],
        "title": "Canonical data remains in objects, patches, and audit",
        "text": "记忆系统的 canonical data 存放在 memory objects、patches 和 audit 中；向量索引可以删除并重建。",
    },
    {
        "object_id": "synthetic:soft-duplicates",
        "chunk_id": "synthetic:soft-duplicates#summary",
        "object_type": "knowledge",
        "kind": "procedure",
        "status": "active",
        "scope_refs": ["scope:memory-substrate"],
        "title": "Soft duplicates are review candidates",
        "text": "Unstructured title and summary duplicates should return possible_duplicates for review instead of being merged automatically.",
    },
]

DEFAULT_EVAL_CASES = [
    {"query": "是否需要第二个模型 API key", "expected_object_id": "synthetic:local-first"},
    {"query": "Codex 能不能调用记忆 MCP", "expected_object_id": "synthetic:codex-dogfood"},
    {"query": "向量数据库是不是原始数据源", "expected_object_id": "synthetic:semantic-index"},
    {"query": "知识图谱本地后端用什么", "expected_object_id": "synthetic:kuzu"},
    {"query": "重复知识如何处理", "expected_object_id": "synthetic:soft-duplicates"},
]


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _chunk_text(object_type: str, obj: dict[str, Any]) -> str:
    title = str(obj.get("title") or obj.get("name") or obj.get("id") or "")
    summary = str(obj.get("summary") or "")
    payload = obj.get("payload", {})
    metadata = obj.get("metadata", {})
    return "\n".join(part for part in (title, summary, _json_text(payload), _json_text(metadata)) if part)


def _memory_records(root: Path, limit: int | None) -> list[dict[str, Any]]:
    repository = FsObjectRepository(root)
    records: list[dict[str, Any]] = []
    for object_type in ("knowledge", "work_item", "activity", "node"):
        for obj in repository.list(object_type):
            object_id = str(obj["id"])
            records.append(
                {
                    "object_id": object_id,
                    "chunk_id": f"{object_id}#object",
                    "object_type": object_type,
                    "kind": str(obj.get("kind", object_type)),
                    "status": str(obj.get("status") or obj.get("lifecycle_state") or ""),
                    "scope_refs": [str(ref) for ref in obj.get("scope_refs", [])],
                    "title": str(obj.get("title") or obj.get("name") or object_id),
                    "text": _chunk_text(object_type, obj),
                }
            )
            if limit is not None and len(records) >= limit:
                return records
    for source in repository.list("source"):
        object_id = str(source["id"])
        for segment in source.get("segments", []):
            segment_id = str(segment.get("segment_id") or "segment")
            text = "\n".join(
                part
                for part in (
                    str(source.get("title") or object_id),
                    str(segment.get("excerpt") or ""),
                )
                if part
            )
            records.append(
                {
                    "object_id": object_id,
                    "chunk_id": f"{object_id}#{segment_id}",
                    "object_type": "source",
                    "kind": str(source.get("kind", "source")),
                    "status": str(source.get("status") or ""),
                    "scope_refs": [],
                    "title": str(source.get("title") or object_id),
                    "text": text,
                }
            )
            if limit is not None and len(records) >= limit:
                return records
    return records


def _load_eval_cases(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return DEFAULT_EVAL_CASES
    return json.loads(path.read_text(encoding="utf-8"))


def _embed_passages(provider: str, model: Any, texts: list[str], batch_size: int) -> list[list[float]]:
    if provider == "flagembedding":
        output = model.encode(
            texts,
            batch_size=batch_size,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return [embedding.tolist() for embedding in output["dense_vecs"]]
    if hasattr(model, "passage_embed"):
        embeddings = model.passage_embed(texts, batch_size=batch_size)
    else:
        embeddings = model.embed(texts, batch_size=batch_size)
    return [embedding.tolist() for embedding in embeddings]


def _embed_query(provider: str, model: Any, query: str) -> list[float]:
    if provider == "flagembedding":
        output = model.encode(
            [query],
            batch_size=1,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return output["dense_vecs"][0].tolist()
    if hasattr(model, "query_embed"):
        embedding = next(iter(model.query_embed(query)))
    else:
        embedding = next(iter(model.embed([query])))
    return embedding.tolist()


def _create_embedding_model(provider: str, model_name: str) -> Any:
    if provider == "fastembed":
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise SystemExit(
                "Missing FastEmbed dependency. Run:\n"
                "  uv run --with lancedb --with fastembed python experiments/semantic_retrieval_spike.py\n"
            ) from exc
        supported = {model["model"] for model in TextEmbedding.list_supported_models()}
        if model_name not in supported:
            raise SystemExit(
                f"FastEmbed TextEmbedding does not support {model_name!r} in this environment.\n"
                "Use --model intfloat/multilingual-e5-large, or try --provider flagembedding --model BAAI/bge-m3."
            )
        return TextEmbedding(model_name=model_name)

    if provider == "flagembedding":
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise SystemExit(
                "Missing FlagEmbedding dependency. Run:\n"
                "  uv run --with lancedb --with FlagEmbedding python experiments/semantic_retrieval_spike.py "
                "--provider flagembedding --model BAAI/bge-m3\n"
            ) from exc
        return BGEM3FlagModel(model_name, use_fp16=True)

    raise ValueError(f"Unsupported provider: {provider}")


def _import_lancedb() -> Any:
    try:
        import lancedb
    except ImportError as exc:
        raise SystemExit(
            "Missing LanceDB dependency. Run with --with lancedb.\n"
        ) from exc
    return lancedb


def _run_once(
    *,
    provider: str,
    model_name: str,
    records: list[dict[str, Any]],
    eval_cases: list[dict[str, str]],
    db_root: Path,
    limit: int,
    batch_size: int,
    probe_queries: list[str],
) -> dict[str, Any]:
    lancedb = _import_lancedb()
    if db_root.exists():
        shutil.rmtree(db_root)
    db_root.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    model = _create_embedding_model(provider, model_name)
    model_ready_seconds = time.perf_counter() - started

    texts = [record["text"] for record in records]
    embed_started = time.perf_counter()
    vectors = _embed_passages(provider, model, texts, batch_size=batch_size)
    embed_seconds = time.perf_counter() - embed_started
    rows = [{**record, "vector": vector} for record, vector in zip(records, vectors, strict=True)]

    db = lancedb.connect(str(db_root))
    table = db.create_table(DEFAULT_TABLE, data=rows, mode="overwrite")

    case_results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    query_started = time.perf_counter()
    for case in eval_cases:
        query_vector = _embed_query(provider, model, case["query"])
        rows = (
            table.search(query_vector)
            .distance_type("cosine")
            .select(["object_id", "chunk_id", "title", "object_type", "kind", "status", "text"])
            .limit(limit)
            .to_list()
        )
        object_ids = [row["object_id"] for row in rows]
        passed = case["expected_object_id"] in object_ids
        result = {
            "query": case["query"],
            "expected_object_id": case["expected_object_id"],
            "passed": passed,
            "rank": object_ids.index(case["expected_object_id"]) + 1 if passed else None,
            "top_results": [
                {
                    "object_id": row["object_id"],
                    "title": row["title"],
                    "distance": row.get("_distance"),
                }
                for row in rows
            ],
        }
        case_results.append(result)
        if not passed:
            failures.append(result)
    query_seconds = time.perf_counter() - query_started
    probes: list[dict[str, Any]] = []
    for query in probe_queries:
        query_vector = _embed_query(provider, model, query)
        rows = (
            table.search(query_vector)
            .distance_type("cosine")
            .select(["object_id", "chunk_id", "title", "object_type", "kind", "status", "text"])
            .limit(limit)
            .to_list()
        )
        probes.append(
            {
                "query": query,
                "top_results": [
                    {
                        "object_id": row["object_id"],
                        "title": row["title"],
                        "distance": row.get("_distance"),
                    }
                    for row in rows
                ],
            }
        )

    ranks = [case["rank"] for case in case_results if case["rank"] is not None]
    return {
        "model": model_name,
        "provider": provider,
        "db_path": str(db_root),
        "record_count": len(records),
        "vector_dim": len(vectors[0]) if vectors else None,
        "eval_count": len(eval_cases),
        "passed": len(eval_cases) - len(failures),
        "failed": len(failures),
        "recall_at_limit": round((len(eval_cases) - len(failures)) / len(eval_cases), 3) if eval_cases else None,
        "mean_rank": round(sum(ranks) / len(ranks), 3) if ranks else None,
        "model_ready_seconds": round(model_ready_seconds, 3),
        "embed_seconds": round(embed_seconds, 3),
        "query_seconds": round(query_seconds, 3),
        "cases": case_results,
        "probes": probes,
    }


def run(args: argparse.Namespace) -> int:
    records = list(SYNTHETIC_RECORDS)
    if args.include_memory_root:
        records.extend(_memory_records(Path(args.root).expanduser(), args.max_memory_objects))
    if not records:
        print("No records to index.")
        return 1

    eval_cases = _load_eval_cases(args.eval_cases)
    db_root = Path(args.db_path).expanduser() if args.db_path else Path(tempfile.mkdtemp(prefix="memory-semantic-spike-"))
    if db_root.exists() and args.clean and not args.compare:
        shutil.rmtree(db_root)

    if args.compare:
        summaries: list[dict[str, Any]] = []
        for preset in args.compare:
            if preset not in PRESET_MODELS:
                supported = ", ".join(sorted(PRESET_MODELS))
                raise SystemExit(f"Unknown compare preset {preset!r}. Supported presets: {supported}")
            provider, model_name = PRESET_MODELS[preset]
            summary = _run_once(
                provider=provider,
                model_name=model_name,
                records=records,
                eval_cases=eval_cases,
                db_root=db_root / preset,
                limit=args.limit,
                batch_size=args.batch_size,
                probe_queries=args.probe_query,
            )
            summary["preset"] = preset
            summaries.append(summary)
        comparison = {
            "record_count": len(records),
            "eval_count": len(eval_cases),
            "models": summaries,
        }
        print(json.dumps(comparison, ensure_ascii=False, indent=2))
        return 0

    summary = _run_once(
        provider=args.provider,
        model_name=args.model,
        records=records,
        eval_cases=eval_cases,
        db_root=db_root,
        limit=args.limit,
        batch_size=args.batch_size,
        probe_queries=args.probe_query,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spike LanceDB + FastEmbed/BGE-M3 semantic retrieval.")
    parser.add_argument("--provider", choices=("fastembed", "flagembedding"), default=DEFAULT_PROVIDER, help=f"Embedding runtime. Default: {DEFAULT_PROVIDER}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Embedding model name. Default: {DEFAULT_MODEL}; use {FASTEMBED_STRONG_MODEL} with --provider fastembed.")
    parser.add_argument("--root", default=str(Path.home() / "memory-substrate"), help="Memory root to optionally include.")
    parser.add_argument("--include-memory-root", action="store_true", help="Also index canonical memory objects from --root.")
    parser.add_argument("--max-memory-objects", type=int, default=200, help="Maximum canonical memory objects to index.")
    parser.add_argument("--eval-cases", type=Path, default=None, help="Optional JSON eval case file.")
    parser.add_argument("--db-path", default=None, help="Optional LanceDB path. Defaults to a temporary directory.")
    parser.add_argument("--clean", action="store_true", help="Delete --db-path before rebuilding.")
    parser.add_argument("--limit", type=int, default=5, help="Top-k result count for each eval query.")
    parser.add_argument("--batch-size", type=int, default=8, help="Embedding batch size.")
    parser.add_argument("--probe-query", action="append", default=[], help="Additional query to print top-k results for without pass/fail scoring.")
    parser.add_argument("--compare", action="append", default=[], help=f"Run a model preset comparison. Supported: {', '.join(sorted(PRESET_MODELS))}.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
