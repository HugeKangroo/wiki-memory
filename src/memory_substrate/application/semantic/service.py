from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


@dataclass(frozen=True, slots=True)
class SemanticChunk:
    object_id: str
    chunk_id: str
    object_type: str
    kind: str
    title: str
    text: str
    status: str
    scope_refs: list[str]
    summary: str = ""


class SemanticIndex(Protocol):
    backend_name: str
    model_name: str

    def rebuild(self, chunks: list[SemanticChunk]) -> dict:
        ...

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        ...


class SemanticIndexService:
    def __init__(self, root: str | Path, index: SemanticIndex) -> None:
        self.root = Path(root)
        self.repository = FsObjectRepository(self.root)
        self.index = index

    def rebuild(self) -> dict:
        chunks = self._chunks()
        result = self.index.rebuild(chunks)
        return {
            "backend": result.get("backend", getattr(self.index, "backend_name", self.index.__class__.__name__)),
            "model": result.get("model", getattr(self.index, "model_name", "")),
            "chunk_count": result.get("chunk_count", len(chunks)),
        }

    def search(self, query: str, max_items: int = 20, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        hits = self.index.search(query, limit=max(max_items * 10, max_items))
        items: list[dict] = []
        seen: set[str] = set()
        for hit in hits:
            object_id = str(hit.get("object_id") or "")
            if not object_id or object_id in seen:
                continue
            object_type, obj = self._find_object(object_id)
            if object_type is None or obj is None:
                continue
            if not self._matches_filters(object_type, obj, filters):
                continue
            seen.add(object_id)
            distance = float(hit.get("distance", hit.get("_distance", 1.0)))
            semantic_score = max(0.0, 1.0 - distance)
            items.append(
                {
                    "object_type": object_type,
                    "id": obj["id"],
                    "kind": obj.get("kind", object_type),
                    "title": obj.get("title") or obj.get("name") or obj["id"],
                    "status": obj.get("status") or obj.get("lifecycle_state"),
                    "summary": obj.get("summary", ""),
                    "score": round(semantic_score * 15, 3),
                    "semantic_score": round(semantic_score, 6),
                    "retrieval_sources": ["semantic"],
                }
            )
            if len(items) >= max_items:
                break
        return items

    def _chunks(self) -> list[SemanticChunk]:
        chunks: list[SemanticChunk] = []
        for object_type in ("knowledge", "work_item", "activity", "node"):
            for obj in self.repository.list(object_type):
                text = self._object_text(object_type, obj)
                if not text.strip():
                    continue
                object_id = str(obj["id"])
                chunks.append(
                    SemanticChunk(
                        object_id=object_id,
                        chunk_id=f"{object_id}#object",
                        object_type=object_type,
                        kind=str(obj.get("kind", object_type)),
                        title=str(obj.get("title") or obj.get("name") or object_id),
                        summary=str(obj.get("summary", "")),
                        text=text,
                        status=str(obj.get("status") or obj.get("lifecycle_state") or ""),
                        scope_refs=self._scope_refs(obj),
                    )
                )
        for source in self.repository.list("source"):
            object_id = str(source["id"])
            title = str(source.get("title") or object_id)
            for segment in source.get("segments", []):
                if not isinstance(segment, dict):
                    continue
                segment_id = str(segment.get("segment_id") or "segment")
                excerpt = str(segment.get("excerpt") or "")
                if not excerpt.strip():
                    continue
                chunks.append(
                    SemanticChunk(
                        object_id=object_id,
                        chunk_id=f"{object_id}#{segment_id}",
                        object_type="source",
                        kind=str(source.get("kind", "source")),
                        title=title,
                        summary=excerpt,
                        text="\n".join(part for part in (title, excerpt, self._json_text(segment.get("locator", {}))) if part),
                        status=str(source.get("status") or ""),
                        scope_refs=self._scope_refs(source),
                    )
                )
        return chunks

    def _object_text(self, object_type: str, obj: dict) -> str:
        title = str(obj.get("title") or obj.get("name") or obj.get("id") or "")
        summary = str(obj.get("summary") or "")
        payload = self._json_text(obj.get("payload", {}))
        metadata = self._json_text(obj.get("metadata", {}))
        refs = self._json_text(
            {
                "scope_refs": self._scope_refs(obj),
                "subject_refs": obj.get("subject_refs", []),
                "source_refs": obj.get("source_refs", []),
                "related_node_refs": obj.get("related_node_refs", []),
                "related_knowledge_refs": obj.get("related_knowledge_refs", []),
            }
        )
        return "\n".join(part for part in (title, summary, payload, metadata, refs) if part)

    def _find_object(self, object_id: str) -> tuple[str | None, dict | None]:
        for object_type in ("knowledge", "work_item", "activity", "node", "source"):
            obj = self.repository.get(object_type, object_id)
            if obj is not None:
                return object_type, obj
        return None, None

    def _matches_filters(self, object_type: str, obj: dict, filters: dict) -> bool:
        object_types = set(filters.get("object_types", []))
        if filters.get("object_type"):
            object_types.add(str(filters["object_type"]))
        if object_types and object_type not in object_types:
            return False

        kinds = set(filters.get("kinds", []))
        if filters.get("kind"):
            kinds.add(str(filters["kind"]))
        if kinds and str(obj.get("kind", object_type)) not in kinds:
            return False

        statuses = set(filters.get("statuses", []))
        if filters.get("status"):
            statuses.add(str(filters["status"]))
        status = obj.get("status") or obj.get("lifecycle_state")
        if statuses and str(status) not in statuses:
            return False

        scope_refs = set(filters.get("scope_refs", []))
        if filters.get("scope_ref"):
            scope_refs.add(str(filters["scope_ref"]))
        if scope_refs and not scope_refs.intersection(self._scope_refs(obj)):
            return False

        return True

    def _scope_refs(self, obj: dict) -> list[str]:
        scope_refs = obj.get("scope_refs", [])
        if isinstance(scope_refs, list) and scope_refs:
            return [str(ref) for ref in scope_refs]
        payload = obj.get("payload", {})
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        metadata_scope_refs = metadata.get("scope_refs", []) if isinstance(metadata, dict) else []
        return [str(ref) for ref in metadata_scope_refs]

    def _json_text(self, value: Any) -> str:
        if value in ({}, [], None, ""):
            return ""
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
