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
            "insights": self._insights(),
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

    def _insights(self) -> dict[str, list[dict]]:
        exported = self.graph_backend.export_scope("*")
        records = self._graph_records(exported)
        relations = [relation for relation in exported.get("relations", []) if isinstance(relation, dict)]
        adjacency = self._adjacency(records, relations)
        components = self._components(records, adjacency)
        return {
            "isolated_nodes": self._isolated_nodes(records, adjacency),
            "sparse_clusters": self._sparse_clusters(components, adjacency),
            "bridge_nodes": self._bridge_nodes(records, adjacency),
            "weakly_connected_scopes": self._weakly_connected_scopes(records, adjacency),
        }

    def _graph_records(self, exported: dict[str, Any]) -> dict[str, dict]:
        records: dict[str, dict] = {}
        for bucket in ("entities", "knowledge", "episodes"):
            for record in exported.get(bucket, []):
                if isinstance(record, dict) and record.get("id"):
                    records[str(record["id"])] = record
        return records

    def _adjacency(self, records: dict[str, dict], relations: list[dict]) -> dict[str, set[str]]:
        adjacency = {record_id: set() for record_id in records}
        for relation in relations:
            source_id = str(relation.get("source_id") or "")
            target_id = str(relation.get("target_id") or "")
            if not source_id or not target_id:
                continue
            adjacency.setdefault(source_id, set()).add(target_id)
            adjacency.setdefault(target_id, set()).add(source_id)
        return adjacency

    def _isolated_nodes(self, records: dict[str, dict], adjacency: dict[str, set[str]]) -> list[dict]:
        isolated = []
        for record_id, record in records.items():
            if adjacency.get(record_id):
                continue
            isolated.append(self._record_summary(record, degree=0))
        return sorted(isolated, key=lambda item: item["id"])[:20]

    def _sparse_clusters(self, components: list[set[str]], adjacency: dict[str, set[str]]) -> list[dict]:
        sparse = []
        for component in components:
            if len(component) < 3:
                continue
            edge_count = self._component_edge_count(component, adjacency)
            possible_edges = len(component) * (len(component) - 1) / 2
            density = edge_count / possible_edges if possible_edges else 0.0
            if density > 0.5:
                continue
            sparse.append(
                {
                    "node_ids": sorted(component)[:20],
                    "node_count": len(component),
                    "edge_count": edge_count,
                    "density": round(density, 3),
                }
            )
        return sorted(sparse, key=lambda item: (item["density"], -item["node_count"], item["node_ids"]))[:10]

    def _bridge_nodes(self, records: dict[str, dict], adjacency: dict[str, set[str]]) -> list[dict]:
        bridges = []
        for component in self._components(records, adjacency):
            if len(component) < 3:
                continue
            for record_id in component:
                neighbors = adjacency.get(record_id, set()).intersection(component)
                if len(neighbors) < 2:
                    continue
                remaining = set(component)
                remaining.remove(record_id)
                if self._component_count_within(remaining, adjacency) <= 1:
                    continue
                bridges.append(self._record_summary(records.get(record_id, {"id": record_id}), degree=len(adjacency[record_id])))
        return sorted(bridges, key=lambda item: (-item["degree"], item["id"]))[:20]

    def _weakly_connected_scopes(self, records: dict[str, dict], adjacency: dict[str, set[str]]) -> list[dict]:
        scoped: dict[str, set[str]] = {}
        for record_id, record in records.items():
            for scope_ref in record.get("scope_refs", []):
                scoped.setdefault(str(scope_ref), set()).add(record_id)
        weak = []
        for scope_ref, node_ids in scoped.items():
            if len(node_ids) < 2:
                continue
            edge_count = self._component_edge_count(node_ids, adjacency)
            if edge_count >= max(1, len(node_ids) - 1):
                continue
            weak.append(
                {
                    "scope_ref": scope_ref,
                    "node_count": len(node_ids),
                    "edge_count": edge_count,
                    "sample_node_ids": sorted(node_ids)[:10],
                }
            )
        return sorted(weak, key=lambda item: (-item["node_count"], item["scope_ref"]))[:10]

    def _components(self, records: dict[str, dict], adjacency: dict[str, set[str]]) -> list[set[str]]:
        unseen = set(records) | set(adjacency)
        components = []
        while unseen:
            start = unseen.pop()
            component = {start}
            stack = [start]
            while stack:
                node_id = stack.pop()
                for neighbor in adjacency.get(node_id, set()):
                    if neighbor not in unseen:
                        continue
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
            components.append(component)
        return components

    def _component_edge_count(self, component: set[str], adjacency: dict[str, set[str]]) -> int:
        return sum(len(adjacency.get(node_id, set()).intersection(component)) for node_id in component) // 2

    def _component_count_within(self, node_ids: set[str], adjacency: dict[str, set[str]]) -> int:
        unseen = set(node_ids)
        count = 0
        while unseen:
            count += 1
            start = unseen.pop()
            stack = [start]
            while stack:
                node_id = stack.pop()
                for neighbor in adjacency.get(node_id, set()).intersection(node_ids):
                    if neighbor not in unseen:
                        continue
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        return count

    def _record_summary(self, record: dict, degree: int) -> dict:
        return {
            "id": str(record.get("id")),
            "kind": record.get("kind"),
            "title": record.get("title") or record.get("name") or record.get("id"),
            "status": record.get("status"),
            "degree": degree,
            "scope_refs": record.get("scope_refs", []),
        }
