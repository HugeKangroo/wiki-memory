from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory_substrate.infrastructure.storage.paths import StoragePaths


GRAPH_BUCKETS = ("episodes", "entities", "relations", "knowledge")
OBJECT_TYPES = {"episode", "entity", "knowledge"}
OBJECT_TYPE_TO_BUCKET = {
    "episode": "episodes",
    "entity": "entities",
    "knowledge": "knowledge",
}
BUCKET_TO_OBJECT_TYPE = {bucket: object_type for object_type, bucket in OBJECT_TYPE_TO_BUCKET.items()}

SCHEMA_QUERIES = """
CREATE NODE TABLE IF NOT EXISTS MemoryObject(
    id STRING PRIMARY KEY,
    object_type STRING,
    kind STRING,
    title STRING,
    name STRING,
    summary STRING,
    status STRING,
    confidence DOUBLE,
    scope_refs STRING[],
    evidence_refs STRING,
    payload STRING,
    valid_from STRING,
    valid_until STRING,
    created_at STRING,
    updated_at STRING
);
CREATE REL TABLE IF NOT EXISTS MEMORY_RELATION(
    FROM MemoryObject TO MemoryObject,
    id STRING,
    relation_type STRING,
    kind STRING,
    status STRING,
    confidence DOUBLE,
    scope_refs STRING[],
    evidence_refs STRING,
    payload STRING,
    valid_from STRING,
    valid_until STRING,
    created_at STRING,
    updated_at STRING
);
"""


