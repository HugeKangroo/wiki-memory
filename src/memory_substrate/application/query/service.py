from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from memory_substrate.domain.services.context_builder import ContextBuilder
from memory_substrate.domain.services.ids import new_id
from memory_substrate.domain.services.patch_applier import utc_now_iso
from memory_substrate.domain.protocols.remember_request import TEMPORARY_LIFECYCLE_STATES
from memory_substrate.application.semantic.service import SemanticIndexService
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


RRF_K = 60
QUERY_SANITIZER_MAX_CHARS = 400
QUERY_SANITIZER_LABEL_RE = re.compile(
    r"^\s*(?:question|query|task|user question|用户问题|问题|任务)\s*[:：]\s*(.+?)\s*$",
    re.IGNORECASE,
)

QUERY_NORMALIZATION_RULES = (
    {
        "triggers": ("待办", "待办项", "todo", "to-do", "task", "tasks", "任务"),
        "terms": ("待办", "待办项", "todo", "to-do", "task", "tasks", "任务", "work_item", "open", "pending"),
        "filters": {"object_types": ("work_item",), "statuses": ("open", "in_progress", "blocked", "pending")},
    },
    {
        "triggers": ("决策", "decision", "decisions"),
        "terms": ("决策", "decision", "decisions"),
        "filters": {"object_types": ("knowledge",), "kinds": ("decision",)},
    },
    {
        "triggers": ("偏好", "preference", "preferences"),
        "terms": ("偏好", "preference", "preferences"),
        "filters": {"object_types": ("knowledge",), "kinds": ("preference",)},
    },
    {
        "triggers": ("流程", "procedure", "procedures"),
        "terms": ("流程", "procedure", "procedures"),
        "filters": {"object_types": ("knowledge",), "kinds": ("procedure",)},
    },
    {
        "triggers": ("证据", "evidence", "source", "sources"),
        "terms": ("证据", "evidence", "source", "sources"),
        "filters": {"object_types": ("source", "knowledge")},
    },
    {
        "triggers": (
            "架构",
            "architecture",
            "codebase",
            "repo",
            "repository",
            "module",
            "modules",
            "源码",
            "代码",
        ),
        "terms": (
            "架构",
            "architecture",
            "codebase",
            "repo",
            "repository",
            "module",
            "modules",
            "source",
            "code_index",
            "code_modules",
        ),
        "filters": {"object_types": ("source", "node")},
    },
)


