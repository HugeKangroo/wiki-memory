from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory_substrate.infrastructure.storage.fs_utils import read_json, write_json
from memory_substrate.infrastructure.storage.paths import StoragePaths


GRAPH_BUCKETS = ("episodes", "entities", "relations", "knowledge")
OBJECT_TO_BUCKET = {
    "episode": "episodes",
    "entity": "entities",
    "relation": "relations",
    "knowledge": "knowledge",
}
BUCKET_TO_OBJECT = {bucket: object_type for object_type, bucket in OBJECT_TO_BUCKET.items()}


class FileGraphBackend:
    """Deterministic file-backed graph backend for tests and local contract work."""

    def __init__(self, root: str | Path) -> None:
        self.paths = StoragePaths(root)
        self.path = self.paths.indexes_root / "file_graph.json"

    def upsert_episode(self, episode: dict[str, Any]) -> dict[str, Any]:
        return self._upsert("episodes", episode)

    def upsert_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        return self._upsert("entities", entity)

    def upsert_relation(self, relation: dict[str, Any]) -> dict[str, Any]:
        return self._upsert("relations", relation)

    def upsert_knowledge(self, knowledge: dict[str, Any]) -> dict[str, Any]:
        return self._upsert("knowledge", knowledge)

    def link_evidence(self, object_type: str, object_id: str, evidence_refs: list[dict[str, Any]]) -> dict[str, Any]:
        bucket = OBJECT_TO_BUCKET[object_type]
        graph = self._read()
        if object_id not in graph[bucket]:
            raise ValueError(f"{object_type} not found: {object_id}")
        existing = graph[bucket][object_id]
        existing_refs = existing.get("evidence_refs", [])
        existing["evidence_refs"] = self._merge_evidence(existing_refs, evidence_refs)
        self._write(graph)
        return existing

    def search(self, query: str, scope_refs: list[str] | None = None, max_items: int = 10) -> list[dict[str, Any]]:
        q = query.strip().lower()
        if not q:
            return []
        graph = self._read()
        results: list[dict[str, Any]] = []
        for bucket in ("entities", "knowledge", "episodes"):
            object_type = BUCKET_TO_OBJECT[bucket]
            for record in graph[bucket].values():
                if not self._matches_scope(record, scope_refs):
                    continue
                title = str(record.get("title") or record.get("name") or record["id"])
                summary = str(record.get("summary", ""))
                payload = str(record.get("payload", ""))
                haystack = f"{title}\n{summary}\n{payload}".lower()
                if q not in haystack:
                    continue
                results.append(
                    {
                        "object_type": object_type,
                        "id": record["id"],
                        "kind": record.get("kind", object_type),
                        "title": title,
                        "status": record.get("status", "active"),
                        "summary": summary,
                        "evidence_refs": record.get("evidence_refs", []),
                        "score": self._score(q, title.lower(), summary.lower(), payload.lower()),
                    }
                )
        results.sort(key=lambda item: (-item["score"], item["title"], item["id"]))
        return results[:max_items]

    def neighborhood(self, object_id: str, depth: int = 1, max_items: int = 20) -> dict[str, Any]:
        graph = self._read()
        node_ids = {object_id}
        relations: list[dict[str, Any]] = []

        frontier = {object_id}
        for _ in range(max(depth, 1)):
            next_frontier: set[str] = set()
            for relation in graph["relations"].values():
                source_id = str(relation.get("source_id", ""))
                target_id = str(relation.get("target_id", ""))
                if source_id in frontier or target_id in frontier:
                    if relation["id"] not in {item["id"] for item in relations}:
                        relations.append(relation)
                    for node_id in (source_id, target_id):
                        if node_id and node_id not in node_ids:
                            node_ids.add(node_id)
                            next_frontier.add(node_id)
                if len(node_ids) >= max_items:
                    break
            frontier = next_frontier
            if not frontier or len(node_ids) >= max_items:
                break

        nodes = [node for node in (self._find_node(graph, node_id) for node_id in sorted(node_ids)) if node is not None]
        return {
            "root_id": object_id,
            "nodes": nodes[:max_items],
            "relations": relations[:max_items],
        }

    def temporal_lookup(self, reference_time: str, scope_refs: list[str] | None = None) -> dict[str, Any]:
        reference = self._parse_time(reference_time)
        graph = self._read()
        return {
            "reference_time": reference_time,
            "knowledge": [
                record
                for record in graph["knowledge"].values()
                if self._matches_scope(record, scope_refs) and self._valid_at(record, reference)
            ],
            "relations": [
                record
                for record in graph["relations"].values()
                if self._matches_scope(record, scope_refs) and self._valid_at(record, reference)
            ],
        }

    def health(self) -> dict[str, Any]:
        graph = self._read()
        return {
            "status": "ok",
            "path": str(self.path),
            "counts": {bucket: len(graph[bucket]) for bucket in GRAPH_BUCKETS},
        }

    def rebuild(self) -> dict[str, Any]:
        graph = self._read()
        self._write(graph)
        return {
            "status": "noop",
            "path": str(self.path),
            "counts": {bucket: len(graph[bucket]) for bucket in GRAPH_BUCKETS},
        }

    def export_scope(self, scope_ref: str) -> dict[str, Any]:
        graph = self._read()
        if scope_ref == "*":
            return {
                bucket: list(graph[bucket].values())
                for bucket in GRAPH_BUCKETS
            }
        return {
            bucket: [record for record in graph[bucket].values() if scope_ref in record.get("scope_refs", [])]
            for bucket in GRAPH_BUCKETS
        }

    def _upsert(self, bucket: str, record: dict[str, Any]) -> dict[str, Any]:
        if "id" not in record:
            raise ValueError(f"Graph {bucket} record requires id")
        graph = self._read()
        graph[bucket][record["id"]] = dict(record)
        self._write(graph)
        return graph[bucket][record["id"]]

    def _read(self) -> dict[str, dict[str, dict[str, Any]]]:
        if not self.path.exists():
            return {bucket: {} for bucket in GRAPH_BUCKETS}
        graph = read_json(self.path)
        for bucket in GRAPH_BUCKETS:
            graph.setdefault(bucket, {})
        return graph

    def _write(self, graph: dict[str, Any]) -> None:
        write_json(self.path, graph)

    def _find_node(self, graph: dict[str, Any], object_id: str) -> dict[str, Any] | None:
        for bucket in ("entities", "knowledge", "episodes"):
            record = graph[bucket].get(object_id)
            if record is not None:
                result = dict(record)
                result["object_type"] = BUCKET_TO_OBJECT[bucket]
                return result
        return None

    def _matches_scope(self, record: dict[str, Any], scope_refs: list[str] | None) -> bool:
        if not scope_refs:
            return True
        record_scopes = set(record.get("scope_refs", []))
        return bool(record_scopes.intersection(scope_refs))

    def _score(self, query: str, title: str, summary: str, payload: str) -> int:
        score = 0
        if query == title:
            score += 100
        if query in title:
            score += 20
        if query in summary:
            score += 10
        if query in payload:
            score += 5
        return score

    def _valid_at(self, record: dict[str, Any], reference: datetime) -> bool:
        valid_from = self._parse_time(record.get("valid_from"))
        valid_until = self._parse_time(record.get("valid_until"))
        if valid_from and reference < valid_from:
            return False
        if valid_until and reference >= valid_until:
            return False
        return True

    def _parse_time(self, value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _merge_evidence(self, existing: list[dict[str, Any]], new_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for ref in [*existing, *new_refs]:
            key = (str(ref.get("source_id", "")), str(ref.get("segment_id", "")))
            if key in seen:
                continue
            seen.add(key)
            merged.append(dict(ref))
        return merged
