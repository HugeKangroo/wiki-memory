from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.request import urlopen

from memory_substrate.adapters.repo.adapter import RepoAdapter
from memory_substrate.adapters.repo.models import RepoPreflightOutput
from memory_substrate.domain.objects.activity import Activity
from memory_substrate.domain.objects.node import Node
from memory_substrate.domain.objects.source import Source, SourceSegment
from memory_substrate.domain.protocols.memory_patch import PatchOperation, MemoryPatch
from memory_substrate.domain.services.concept_candidates import ConceptCandidateDiscovery
from memory_substrate.domain.services.document_chunker import DocumentChunker
from memory_substrate.domain.services.ids import new_id, slugify, stable_id
from memory_substrate.domain.services.patch_applier import PatchApplier, utc_now_iso
from memory_substrate.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from memory_substrate.projections.markdown.projector import MarkdownProjector


class IngestService:
    def __init__(self, root: str | Path) -> None:
        """Create an ingest service bound to one memory-substrate root.

        Args:
            root: Memory-substrate root directory that stores canonical objects and projections.

        Returns:
            None.
        """
        self.root = Path(root)
        self.object_repository = FsObjectRepository(self.root)
        self.patch_repository = FsPatchRepository(self.root)
        self.audit_repository = FsAuditRepository(self.root)
        self.patch_applier = PatchApplier(
            object_repository=self.object_repository,
            patch_repository=self.patch_repository,
            audit_repository=self.audit_repository,
        )
        self.document_chunker = DocumentChunker()
        self.concept_candidates = ConceptCandidateDiscovery()
        self.repo_adapter = RepoAdapter()
        self.projector = MarkdownProjector(self.root)

    def ingest_repo(
        self,
        repo_path: str | Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        force: bool = False,
    ) -> dict:
        """Scan a repository and write its source, node, knowledge, and activity objects.

        Args:
            repo_path: Local repository path to scan.
            include_patterns: Optional glob-like relative path patterns to include.
            exclude_patterns: Optional glob-like relative path patterns to exclude.
            force: Proceed with ingest even when preflight warnings require an explicit decision.

        Returns:
            Ingest result with patch, source, node, knowledge, activity, audit, and projection metadata.
        """
        preflight = self.repo_adapter.preflight(
            repo_path,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
        pending_decisions = self._repo_pending_decisions(preflight, force=force)
        excluded_by_preflight = [decision["path"] for decision in pending_decisions]
        effective_exclude_patterns = self._effective_repo_exclude_patterns(
            exclude_patterns,
            excluded_by_preflight=excluded_by_preflight,
            force=force,
        )
        output = self.repo_adapter.ingest(
            repo_path,
            include_patterns=include_patterns,
            exclude_patterns=effective_exclude_patterns,
        )
        self._annotate_repo_ingest_metadata(
            output=output,
            pending_decisions=pending_decisions,
            excluded_by_preflight=excluded_by_preflight,
        )
        warnings = preflight.warnings if pending_decisions else output.warnings
        suggested_exclude_patterns = (
            preflight.suggested_exclude_patterns
            if pending_decisions
            else output.suggested_exclude_patterns
        )
        if self._repo_ingest_is_noop(output):
            return self._noop_repo_ingest_result(
                output,
                warnings=warnings,
                suggested_exclude_patterns=suggested_exclude_patterns,
                pending_decisions=pending_decisions,
                excluded_by_preflight=excluded_by_preflight,
            )

        repo_root = str(Path(repo_path).resolve())
        operations = [
            self._upsert_operation(
                object_type="source",
                object_id=output.source.id,
                changes={
                    "kind": output.source.kind,
                    "origin": output.source.origin,
                    "title": output.source.title,
                    "identity_key": output.source.identity_key,
                    "fingerprint": output.source.fingerprint,
                    "content_type": output.source.content_type,
                    "payload": output.source.payload,
                    "segments": output.source.segments,
                    "metadata": output.source.metadata,
                    "status": output.source.status,
                    "created_at": output.source.created_at,
                    "updated_at": output.source.updated_at,
                },
            )
        ]
        operations.extend(self._archive_missing_repo_objects(repo_root, output))

        for node in output.nodes:
            operations.append(
                self._upsert_operation(
                    object_type="node",
                    object_id=node.id,
                    changes={
                        "kind": node.kind,
                        "name": node.name,
                        "slug": node.slug,
                        "identity_key": node.identity_key,
                        "aliases": node.aliases,
                        "summary": node.summary,
                        "status": node.status,
                        "created_at": node.created_at,
                        "updated_at": node.updated_at,
                    },
                )
            )

        for item in output.knowledge_items:
            operations.append(
                self._upsert_operation(
                    object_type="knowledge",
                    object_id=item.id,
                    changes={
                        "kind": item.kind,
                        "title": item.title,
                        "summary": item.summary,
                        "identity_key": item.identity_key,
                        "subject_refs": item.subject_refs,
                        "evidence_refs": item.evidence_refs,
                        "payload": item.payload,
                        "status": item.status,
                        "confidence": item.confidence,
                        "valid_from": item.valid_from,
                        "valid_until": item.valid_until,
                        "last_verified_at": item.last_verified_at,
                        "created_at": item.created_at,
                        "updated_at": item.updated_at,
                    },
                )
            )

        if output.activity is not None:
            operations.append(
                self._upsert_operation(
                    object_type="activity",
                    object_id=output.activity.id,
                    changes={
                        "kind": output.activity.kind,
                        "title": output.activity.title,
                        "summary": output.activity.summary,
                        "identity_key": output.activity.identity_key,
                        "status": output.activity.status,
                        "started_at": output.activity.started_at,
                        "ended_at": output.activity.ended_at,
                        "related_node_refs": output.activity.related_node_refs,
                        "related_work_item_refs": output.activity.related_work_item_refs,
                        "source_refs": output.activity.source_refs,
                        "produced_object_refs": output.activity.produced_object_refs,
                        "artifact_refs": output.activity.artifact_refs,
                        "created_at": output.activity.created_at,
                        "updated_at": output.activity.updated_at,
                    },
                )
            )

        patch = MemoryPatch(
            id=new_id("patch"),
            source={
                "type": "system",
                "id": "memory.ingest.repo",
                "repo_path": str(Path(repo_path).resolve()),
            },
            operations=operations,
            created_at=utc_now_iso(),
        )
        apply_result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "result_type": "repo_ingest_result",
            "status": "completed_with_pending_decisions" if pending_decisions else "completed",
            "requires_decision": bool(pending_decisions),
            "patch_id": apply_result.patch_id,
            "source_id": output.source.id,
            "node_ids": [node.id for node in output.nodes],
            "knowledge_ids": [item.id for item in output.knowledge_items],
            "activity_id": output.activity.id if output.activity else None,
            "applied_operations": apply_result.applied_operations,
            "audit_event_ids": apply_result.audit_event_ids,
            "projection_count": projection_result["count"],
            "warnings": warnings,
            "suggested_exclude_patterns": suggested_exclude_patterns,
            "pending_decisions": pending_decisions,
            "excluded_by_preflight": excluded_by_preflight,
            "memory_suggestions": self._memory_suggestions(output.source.id),
            "next_actions": self._ingest_next_actions(),
        }

    def _repo_ingest_is_noop(self, output) -> bool:
        existing_source = self.object_repository.get("source", output.source.id)
        if existing_source is None:
            return False
        existing_scope = existing_source.get("metadata", {}).get("repo_ingest", {})
        output_scope = output.source.metadata.get("repo_ingest", {})
        return (
            existing_source.get("kind") == output.source.kind
            and existing_source.get("identity_key") == output.source.identity_key
            and existing_source.get("status") == "active"
            and existing_source.get("fingerprint") == output.source.fingerprint
            and self._normalized_repo_patterns(existing_scope.get("include_patterns", []))
            == self._normalized_repo_patterns(output_scope.get("include_patterns", []))
            and self._normalized_repo_patterns(existing_scope.get("exclude_patterns", []))
            == self._normalized_repo_patterns(output_scope.get("exclude_patterns", []))
        )

    def _normalized_repo_patterns(self, patterns: list[str] | None) -> list[str]:
        return sorted(patterns or [])

    def _noop_repo_ingest_result(
        self,
        output,
        warnings: list[str],
        suggested_exclude_patterns: list[str],
        pending_decisions: list[dict],
        excluded_by_preflight: list[str],
    ) -> dict:
        return {
            "result_type": "repo_ingest_result",
            "status": "noop",
            "requires_decision": bool(pending_decisions),
            "patch_id": None,
            "source_id": output.source.id,
            "node_ids": [node.id for node in output.nodes],
            "knowledge_ids": [item.id for item in output.knowledge_items],
            "activity_id": output.activity.id if output.activity else None,
            "applied_operations": 0,
            "audit_event_ids": [],
            "projection_count": 0,
            "warnings": warnings,
            "suggested_exclude_patterns": suggested_exclude_patterns,
            "pending_decisions": pending_decisions,
            "excluded_by_preflight": excluded_by_preflight,
            "reason": "repo_fingerprint_unchanged",
            "memory_suggestions": self._memory_suggestions(output.source.id),
            "next_actions": self._ingest_next_actions(),
        }

    def _ingest_next_actions(self) -> list[str]:
        return [
            "query_related_context",
            "analyze_evidence_outside_ingest",
            "review_memory_suggestions",
            "call_memory_remember_if_durable",
        ]

    def _memory_suggestions(self, source_id: str, limit: int = 5) -> dict:
        analysis = self.concept_candidates.analyze(
            sources=self.object_repository.list("source"),
            knowledge_items=self.object_repository.list("knowledge"),
            nodes=self.object_repository.list("node"),
            source_ids={source_id},
            limit=limit,
        )
        concept_candidates = [self._compact_concept_candidate(candidate) for candidate in analysis["candidates"]]
        return {
            "concept_candidates": concept_candidates,
            "candidate_diagnostics": self._compact_candidate_diagnostics(analysis["candidate_diagnostics"]),
            "agent_extraction": self._agent_extraction_protocol(source_id),
            "counts": {
                "concept_candidates": len(concept_candidates),
                "concept_candidates_available": analysis["candidate_diagnostics"]["counts"].get("eligible", len(concept_candidates)),
            },
            "next_actions": [
                "follow_agent_extraction_protocol",
                "review_concept_candidates",
                "run_memory_maintain_report_for_cross_source_candidates",
                "call_memory_remember_if_durable",
            ],
        }

    def _agent_extraction_protocol(self, source_id: str) -> dict:
        return {
            "protocol": "agent_extraction.v1",
            "source_id": source_id,
            "resource": "memory://agent-playbook",
            "summary": "Ingest captured evidence; agent analyzes it and uses memory_remember for durable writes.",
            "required_steps": [
                "inspect_source",
                "query_existing_memory",
                "prepare_durable_candidates",
                "commit_reviewed_memory",
            ],
            "remember_write_contract": {
                "required_fields": ["kind", "title", "summary", "reason", "memory_source", "scope_refs"],
                "recommended_fields": ["subject_refs", "evidence_refs", "payload", "confidence", "status"],
            },
            "next_actions": [
                "inspect_source",
                "query_existing_memory",
                "prepare_durable_candidates",
                "call_memory_remember_if_durable",
            ],
        }

    def _compact_concept_candidate(self, candidate: dict) -> dict:
        evidence_refs = candidate.get("evidence_refs", [])[:2]
        review_guidance = candidate.get("review_guidance", {})
        suggested_memory = candidate.get("suggested_memory", {})
        return {
            "kind": candidate.get("kind"),
            "detail": "compact",
            "candidate_type": candidate.get("candidate_type"),
            "title": candidate.get("title"),
            "normalized_key": candidate.get("normalized_key"),
            "score": candidate.get("score"),
            "occurrences": candidate.get("occurrences"),
            "source_count": candidate.get("source_count"),
            "support_count": candidate.get("support_count"),
            "evidence_refs": evidence_refs,
            "evidence_ref_count": len(candidate.get("evidence_refs", [])),
            "object_ref_count": len(candidate.get("object_refs", [])),
            "reasons": candidate.get("reasons", []),
            "ranking_signals": candidate.get("ranking_signals", {}),
            "recommendation": candidate.get("recommendation", {}),
            "suggested_memory": {
                "mode": suggested_memory.get("mode"),
                "kind": suggested_memory.get("kind"),
                "title": suggested_memory.get("title"),
                "status": suggested_memory.get("status"),
                "confidence": suggested_memory.get("confidence"),
                "input_data_available_from": "memory_maintain report",
            },
            "review_guidance": {
                "required_checks": review_guidance.get("required_checks", []),
                "outcome_actions": [
                    outcome.get("action")
                    for outcome in review_guidance.get("outcomes", [])
                    if outcome.get("action")
                ],
            },
            "omitted_fields": [
                "object_refs",
                "suggested_memory.input_data",
                "review_guidance.outcomes",
            ],
            "next_actions": candidate.get("next_actions", []),
        }

    def _compact_candidate_diagnostics(self, diagnostics: dict) -> dict:
        return {
            "skipped": diagnostics.get("skipped", [])[:5],
            "skipped_by_reason": diagnostics.get("skipped_by_reason", {}),
            "noise_classes": diagnostics.get("noise_classes", [])[:5],
            "counts": diagnostics.get("counts", {}),
        }

    def _repo_pending_decisions(self, preflight: RepoPreflightOutput, force: bool) -> list[dict]:
        if force:
            return []
        return [
            {
                "path": pattern,
                "kind": "local_agent_state",
                "reason": "Repository contains local/agent state that may not belong in durable memory.",
                "suggested_action": "exclude",
            }
            for pattern in preflight.suggested_exclude_patterns
        ]

    def _effective_repo_exclude_patterns(
        self,
        exclude_patterns: list[str] | None,
        excluded_by_preflight: list[str],
        force: bool,
    ) -> list[str] | None:
        if force:
            return exclude_patterns
        merged = list(exclude_patterns or [])
        for pattern in excluded_by_preflight:
            if pattern not in merged:
                merged.append(pattern)
        return merged

    def _annotate_repo_ingest_metadata(
        self,
        output,
        pending_decisions: list[dict],
        excluded_by_preflight: list[str],
    ) -> None:
        timestamp = output.source.updated_at
        output.source.metadata["adapter"] = self._adapter_metadata(
            name="repo",
            version="repo-adapter.v1",
            mode="repo",
            supported_modes=["repo"],
            declared_transformations=[
                "repo_map",
                "code_index",
                "document_sections",
                "source_segments",
            ],
            default_privacy_class="local_repo",
            origin_classification="local_repo",
        )
        output.source.metadata["freshness"] = self._freshness_metadata(
            checked_at=timestamp,
            fingerprint=output.source.fingerprint,
        )
        repo_ingest = output.source.metadata.setdefault("repo_ingest", {})
        repo_ingest["pending_decisions"] = pending_decisions
        repo_ingest["excluded_by_preflight"] = excluded_by_preflight

    def _blocked_repo_ingest_result(self, preflight: RepoPreflightOutput) -> dict:
        return {
            "result_type": "repo_ingest_preflight",
            "status": "blocked",
            "requires_decision": True,
            "patch_id": None,
            "source_id": None,
            "node_ids": [],
            "knowledge_ids": [],
            "activity_id": None,
            "applied_operations": 0,
            "audit_event_ids": [],
            "projection_count": 0,
            "warnings": preflight.warnings,
            "suggested_exclude_patterns": preflight.suggested_exclude_patterns,
        }

    def ingest_file(self, file_path: str | Path) -> dict:
        """Ingest a plain text file as a document source.

        Args:
            file_path: Local file path to read.

        Returns:
            Ingest result for the created or updated document source and projection.
        """
        return self._ingest_document(file_path, kind="file", content_type="text")

    def ingest_markdown(self, file_path: str | Path) -> dict:
        """Ingest a Markdown file as a structured document source.

        Args:
            file_path: Local Markdown file path to read.

        Returns:
            Ingest result for the created or updated Markdown source and projection.
        """
        return self._ingest_document(file_path, kind="markdown", content_type="markdown")

    def ingest_web(self, url: str) -> dict:
        """Fetch a web page and ingest its readable text as a source.

        Args:
            url: HTTP or HTTPS URL to fetch.

        Returns:
            Ingest result for the created or updated web source and projection.
        """
        with urlopen(url, timeout=20) as response:
            raw = response.read()
            content_type_header = response.headers.get("content-type", "")
        text = raw.decode("utf-8", errors="replace")
        text = self._html_to_text(text) if "html" in content_type_header or "<html" in text.lower() else text
        return self._ingest_text_source(
            identity=f"source|web|{url}",
            kind="web",
            title=url,
            origin={"url": url},
            text=text,
            content_type="text",
            activity_kind="reading",
            artifact_ref=url,
        )

    def ingest_pdf(self, file_path: str | Path) -> dict:
        """Ingest a PDF path as text when possible or as a binary stub otherwise.

        Args:
            file_path: Local PDF file path to read.

        Returns:
            Ingest result for the created or updated PDF source and projection.
        """
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"PDF path is not a file: {path}")
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="ignore").strip()
        if text and not text.startswith("%PDF"):
            return self._ingest_text_source(
                identity=f"source|pdf|{path}",
                kind="pdf",
                title=path.name,
                origin={"path": str(path)},
                text=text,
                content_type="text",
                activity_kind="reading",
                artifact_ref=str(path),
            )
        return self._ingest_binary_stub(path, kind="pdf", raw=raw)

    def ingest_conversation(self, title: str, messages: list[dict], origin: dict | None = None) -> dict:
        """Ingest chat or meeting messages as a conversation source.

        Args:
            title: Human-readable conversation title.
            messages: Message dictionaries containing role and content fields.
            origin: Optional metadata describing where the conversation came from.

        Returns:
            Ingest result for the created or updated conversation source and projection.
        """
        lines = []
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            lines.append(f"{role}: {content}")
        text = "\n\n".join(lines)
        return self._ingest_text_source(
            identity=f"source|conversation|{title}|{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
            kind="conversation",
            title=title,
            origin=origin or {"title": title},
            text=text,
            content_type="structured",
            activity_kind="meeting",
            artifact_ref=title,
        )

    def _upsert_operation(self, object_type: str, object_id: str, changes: dict) -> PatchOperation:
        exists = self.object_repository.exists(object_type, object_id)
        payload = dict(changes)
        if exists:
            payload.pop("created_at", None)
        return PatchOperation(
            op="update_object" if exists else "create_object",
            object_type=object_type,
            object_id=object_id,
            changes=payload,
        )

    def _archive_missing_repo_objects(self, repo_root: str, output) -> list[PatchOperation]:
        operations: list[PatchOperation] = []
        expected_ids = {
            "node": {node.id for node in output.nodes},
            "knowledge": {item.id for item in output.knowledge_items},
        }
        identity_prefixes = {
            "node": (
                f"node|repo|{repo_root}",
                f"node|repo_entry|{repo_root}|",
                f"node|module|{repo_root}|",
            ),
            "knowledge": (f"knowledge|repo|{repo_root}|",),
        }

        for object_type in ("node", "knowledge"):
            for obj in self.object_repository.list(object_type):
                identity_key = str(obj.get("identity_key", ""))
                if not identity_key.startswith(identity_prefixes[object_type]):
                    continue
                if obj["id"] in expected_ids[object_type]:
                    continue
                if obj.get("status") == "archived":
                    continue
                operations.append(
                    PatchOperation(
                        op="archive_object",
                        object_type=object_type,
                        object_id=obj["id"],
                        changes={"reason": "repo_ingest_missing_from_latest_scan"},
                    )
                )
        return operations

    def _ingest_document(self, file_path: str | Path, kind: str, content_type: str) -> dict:
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"File path is not a file: {path}")
        text = path.read_text(encoding="utf-8")
        return self._ingest_text_source(
            identity=f"source|{kind}|{path}",
            kind=kind,
            title=path.name,
            origin={"path": str(path)},
            text=text,
            content_type=content_type,
            activity_kind="reading",
            artifact_ref=str(path),
        )

    def _ingest_text_source(
        self,
        identity: str,
        kind: str,
        title: str,
        origin: dict,
        text: str,
        content_type: str,
        activity_kind: str,
        artifact_ref: str,
    ) -> dict:
        timestamp = utc_now_iso()
        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
        source_id = stable_id("src", identity)
        node_id = stable_id("node", f"node|document|{identity}")
        segments = self._document_segments(artifact_ref, text, content_type)

        source = Source(
            id=source_id,
            kind=kind,
            origin=origin,
            title=title,
            identity_key=identity,
            fingerprint=fingerprint,
            content_type=content_type,
            payload={
                "text": text,
                "byte_count": len(text.encode("utf-8")),
                "segment_count": len(segments),
                "chunking": {
                    "strategy": "document_chunker.v1",
                    "max_chars": self.document_chunker.max_chars,
                    "overlap_lines": self.document_chunker.overlap_lines,
                },
            },
            segments=segments,
            metadata={
                "scanned_at": timestamp,
                "adapter": self._adapter_metadata(
                    name="document",
                    version="document-adapter.v1",
                    mode=kind,
                    supported_modes=["file", "markdown", "web", "pdf", "conversation"],
                    declared_transformations=[
                        "read_text",
                        "document_chunker.v1",
                        "source_segments",
                    ],
                    default_privacy_class=self._privacy_class_for_origin(origin),
                    origin_classification=self._origin_classification(origin),
                ),
                "freshness": self._freshness_metadata(
                    checked_at=timestamp,
                    fingerprint=fingerprint,
                ),
            },
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        node = Node(
            id=node_id,
            kind="document",
            name=title,
            slug=slugify(title),
            identity_key=f"node|document|{identity}",
            aliases=[artifact_ref],
            summary=f"{content_type.title()} document with {len(segments)} source segments.",
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        activity = Activity(
            id=stable_id("act", f"activity|{kind}_ingest|{identity}|{fingerprint}"),
            kind=activity_kind,
            title=f"Ingest source: {title}",
            summary=f"Captured {title} as a {content_type} source.",
            identity_key=f"activity|{kind}_ingest|{identity}|{fingerprint}",
            status="finalized",
            started_at=timestamp,
            ended_at=timestamp,
            related_node_refs=[node.id],
            related_work_item_refs=[],
            source_refs=[source.id],
            produced_object_refs=[node.id],
            artifact_refs=[artifact_ref],
            created_at=timestamp,
            updated_at=timestamp,
        )
        operations = [
            self._upsert_operation(
                object_type="source",
                object_id=source.id,
                changes={
                    "kind": source.kind,
                    "origin": source.origin,
                    "title": source.title,
                    "identity_key": source.identity_key,
                    "fingerprint": source.fingerprint,
                    "content_type": source.content_type,
                    "payload": source.payload,
                    "segments": source.segments,
                    "metadata": source.metadata,
                    "status": source.status,
                    "created_at": source.created_at,
                    "updated_at": source.updated_at,
                },
            ),
            self._upsert_operation(
                object_type="node",
                object_id=node.id,
                changes={
                    "kind": node.kind,
                    "name": node.name,
                    "slug": node.slug,
                    "identity_key": node.identity_key,
                    "aliases": node.aliases,
                    "summary": node.summary,
                    "status": node.status,
                    "created_at": node.created_at,
                    "updated_at": node.updated_at,
                },
            ),
            self._upsert_operation(
                object_type="activity",
                object_id=activity.id,
                changes={
                    "kind": activity.kind,
                    "title": activity.title,
                    "summary": activity.summary,
                    "identity_key": activity.identity_key,
                    "status": activity.status,
                    "started_at": activity.started_at,
                    "ended_at": activity.ended_at,
                    "related_node_refs": activity.related_node_refs,
                    "related_work_item_refs": activity.related_work_item_refs,
                    "source_refs": activity.source_refs,
                    "produced_object_refs": activity.produced_object_refs,
                    "artifact_refs": activity.artifact_refs,
                    "created_at": activity.created_at,
                    "updated_at": activity.updated_at,
                },
            ),
        ]
        patch = MemoryPatch(
            id=new_id("patch"),
            source={"type": "system", "id": f"memory.ingest.{kind}", **origin},
            operations=operations,
            created_at=timestamp,
        )
        apply_result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "result_type": "source_ingest_result",
            "status": "completed",
            "warnings": [],
            "patch_id": apply_result.patch_id,
            "source_id": source.id,
            "node_id": node.id,
            "activity_id": activity.id,
            "segment_count": len(segments),
            "applied_operations": apply_result.applied_operations,
            "audit_event_ids": apply_result.audit_event_ids,
            "projection_count": projection_result["count"],
            "memory_suggestions": self._memory_suggestions(source.id),
            "next_actions": self._ingest_next_actions(),
        }

    def _ingest_binary_stub(self, path: Path, kind: str, raw: bytes) -> dict:
        timestamp = utc_now_iso()
        fingerprint = hashlib.sha256(raw).hexdigest()
        identity = f"source|{kind}|{path}"
        source_id = stable_id("src", identity)
        source = Source(
            id=source_id,
            kind=kind,
            origin={"path": str(path)},
            title=path.name,
            identity_key=identity,
            fingerprint=fingerprint,
            content_type="binary_stub",
            payload={"path": str(path), "byte_count": len(raw), "sha256": fingerprint},
            segments=[],
            metadata={
                "scanned_at": timestamp,
                "adapter": self._adapter_metadata(
                    name="document",
                    version="document-adapter.v1",
                    mode=kind,
                    supported_modes=["file", "markdown", "web", "pdf", "conversation"],
                    declared_transformations=["binary_stub"],
                    default_privacy_class="local_file",
                    origin_classification="local_file",
                ),
                "freshness": self._freshness_metadata(
                    checked_at=timestamp,
                    fingerprint=fingerprint,
                ),
            },
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        operation = self._upsert_operation(
            object_type="source",
            object_id=source.id,
            changes={
                "kind": source.kind,
                "origin": source.origin,
                "title": source.title,
                "identity_key": source.identity_key,
                "fingerprint": source.fingerprint,
                "content_type": source.content_type,
                "payload": source.payload,
                "segments": source.segments,
                "metadata": source.metadata,
                "status": source.status,
                "created_at": source.created_at,
                "updated_at": source.updated_at,
            },
        )
        patch = MemoryPatch(
            id=new_id("patch"),
            source={"type": "system", "id": f"memory.ingest.{kind}", "path": str(path)},
            operations=[operation],
            created_at=timestamp,
        )
        apply_result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "result_type": "source_ingest_result",
            "status": "completed",
            "warnings": [],
            "patch_id": apply_result.patch_id,
            "source_id": source.id,
            "node_id": None,
            "activity_id": None,
            "segment_count": 0,
            "applied_operations": apply_result.applied_operations,
            "audit_event_ids": apply_result.audit_event_ids,
            "projection_count": projection_result["count"],
            "memory_suggestions": self._memory_suggestions(source.id),
            "next_actions": self._ingest_next_actions(),
        }

    def _document_segments(self, locator: str, text: str, content_type: str) -> list[SourceSegment]:
        chunks = self.document_chunker.chunk(text, content_type)
        segments: list[SourceSegment] = []
        for chunk in chunks[:100]:
            segment_id = slugify(f"{chunk.chunk_index}-{chunk.title}") or f"segment-{chunk.chunk_index}"
            segment_locator = {
                "kind": "source",
                "ref": locator,
                "segment_index": chunk.chunk_index,
                "chunk_kind": chunk.kind,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
            }
            if chunk.heading_path:
                segment_locator["heading_path"] = chunk.heading_path
            segments.append(
                SourceSegment(
                    segment_id=segment_id,
                    locator=segment_locator,
                    excerpt=chunk.excerpt,
                    hash=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
                )
            )
        return segments

    def _adapter_metadata(
        self,
        name: str,
        version: str,
        mode: str,
        supported_modes: list[str],
        declared_transformations: list[str],
        default_privacy_class: str,
        origin_classification: str,
    ) -> dict:
        return {
            "name": name,
            "version": version,
            "mode": mode,
            "supported_modes": supported_modes,
            "declared_transformations": declared_transformations,
            "default_privacy_class": default_privacy_class,
            "origin_classification": origin_classification,
        }

    def _freshness_metadata(self, checked_at: str, fingerprint: str) -> dict:
        return {
            "checked_at": checked_at,
            "is_current": True,
            "fingerprint": fingerprint,
        }

    def _origin_classification(self, origin: dict) -> str:
        if origin.get("url"):
            return "remote_url"
        if origin.get("path"):
            return "local_file"
        if origin.get("title"):
            return "conversation"
        return "unknown"

    def _privacy_class_for_origin(self, origin: dict) -> str:
        classification = self._origin_classification(origin)
        if classification == "remote_url":
            return "remote_url"
        if classification == "conversation":
            return "conversation"
        return "local_file"

    def _html_to_text(self, html: str) -> str:
        html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        html = re.sub(r"(?s)<[^>]+>", "\n", html)
        return re.sub(r"\n{3,}", "\n\n", html).strip()
