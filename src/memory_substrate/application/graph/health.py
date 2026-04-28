from __future__ import annotations

from pathlib import Path
from typing import Any

from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


CANONICAL_GRAPH_COUNTS = {
    "episodes": ("source", "episode"),
    "entities": ("node", "entity", "memory_scope", "activity", "work_item"),
    "knowledge": ("knowledge",),
}


class GraphHealthReporter:
    """Build read-only health summaries for a configured graph backend."""

    def __init__(self, root: str | Path, graph_backend) -> None:
        self.repository = FsObjectRepository(root)
        self.graph_backend = graph_backend

    def report(self) -> dict[str, Any]:
        backend_health = self.graph_backend.health()
        backend_counts = dict(backend_health.get("counts", {}))
        canonical_counts = self._canonical_counts()
        missing = {
            bucket: max(canonical_counts.get(bucket, 0) - int(backend_counts.get(bucket, 0)), 0)
            for bucket in canonical_counts
        }
        return {
            "status": backend_health.get("status", "unknown"),
            "backend": self.graph_backend.__class__.__name__,
            "path": backend_health.get("path"),
            "canonical_counts": canonical_counts,
            "backend_counts": backend_counts,
            "missing_from_backend": missing,
            "stub_nodes": self._stub_nodes(),
        }

    def _canonical_counts(self) -> dict[str, int]:
        return {
            bucket: sum(len(self.repository.list(object_type)) for object_type in object_types)
            for bucket, object_types in CANONICAL_GRAPH_COUNTS.items()
        } | {"relations": len(self.repository.list("relation"))}

    def _stub_nodes(self) -> int:
        exported = self.graph_backend.export_scope("*")
        entities = exported.get("entities", [])
        return sum(1 for item in entities if item.get("status") == "stub" or item.get("kind") == "stub")
