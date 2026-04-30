from __future__ import annotations

from pathlib import Path

from memory_substrate.application.maintain.lifecycle import MaintenanceLifecycle
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


REFERENCE_TIME = "2026-04-30T00:00:00+00:00"

EXPECTED_COUNTS = {
    "promote_candidates": 1,
    "low_evidence_candidates": 1,
    "stale_candidates": 1,
    "duplicate_groups": 1,
    "soft_duplicate_candidates": 1,
}


def run_maintenance_dogfood_benchmark(root: str | Path) -> dict:
    """Run a deterministic local benchmark for read-only maintenance signals."""
    root = Path(root)
    _seed_maintenance_cases(root)
    report = MaintenanceLifecycle(root).report(
        min_confidence=0.75,
        min_evidence=1,
        reference_time=REFERENCE_TIME,
        stale_after_days=30,
    )
    data = report["data"]
    observed_counts = {
        "promote_candidates": len(data["promote_candidate_ids"]),
        "low_evidence_candidates": len(data["low_evidence_candidate_ids"]),
        "stale_candidates": len(data["stale_candidate_ids"]),
        "duplicate_groups": len(data["duplicate_groups"]),
        "soft_duplicate_candidates": len(data["soft_duplicate_candidates"]),
    }
    checks = [
        _check("promote_candidate", EXPECTED_COUNTS["promote_candidates"], observed_counts["promote_candidates"]),
        _check("low_evidence_candidate", EXPECTED_COUNTS["low_evidence_candidates"], observed_counts["low_evidence_candidates"]),
        _check("stale_candidate", EXPECTED_COUNTS["stale_candidates"], observed_counts["stale_candidates"]),
        _check("structured_duplicate_group", EXPECTED_COUNTS["duplicate_groups"], observed_counts["duplicate_groups"]),
        _check("soft_duplicate_candidate", EXPECTED_COUNTS["soft_duplicate_candidates"], observed_counts["soft_duplicate_candidates"]),
    ]
    return {
        "status": "completed",
        "case_count": len(checks),
        "mutated": False,
        "reference_time": REFERENCE_TIME,
        "expected_counts": EXPECTED_COUNTS,
        "observed_counts": observed_counts,
        "checks": checks,
    }


def _check(name: str, expected: int, actual: int) -> dict:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def _seed_maintenance_cases(root: Path) -> None:
    repository = FsObjectRepository(root)
    source_id = "src:bench-maintenance"
    subject_id = "node:bench-project"
    timestamp = "2026-01-01T00:00:00+00:00"
    repository.save(
        "source",
        {
            "id": source_id,
            "kind": "benchmark",
            "title": "Maintenance benchmark source",
            "origin": {"benchmark": "maintenance_dogfood"},
            "identity_key": "source|benchmark|maintenance_dogfood",
            "fingerprint": "maintenance-dogfood",
            "content_type": "text",
            "payload": {"text": "Maintenance benchmark evidence."},
            "segments": [
                {
                    "segment_id": "seg:1",
                    "locator": {"kind": "benchmark"},
                    "excerpt": "Maintenance benchmark evidence.",
                    "hash": "seg-1",
                }
            ],
            "metadata": {},
            "status": "active",
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    repository.save(
        "node",
        {
            "id": subject_id,
            "kind": "project",
            "name": "Maintenance Benchmark Project",
            "slug": "maintenance-benchmark-project",
            "identity_key": "node|benchmark|maintenance",
            "aliases": [],
            "summary": "Synthetic benchmark scope for maintenance signals.",
            "status": "active",
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )

    _save_knowledge(
        repository,
        "know:bench-promote",
        title="Promotable candidate",
        summary="Candidate has confidence, evidence, and a subject.",
        status="candidate",
        subject_id=subject_id,
        source_id=source_id,
        predicate="promotable",
        value=True,
        confidence=0.9,
    )
    _save_knowledge(
        repository,
        "know:bench-low-evidence",
        title="Low evidence candidate",
        summary="Candidate has confidence and subject but no evidence.",
        status="candidate",
        subject_id=subject_id,
        source_id=None,
        predicate="low_evidence",
        value=True,
        confidence=0.9,
    )
    _save_knowledge(
        repository,
        "know:bench-stale",
        title="Stale active fact",
        summary="Old verified fact should be reported stale.",
        status="active",
        subject_id=subject_id,
        source_id=source_id,
        predicate="stale",
        value=True,
        confidence=0.8,
        last_verified_at="2026-01-01T00:00:00+00:00",
    )
    for object_id, title in (
        ("know:bench-duplicate-a", "Structured duplicate A"),
        ("know:bench-duplicate-b", "Structured duplicate B"),
    ):
        _save_knowledge(
            repository,
            object_id,
            title=title,
            summary="Structured duplicate benchmark fact.",
            status="active",
            subject_id=subject_id,
            source_id=source_id,
            predicate="duplicate_claim",
            value="same",
            confidence=0.8,
        )
    _save_unstructured_knowledge(
        repository,
        "know:bench-soft-a",
        title="Use Kuzu as local graph backend",
        summary="Kuzu is selected as the local graph backend for lightweight prototypes.",
        status="active",
        confidence=0.9,
    )
    _save_unstructured_knowledge(
        repository,
        "know:bench-soft-b",
        title="Kuzu remains local graph backend",
        summary="The local prototype graph backend should stay on Kuzu.",
        status="candidate",
        confidence=0.7,
    )


def _save_knowledge(
    repository: FsObjectRepository,
    object_id: str,
    *,
    title: str,
    summary: str,
    status: str,
    subject_id: str,
    source_id: str | None,
    predicate: str,
    value,
    confidence: float,
    last_verified_at: str | None = None,
) -> None:
    timestamp = "2026-01-01T00:00:00+00:00"
    repository.save(
        "knowledge",
        {
            "id": object_id,
            "kind": "fact",
            "title": title,
            "summary": summary,
            "identity_key": f"knowledge|benchmark|{object_id}",
            "subject_refs": [subject_id],
            "evidence_refs": [{"source_id": source_id, "segment_id": "seg:1"}] if source_id else [],
            "payload": {
                "subject": subject_id,
                "predicate": predicate,
                "value": value,
                "object": None,
            },
            "status": status,
            "confidence": confidence,
            "valid_from": timestamp,
            "valid_until": None,
            "last_verified_at": last_verified_at,
            "scope_refs": ["scope:maintenance-benchmark"],
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )


def _save_unstructured_knowledge(
    repository: FsObjectRepository,
    object_id: str,
    *,
    title: str,
    summary: str,
    status: str,
    confidence: float,
) -> None:
    timestamp = "2026-01-01T00:00:00+00:00"
    repository.save(
        "knowledge",
        {
            "id": object_id,
            "kind": "decision",
            "title": title,
            "summary": summary,
            "identity_key": f"knowledge|benchmark|{object_id}",
            "subject_refs": [],
            "evidence_refs": [],
            "payload": {},
            "status": status,
            "confidence": confidence,
            "valid_from": timestamp,
            "valid_until": None,
            "last_verified_at": None,
            "scope_refs": ["scope:maintenance-benchmark"],
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
