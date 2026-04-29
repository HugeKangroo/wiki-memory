from __future__ import annotations

from pathlib import Path
from time import perf_counter

from memory_substrate.application.query.service import QueryService
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


PLANTED_NEEDLES = [
    {
        "id": "know:bench-lancedb-derived",
        "kind": "decision",
        "title": "LanceDB is a derived index",
        "summary": "Canonical memory remains in object storage; LanceDB can be rebuilt.",
        "query": "which storage is derived and rebuildable",
    },
    {
        "id": "know:bench-agent-prompt-sanitizer",
        "kind": "implementation_note",
        "title": "Query sanitizer protects MCP retrieval",
        "summary": "Long agent prompts are shortened before query planning.",
        "query": "agent prompt sanitizer retrieval",
    },
    {
        "id": "know:bench-evidence-not-memory",
        "kind": "concept",
        "title": "Evidence is not durable memory",
        "summary": "Source chunks support memory claims but do not replace governed memory objects.",
        "query": "evidence source chunks durable memory",
    },
]


def run_planted_needle_benchmark(root: str | Path, max_items: int = 5, semantic_index=None) -> dict:
    root = Path(root)
    repository = FsObjectRepository(root)
    for case in PLANTED_NEEDLES:
        repository.save(
            "knowledge",
            {
                "id": case["id"],
                "kind": case["kind"],
                "title": case["title"],
                "summary": case["summary"],
                "status": "active",
                "confidence": 1.0,
            },
        )

    lexical = _run_stream(root=root, max_items=max_items, semantic_index=None)
    if semantic_index is None:
        semantic = {"status": "not_configured"}
        hybrid = {"status": "not_configured"}
    else:
        hybrid = _run_stream(root=root, max_items=max_items, semantic_index=semantic_index)
        semantic = {"status": "covered_by_hybrid_query_service"}

    return {
        "case_count": len(PLANTED_NEEDLES),
        "streams": {
            "lexical": lexical["summary"],
            "semantic": semantic,
            "hybrid": hybrid["summary"] if semantic_index is not None else hybrid,
        },
        "cases": lexical["cases"],
    }


def _run_stream(root: Path, max_items: int, semantic_index=None) -> dict:
    service = QueryService(root, semantic_index=semantic_index) if semantic_index is not None else QueryService(root)
    cases = []
    hits = 0
    start = perf_counter()
    for case in PLANTED_NEEDLES:
        result = service.search(case["query"], max_items=max_items)
        top_ids = [item["id"] for item in result["data"]["items"]]
        matched = case["id"] in top_ids
        hits += 1 if matched else 0
        cases.append(
            {
                "query": case["query"],
                "expected_id": case["id"],
                "top_ids": top_ids,
                "matched": matched,
            }
        )
    elapsed_ms = round((perf_counter() - start) * 1000, 3)
    return {
        "summary": {
            "status": "completed",
            f"recall_at_{max_items}": round(hits / len(PLANTED_NEEDLES), 3),
            "latency_ms": elapsed_ms,
        },
        "cases": cases,
    }