class KuzuGraphBackend:
    """Local Kuzu implementation of the project-owned graph backend contract."""

    def __init__(self, root: str | Path) -> None:
        try:
            import kuzu
        except ImportError as exc:  # pragma: no cover - exercised only without optional extra.
            raise ImportError("Install memory-substrate[kuzu] to use KuzuGraphBackend") from exc

        paths = StoragePaths(root)
        self.path = paths.indexes_root / "kuzu_graph"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(self.path))
        self._connection = kuzu.Connection(self._db)
        self._connection.execute(SCHEMA_QUERIES)

    def close(self) -> None:
        self._connection.close()

    def upsert_episode(self, episode: dict[str, Any]) -> dict[str, Any]:
        return self._upsert_object("episode", episode)

    def upsert_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        return self._upsert_object("entity", entity)

    def upsert_relation(self, relation: dict[str, Any]) -> dict[str, Any]:
        if "id" not in relation:
            raise ValueError("Graph relation record requires id")
        source_id = str(relation.get("source_id") or relation.get("source_ref") or "")
        target_id = str(relation.get("target_id") or relation.get("target_ref") or "")
        if not source_id or not target_id:
            raise ValueError("Graph relation record requires source_id/source_ref and target_id/target_ref")

        self._ensure_object(source_id)
        self._ensure_object(target_id)
        data = self._relation_data(relation, source_id, target_id)
        self._execute(
            "MATCH ()-[r:MEMORY_RELATION {id: $id}]->() DELETE r",
            {"id": data["id"]},
        )
        self._execute(
            """
            MATCH (source:MemoryObject {id: $source_id}), (target:MemoryObject {id: $target_id})
            CREATE (source)-[:MEMORY_RELATION {
                id: $id,
                relation_type: $relation_type,
                kind: $kind,
                status: $status,
                confidence: $confidence,
                scope_refs: $scope_refs,
                evidence_refs: $evidence_refs,
                payload: $payload,
                valid_from: $valid_from,
                valid_until: $valid_until,
                created_at: $created_at,
                updated_at: $updated_at
            }]->(target)
            """,
            data,
        )
        return self._get_relation(data["id"])

    def upsert_knowledge(self, knowledge: dict[str, Any]) -> dict[str, Any]:
        return self._upsert_object("knowledge", knowledge)

    def link_evidence(self, object_type: str, object_id: str, evidence_refs: list[dict[str, Any]]) -> dict[str, Any]:
        if object_type == "relation":
            existing = self._get_relation(object_id)
            merged_refs = self._merge_evidence(existing.get("evidence_refs", []), evidence_refs)
            self._execute(
                "MATCH ()-[r:MEMORY_RELATION {id: $id}]->() SET r.evidence_refs = $evidence_refs",
                {"id": object_id, "evidence_refs": self._dump_json(merged_refs)},
            )
            return self._get_relation(object_id)

        if object_type not in OBJECT_TYPES:
            raise ValueError(f"Unsupported graph object type: {object_type}")
        existing = self._get_object(object_id)
        if existing["object_type"] != object_type:
            raise ValueError(f"{object_type} not found: {object_id}")
        merged_refs = self._merge_evidence(existing.get("evidence_refs", []), evidence_refs)
        self._execute(
            "MATCH (n:MemoryObject {id: $id}) SET n.evidence_refs = $evidence_refs",
            {"id": object_id, "evidence_refs": self._dump_json(merged_refs)},
        )
        return self._get_object(object_id)

    def search(self, query: str, scope_refs: list[str] | None = None, max_items: int = 10) -> list[dict[str, Any]]:
        q = query.strip().lower()
        if not q:
            return []

        results: list[dict[str, Any]] = []
        for record in self._all_objects():
            if not self._matches_scope(record, scope_refs):
                continue
            title = str(record.get("title") or record.get("name") or record["id"])
            summary = str(record.get("summary", ""))
            payload = self._dump_json(record.get("payload", {}))
            haystack = f"{title}\n{summary}\n{payload}".lower()
            if q not in haystack:
                continue
            results.append(
                {
                    "object_type": record["object_type"],
                    "id": record["id"],
                    "kind": record.get("kind", record["object_type"]),
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
        objects = {record["id"]: record for record in self._all_objects()}
        relations = self._all_relations()
        node_ids = {object_id}
        neighborhood_relations: list[dict[str, Any]] = []

        frontier = {object_id}
        for _ in range(max(depth, 1)):
            next_frontier: set[str] = set()
            for relation in relations:
                source_id = str(relation.get("source_id", ""))
                target_id = str(relation.get("target_id", ""))
                if source_id not in frontier and target_id not in frontier:
                    continue
                if relation["id"] not in {item["id"] for item in neighborhood_relations}:
                    neighborhood_relations.append(relation)
                for node_id in (source_id, target_id):
                    if node_id and node_id not in node_ids:
                        node_ids.add(node_id)
                        next_frontier.add(node_id)
                if len(node_ids) >= max_items:
                    break
            frontier = next_frontier
            if not frontier or len(node_ids) >= max_items:
                break

        nodes = [objects[node_id] for node_id in sorted(node_ids) if node_id in objects]
        return {
            "root_id": object_id,
            "nodes": nodes[:max_items],
            "relations": neighborhood_relations[:max_items],
        }

    def temporal_lookup(self, reference_time: str, scope_refs: list[str] | None = None) -> dict[str, Any]:
        reference = self._parse_time(reference_time)
        return {
            "reference_time": reference_time,
            "knowledge": [
                record
                for record in self._all_objects("knowledge")
                if self._matches_scope(record, scope_refs) and self._valid_at(record, reference)
            ],
            "relations": [
                record
                for record in self._all_relations()
                if self._matches_scope(record, scope_refs) and self._valid_at(record, reference)
            ],
        }

    def health(self) -> dict[str, Any]:
        objects = self._all_objects()
        counts = {bucket: 0 for bucket in GRAPH_BUCKETS}
        for record in objects:
            bucket = OBJECT_TYPE_TO_BUCKET.get(record["object_type"])
            if bucket is not None:
                counts[bucket] += 1
        counts["relations"] = len(self._all_relations())
        return {
            "status": "ok",
            "path": str(self.path),
            "counts": counts,
        }

    def rebuild(self) -> dict[str, Any]:
        health = self.health()
        return {
            "status": "noop",
            "path": health["path"],
            "counts": health["counts"],
        }

    def export_scope(self, scope_ref: str) -> dict[str, Any]:
        exported = {bucket: [] for bucket in GRAPH_BUCKETS}
        for record in self._all_objects():
            if scope_ref != "*" and scope_ref not in record.get("scope_refs", []):
                continue
            exported[OBJECT_TYPE_TO_BUCKET[record["object_type"]]].append(record)
        exported["relations"] = [
            relation
            for relation in self._all_relations()
            if scope_ref == "*" or scope_ref in relation.get("scope_refs", [])
        ]
        return exported

    def _upsert_object(self, object_type: str, record: dict[str, Any]) -> dict[str, Any]:
        if "id" not in record:
            raise ValueError(f"Graph {object_type} record requires id")
        data = self._object_data(object_type, record)
        self._execute(
            """
            MERGE (n:MemoryObject {id: $id})
            SET n.object_type = $object_type,
                n.kind = $kind,
                n.title = $title,
                n.name = $name,
                n.summary = $summary,
                n.status = $status,
                n.confidence = $confidence,
                n.scope_refs = $scope_refs,
                n.evidence_refs = $evidence_refs,
                n.payload = $payload,
                n.valid_from = $valid_from,
                n.valid_until = $valid_until,
                n.created_at = $created_at,
                n.updated_at = $updated_at
            """,
            data,
        )
        return self._get_object(data["id"])

    def _ensure_object(self, object_id: str) -> None:
        if self._find_object(object_id) is not None:
            return
        object_type = self._infer_object_type(object_id)
        self._upsert_object(
            object_type,
            {
                "id": object_id,
                "kind": object_type,
                "title": object_id,
                "name": object_id,
                "summary": "",
                "status": "stub",
                "scope_refs": [],
                "payload": {},
            },
        )

    def _object_data(self, object_type: str, record: dict[str, Any]) -> dict[str, Any]:
        title = str(record.get("title") or record.get("name") or record["id"])
        name = str(record.get("name") or title)
        return {
            "id": str(record["id"]),
            "object_type": object_type,
            "kind": str(record.get("kind", object_type)),
            "title": title,
            "name": name,
            "summary": str(record.get("summary", "")),
            "status": str(record.get("status", "active")),
            "confidence": self._optional_float(record.get("confidence")),
            "scope_refs": [str(ref) for ref in record.get("scope_refs", [])],
            "evidence_refs": self._dump_json(record.get("evidence_refs", [])),
            "payload": self._dump_json(record.get("payload", {})),
            "valid_from": record.get("valid_from"),
            "valid_until": record.get("valid_until"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
        }

    def _relation_data(self, relation: dict[str, Any], source_id: str, target_id: str) -> dict[str, Any]:
        return {
            "id": str(relation["id"]),
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": str(relation.get("relation_type") or relation.get("kind") or "related_to"),
            "kind": str(relation.get("kind") or relation.get("relation_type") or "related_to"),
            "status": str(relation.get("status", "candidate")),
            "confidence": self._optional_float(relation.get("confidence")),
            "scope_refs": [str(ref) for ref in relation.get("scope_refs", [])],
            "evidence_refs": self._dump_json(relation.get("evidence_refs", [])),
            "payload": self._dump_json(relation.get("payload", {})),
            "valid_from": relation.get("valid_from"),
            "valid_until": relation.get("valid_until"),
            "created_at": relation.get("created_at"),
            "updated_at": relation.get("updated_at"),
        }

    def _all_objects(self, object_type: str | None = None) -> list[dict[str, Any]]:
        if object_type is None:
            rows = self._execute(
                """
                MATCH (n:MemoryObject)
                RETURN n.id AS id,
                       n.object_type AS object_type,
                       n.kind AS kind,
                       n.title AS title,
                       n.name AS name,
                       n.summary AS summary,
                       n.status AS status,
                       n.confidence AS confidence,
                       n.scope_refs AS scope_refs,
                       n.evidence_refs AS evidence_refs,
                       n.payload AS payload,
                       n.valid_from AS valid_from,
                       n.valid_until AS valid_until,
                       n.created_at AS created_at,
                       n.updated_at AS updated_at
                ORDER BY n.id
                """
            )
        else:
            rows = self._execute(
                """
                MATCH (n:MemoryObject)
                WHERE n.object_type = $object_type
                RETURN n.id AS id,
                       n.object_type AS object_type,
                       n.kind AS kind,
                       n.title AS title,
                       n.name AS name,
                       n.summary AS summary,
                       n.status AS status,
                       n.confidence AS confidence,
                       n.scope_refs AS scope_refs,
                       n.evidence_refs AS evidence_refs,
                       n.payload AS payload,
                       n.valid_from AS valid_from,
                       n.valid_until AS valid_until,
                       n.created_at AS created_at,
                       n.updated_at AS updated_at
                ORDER BY n.id
                """,
                {"object_type": object_type},
            )
        return [self._decode_object(row) for row in rows]

    def _all_relations(self) -> list[dict[str, Any]]:
        rows = self._execute(
            """
            MATCH (source:MemoryObject)-[r:MEMORY_RELATION]->(target:MemoryObject)
            RETURN source.id AS source_id,
                   target.id AS target_id,
                   r.id AS id,
                   r.relation_type AS relation_type,
                   r.kind AS kind,
                   r.status AS status,
                   r.confidence AS confidence,
                   r.scope_refs AS scope_refs,
                   r.evidence_refs AS evidence_refs,
                   r.payload AS payload,
                   r.valid_from AS valid_from,
                   r.valid_until AS valid_until,
                   r.created_at AS created_at,
                   r.updated_at AS updated_at
            ORDER BY r.id
            """
        )
        return [self._decode_relation(row) for row in rows]

    def _get_object(self, object_id: str) -> dict[str, Any]:
        record = self._find_object(object_id)
        if record is None:
            raise ValueError(f"Graph object not found: {object_id}")
        return record

    def _find_object(self, object_id: str) -> dict[str, Any] | None:
        rows = self._execute(
            """
            MATCH (n:MemoryObject {id: $id})
            RETURN n.id AS id,
                   n.object_type AS object_type,
                   n.kind AS kind,
                   n.title AS title,
                   n.name AS name,
                   n.summary AS summary,
                   n.status AS status,
                   n.confidence AS confidence,
                   n.scope_refs AS scope_refs,
                   n.evidence_refs AS evidence_refs,
                   n.payload AS payload,
                   n.valid_from AS valid_from,
                   n.valid_until AS valid_until,
                   n.created_at AS created_at,
                   n.updated_at AS updated_at
            """,
            {"id": object_id},
        )
        if not rows:
            return None
        return self._decode_object(rows[0])

    def _get_relation(self, relation_id: str) -> dict[str, Any]:
        rows = self._execute(
            """
            MATCH (source:MemoryObject)-[r:MEMORY_RELATION {id: $id}]->(target:MemoryObject)
            RETURN source.id AS source_id,
                   target.id AS target_id,
                   r.id AS id,
                   r.relation_type AS relation_type,
                   r.kind AS kind,
                   r.status AS status,
                   r.confidence AS confidence,
                   r.scope_refs AS scope_refs,
                   r.evidence_refs AS evidence_refs,
                   r.payload AS payload,
                   r.valid_from AS valid_from,
                   r.valid_until AS valid_until,
                   r.created_at AS created_at,
                   r.updated_at AS updated_at
            """,
            {"id": relation_id},
        )
        if not rows:
            raise ValueError(f"Graph relation not found: {relation_id}")
        return self._decode_relation(rows[0])

    def _execute(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        result = self._connection.execute(query, parameters or {})
        if result is None:
            return []
        return list(result.rows_as_dict())

    def _decode_object(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["scope_refs"] = list(result.get("scope_refs") or [])
        result["evidence_refs"] = self._load_json(result.get("evidence_refs"), [])
        result["payload"] = self._load_json(result.get("payload"), {})
        return {key: value for key, value in result.items() if value is not None}

    def _decode_relation(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["scope_refs"] = list(result.get("scope_refs") or [])
        result["evidence_refs"] = self._load_json(result.get("evidence_refs"), [])
        result["payload"] = self._load_json(result.get("payload"), {})
        return {key: value for key, value in result.items() if value is not None}

    def _matches_scope(self, record: dict[str, Any], scope_refs: list[str] | None) -> bool:
        if not scope_refs:
            return True
        return bool(set(record.get("scope_refs", [])).intersection(scope_refs))

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

    def _valid_at(self, record: dict[str, Any], reference: datetime | None) -> bool:
        if reference is None:
            return True
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

    def _dump_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    def _load_json(self, value: str | None, default: Any) -> Any:
        if not value:
            return default
        return json.loads(value)

    def _optional_float(self, value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    def _infer_object_type(self, object_id: str) -> str:
        if object_id.startswith("ep:"):
            return "episode"
        if object_id.startswith("know:"):
            return "knowledge"
        return "entity"
