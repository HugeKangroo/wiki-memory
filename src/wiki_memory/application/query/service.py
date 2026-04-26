from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from wiki_memory.domain.services.context_builder import ContextBuilder
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository


class QueryService:
    def __init__(self, root: str | Path) -> None:
        """Create a query service bound to one wiki-memory root.

        Args:
            root: Wiki-memory root directory to query.

        Returns:
            None.
        """
        self.builder = ContextBuilder(root)
        self.repository = FsObjectRepository(root)

    def context(self, task: str, scope: dict | None = None, max_items: int = 12) -> dict:
        """Build a task-focused context pack from relevant memory objects.

        Args:
            task: Natural-language task or question to gather context for.
            scope: Optional filters or hints that constrain retrieval.
            max_items: Maximum number of context items to return.

        Returns:
            Context pack with ranked items, conflicts, missing context, citations, and expiry metadata.
        """
        pack = self.builder.build(task=task, scope=scope, max_items=max_items)
        return {
            "result_type": "context_pack",
            "data": {
                "id": pack.id,
                "task": pack.task,
                "summary": pack.summary,
                "scope": pack.scope,
                "items": [asdict(item) for item in pack.items],
                "conflicts": pack.conflicts,
                "missing_context": pack.missing_context,
                "recommended_next_reads": pack.recommended_next_reads,
                "citations": pack.citations,
                "generated_at": pack.generated_at,
                "expires_at": pack.expires_at,
            },
            "warnings": [],
        }

    def expand(self, object_id: str, max_items: int = 10) -> dict:
        """Expand one memory object into nearby context and source evidence.

        Args:
            object_id: Source, node, knowledge, activity, or work item identifier to expand from.
            max_items: Maximum number of related context items to return.

        Returns:
            Expanded context items and source segments for the requested object.
        """
        items, source_segments = self.builder.expand(object_id=object_id, max_items=max_items)
        return {
            "result_type": "expanded_context",
            "data": {
                "root_id": object_id,
                "items": [asdict(item) for item in items],
                "source_segments": source_segments,
            },
            "warnings": [],
        }

    def page(self, object_id: str) -> dict:
        """Fetch the full stored object for a single memory identifier.

        Args:
            object_id: Source, node, knowledge, activity, or work item identifier to fetch.

        Returns:
            Page result containing the object type and object payload, or a warning if missing.
        """
        for object_type in ("source", "node", "knowledge", "activity", "work_item"):
            obj = self.repository.get(object_type, object_id)
            if obj is not None:
                return {
                    "result_type": "page",
                    "data": {
                        "object_type": object_type,
                        "object": obj,
                    },
                    "warnings": [],
                }
        return {
            "result_type": "page",
            "data": None,
            "warnings": [f"Object not found: {object_id}"],
        }

    def graph(self, object_id: str, max_items: int = 20) -> dict:
        """Build a lightweight one-hop relationship graph around an object.

        Args:
            object_id: Memory object identifier to use as the graph root.
            max_items: Maximum number of graph nodes to include.

        Returns:
            Graph result with root id, nodes, edges, and warnings for missing roots.
        """
        nodes: list[dict] = []
        edges: list[dict] = []
        seen_nodes: set[str] = set()

        root_type, root = self._find_object(object_id)
        if root is None or root_type is None:
            return {"result_type": "graph", "data": {"root_id": object_id, "nodes": [], "edges": []}, "warnings": [f"Object not found: {object_id}"]}

        self._append_graph_node(nodes, seen_nodes, root_type, root)
        for object_type in ("source", "node", "knowledge", "activity", "work_item"):
            for obj in self.repository.list(object_type):
                if obj["id"] == object_id:
                    continue
                relation = self._relation_to(obj, object_id)
                if relation is None:
                    continue
                self._append_graph_node(nodes, seen_nodes, object_type, obj)
                edges.append({"source_id": object_id, "target_id": obj["id"], "relation": relation})
                if len(nodes) >= max_items:
                    return {"result_type": "graph", "data": {"root_id": object_id, "nodes": nodes, "edges": edges}, "warnings": []}
        return {"result_type": "graph", "data": {"root_id": object_id, "nodes": nodes, "edges": edges}, "warnings": []}

    def recent(self, max_items: int = 20, filters: dict | None = None) -> dict:
        """List recently updated memory objects across all object types.

        Args:
            max_items: Maximum number of recent entries to return.
            filters: Optional object type, kind, status, or lifecycle filters.

        Returns:
            Recent result containing sorted object summaries.
        """
        filters = filters or {}
        entries: list[dict] = []
        for object_type in ("activity", "work_item", "knowledge", "source", "node"):
            for obj in self.repository.list(object_type):
                if not self._matches_filters(object_type, obj, filters):
                    continue
                entries.append(
                    {
                        "object_type": object_type,
                        "id": obj["id"],
                        "kind": obj.get("kind", object_type),
                        "title": obj.get("title") or obj.get("name") or obj["id"],
                        "status": obj.get("status") or obj.get("lifecycle_state"),
                        "updated_at": obj.get("updated_at") or obj.get("created_at"),
                        "summary": obj.get("summary", ""),
                    }
                )
        entries.sort(key=lambda item: self._parse_time(item["updated_at"]), reverse=True)
        return {
            "result_type": "recent",
            "data": {
                "items": entries[:max_items],
            },
            "warnings": [],
        }

    def search(self, query: str, max_items: int = 20, filters: dict | None = None) -> dict:
        """Search memory objects by title, summary, payload, and source segments.

        Args:
            query: Case-insensitive substring query.
            max_items: Maximum number of search results to return.
            filters: Optional object type, kind, status, or lifecycle filters.

        Returns:
            Search result containing scored object summaries.
        """
        q = query.strip().lower()
        filters = filters or {}
        items: list[dict] = []
        if not q:
            return {
                "result_type": "search_results",
                "data": {"query": query, "items": []},
                "warnings": [],
            }

        for object_type in ("node", "knowledge", "activity", "work_item", "source"):
            for obj in self.repository.list(object_type):
                if not self._matches_filters(object_type, obj, filters):
                    continue
                title = str(obj.get("title") or obj.get("name") or obj["id"])
                summary = str(obj.get("summary", ""))
                payload = str(obj.get("payload", ""))
                segments = self._segment_text(obj)
                haystack = f"{title}\n{summary}\n{payload}\n{segments}".lower()
                if q not in haystack:
                    continue
                score = self._score(q, title.lower(), summary.lower(), payload.lower(), segments.lower())
                items.append(
                    {
                        "object_type": object_type,
                        "id": obj["id"],
                        "kind": obj.get("kind", object_type),
                        "title": title,
                        "status": obj.get("status") or obj.get("lifecycle_state"),
                        "summary": summary,
                        "score": score,
                    }
                )
        items.sort(key=lambda item: (-item["score"], item["title"]))
        return {
            "result_type": "search_results",
            "data": {
                "query": query,
                "items": items[:max_items],
            },
            "warnings": [],
        }

    def _parse_time(self, value: str | None) -> datetime:
        if not value:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    def _score(self, query: str, title: str, summary: str, payload: str, segments: str = "") -> int:
        score = 0
        if query == title:
            score += 100
        if query in title:
            score += 20
        if query in summary:
            score += 10
        if query in payload:
            score += 5
        if query in segments:
            score += 3
        return score

    def _segment_text(self, obj: dict) -> str:
        segments = obj.get("segments", [])
        if not isinstance(segments, list):
            return ""
        parts = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            parts.append(str(segment.get("excerpt", "")))
            locator = segment.get("locator", {})
            if isinstance(locator, dict):
                parts.append(str(locator.get("path", "")))
        return "\n".join(parts)

    def _find_object(self, object_id: str) -> tuple[str | None, dict | None]:
        for object_type in ("source", "node", "knowledge", "activity", "work_item"):
            obj = self.repository.get(object_type, object_id)
            if obj is not None:
                return object_type, obj
        return None, None

    def _append_graph_node(self, nodes: list[dict], seen_nodes: set[str], object_type: str, obj: dict) -> None:
        if obj["id"] in seen_nodes:
            return
        seen_nodes.add(obj["id"])
        nodes.append(
            {
                "object_type": object_type,
                "id": obj["id"],
                "kind": obj.get("kind", object_type),
                "title": obj.get("title") or obj.get("name") or obj["id"],
                "status": obj.get("status") or obj.get("lifecycle_state"),
            }
        )

    def _relation_to(self, obj: dict, object_id: str) -> str | None:
        relation_fields = {
            "subject_refs": "subject",
            "related_node_refs": "related_node",
            "related_work_item_refs": "related_work_item",
            "produced_object_refs": "produced_object",
            "source_refs": "source",
            "related_knowledge_refs": "related_knowledge",
            "depends_on": "depends_on",
            "blocked_by": "blocked_by",
            "child_refs": "child",
        }
        for field, relation in relation_fields.items():
            values = obj.get(field, [])
            if isinstance(values, list) and object_id in values:
                return relation
        if obj.get("parent_ref") == object_id:
            return "parent"
        for evidence in obj.get("evidence_refs", []):
            if isinstance(evidence, dict) and evidence.get("source_id") == object_id:
                return "evidence"
        payload = obj.get("payload", {})
        if isinstance(payload, dict) and object_id in payload.values():
            return "payload"
        return None

    def _matches_filters(self, object_type: str, obj: dict, filters: dict) -> bool:
        object_types = self._filter_values(filters, "object_type", "object_types")
        if object_types and object_type not in object_types:
            return False

        kinds = self._filter_values(filters, "kind", "kinds")
        if kinds and str(obj.get("kind", object_type)) not in kinds:
            return False

        statuses = self._filter_values(filters, "status", "statuses")
        status = str(obj.get("status") or obj.get("lifecycle_state") or "")
        if statuses and status not in statuses:
            return False

        node_ids = self._filter_values(filters, "node_id", "node_ids")
        if node_ids and object_type != "node" and not any(self._references_root(obj, node_id) for node_id in node_ids):
            return False
        if node_ids and object_type == "node" and str(obj["id"]) not in node_ids:
            return False

        source_ids = self._filter_values(filters, "source_id", "source_ids")
        if source_ids and object_type != "source" and not any(self._references_root(obj, source_id) for source_id in source_ids):
            return False
        if source_ids and object_type == "source" and str(obj["id"]) not in source_ids:
            return False
        return True

    def _filter_values(self, filters: dict, singular: str, plural: str) -> set[str]:
        value = filters.get(plural, filters.get(singular))
        if value is None:
            return set()
        if isinstance(value, list):
            return {str(item) for item in value}
        return {str(value)}

    def _references_root(self, obj: dict, root_id: str) -> bool:
        for field in (
            "subject_refs",
            "related_node_refs",
            "related_work_item_refs",
            "produced_object_refs",
            "source_refs",
            "related_knowledge_refs",
            "depends_on",
            "blocked_by",
            "child_refs",
        ):
            values = obj.get(field, [])
            if isinstance(values, list) and root_id in values:
                return True
        if obj.get("parent_ref") == root_id:
            return True
        for evidence in obj.get("evidence_refs", []):
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
