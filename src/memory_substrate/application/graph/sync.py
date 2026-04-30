from __future__ import annotations

from hashlib import sha1
from pathlib import Path
from typing import Any

from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


GRAPH_OBJECT_TYPES = (
    "source",
    "node",
    "knowledge",
    "activity",
    "work_item",
    "memory_scope",
    "episode",
    "entity",
    "relation",
)

RELATION_SCHEMA_VERSION = 1

REFERENCE_FIELDS = {
    "subject_refs": "subject",
    "related_node_refs": "related_node",
    "related_work_item_refs": "related_work_item",
    "produced_object_refs": "produced_object",
    "source_refs": "source",
    "related_knowledge_refs": "related_knowledge",
    "depends_on": "depends_on",
    "blocked_by": "blocked_by",
    "child_refs": "child",
    "owner_refs": "owner",
    "parent_refs": "parent",
}


class GraphSyncService:
    """Synchronize canonical memory objects into a configured graph backend."""

    def __init__(self, root: str | Path, graph_backend) -> None:
        self.root = Path(root)
        self.repository = FsObjectRepository(self.root)
        self.graph_backend = graph_backend

    def sync_all(self) -> dict[str, Any]:
        synced_objects = 0
        synced_relations = 0
        for object_type in GRAPH_OBJECT_TYPES:
            for obj in self.repository.list(object_type):
                result = self.sync_object(object_type, obj)
                synced_objects += result["synced_objects"]
                synced_relations += result["synced_relations"]
        return {
            "status": "completed",
            "synced_objects": synced_objects,
            "synced_relations": synced_relations,
            "backend": self.graph_backend.__class__.__name__,
        }

    def sync_object(self, object_type: str, obj_or_id: dict[str, Any] | str) -> dict[str, Any]:
        obj = self._resolve_object(object_type, obj_or_id)
        if obj is None:
            return {
                "status": "missing",
                "synced_objects": 0,
                "synced_relations": 0,
                "backend": self.graph_backend.__class__.__name__,
            }

        synced_objects = 0
        if self._sync_graph_object(object_type, obj):
            synced_objects = 1
        synced_relations = self._sync_relations(object_type, obj)
        return {
            "status": "completed",
            "synced_objects": synced_objects,
            "synced_relations": synced_relations,
            "backend": self.graph_backend.__class__.__name__,
        }

    def _resolve_object(self, object_type: str, obj_or_id: dict[str, Any] | str) -> dict[str, Any] | None:
        if isinstance(obj_or_id, dict):
            return obj_or_id
        return self.repository.get(object_type, obj_or_id)

    def _sync_graph_object(self, object_type: str, obj: dict[str, Any]) -> bool:
        if object_type == "relation":
            self.graph_backend.upsert_relation(self._relation_record(obj))
            return True
        record = self._object_record(object_type, obj)
        if object_type in {"source", "episode"}:
            self.graph_backend.upsert_episode(record)
            return True
        if object_type in {"knowledge"}:
            self.graph_backend.upsert_knowledge(record)
            return True
        self.graph_backend.upsert_entity(record)
        return True

    def _sync_relations(self, object_type: str, obj: dict[str, Any]) -> int:
        if object_type == "relation":
            return 0
        synced = 0
        for field, relation_type in REFERENCE_FIELDS.items():
            values = obj.get(field, [])
            if not isinstance(values, list):
                continue
            for target_id in values:
                synced += self._sync_reference_relation(
                    object_type,
                    obj,
                    relation_type,
                    str(target_id),
                    [],
                    derivation="field_reference",
                    origin_field=field,
                )

        parent_ref = obj.get("parent_ref")
        if parent_ref:
            synced += self._sync_reference_relation(
                object_type,
                obj,
                "parent",
                str(parent_ref),
                [],
                derivation="field_reference",
                origin_field="parent_ref",
            )

        for evidence in obj.get("evidence_refs", []):
            if not isinstance(evidence, dict) or not evidence.get("source_id"):
                continue
            synced += self._sync_reference_relation(
                object_type,
                obj,
                "evidence",
                str(evidence["source_id"]),
                [evidence],
                derivation="evidence_ref",
                origin_field="evidence_refs",
            )
        synced += self._sync_payload_relation(object_type, obj)
        return synced

    def _sync_payload_relation(self, object_type: str, obj: dict[str, Any]) -> int:
        if object_type != "knowledge":
            return 0
        payload = obj.get("payload", {})
        if not isinstance(payload, dict):
            return 0
        subject_id = str(payload.get("subject") or "")
        predicate = str(payload.get("predicate") or "")
        target_id = payload.get("object")
        if not subject_id or not predicate or not isinstance(target_id, str):
            return 0
        if not self._looks_like_object_id(target_id):
            return 0
        self._ensure_target(subject_id)
        self._ensure_target(target_id)
        self.graph_backend.upsert_relation(
            {
                "id": self._relation_id(subject_id, predicate, target_id),
                "source_id": subject_id,
                "target_id": target_id,
                "relation_type": predicate,
                "kind": predicate,
                "status": obj.get("status", "active"),
                "confidence": obj.get("confidence"),
                "scope_refs": obj.get("scope_refs", []),
                "evidence_refs": obj.get("evidence_refs", []),
                "payload": self._relation_payload(
                    {"knowledge_id": obj["id"], "value": payload.get("value")},
                    origin_object_type=object_type,
                    origin_object_id=obj["id"],
                    derivation="structured_payload",
                    origin_field="payload.object",
                    source_id=subject_id,
                    target_id=target_id,
                ),
                "valid_from": obj.get("valid_from"),
                "valid_until": obj.get("valid_until"),
                "created_at": obj.get("created_at"),
                "updated_at": obj.get("updated_at"),
            }
        )
        return 1

    def _sync_reference_relation(
        self,
        object_type: str,
        source: dict[str, Any],
        relation_type: str,
        target_id: str,
        evidence_refs: list[dict[str, Any]],
        *,
        derivation: str,
        origin_field: str,
    ) -> int:
        if not target_id:
            return 0
        self._ensure_target(target_id)
        self.graph_backend.upsert_relation(
            {
                "id": self._relation_id(source["id"], relation_type, target_id),
                "source_id": source["id"],
                "target_id": target_id,
                "relation_type": relation_type,
                "kind": relation_type,
                "status": source.get("status", "active"),
                "confidence": source.get("confidence"),
                "scope_refs": source.get("scope_refs", []),
                "evidence_refs": evidence_refs,
                "payload": self._relation_payload(
                    {"derived_from_field": origin_field},
                    origin_object_type=object_type,
                    origin_object_id=source["id"],
                    derivation=derivation,
                    origin_field=origin_field,
                    source_id=source["id"],
                    target_id=target_id,
                ),
                "valid_from": source.get("valid_from"),
                "valid_until": source.get("valid_until"),
                "created_at": source.get("created_at"),
                "updated_at": source.get("updated_at"),
            }
        )
        return 1

    def _ensure_target(self, object_id: str) -> None:
        target_type, target = self._find_object(object_id)
        if target is None:
            self.graph_backend.upsert_entity(
                {
                    "id": object_id,
                    "kind": "stub",
                    "name": object_id,
                    "summary": "",
                    "status": "stub",
                    "scope_refs": [],
                }
            )
            return
        self._sync_graph_object(target_type, target)

    def _find_object(self, object_id: str) -> tuple[str, dict[str, Any] | None]:
        for object_type in GRAPH_OBJECT_TYPES:
            obj = self.repository.get(object_type, object_id)
            if obj is not None:
                return object_type, obj
        return self._infer_object_type(object_id), None

    def _object_record(self, object_type: str, obj: dict[str, Any]) -> dict[str, Any]:
        title = str(obj.get("title") or obj.get("name") or obj["id"])
        return {
            "id": obj["id"],
            "kind": obj.get("kind", object_type),
            "title": title,
            "name": obj.get("name", title),
            "summary": obj.get("summary", self._summary_from_payload(obj)),
            "status": obj.get("status") or obj.get("lifecycle_state") or "active",
            "confidence": obj.get("confidence"),
            "scope_refs": obj.get("scope_refs", []),
            "evidence_refs": obj.get("evidence_refs", []),
            "payload": obj.get("payload", {}),
            "valid_from": obj.get("valid_from"),
            "valid_until": obj.get("valid_until"),
            "created_at": obj.get("created_at"),
            "updated_at": obj.get("updated_at"),
        }

    def _relation_record(self, obj: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": obj["id"],
            "source_id": obj.get("source_id") or obj.get("source_ref"),
            "target_id": obj.get("target_id") or obj.get("target_ref"),
            "relation_type": obj.get("relation_type", obj.get("kind", "related_to")),
            "kind": obj.get("kind", obj.get("relation_type", "related_to")),
            "status": obj.get("status", "candidate"),
            "confidence": obj.get("confidence"),
            "scope_refs": obj.get("scope_refs", []),
            "evidence_refs": obj.get("evidence_refs", []),
            "payload": self._relation_payload(
                obj.get("payload", {}),
                origin_object_type="relation",
                origin_object_id=obj["id"],
                derivation="canonical_relation",
                origin_field="relation",
                source_id=str(obj.get("source_id") or obj.get("source_ref") or ""),
                target_id=str(obj.get("target_id") or obj.get("target_ref") or ""),
            ),
            "valid_from": obj.get("valid_from"),
            "valid_until": obj.get("valid_until"),
            "created_at": obj.get("created_at"),
            "updated_at": obj.get("updated_at"),
        }

    def _relation_payload(
        self,
        payload: Any,
        *,
        origin_object_type: str,
        origin_object_id: str,
        derivation: str,
        origin_field: str,
        source_id: str,
        target_id: str,
    ) -> dict[str, Any]:
        result = dict(payload) if isinstance(payload, dict) else {"value": payload}
        existing_schema = result.get("relation_schema", {})
        schema = dict(existing_schema) if isinstance(existing_schema, dict) else {}
        schema.update(
            {
                "version": RELATION_SCHEMA_VERSION,
                "derivation": derivation,
                "origin_object_type": origin_object_type,
                "origin_object_id": origin_object_id,
                "origin_field": origin_field,
                "source_object_type": self._canonical_object_type(source_id),
                "target_object_type": self._canonical_object_type(target_id),
            }
        )
        result["relation_schema"] = schema
        return result

    def _canonical_object_type(self, object_id: str) -> str:
        object_type, _ = self._find_object(object_id)
        return object_type

    def _summary_from_payload(self, obj: dict[str, Any]) -> str:
        payload = obj.get("payload", "")
        if isinstance(payload, dict):
            text = str(payload.get("text") or payload.get("summary") or "")
        else:
            text = str(payload)
        return text[:240]

    def _relation_id(self, source_id: str, relation_type: str, target_id: str) -> str:
        digest = sha1(f"{source_id}\0{relation_type}\0{target_id}".encode("utf-8")).hexdigest()
        return f"rel:{digest}"

    def _infer_object_type(self, object_id: str) -> str:
        if object_id.startswith("src:"):
            return "source"
        if object_id.startswith("node:"):
            return "node"
        if object_id.startswith("know:"):
            return "knowledge"
        if object_id.startswith("act:"):
            return "activity"
        if object_id.startswith("work:"):
            return "work_item"
        if object_id.startswith("scope:"):
            return "memory_scope"
        if object_id.startswith("ep:"):
            return "episode"
        if object_id.startswith("rel:"):
            return "relation"
        return "entity"

    def _looks_like_object_id(self, value: str) -> bool:
        return ":" in value
