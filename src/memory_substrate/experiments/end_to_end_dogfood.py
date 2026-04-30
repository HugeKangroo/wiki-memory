from __future__ import annotations

import json
from pathlib import Path

from memory_substrate.interfaces.mcp.tools import memory_ingest, memory_maintain, memory_query, memory_remember


def run_end_to_end_dogfood_acceptance(root: str | Path) -> dict:
    """Run a deterministic local acceptance flow through the MCP dispatch layer."""
    root = Path(root)
    memory_root = root / "memory"
    repo_path = root / "input-repo"
    _seed_repo(repo_path)

    ingest = memory_ingest(memory_root, "repo", {"path": str(repo_path)})
    suggestions = ingest["memory_suggestions"]
    candidate = _find_candidate(suggestions["concept_candidates"], "Context Pack")

    search = memory_query(memory_root, "search", {"query": "Context Pack working set agents"}, {"max_items": 5})
    full_page = memory_query(memory_root, "page", {"id": ingest["source_id"]}, {"detail": "full"})

    evidence_refs = candidate["evidence_refs"]
    subject_refs = ingest["node_ids"][:1] or [ingest["source_id"]]
    remember = memory_remember(
        memory_root,
        "knowledge",
        {
            "kind": "concept",
            "title": "Context Pack",
            "summary": (
                "Context Pack is a compact working set of decisions, procedures, evidence, "
                "and open work that agents load before implementation."
            ),
            "reason": "Dogfood acceptance reviewed the ingested candidate and this concept affects future agent work.",
            "memory_source": "agent_inferred",
            "scope_refs": subject_refs,
            "subject_refs": subject_refs,
            "evidence_refs": evidence_refs,
            "status": "candidate",
            "confidence": 0.82,
        },
    )
    knowledge_id = remember["knowledge_id"]

    report = memory_maintain(memory_root, "report", {"min_confidence": 0.75, "min_evidence": 1})
    reindex = memory_maintain(memory_root, "reindex")
    context = memory_query(
        memory_root,
        "context",
        {"task": "How should agents use the Context Pack before implementation?"},
        {"max_items": 8},
    )

    observed = {
        "ingest_status": ingest["status"],
        "candidate_detail": candidate.get("detail"),
        "search_item_ids": [item["id"] for item in search["data"]["items"]],
        "full_page_result_type": full_page["result_type"],
        "full_page_status": full_page.get("status"),
        "remember_status": remember["status"],
        "promote_candidate_ids": report["data"]["promote_candidate_ids"],
        "reindex_result_type": reindex["result_type"],
        "context_item_ids": [item["id"] for item in context["data"]["items"]],
    }
    checks = [
        _check("repo_ingest_completed", "completed", observed["ingest_status"]),
        _check("ingest_candidate_is_compact", "compact", observed["candidate_detail"]),
        _check_contains("search_finds_ingested_repo", observed["search_item_ids"], ingest["source_id"]),
        _check(
            "repo_full_page_is_unsupported",
            ("page_unavailable", "unsupported"),
            (observed["full_page_result_type"], observed["full_page_status"]),
        ),
        _check("remember_candidate_created", "candidate", observed["remember_status"]),
        _check_contains("maintain_report_sees_promotable_memory", observed["promote_candidate_ids"], knowledge_id),
        _check("reindex_completed", "reindex_result", observed["reindex_result_type"]),
        _check_contains("context_returns_remembered_memory", observed["context_item_ids"], knowledge_id),
    ]
    return {
        "status": "completed" if all(check["passed"] for check in checks) else "failed",
        "case_count": len(checks),
        "mutated": True,
        "object_ids": {
            "source_id": ingest["source_id"],
            "knowledge_id": knowledge_id,
            "candidate_title": candidate["title"],
        },
        "payload_sizes": {
            "compact_candidate_chars": len(json.dumps(candidate, ensure_ascii=False)),
            "context_chars": len(json.dumps(context, ensure_ascii=False)),
        },
        "observed": observed,
        "checks": checks,
    }


def _seed_repo(repo_path: Path) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    (repo_path / "README.md").write_text(
        "# Dogfood Acceptance\n"
        "\n"
        "Context Pack is the working set that agents should load before implementation.\n"
        "\n"
        "## Context Pack\n"
        "\n"
        "The Context Pack contains decisions, procedures, evidence, and open work.\n",
        encoding="utf-8",
    )
    src_dir = repo_path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "agent_flow.py").write_text(
        "def build_context_pack():\n"
        "    return {'sections': ['decisions', 'procedures', 'evidence', 'open_work']}\n",
        encoding="utf-8",
    )


def _find_candidate(candidates: list[dict], title: str) -> dict:
    for candidate in candidates:
        if candidate.get("title") == title:
            return candidate
    raise AssertionError(f"Candidate not found: {title}")


def _check(name: str, expected, actual) -> dict:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def _check_contains(name: str, values: list[str], expected: str) -> dict:
    return {
        "name": name,
        "expected": expected,
        "actual": values,
        "passed": expected in values,
    }
