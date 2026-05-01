from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from memory_substrate.domain.protocols.context_pack import ContextItem, ContextPack
from memory_substrate.domain.services.ids import new_id
from memory_substrate.domain.services.patch_applier import utc_now_iso
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


CONTEXT_ITEM_SUMMARY_CHARS = 240


class ContextBuilder:
    def __init__(self, root: str | Path) -> None:
        self.repository = FsObjectRepository(root)

    def build(
        self,
        task: str,
        scope: dict | None = None,
        max_items: int = 12,
        query_terms: list[str] | None = None,
    ) -> ContextPack:
        scope = scope or {}
        query_terms = query_terms or []
        items: list[ContextItem] = []
        items.extend(self._items_for("node", scope.get("node_ids")))
        items.extend(self._items_for("knowledge", None))
        items.extend(self._items_for("activity", None))
        items.extend(self._items_for("work_item", None))
        items.extend(self._items_for("source", None))

        filtered = self._filter(items, scope, query_terms)
        selected = filtered[:max_items]
        summary = self._summary(task, selected)
        generated_at = utc_now_iso()
        citations = self._citations(selected)
        decisions = self._typed_items(selected, object_type="knowledge", kind="decision")
        procedures = self._typed_items(selected, object_type="knowledge", kind="procedure")
        open_work = self._open_work(selected)
        decision_ref = self._tier_ref("decisions", decisions)
        procedure_ref = self._tier_ref("procedures", procedures)
        open_work_ref = self._tier_ref("open_work", open_work)
        return ContextPack(
            id=new_id("ctx"),
            task=task,
            summary=summary,
            scope=scope,
            items=selected,
            evidence=citations,
            decisions=decision_ref,
            procedures=procedure_ref,
            open_work=open_work_ref,
            conflicts=[],
            missing_context=[] if selected else ["No relevant context found yet."],
            recommended_next_reads=[item.id for item in selected[:5]],
            citations=citations,
            freshness={"generated_at": generated_at, "expires_at": None},
            context_tiers=self._context_tiers(
                task=task,
                scope=scope,
                decisions=decision_ref,
                procedures=procedure_ref,
                evidence=citations,
                open_work=open_work_ref,
                recommended_next_reads=[item.id for item in selected[:5]],
            ),
            context_budget={
                "max_items": max_items,
                "returned_items": len(selected),
                "detail": "compact",
            },
            generated_at=generated_at,
            expires_at=None,
        )

    def expand(
        self,
        object_id: str,
        max_items: int = 10,
        include_segments: bool = True,
        snippet_chars: int = 360,
    ) -> tuple[list[ContextItem], list[dict]]:
        items: list[ContextItem] = []
        source_segments: list[dict] = []
        for object_type in ("node", "knowledge", "activity", "work_item", "source"):
            obj = self.repository.get(object_type, object_id)
            if obj is not None:
                items.append(self._to_item(object_type, obj))
                items.extend(self._related_items(object_id, obj, max_items=max_items - 1))
                if include_segments:
                    source_segments.extend(
                        self._collect_source_segments(
                            object_id,
                            obj,
                            max_segments=max_items,
                            snippet_chars=snippet_chars,
                        )
                    )
                break
        return items[:max_items], source_segments

    def _items_for(self, object_type: str, object_ids: list[str] | None) -> list[ContextItem]:
        if object_ids:
            objects = [self.repository.get(object_type, object_id) for object_id in object_ids]
            return [self._to_item(object_type, obj) for obj in objects if obj is not None]
        return [self._to_item(object_type, obj) for obj in self.repository.list(object_type)]

    def _filter(self, items: list[ContextItem], scope: dict, query_terms: list[str]) -> list[ContextItem]:
        object_types = set(scope.get("object_types", []))
        if scope.get("object_type"):
            object_types.add(str(scope["object_type"]))
        if object_types:
            items = [item for item in items if item.object_type in object_types]

        statuses = set(scope.get("statuses", []))
        if scope.get("status"):
            statuses.add(str(scope["status"]))
        if statuses:
            items = [item for item in items if item.status in statuses]

        kinds = set(scope.get("kinds", []))
        if scope.get("kind"):
            kinds.add(str(scope["kind"]))
        if kinds:
            items = [item for item in items if item.kind in kinds]

        node_ids = set(scope.get("node_ids", []))
        if not node_ids:
            return self._rank(items, query_terms)
        filtered = [
            item
            for item in items
            if item.id in node_ids or self._references_any_node(item.object_type, item.id, node_ids)
        ]
        return self._rank(filtered or items, query_terms)

    def _rank(self, items: list[ContextItem], query_terms: list[str] | None = None) -> list[ContextItem]:
        query_terms = query_terms or []
        status_rank = {
            "active": 0,
            "finalized": 1,
            "completed": 1,
            "candidate": 2,
            "open": 3,
            "in_progress": 4,
            "blocked": 5,
            "draft": 6,
            "archived": 99,
        }
        return sorted(
            items,
            key=lambda item: (
                -self._query_score(item, query_terms),
                status_rank.get(item.status, 50),
                item.object_type,
                item.title,
            ),
        )

    def _query_score(self, item: ContextItem, query_terms: list[str]) -> int:
        if not query_terms:
            return 0
        title = item.title.lower()
        summary = item.summary.lower()
        metadata = f"{item.kind}\n{item.object_type}".lower()
        score = 0
        for term in query_terms:
            if not term:
                continue
            if term in title:
                score += 3
            if term in summary:
                score += 1
            if term in metadata:
                score += 1
        return score

    def _summary(self, task: str, items: list[ContextItem]) -> str:
        if not items:
            return f"No stored context available yet for task: {task}"
        titles = ", ".join(item.title for item in items[:3])
        return f"Context for '{task}' built from {len(items)} items. Key entries: {titles}"

    def _to_item(self, object_type: str, obj: dict) -> ContextItem:
        kind = str(obj.get("kind", object_type))
        title = str(obj.get("title") or obj.get("name") or obj["id"])
        summary = self._clip_summary(self._summary_text(object_type, obj))
        status = str(obj.get("status") or obj.get("lifecycle_state") or "unknown")
        return ContextItem(
            object_type=object_type,
            id=str(obj["id"]),
            kind=kind,
            title=title,
            status=status,
            summary=summary,
        )

    def _summary_text(self, object_type: str, obj: dict) -> str:
        summary = str(obj.get("summary", ""))
        if summary or object_type != "source" or obj.get("kind") != "repo":
            return summary
        payload = obj.get("payload", {})
        if not isinstance(payload, dict):
            return ""
        source_roots = payload.get("source_roots", [])
        roots = ""
        if isinstance(source_roots, list) and source_roots:
            roots = f" Source roots: {', '.join(str(root) for root in source_roots)}."
        code_modules = payload.get("code_modules", payload.get("python_modules", []))
        module_names = []
        if isinstance(code_modules, list):
            module_names = [
                str(Path(str(module.get("path", ""))).with_suffix("")).replace("/", ".")
                for module in code_modules[:12]
                if isinstance(module, dict) and module.get("path")
            ]
        modules = f" Code modules: {', '.join(module_names)}." if module_names else ""
        document_sections = payload.get("document_sections", [])
        document_parts: list[str] = []
        if isinstance(document_sections, list):
            for section in document_sections[:3]:
                if not isinstance(section, dict):
                    continue
                path = str(section.get("path", ""))
                heading = str(section.get("heading", ""))
                excerpt = " ".join(str(section.get("excerpt", "")).split())[:120]
                if path and heading:
                    document_parts.append(f"{path}#{heading}: {excerpt}")
        documents = f" Documents: {' | '.join(document_parts)}." if document_parts else ""
        language_counts = payload.get("language_counts", {})
        languages = ""
        if isinstance(language_counts, dict) and language_counts:
            languages = ". Languages: " + ", ".join(
                f"{language}:{count}" for language, count in list(language_counts.items())[:5]
            )
        return (
            f"Repository {payload.get('repo_name', obj.get('title', 'repo'))} "
            f"with {payload.get('file_count', 0)} files and {payload.get('dir_count', 0)} directories."
            f"{roots}{modules}{documents}{languages}"
        )

    def _clip_summary(self, summary: str) -> str:
        if len(summary) <= CONTEXT_ITEM_SUMMARY_CHARS:
            return summary
        return summary[: CONTEXT_ITEM_SUMMARY_CHARS - 3].rstrip() + "..."

    def _citations(self, items: list[ContextItem]) -> list[dict]:
        citations: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            obj = self.repository.get(item.object_type, item.id)
            if obj is None:
                continue
            for evidence in obj.get("evidence_refs", []):
                if not isinstance(evidence, dict):
                    continue
                source_id = str(evidence.get("source_id", ""))
                segment_id = str(evidence.get("segment_id", ""))
                if not source_id or not segment_id:
                    continue
                key = (source_id, segment_id)
                if key in seen:
                    continue
                seen.add(key)
                citations.append({"source_id": source_id, "segment_id": segment_id, "object_id": item.id})
        return citations

    def _typed_items(self, items: list[ContextItem], object_type: str, kind: str) -> list[dict]:
        return [
            {
                "object_type": item.object_type,
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "status": item.status,
                "summary": item.summary,
            }
            for item in items
            if item.object_type == object_type and item.kind == kind
        ]

    def _open_work(self, items: list[ContextItem]) -> list[dict]:
        open_statuses = {"open", "in_progress", "blocked"}
        return [
            {
                "object_type": item.object_type,
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "status": item.status,
                "summary": item.summary,
            }
            for item in items
            if item.object_type == "work_item" and item.status in open_statuses
        ]

    def _context_tiers(
        self,
        task: str,
        scope: dict,
        decisions: dict,
        procedures: dict,
        evidence: list[dict],
        open_work: dict,
        recommended_next_reads: list[str],
    ) -> dict:
        return {
            "policy": {"field": "policy", "count": 0, "ids": []},
            "active_task": {
                "task": task,
                "scope": scope,
            },
            "decisions": decisions,
            "procedures": procedures,
            "evidence": self._tier_ref("evidence", evidence),
            "open_work": open_work,
            "deep_search_hints": [
                {
                    "tool": "memory_query",
                    "mode": "expand",
                    "ids": recommended_next_reads,
                }
            ] if recommended_next_reads else [],
        }

    def _tier_ref(self, field: str, items: list[dict]) -> dict:
        return {
            "field": field,
            "count": len(items),
            "ids": [str(item.get("id") or f"{item.get('source_id')}#{item.get('segment_id')}") for item in items],
        }

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

    def _collect_source_segments(
        self,
        root_id: str,
        obj: dict,
        max_segments: int = 10,
        snippet_chars: int = 360,
    ) -> list[dict]:
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
            for segment in source.get("segments", [])[:max_segments]:
                segments.append(
                    {
                        "source_id": source_id,
                        "segment_id": segment.get("segment_id"),
                        "locator": segment.get("locator"),
                        "excerpt": self._clip(str(segment.get("excerpt", "")), snippet_chars),
                    }
                )
        return segments

    def _clip(self, text: str, max_chars: int) -> str:
        max_chars = max(3, max_chars)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

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
