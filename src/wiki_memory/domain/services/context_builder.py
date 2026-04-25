from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from wiki_memory.domain.protocols.context_pack import ContextItem, ContextPack
from wiki_memory.domain.services.ids import new_id
from wiki_memory.domain.services.patch_applier import utc_now_iso
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository


class ContextBuilder:
    def __init__(self, root: str | Path) -> None:
        self.repository = FsObjectRepository(root)

    def build(self, task: str, scope: dict | None = None, max_items: int = 12) -> ContextPack:
        scope = scope or {}
        items: list[ContextItem] = []
        items.extend(self._items_for("node", scope.get("node_ids")))
        items.extend(self._items_for("knowledge", None))
        items.extend(self._items_for("activity", None))
        items.extend(self._items_for("work_item", None))

        filtered = self._filter(items, scope)
        selected = filtered[:max_items]
        summary = self._summary(task, selected)
        generated_at = utc_now_iso()
        return ContextPack(
            id=new_id("ctx"),
            task=task,
            summary=summary,
            scope=scope,
            items=selected,
            conflicts=[],
            missing_context=[] if selected else ["No relevant context found yet."],
            recommended_next_reads=[item.id for item in selected[:5]],
            citations=[],
            generated_at=generated_at,
            expires_at=None,
        )

    def expand(self, object_id: str, max_items: int = 10) -> tuple[list[ContextItem], list[dict]]:
        items: list[ContextItem] = []
        source_segments: list[dict] = []
        for object_type in ("node", "knowledge", "activity", "work_item", "source"):
            obj = self.repository.get(object_type, object_id)
            if obj is not None:
                items.append(self._to_item(object_type, obj))
                items.extend(self._related_items(object_id, obj, max_items=max_items - 1))
                source_segments.extend(self._collect_source_segments(object_id, obj))
                break
        return items[:max_items], source_segments

    def _items_for(self, object_type: str, object_ids: list[str] | None) -> list[ContextItem]:
        if object_ids:
            objects = [self.repository.get(object_type, object_id) for object_id in object_ids]
            return [self._to_item(object_type, obj) for obj in objects if obj is not None]
        return [self._to_item(object_type, obj) for obj in self.repository.list(object_type)]

    def _filter(self, items: list[ContextItem], scope: dict) -> list[ContextItem]:
        node_ids = set(scope.get("node_ids", []))
        if not node_ids:
            return self._rank(items)
        filtered = [
            item
            for item in items
            if item.id in node_ids or self._references_any_node(item.object_type, item.id, node_ids)
        ]
        return self._rank(filtered or items)

    def _rank(self, items: list[ContextItem]) -> list[ContextItem]:
        status_rank = {
            "active": 0,
            "finalized": 1,
            "candidate": 2,
            "open": 3,
            "in_progress": 4,
            "blocked": 5,
            "draft": 6,
            "archived": 99,
        }
        return sorted(items, key=lambda item: (status_rank.get(item.status, 50), item.object_type, item.title))

    def _summary(self, task: str, items: list[ContextItem]) -> str:
        if not items:
            return f"No stored context available yet for task: {task}"
        titles = ", ".join(item.title for item in items[:3])
        return f"Context for '{task}' built from {len(items)} items. Key entries: {titles}"

    def _to_item(self, object_type: str, obj: dict) -> ContextItem:
        kind = str(obj.get("kind", object_type))
        title = str(obj.get("title") or obj.get("name") or obj["id"])
        summary = str(obj.get("summary", ""))
        status = str(obj.get("status") or obj.get("lifecycle_state") or "unknown")
        return ContextItem(
            object_type=object_type,
            id=str(obj["id"]),
            kind=kind,
            title=title,
            status=status,
            summary=summary,
        )

    def _related_items(self, root_id: str, obj: dict, max_items: int) -> list[ContextItem]:
        refs: list[str] = []
        for key in (
            "subject_refs",
            "related_node_refs",
            "related_work_item_refs",
            "produced_object_refs",
            "source_refs",
        ):
            value = obj.get(key, [])
            if isinstance(value, list):
                refs.extend(str(item) for item in value)
        seen: set[str] = set()
        items: list[ContextItem] = []
        for object_type in ("node", "knowledge", "activity", "work_item", "source"):
            for candidate in self.repository.list(object_type):
                candidate_id = str(candidate["id"])
                if candidate_id not in seen and (
                    candidate_id in refs or self._references_root(candidate, root_id)
                ):
                    seen.add(candidate_id)
                    items.append(self._to_item(object_type, candidate))
                    if len(items) >= max_items:
                        return items
        return items

    def _collect_source_segments(self, root_id: str, obj: dict) -> list[dict]:
        segments: list[dict] = []
        source_ids: set[str] = set()
        if obj.get("id", "").startswith("src:"):
            source_ids.add(obj["id"])
        for field in ("source_refs",):
            values = obj.get(field, [])
            if isinstance(values, list):
                source_ids.update(str(value) for value in values if str(value).startswith("src:"))
        for evidence in obj.get("evidence_refs", []):
            if isinstance(evidence, dict) and evidence.get("source_id"):
                source_ids.add(str(evidence["source_id"]))
        if not source_ids and obj.get("kind") == "repo":
            source_ids.update(self._matching_repo_sources(obj))

        for source_id in source_ids:
            source = self.repository.get("source", source_id)
            if source is None:
                continue
            for segment in source.get("segments", [])[:10]:
                segments.append(
                    {
                        "source_id": source_id,
                        "segment_id": segment.get("segment_id"),
                        "locator": segment.get("locator"),
                        "excerpt": segment.get("excerpt", ""),
                    }
                )
        return segments

    def _matching_repo_sources(self, obj: dict) -> set[str]:
        matches: set[str] = set()
        node_name = str(obj.get("name") or obj.get("title") or "")
        node_slug = str(obj.get("slug") or "")
        for source in self.repository.list("source"):
            if source.get("kind") != "repo":
                continue
            payload = source.get("payload", {})
            repo_name = str(payload.get("repo_name") or source.get("title") or "")
            if repo_name == node_name or repo_name == node_slug:
                matches.add(str(source["id"]))
        return matches

    def _references_root(self, obj: dict, root_id: str) -> bool:
        direct_list_fields = (
            "subject_refs",
            "related_node_refs",
            "related_work_item_refs",
            "produced_object_refs",
            "source_refs",
            "related_knowledge_refs",
            "depends_on",
            "blocked_by",
            "child_refs",
        )
        for field in direct_list_fields:
            values = obj.get(field, [])
            if isinstance(values, list) and root_id in values:
                return True
        if obj.get("parent_ref") == root_id:
            return True
        if obj.get("source_id") == root_id:
            return True
        evidence_refs = obj.get("evidence_refs", [])
        for evidence in evidence_refs:
            if isinstance(evidence, dict) and evidence.get("source_id") == root_id:
                return True
        payload = obj.get("payload", {})
        if isinstance(payload, dict):
            for value in payload.values():
                if value == root_id:
                    return True
                if isinstance(value, list) and root_id in value:
                    return True
        return False

    def _references_any_node(self, object_type: str, object_id: str, node_ids: set[str]) -> bool:
        obj = self.repository.get(object_type, object_id)
        if obj is None:
            return False
        if object_type == "node":
            return object_id in node_ids
        if object_type == "source":
            payload = obj.get("payload", {})
            if isinstance(payload, dict):
                for value in payload.values():
                    if value in node_ids:
                        return True
                    if isinstance(value, list) and any(item in node_ids for item in value):
                        return True
            return False
        return any(self._references_root(obj, node_id) for node_id in node_ids)