class QueryService:
    def __init__(self, root: str | Path, graph_backend=None, semantic_index: SemanticIndexService | None = None) -> None:
        """Create a query service bound to one memory-substrate root.

        Args:
            root: Memory-substrate root directory to query.

        Returns:
            None.
        """
        self.builder = ContextBuilder(root)
        self.repository = FsObjectRepository(root)
        self.graph_backend = graph_backend
        self.semantic_index = semantic_index

    def context(self, task: str, scope: dict | None = None, max_items: int = 12) -> dict:
        """Build a task-focused context pack from relevant memory objects.

        Args:
            task: Natural-language task or question to gather context for.
            scope: Optional filters or hints that constrain retrieval.
            max_items: Maximum number of context items to return.

        Returns:
            Context pack with ranked items, conflicts, missing context, citations, and expiry metadata.
        """
        sanitized = self._sanitize_query_text(task)
        effective_task = sanitized["query"]
        plan = self._query_plan(effective_task)
        scoped = self._scope_with_query_plan(scope or {}, plan)
        if self.graph_backend is not None:
            result = self._graph_context(task=effective_task, scope=scoped, max_items=max_items, plan=plan)
            result["data"]["query_sanitizer"] = sanitized["diagnostics"]
            result["warnings"].extend(self._query_sanitizer_warnings(sanitized["diagnostics"]))
            return result

        pack = self.builder.build(task=effective_task, scope=scoped, max_items=max_items, query_terms=plan["terms"])
        return {
            "result_type": "context_pack",
            "data": {
                "id": pack.id,
                "task": pack.task,
                "summary": pack.summary,
                "scope": pack.scope,
                "items": [asdict(item) for item in pack.items],
                "evidence": pack.evidence,
                "decisions": pack.decisions,
                "procedures": pack.procedures,
                "open_work": pack.open_work,
                "conflicts": pack.conflicts,
                "missing_context": pack.missing_context,
                "recommended_next_reads": pack.recommended_next_reads,
                "citations": pack.citations,
                "freshness": pack.freshness,
                "context_tiers": pack.context_tiers,
                "context_budget": pack.context_budget,
                "generated_at": pack.generated_at,
                "expires_at": pack.expires_at,
                "normalized_terms": plan["terms"],
                "inferred_filters": plan["inferred_filters"],
                "query_sanitizer": sanitized["diagnostics"],
            },
            "warnings": self._query_sanitizer_warnings(sanitized["diagnostics"]),
        }

    def expand(
        self,
        object_id: str,
        max_items: int = 10,
        include_segments: bool | None = None,
        snippet_chars: int | None = None,
    ) -> dict:
        """Expand one memory object into nearby context and source evidence.

        Args:
            object_id: Source, node, knowledge, activity, or work item identifier to expand from.
            max_items: Maximum number of related context items to return.

        Returns:
            Expanded context items and source segments for the requested object.
        """
        items, source_segments = self.builder.expand(
            object_id=object_id,
            max_items=max_items,
            include_segments=True if include_segments is None else include_segments,
            snippet_chars=snippet_chars or 360,
        )
        return {
            "result_type": "expanded_context",
            "data": {
                "root_id": object_id,
                "items": [asdict(item) for item in items],
                "source_segments": source_segments,
            },
            "warnings": [],
        }

    def expand_many(
        self,
        object_ids: list[str],
        max_items: int = 20,
        per_id_max_items: int = 5,
        include_segments: bool | None = None,
        snippet_chars: int | None = None,
    ) -> dict:
        """Expand several memory objects in one bounded grouped result.

        Args:
            object_ids: Source, node, knowledge, activity, or work item identifiers to expand.
            max_items: Total context item budget across all expanded ids.
            per_id_max_items: Maximum context items per requested id.
            include_segments: Whether to include source segment snippets.
            snippet_chars: Maximum segment excerpt length.

        Returns:
            Grouped expanded contexts keyed by root id, plus deduplicated source segments and warnings.
        """
        unique_ids = self._unique_ids(object_ids)
        max_items = max(1, int(max_items or 20))
        per_id_max_items = max(1, int(per_id_max_items or 5))
        include = True if include_segments is None else include_segments
        snippets = snippet_chars or 360
        groups: dict[str, dict] = {}
        source_segments: list[dict] = []
        seen_segments: set[tuple[str, str]] = set()
        warnings: list[str] = []
        returned_items = 0
        expanded_ids: list[str] = []
        missing_ids: list[str] = []

        for object_id in unique_ids:
            remaining_items = max_items - returned_items
            if remaining_items <= 0:
                warning = "Global expand item budget exhausted before all ids were expanded."
                if warning not in warnings:
                    warnings.append(warning)
                groups[object_id] = {
                    "root_id": object_id,
                    "status": "budget_exhausted",
                    "items": [],
                    "source_segments": [],
                    "warnings": ["Global expand item budget exhausted before this id was expanded."],
                }
                continue

            object_type, obj = self._find_object(object_id)
            if obj is None or object_type is None:
                missing_ids.append(object_id)
                warning = f"Object not found: {object_id}"
                warnings.append(warning)
                groups[object_id] = {
                    "root_id": object_id,
                    "status": "not_found",
                    "items": [],
                    "source_segments": [],
                    "warnings": [warning],
                }
                continue

            group_budget = min(per_id_max_items, remaining_items)
            items, segments = self.builder.expand(
                object_id=object_id,
                max_items=group_budget,
                include_segments=include,
                snippet_chars=snippets,
            )
            item_payloads = [asdict(item) for item in items]
            segment_payloads = list(segments)
            returned_items += len(item_payloads)
            expanded_ids.append(object_id)
            for segment in segment_payloads:
                key = (str(segment.get("source_id", "")), str(segment.get("segment_id", "")))
                if key in seen_segments:
                    continue
                seen_segments.add(key)
                source_segments.append(segment)
            groups[object_id] = {
                "root_id": object_id,
                "object_type": object_type,
                "status": "ok",
                "items": item_payloads,
                "source_segments": segment_payloads,
                "context_budget": {
                    "max_items": group_budget,
                    "returned_items": len(item_payloads),
                    "include_segments": include,
                    "snippet_chars": snippets,
                },
                "warnings": [],
            }

        return {
            "result_type": "expanded_context_many",
            "data": {
                "root_ids": unique_ids,
                "expanded_ids": expanded_ids,
                "missing_ids": missing_ids,
                "groups": groups,
                "source_segments": source_segments,
                "context_budget": {
                    "max_items": max_items,
                    "per_id_max_items": per_id_max_items,
                    "returned_items": returned_items,
                    "include_segments": include,
                    "snippet_chars": snippets,
                },
            },
            "warnings": warnings,
        }

    def page(
        self,
        object_id: str,
        detail: str | None = None,
        max_items: int | None = None,
        include_segments: bool | None = None,
        snippet_chars: int | None = None,
    ) -> dict:
        """Fetch one memory object, compact by default and full on request.

        Args:
            object_id: Source, node, knowledge, activity, or work item identifier to fetch.
            detail: `compact` by default, or `full` to return complete bounded objects.
                Repo sources do not support full detail because their payloads are intended as compact locators.
            max_items: Maximum list entries in compact object previews.
            include_segments: Whether compact source pages include segment snippets.
            snippet_chars: Maximum excerpt length in compact previews.

        Returns:
            Page result containing the object type and object payload, or a warning if missing.
        """
        for object_type in ("source", "node", "knowledge", "activity", "work_item"):
            obj = self.repository.get(object_type, object_id)
            if obj is not None:
                if detail == "full":
                    if object_type == "source" and obj.get("kind") == "repo":
                        return {
                            "result_type": "page_unavailable",
                            "status": "unsupported",
                            "data": {
                                "object_type": object_type,
                                "object_id": obj["id"],
                                "kind": obj.get("kind"),
                                "requested_detail": "full",
                                "unsupported_detail": "repo_source_full",
                                "supported_details": ["compact"],
                                "reason": "repo_sources_expose_compact_locators_not_full_payloads",
                                "next_actions": [
                                    "call_memory_query_page_without_full_detail",
                                    "use_compact_locators_to_choose_files",
                                    "read_local_files_for_complete_source",
                                ],
                            },
                            "warnings": [
                                "Repo source full detail is unavailable through memory_query page. Use compact page indexes and local file reads for complete source.",
                            ],
                        }
                    return {
                        "result_type": "page",
                        "data": {
                            "object_type": object_type,
                            "object": obj,
                            "detail": "full",
                        },
                        "warnings": [],
                    }
                compact = self._compact_object_page(
                    object_type=object_type,
                    obj=obj,
                    max_items=max_items or 10,
                    include_segments=False if include_segments is None else include_segments,
                    snippet_chars=snippet_chars or 360,
                )
                warnings = ["Compact page returned. Use options.detail='full' only when the complete stored object is required."]
                if object_type == "source" and obj.get("kind") == "repo":
                    warnings = [
                        "Compact repo source page returned. Use returned locators and local file reads for complete code or documents; full repo source pages are unavailable through memory_query page.",
                    ]
                return {
                    "result_type": "page",
                    "data": {
                        "object_type": object_type,
                        "object": compact["object"],
                        "detail": "compact",
                        "truncated": compact["truncated"],
                    },
                    "warnings": warnings,
                }
        return {
            "result_type": "page",
            "data": None,
            "warnings": [f"Object not found: {object_id}"],
        }

    def source_slice(
        self,
        source_id: str,
        path: str | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        segment_id: str | None = None,
        max_lines: int = 120,
        snippet_chars: int = 8000,
    ) -> dict:
        """Hydrate a bounded source text slice by source id and optional path/line locator.

        Args:
            source_id: Source object id to read from.
            path: Repo-relative path for repo sources. Optional for text document sources.
            line_start: 1-based start line. Defaults to 1 or the segment start when segment_id is supplied.
            line_end: 1-based inclusive end line. Defaults to a bounded window.
            segment_id: Optional source segment id whose locator provides default line bounds.
            max_lines: Maximum number of lines to return.
            snippet_chars: Maximum number of characters to return.

        Returns:
            Bounded source slice or an unavailable result with warnings.
        """
        source = self.repository.get("source", source_id)
        if source is None:
            return self._source_slice_unavailable(
                status="not_found",
                source_id=source_id,
                path=path,
                warnings=[f"Source not found: {source_id}"],
            )
        if source.get("kind") == "repo":
            return self._repo_source_slice(
                source=source,
                path=path,
                line_start=line_start,
                line_end=line_end,
                max_lines=max_lines,
                snippet_chars=snippet_chars,
            )
        return self._text_source_slice(
            source=source,
            path=path,
            line_start=line_start,
            line_end=line_end,
            segment_id=segment_id,
            max_lines=max_lines,
            snippet_chars=snippet_chars,
        )

    def graph(self, object_id: str, max_items: int = 20) -> dict:
        """Build a lightweight one-hop relationship graph around an object.

        Args:
            object_id: Memory object identifier to use as the graph root.
            max_items: Maximum number of graph nodes to include.

        Returns:
            Graph result with root id, nodes, edges, and warnings for missing roots.
        """
        if self.graph_backend is not None:
            graph = self.graph_backend.neighborhood(object_id, max_items=max_items)
            nodes = graph.get("nodes", [])
            warnings = [] if nodes else [f"Object not found: {object_id}"]
            return {
                "result_type": "graph",
                "data": {
                    "root_id": object_id,
                    "nodes": nodes,
                    "edges": [
                        {
                            "source_id": relation.get("source_id"),
                            "target_id": relation.get("target_id"),
                            "relation": relation.get("relation_type"),
                            "id": relation.get("id"),
                        }
                        for relation in graph.get("relations", [])
                    ],
                },
                "warnings": warnings,
            }

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
        sanitized = self._sanitize_query_text(query)
        effective_query = sanitized["query"]
        plan = self._query_plan(effective_query)
        terms = plan["terms"]
        filters = filters or {}
        applied_filters = self._scope_with_query_plan(filters, plan)
        items: list[dict] = []
        if not terms:
            return {
                "result_type": "search_results",
                "data": {
                    "query": effective_query,
                    "items": [],
                    "normalized_terms": [],
                    "applied_filters": applied_filters,
                    "inferred_filters": {},
                    "suggested_retry_terms": [],
                    "query_sanitizer": sanitized["diagnostics"],
                },
                "warnings": self._query_sanitizer_warnings(sanitized["diagnostics"]),
            }

        primary_terms = plan.get("primary_terms", terms)
        search_terms = terms or primary_terms
        fallback_terms = plan.get("fallback_terms", terms[1:])
        if self.graph_backend is not None:
            items = self._graph_search_terms(primary_terms, max_items=max_items, filters=applied_filters)
            if not items:
                items = self._graph_search_terms(fallback_terms, max_items=max_items, filters=applied_filters)
        else:
            items = self._lexical_search_terms(search_terms, filters=applied_filters)
            if not items:
                items = self._lexical_search_terms(fallback_terms, filters=applied_filters)
        if self.semantic_index is not None:
            semantic_items = self.semantic_index.search(effective_query, max_items=max_items, filters=applied_filters)
            items = self._merge_search_items(items, semantic_items)
        items.sort(key=lambda item: (-item["score"], item["title"]))
        return {
            "result_type": "search_results",
            "data": {
                "query": effective_query,
                "items": items[:max_items],
                "normalized_terms": terms,
                "applied_filters": applied_filters,
                "inferred_filters": plan["inferred_filters"],
                "suggested_retry_terms": [] if items else terms[1:],
                "semantic_backend": self.semantic_index.__class__.__name__ if self.semantic_index is not None else None,
                "query_sanitizer": sanitized["diagnostics"],
            },
            "warnings": self._query_sanitizer_warnings(sanitized["diagnostics"]),
        }

    def _unique_ids(self, object_ids: list[str]) -> list[str]:
        unique: list[str] = []
        for object_id in object_ids:
            value = str(object_id or "").strip()
            if value and value not in unique:
                unique.append(value)
        return unique

    def _repo_source_slice(
        self,
        source: dict,
        path: str | None,
        line_start: int | None,
        line_end: int | None,
        max_lines: int,
        snippet_chars: int,
    ) -> dict:
        repo_root = Path(str(source.get("origin", {}).get("path") or ""))
        if not path:
            return self._source_slice_unavailable(
                status="missing_path",
                source_id=source["id"],
                path=path,
                warnings=["Repo source slices require input_data.path."],
            )
        requested = Path(path)
        if requested.is_absolute():
            return self._source_slice_unavailable(
                status="invalid_path",
                source_id=source["id"],
                path=path,
                warnings=["Repo source slice path must be relative and must stay within repo origin."],
            )
        target = (repo_root / requested).resolve()
        repo_root = repo_root.resolve()
        if not target.is_relative_to(repo_root):
            return self._source_slice_unavailable(
                status="invalid_path",
                source_id=source["id"],
                path=path,
                warnings=["Repo source slice path must stay within repo origin."],
            )
        normalized_path = target.relative_to(repo_root).as_posix()
        indexed_sha256 = self._repo_indexed_sha256(source, normalized_path)
        if indexed_sha256 is None:
            return self._source_slice_unavailable(
                status="path_not_indexed",
                source_id=source["id"],
                path=path,
                warnings=[f"Repo source path was not part of the ingested repo source index: {path}"],
            )
        if not target.exists() or not target.is_file():
            return self._source_slice_unavailable(
                status="path_not_found",
                source_id=source["id"],
                path=path,
                warnings=[f"Repo source path not found: {path}"],
            )
        try:
            raw = target.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return self._source_slice_unavailable(
                status="unreadable",
                source_id=source["id"],
                path=path,
                warnings=[f"Repo source path is not readable as utf-8 text: {path}"],
            )
        current_sha256 = hashlib.sha256(raw).hexdigest()
        content_hash = {
            "algorithm": "sha256",
            "current": current_sha256,
            "indexed": indexed_sha256,
            "matches_index": current_sha256 == indexed_sha256,
        }
        warnings = []
        if not content_hash["matches_index"]:
            warnings.append(
                "Repo source slice current file hash differs from the ingested index. Re-ingest before treating it as current evidence."
            )
        return self._source_slice_from_text(
            source=source,
            path=normalized_path,
            text=text,
            line_start=line_start,
            line_end=line_end,
            max_lines=max_lines,
            snippet_chars=snippet_chars,
            locator_kind="repo_file_slice",
            content_hash=content_hash,
            warnings=warnings,
        )

    def _text_source_slice(
        self,
        source: dict,
        path: str | None,
        line_start: int | None,
        line_end: int | None,
        segment_id: str | None,
        max_lines: int,
        snippet_chars: int,
    ) -> dict:
        payload = source.get("payload", {})
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            return self._source_slice_unavailable(
                status="unsupported_source",
                source_id=source["id"],
                path=path,
                warnings=["Source does not expose text payload slices."],
            )
        segment = self._source_segment(source, segment_id) if segment_id else None
        if segment_id and segment is None:
            return self._source_slice_unavailable(
                status="segment_not_found",
                source_id=source["id"],
                path=path,
                warnings=[f"Source segment not found: {segment_id}"],
            )
        locator = segment.get("locator", {}) if isinstance(segment, dict) else {}
        if isinstance(locator, dict):
            line_start = line_start or locator.get("line_start")
            line_end = line_end or locator.get("line_end")
        display_path = path or str(source.get("origin", {}).get("path") or source.get("title") or source["id"])
        return self._source_slice_from_text(
            source=source,
            path=display_path,
            text=text,
            line_start=line_start,
            line_end=line_end,
            max_lines=max_lines,
            snippet_chars=snippet_chars,
            locator_kind="text_source_slice",
            segment_id=segment_id,
            content_hash=self._text_content_hash(text),
        )

    def _source_segment(self, source: dict, segment_id: str | None) -> dict | None:
        if not segment_id:
            return None
        for segment in source.get("segments", []):
            if isinstance(segment, dict) and segment.get("segment_id") == segment_id:
                return segment
        return None

    def _source_slice_from_text(
        self,
        source: dict,
        path: str,
        text: str,
        line_start: int | None,
        line_end: int | None,
        max_lines: int,
        snippet_chars: int,
        locator_kind: str,
        segment_id: str | None = None,
        content_hash: dict | None = None,
        warnings: list[str] | None = None,
    ) -> dict:
        lines = text.splitlines()
        total_lines = len(lines)
        max_lines = max(1, int(max_lines or 120))
        snippet_chars = max(40, int(snippet_chars or 8000))
        start = max(1, int(line_start or 1))
        requested_end = int(line_end) if line_end is not None else start + max_lines - 1
        if requested_end < start:
            return self._source_slice_unavailable(
                status="invalid_range",
                source_id=source["id"],
                path=path,
                warnings=["line_end must be greater than or equal to line_start."],
            )
        effective_end = min(requested_end, total_lines, start + max_lines - 1)
        if start > total_lines:
            selected = []
            effective_end = start - 1
        else:
            selected = lines[start - 1 : effective_end]
        slice_text = "\n".join(selected)
        char_truncated = len(slice_text) > snippet_chars
        if char_truncated:
            slice_text = self._clip(slice_text, snippet_chars)
        line_truncated = effective_end < requested_end
        truncated = bool(line_truncated or char_truncated)
        next_slice = None
        if line_truncated and effective_end < total_lines:
            next_slice = {
                "source_id": source["id"],
                "path": path,
                "line_start": effective_end + 1,
                "line_end": min(total_lines, effective_end + max_lines),
            }
        locator = {
            "kind": locator_kind,
            "path": path,
            "line_start": start,
            "line_end": effective_end,
        }
        if segment_id:
            locator["segment_id"] = segment_id
        return {
            "result_type": "source_slice",
            "status": "ok",
            "data": {
                "source_id": source["id"],
                "kind": source.get("kind"),
                "title": source.get("title"),
                "path": path,
                "line_start": start,
                "line_end": effective_end,
                "requested_line_start": start,
                "requested_line_end": requested_end,
                "total_lines": total_lines,
                "text": slice_text,
                "truncated": truncated,
                "truncation": {
                    "line_truncated": line_truncated,
                    "char_truncated": char_truncated,
                    "max_lines": max_lines,
                    "snippet_chars": snippet_chars,
                },
                "next_slice": next_slice,
                "locator": locator,
                "content_hash": content_hash or self._text_content_hash(text),
                "source_fingerprint": source.get("fingerprint"),
            },
            "warnings": warnings or [],
        }

    def _repo_indexed_sha256(self, source: dict, path: str) -> str | None:
        payload = source.get("payload", {})
        if not isinstance(payload, dict):
            return None
        for collection in ("code_index", "doc_index"):
            for entry in payload.get(collection, []):
                if isinstance(entry, dict) and entry.get("path") == path and entry.get("sha256"):
                    return str(entry["sha256"])
        return None

    def _text_content_hash(self, text: str) -> dict:
        return {
            "algorithm": "sha256",
            "current": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "indexed": None,
            "matches_index": None,
        }

    def _source_slice_unavailable(
        self,
        status: str,
        source_id: str,
        path: str | None,
        warnings: list[str],
    ) -> dict:
        return {
            "result_type": "source_slice_unavailable",
            "status": status,
            "data": {
                "source_id": source_id,
                "path": path,
            },
            "warnings": warnings,
        }

    def _lexical_search_terms(self, terms: list[str], filters: dict) -> list[dict]:
        items: list[dict] = []
        for object_type in ("node", "knowledge", "activity", "work_item", "source"):
            for obj in self.repository.list(object_type):
                if not self._matches_filters(object_type, obj, filters):
                    continue
                title = str(obj.get("title") or obj.get("name") or obj["id"])
                summary = self._object_summary(object_type, obj)
                payload = str(obj.get("payload", ""))
                segments = self._segment_text(obj)
                metadata = self._metadata_text(object_type, obj)
                haystack = f"{title}\n{summary}\n{payload}\n{segments}\n{metadata}".lower()
                matching_terms = [term for term in terms if term in haystack]
                if not matching_terms:
                    continue
                score = max(
                    self._score(
                        term,
                        title.lower(),
                        summary.lower(),
                        payload.lower(),
                        segments.lower(),
                        metadata.lower(),
                    )
                    for term in matching_terms
                )
                items.append(
                    {
                        "object_type": object_type,
                        "id": obj["id"],
                        "kind": obj.get("kind", object_type),
                        "title": title,
                        "status": obj.get("status") or obj.get("lifecycle_state"),
                        "summary": summary,
                        "score": score,
                        "lexical_score": score,
                        "matched_terms": matching_terms,
                        "retrieval_sources": ["lexical"],
                    }
                )
        return items

    def _merge_search_items(self, lexical_items: list[dict], semantic_items: list[dict]) -> list[dict]:
        if not semantic_items:
            return lexical_items

        merged: dict[str, dict] = {}
        ranked_lexical = sorted(lexical_items, key=lambda item: (-item.get("score", 0), item["title"], item["id"]))
        lexical_rank_source = (
            "graph" if any("graph" in item.get("retrieval_sources", []) for item in ranked_lexical) else "lexical"
        )

        def add_ranked_item(item: dict, source: str, rank: int) -> None:
            item_id = item["id"]
            if item_id not in merged:
                merged[item_id] = dict(item)
                merged[item_id]["retrieval_sources"] = []
                merged[item_id]["retrieval_ranks"] = {}
            existing = merged[item_id]
            sources = existing["retrieval_sources"]
            for retrieval_source in item.get("retrieval_sources", [source]):
                if retrieval_source not in sources:
                    sources.append(retrieval_source)
            existing["retrieval_ranks"][source] = rank
            if source in {"graph", "lexical"}:
                existing["lexical_score"] = item.get("lexical_score", item.get("score", 0))
                existing["matched_terms"] = item.get("matched_terms", existing.get("matched_terms", []))
            if source == "semantic":
                existing["semantic_score"] = item.get("semantic_score")
                if item.get("matched_chunks"):
                    existing["matched_chunks"] = item["matched_chunks"]
            for field in ("object_type", "kind", "title", "status", "summary"):
                if not existing.get(field) and item.get(field):
                    existing[field] = item[field]

        for rank, item in enumerate(ranked_lexical, start=1):
            add_ranked_item(item, lexical_rank_source, rank)
        for rank, item in enumerate(semantic_items, start=1):
            add_ranked_item(item, "semantic", rank)

        for item in merged.values():
            rank_score = sum(1.0 / (RRF_K + rank) for rank in item["retrieval_ranks"].values())
            item["rank_score"] = round(rank_score, 6)
            item["score"] = round(rank_score * 1000, 6)
        return list(merged.values())

    def _graph_context(
        self, task: str, scope: dict | None = None, max_items: int = 12, plan: dict | None = None
    ) -> dict:
        scope = scope or {}
        plan = plan or self._query_plan(task)
        filters = scope if isinstance(scope, dict) else {}
        search_terms = plan.get("primary_terms", plan["terms"])
        items = [
            self._graph_context_item(item)
            for item in self._graph_search_terms(search_terms, max_items=max_items, filters=filters)
            if self._matches_filters(item.get("object_type", ""), item, filters)
        ][:max_items]
        if not items:
            items = [
                self._graph_context_item(item)
                for item in self._graph_search_terms(
                    plan.get("fallback_terms", plan["terms"][1:]),
                    max_items=max_items,
                    filters=filters,
                )
                if self._matches_filters(item.get("object_type", ""), item, filters)
            ][:max_items]
        generated_at = utc_now_iso()
        citations = self._graph_citations(items)
        decisions = [
            item for item in items if item["object_type"] == "knowledge" and item["kind"] == "decision"
        ]
        procedures = [
            item for item in items if item["object_type"] == "knowledge" and item["kind"] == "procedure"
        ]
        open_work = [
            item
            for item in items
            if item["object_type"] == "work_item" and item.get("status") in {"open", "in_progress", "blocked"}
        ]
        decision_ref = self._tier_ref("decisions", decisions)
        procedure_ref = self._tier_ref("procedures", procedures)
        open_work_ref = self._tier_ref("open_work", open_work)
        recommended_next_reads = [item["id"] for item in items[:5]]
        return {
            "result_type": "context_pack",
            "data": {
                "id": new_id("ctx"),
                "task": task,
                "summary": self._graph_context_summary(task, items),
                "scope": scope,
                "items": items,
                "evidence": citations,
                "decisions": decision_ref,
                "procedures": procedure_ref,
                "open_work": open_work_ref,
                "conflicts": [],
                "missing_context": [] if items else ["No relevant context found yet."],
                "recommended_next_reads": recommended_next_reads,
                "citations": citations,
                "freshness": {"generated_at": generated_at, "expires_at": None},
                "context_tiers": self._context_tiers(
                    task=task,
                    scope=scope,
                    decisions=decision_ref,
                    procedures=procedure_ref,
                    evidence=citations,
                    open_work=open_work_ref,
                    recommended_next_reads=recommended_next_reads,
                ),
                "context_budget": {
                    "max_items": max_items,
                    "returned_items": len(items),
                    "detail": "compact",
                },
                "generated_at": generated_at,
                "expires_at": None,
                "normalized_terms": plan["terms"],
                "inferred_filters": plan["inferred_filters"],
            },
            "warnings": [],
        }

    def _graph_context_item(self, item: dict) -> dict:
        return {
            "object_type": item.get("object_type", "unknown"),
            "id": item["id"],
            "kind": item.get("kind", item.get("object_type", "unknown")),
            "title": item.get("title", item["id"]),
            "status": item.get("status", "active"),
            "summary": self._clip(str(item.get("summary", "")), 240),
            "evidence_refs": item.get("evidence_refs", []),
        }

    def _graph_citations(self, items: list[dict]) -> list[dict]:
        citations: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for item in items:
            for evidence in item.get("evidence_refs", []):
                if not isinstance(evidence, dict):
                    continue
                source_id = str(evidence.get("source_id", ""))
                segment_id = str(evidence.get("segment_id", ""))
                if not source_id or not segment_id:
                    continue
                key = (source_id, segment_id, item["id"])
                if key in seen:
                    continue
                seen.add(key)
                citations.append({"source_id": source_id, "segment_id": segment_id, "object_id": item["id"]})
        return citations

    def _graph_context_summary(self, task: str, items: list[dict]) -> str:
        if not items:
            return f"No stored context available yet for task: {task}"
        titles = ", ".join(item["title"] for item in items[:3])
        return f"Context for '{task}' built from {len(items)} graph items. Key entries: {titles}"

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

    def _graph_search_terms(self, terms: list[str], max_items: int, filters: dict) -> list[dict]:
        graph_items: list[dict] = []
        seen: set[str] = set()
        for term in terms:
            for item in self.graph_backend.search(query=term, max_items=max_items):
                item_id = str(item.get("id", ""))
                if not item_id or item_id in seen:
                    continue
                if not self._matches_filters(item.get("object_type", ""), item, filters):
                    continue
                seen.add(item_id)
                graph_items.append({**item, "retrieval_sources": ["graph"]})
                if len(graph_items) >= max_items:
                    return graph_items
        return graph_items

    def _score(
        self, query: str, title: str, summary: str, payload: str, segments: str = "", metadata: str = ""
    ) -> int:
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
        if query in metadata:
            score += 8
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

    def _metadata_text(self, object_type: str, obj: dict) -> str:
        parts: list[str] = [
            str(obj.get("id") or ""),
            object_type,
            str(obj.get("kind", object_type)),
            str(obj.get("status") or ""),
            str(obj.get("lifecycle_state") or ""),
            str(obj.get("identity_key") or ""),
        ]
        for field in (
            "aliases",
            "subject_refs",
            "related_node_refs",
            "related_work_item_refs",
            "source_refs",
            "related_knowledge_refs",
        ):
            value = obj.get(field, [])
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
        for evidence in obj.get("evidence_refs", []):
            if isinstance(evidence, dict):
                parts.append(str(evidence.get("source_id", "")))
                parts.append(str(evidence.get("segment_id", "")))
        return "\n".join(part for part in parts if part)

    def _object_summary(self, object_type: str, obj: dict) -> str:
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
        module_names: list[str] = []
        if isinstance(code_modules, list):
            module_names = [
                self._module_name(str(module.get("path", "")))
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

    def _module_name(self, module_path: str) -> str:
        return str(Path(module_path).with_suffix("")).replace("/", ".")

    def _compact_object_page(
        self,
        object_type: str,
        obj: dict,
        max_items: int,
        include_segments: bool,
        snippet_chars: int,
    ) -> dict:
        compact = {
            "id": obj["id"],
            "kind": obj.get("kind", object_type),
            "title": obj.get("title") or obj.get("name") or obj["id"],
            "status": obj.get("status") or obj.get("lifecycle_state"),
            "summary": self._object_summary(object_type, obj),
            "identity_key": obj.get("identity_key"),
            "created_at": obj.get("created_at"),
            "updated_at": obj.get("updated_at"),
        }
        truncated: dict[str, dict] = {}
        if object_type == "source":
            compact["origin"] = obj.get("origin", {})
            compact["content_type"] = obj.get("content_type")
            payload = obj.get("payload", {})
            if isinstance(payload, dict):
                compact["payload"] = self._compact_source_payload(obj, payload, max_items, snippet_chars, truncated)
            segments = obj.get("segments", [])
            compact["segment_count"] = len(segments) if isinstance(segments, list) else 0
            if include_segments and isinstance(segments, list):
                compact["segments"] = [self._compact_segment(segment, snippet_chars) for segment in segments[:max_items]]
                self._mark_truncated(truncated, "segments", len(segments), len(compact["segments"]))
        else:
            for field in (
                "subject_refs",
                "evidence_refs",
                "related_node_refs",
                "related_work_item_refs",
                "related_knowledge_refs",
                "source_refs",
                "depends_on",
                "blocked_by",
                "child_refs",
            ):
                value = obj.get(field)
                if isinstance(value, list) and value:
                    compact[field] = value[:max_items]
                    self._mark_truncated(truncated, field, len(value), len(compact[field]))
            payload = obj.get("payload")
            if isinstance(payload, dict) and payload:
                compact["payload"] = self._compact_generic_payload(payload, max_items, snippet_chars, truncated)
        return {"object": {key: value for key, value in compact.items() if value not in (None, [], {})}, "truncated": truncated}

    def _compact_source_payload(
        self,
        obj: dict,
        payload: dict,
        max_items: int,
        snippet_chars: int,
        truncated: dict,
    ) -> dict:
        if obj.get("kind") != "repo":
            result = {
                key: value
                for key, value in payload.items()
                if key not in {"text"}
            }
            if "text" in payload:
                result["text_preview"] = self._clip(str(payload.get("text", "")), snippet_chars)
                result["text_char_count"] = len(str(payload.get("text", "")))
                truncated["payload.text"] = {"returned": "text_preview", "total_chars": result["text_char_count"]}
            return result

        result: dict = {}
        for key in ("repo_name", "file_count", "dir_count", "language_counts", "readme_present", "source_roots"):
            if key in payload:
                result[key] = payload[key]
        for key in ("top_level_entries", "code_files", "code_index", "doc_index", "code_modules", "document_sections"):
            value = payload.get(key, [])
            if not isinstance(value, list):
                continue
            if key == "code_modules":
                result[key] = [self._compact_code_module(module, snippet_chars) for module in value[:max_items]]
            elif key == "document_sections":
                result[key] = [self._compact_document_section(section, snippet_chars) for section in value[:max_items]]
            else:
                result[key] = value[:max_items]
            self._mark_truncated(truncated, f"payload.{key}", len(value), len(result[key]))
        if isinstance(payload.get("code_intelligence"), dict):
            result["code_intelligence"] = payload["code_intelligence"]
        if isinstance(payload.get("api_inventory"), dict):
            result["api_inventory"] = self._compact_api_inventory(
                payload["api_inventory"],
                max_items=max_items,
                truncated=truncated,
            )
        for key in ("module_dependencies", "inheritance_graph", "call_index", "framework_entries"):
            value = payload.get(key, [])
            if not isinstance(value, list):
                continue
            result[key] = value[:max_items]
            self._mark_truncated(truncated, f"payload.{key}", len(value), len(result[key]))
        if "parser_backend" in payload:
            result["parser_backend"] = payload["parser_backend"]
        return result

    def _compact_generic_payload(
        self,
        payload: dict,
        max_items: int,
        snippet_chars: int,
        truncated: dict,
    ) -> dict:
        compact: dict = {}
        for key, value in payload.items():
            if isinstance(value, str):
                compact[key] = self._clip(value, snippet_chars)
                if compact[key] != value:
                    truncated[f"payload.{key}"] = {"returned_chars": len(compact[key]), "total_chars": len(value)}
            elif isinstance(value, list):
                compact[key] = value[:max_items]
                self._mark_truncated(truncated, f"payload.{key}", len(value), len(compact[key]))
            else:
                compact[key] = value
        return compact

    def _compact_code_module(self, module: dict, snippet_chars: int) -> dict:
        symbols = module.get("symbols", [])
        return {
            "path": module.get("path"),
            "language": module.get("language"),
            "line_start": module.get("line_start"),
            "line_end": module.get("line_end"),
            "classes": module.get("classes", [])[:8],
            "functions": module.get("functions", [])[:12],
            "import_details": module.get("import_details", [])[:8],
            "symbols": symbols[:12] if isinstance(symbols, list) else [],
            "interfaces": module.get("interfaces", [])[:8],
            "inheritance": module.get("inheritance", [])[:8],
            "call_sites": module.get("call_sites", [])[:8],
            "framework_entries": module.get("framework_entries", [])[:8],
            "module_doc": self._clip(str(module.get("module_doc", "")), snippet_chars),
            "parser_backend": module.get("parser_backend"),
        }

    def _compact_api_inventory(self, inventory: dict, max_items: int, truncated: dict) -> dict:
        result: dict = {}
        for key in ("schema_version", "parser_backend", "counts", "limitations"):
            if key in inventory:
                result[key] = inventory[key]
        for key in ("classes", "functions", "methods", "framework_surfaces"):
            value = inventory.get(key, [])
            if not isinstance(value, list):
                continue
            result[key] = value[:max_items]
            self._mark_truncated(truncated, f"payload.api_inventory.{key}", len(value), len(result[key]))
        return result

    def _compact_document_section(self, section: dict, snippet_chars: int) -> dict:
        return {
            "path": section.get("path"),
            "heading": section.get("heading"),
            "level": section.get("level"),
            "line_start": section.get("line_start"),
            "line_end": section.get("line_end"),
            "excerpt": self._clip(str(section.get("excerpt", "")), snippet_chars),
            "parser_backend": section.get("parser_backend"),
        }

    def _compact_segment(self, segment: dict, snippet_chars: int) -> dict:
        return {
            "segment_id": segment.get("segment_id"),
            "locator": segment.get("locator"),
            "excerpt": self._clip(str(segment.get("excerpt", "")), snippet_chars),
            "hash": segment.get("hash"),
        }

    def _mark_truncated(self, truncated: dict, field: str, total: int, returned: int) -> None:
        if total > returned:
            truncated[field] = {"returned": returned, "total": total}

    def _clip(self, text: str, max_chars: int) -> str:
        max_chars = max(3, max_chars)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    def _sanitize_query_text(self, query: str) -> dict:
        original = str(query or "")
        stripped = original.strip()
        if len(stripped) <= QUERY_SANITIZER_MAX_CHARS:
            clean = self._collapse_query_whitespace(stripped)
            return {
                "query": clean,
                "diagnostics": self._query_sanitizer_diagnostics(
                    original=original,
                    clean=clean,
                    method="passthrough",
                ),
            }

        for line in reversed([line.strip() for line in stripped.splitlines() if line.strip()]):
            match = QUERY_SANITIZER_LABEL_RE.match(line)
            if match:
                clean = self._sanitize_query_candidate(match.group(1))
                if clean:
                    return {
                        "query": clean,
                        "diagnostics": self._query_sanitizer_diagnostics(
                            original=original,
                            clean=clean,
                            method="labeled_line",
                        ),
                    }

        sentence = self._last_question_sentence(stripped)
        if sentence:
            clean = self._sanitize_query_candidate(sentence)
            return {
                "query": clean,
                "diagnostics": self._query_sanitizer_diagnostics(
                    original=original,
                    clean=clean,
                    method="question_sentence",
                ),
            }

        clean = self._sanitize_query_candidate(stripped[-QUERY_SANITIZER_MAX_CHARS:])
        return {
            "query": clean,
            "diagnostics": self._query_sanitizer_diagnostics(
                original=original,
                clean=clean,
                method="tail_truncation",
            ),
        }

    def _sanitize_query_candidate(self, candidate: str) -> str:
        return self._collapse_query_whitespace(candidate.strip())[:QUERY_SANITIZER_MAX_CHARS].strip()

    def _collapse_query_whitespace(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _last_question_sentence(self, text: str) -> str | None:
        sentences = re.findall(r"[^。！？!?\n]+[。！？!?]?", text)
        for sentence in reversed(sentences):
            sentence = sentence.strip()
            if len(sentence) >= 3 and ("?" in sentence or "？" in sentence):
                return sentence
        return None

    def _query_sanitizer_diagnostics(self, original: str, clean: str, method: str) -> dict:
        original_clean = self._collapse_query_whitespace(original.strip())
        return {
            "was_sanitized": clean != original_clean,
            "method": method,
            "original_length": len(original),
            "clean_length": len(clean),
        }

    def _query_sanitizer_warnings(self, diagnostics: dict) -> list[str]:
        if not diagnostics.get("was_sanitized"):
            return []
        return [
            "Long query text was sanitized before retrieval. Use query_sanitizer diagnostics to inspect the applied method."
        ]

    def _query_plan(self, query: str) -> dict:
        normalized_query = query.strip().lower()
        terms: list[str] = []
        primary_terms: list[str] = []
        inferred_filters: dict[str, list[str]] = {}
        self._append_unique(terms, normalized_query)
        self._append_unique(primary_terms, normalized_query)
        for token in self._query_tokens(normalized_query):
            self._append_unique(terms, token)
        for rule in QUERY_NORMALIZATION_RULES:
            if not self._rule_matches(normalized_query, rule["triggers"]):
                continue
            for term in rule["terms"]:
                self._append_unique(terms, str(term).lower())
            for key, values in rule.get("filters", {}).items():
                bucket = inferred_filters.setdefault(key, [])
                for value in values:
                    self._append_unique(bucket, str(value))
        fallback_terms = [term for term in terms if term not in primary_terms]
        return {
            "terms": terms,
            "primary_terms": primary_terms or terms,
            "fallback_terms": fallback_terms,
            "inferred_filters": inferred_filters,
        }

    def _query_tokens(self, normalized_query: str) -> list[str]:
        stopwords = {
            "a",
            "an",
            "and",
            "are",
            "can",
            "draw",
            "for",
            "from",
            "how",
            "of",
            "the",
            "to",
            "what",
            "with",
            "一下",
            "这个",
            "通过",
            "架构图",
        }
        tokens = re.findall(r"[\w.-]+|[\u4e00-\u9fff]+", normalized_query)
        expanded: list[str] = []
        for token in tokens:
            if len(token) < 2 or token in stopwords:
                continue
            self._append_unique(expanded, token)
            if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 2:
                for index in range(len(token) - 1):
                    bigram = token[index : index + 2]
                    if bigram not in stopwords:
                        self._append_unique(expanded, bigram)
        return expanded

    def _rule_matches(self, query: str, triggers: tuple[str, ...]) -> bool:
        if not query:
            return False
        return any(trigger == query or trigger in query for trigger in triggers)

    def _scope_with_query_plan(self, scope: dict, plan: dict) -> dict:
        if not plan["inferred_filters"]:
            return scope
        scoped = dict(scope)
        for key, values in plan["inferred_filters"].items():
            singular = self._singular_filter_key(key)
            if key in scoped or singular in scoped:
                continue
            scoped[key] = list(values)
        return scoped

    def _singular_filter_key(self, key: str) -> str:
        return {
            "object_types": "object_type",
            "kinds": "kind",
            "statuses": "status",
            "source_ids": "source_id",
            "node_ids": "node_id",
        }.get(key, key[:-1] if key.endswith("s") else key)

    def _append_unique(self, values: list[str], value: str) -> None:
        if value and value not in values:
            values.append(value)

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
        include_temporary = bool(filters.get("include_temporary")) or bool(statuses.intersection(TEMPORARY_LIFECYCLE_STATES))
        if not include_temporary and self._is_temporary_memory(obj):
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

    def _is_temporary_memory(self, obj: dict) -> bool:
        return str(obj.get("status") or "") in TEMPORARY_LIFECYCLE_STATES or str(obj.get("lifecycle_state") or "") in TEMPORARY_LIFECYCLE_STATES

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
