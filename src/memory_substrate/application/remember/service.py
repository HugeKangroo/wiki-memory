from __future__ import annotations

import hashlib
import json
from pathlib import Path

from memory_substrate.application.graph.sync import GraphSyncService
from memory_substrate.domain.protocols.memory_patch import PatchOperation, MemoryPatch
from memory_substrate.domain.protocols.remember_request import (
    RememberRequest,
    TEMPORARY_LIFECYCLE_STATES,
    USER_CURATED_SOURCES,
)
from memory_substrate.domain.services.ids import new_id
from memory_substrate.domain.services.patch_applier import PatchApplier, utc_now_iso
from memory_substrate.domain.services.soft_duplicates import KnowledgeSoftDuplicateDetector
from memory_substrate.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from memory_substrate.projections.markdown.projector import MarkdownProjector


WORK_ITEM_STATUSES = {"open", "in_progress", "blocked", "resolved", "closed", "cancelled"}


class RememberService:
    def __init__(self, root: str | Path, graph_backend=None) -> None:
        """Create a remember service bound to one memory-substrate root.

        Args:
            root: Memory-substrate root directory to mutate through patches.

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
        self.projector = MarkdownProjector(self.root)
        self.graph_sync = GraphSyncService(self.root, graph_backend) if graph_backend is not None else None
        self.soft_duplicates = KnowledgeSoftDuplicateDetector()

    def _apply_and_project(self, patch: MemoryPatch) -> dict:
        result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        payload = {
            "patch_id": result.patch_id,
            "applied_operations": result.applied_operations,
            "audit_event_ids": result.audit_event_ids,
            "projection_count": projection_result["count"],
            "affected_object_ids": result.affected_object_ids,
        }
        if self.graph_sync is not None:
            payload["graph_sync"] = self._sync_patch_to_graph(patch)
        return payload

    def _sync_patch_to_graph(self, patch: MemoryPatch) -> dict:
        synced_objects = 0
        synced_relations = 0
        for operation in patch.operations:
            if operation.op == "delete_object":
                continue
            result = self.graph_sync.sync_object(operation.object_type, operation.object_id)
            synced_objects += result["synced_objects"]
            synced_relations += result["synced_relations"]
        return {
            "status": "completed",
            "synced_objects": synced_objects,
            "synced_relations": synced_relations,
            "backend": self.graph_sync.graph_backend.__class__.__name__,
        }

    def _has_governance_fields(self, data: dict) -> bool:
        return any(field in data for field in ("reason", "memory_source", "scope_refs"))

    def _normalize_governance(
        self,
        mode: str,
        data: dict,
        payload: dict,
        status: str,
        confidence: float,
        evidence_refs: list[dict] | None = None,
    ) -> RememberRequest | None:
        if not self._has_governance_fields(data):
            return None
        metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
        request = RememberRequest(
            mode=mode,
            reason=str(data.get("reason") or metadata.get("reason") or ""),
            memory_source=str(data.get("memory_source") or metadata.get("memory_source") or ""),
            scope_refs=[str(ref) for ref in data.get("scope_refs", [])],
            status=status,
            confidence=confidence,
            payload=payload,
            evidence_refs=evidence_refs or [],
            actor=data.get("actor"),
        )
        return request.normalize()

    def _with_governance_metadata(self, payload: dict, request: RememberRequest) -> dict:
        governed_payload = dict(payload)
        metadata = governed_payload.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        governed_payload["metadata"] = {
            **metadata,
            "reason": request.reason,
            "memory_source": request.memory_source,
            "scope_refs": request.scope_refs,
        }
        return governed_payload

    def _validate_evidence_refs(self, evidence_refs: list[dict], additional_sources: dict[str, dict] | None = None) -> None:
        additional_sources = additional_sources or {}
        for evidence in evidence_refs:
            source_id = str(evidence.get("source_id") or "")
            segment_id = str(evidence.get("segment_id") or "")
            if not source_id:
                raise ValueError("evidence_refs source_id is required")
            if not segment_id:
                raise ValueError(f"evidence_refs segment_id is required for {source_id}")
            source = additional_sources.get(source_id) or self.object_repository.get("source", source_id)
            if source is None:
                raise ValueError(f"evidence_refs source not found: {source_id}")
            segments = {str(segment.get("segment_id")): segment for segment in source.get("segments", [])}
            segment = segments.get(segment_id)
            if segment is None:
                raise ValueError(f"evidence_refs segment not found: {source_id}#{segment_id}")
            if evidence.get("locator") is not None and evidence.get("locator") != segment.get("locator"):
                raise ValueError(f"evidence_refs locator mismatch: {source_id}#{segment_id}")
            if evidence.get("hash") is not None and str(evidence.get("hash")) != str(segment.get("hash")):
                raise ValueError(f"evidence_refs hash mismatch: {source_id}#{segment_id}")

    def _normalize_json(self, value) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _knowledge_evidence_contract(
        self,
        data: dict,
        evidence_refs: list[dict],
        request: RememberRequest | None,
        timestamp: str,
    ) -> dict:
        if evidence_refs:
            return {
                "provenance": "caller_evidence_refs",
                "evidence_refs": evidence_refs,
                "generated_source": None,
                "generated_source_id": None,
                "evidence_ref_count": len(evidence_refs),
                "requires_review": False,
            }
        has_explicit_source_text = bool(str(data.get("source_text") or "").strip())
        if request is not None and (request.memory_source in USER_CURATED_SOURCES or has_explicit_source_text):
            source = self._declaration_source_for_knowledge(data, request, timestamp)
            segment = source["segments"][0]
            generated_evidence_refs = [
                {
                    "source_id": source["id"],
                    "segment_id": segment["segment_id"],
                    "locator": segment["locator"],
                    "hash": segment["hash"],
                }
            ]
            provenance = (
                "declaration_source_created"
                if request.memory_source in USER_CURATED_SOURCES
                else "remember_input_source_created"
            )
            return {
                "provenance": provenance,
                "evidence_refs": generated_evidence_refs,
                "generated_source": source,
                "generated_source_id": source["id"],
                "evidence_ref_count": 1,
                "requires_review": False,
            }
        return {
            "provenance": "evidence_absent",
            "evidence_refs": [],
            "generated_source": None,
            "generated_source_id": None,
            "evidence_ref_count": 0,
            "requires_review": request is not None and request.status != "active",
        }

    def _declaration_source_for_knowledge(self, data: dict, request: RememberRequest, timestamp: str) -> dict:
        text = str(data.get("source_text") or f"{data['title']}\n\n{data['summary']}")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        line_count = max(1, len(text.splitlines()))
        source_id = new_id("src")
        segment_id = "seg:declaration"
        source_kind = "declaration" if request.memory_source in USER_CURATED_SOURCES else "remember_input"
        segment = {
            "segment_id": segment_id,
            "locator": {
                "kind": "declaration",
                "line_start": 1,
                "line_end": line_count,
            },
            "excerpt": self._clip_text(text, 720),
            "hash": digest,
        }
        return {
            "id": source_id,
            "kind": source_kind,
            "origin": {
                "kind": "memory_remember",
                "memory_source": request.memory_source,
                "scope_refs": request.scope_refs,
            },
            "title": str(data.get("source_title") or f"Remember input for {data['title']}"),
            "identity_key": f"source|{source_kind}|{digest}",
            "fingerprint": digest,
            "content_type": "text",
            "payload": {
                "schema_version": "declaration_source.v1",
                "text": text,
                "knowledge_title": data["title"],
            },
            "segments": [segment],
            "metadata": {
                "adapter": {
                    "name": "memory_remember",
                    "version": "declaration_source.v1",
                    "mode": "knowledge_declaration" if source_kind == "declaration" else "knowledge_remember_input",
                    "declared_transformations": ["preserve_remember_input_as_source"],
                    "default_privacy_class": "local",
                    "origin_classification": source_kind,
                },
                "freshness": {
                    "checked_at": timestamp,
                    "is_current": True,
                    "fingerprint": digest,
                },
            },
            "status": "active",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def _clip_text(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    def _temporary_lifecycle_state(self, data: dict, status: str) -> str | None:
        lifecycle_state = str(data.get("lifecycle_state") or "").strip()
        if lifecycle_state in TEMPORARY_LIFECYCLE_STATES:
            return lifecycle_state
        if status in TEMPORARY_LIFECYCLE_STATES:
            return status
        return None

    def _knowledge_scope_refs(self, item: dict) -> list[str]:
        scope_refs = item.get("scope_refs", [])
        if scope_refs:
            return [str(ref) for ref in scope_refs]
        payload = item.get("payload", {})
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        metadata_scope_refs = metadata.get("scope_refs", []) if isinstance(metadata, dict) else []
        return [str(ref) for ref in metadata_scope_refs]

    def _scopes_overlap(self, left: dict, right: dict) -> bool:
        left_scopes = set(self._knowledge_scope_refs(left))
        right_scopes = set(self._knowledge_scope_refs(right))
        if not left_scopes or not right_scopes:
            return True
        return bool(left_scopes.intersection(right_scopes))

    def _knowledge_signature(self, item: dict) -> tuple[str, str, str, str, str] | None:
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            return None
        subject_refs = item.get("subject_refs", [])
        subject = subject_refs[0] if subject_refs else payload.get("subject")
        predicate = payload.get("predicate")
        if not subject or not predicate:
            return None
        return (
            str(item.get("kind", "")),
            str(subject),
            str(predicate),
            self._normalize_json(payload.get("value")),
            self._normalize_json(payload.get("object")),
        )

    def _knowledge_identity_key(self, data: dict) -> str:
        signature = self._knowledge_signature(data)
        if signature is None:
            return f"knowledge|{data.get('kind', '')}|{data.get('title', '')}".lower()
        kind, subject, predicate, value, object_value = signature
        scope_key = self._normalize_json(sorted(self._knowledge_scope_refs(data)))
        return f"knowledge|{kind}|{scope_key}|{subject}|{predicate}|{value}|{object_value}"

    def _active_knowledge_items(self) -> list[dict]:
        return [
            item
            for item in self.object_repository.list("knowledge")
            if item.get("status") not in {"superseded", "archived"}
        ]

    def _duplicate_knowledge_ids(self, data: dict) -> list[str]:
        signature = self._knowledge_signature(data)
        if signature is None:
            return []
        return [
            item["id"]
            for item in self._active_knowledge_items()
            if self._scopes_overlap(item, data) and self._knowledge_signature(item) == signature
        ]

    def _conflicting_knowledge_ids(self, data: dict) -> list[str]:
        signature = self._knowledge_signature(data)
        if signature is None:
            return []
        kind, subject, predicate, value, object_value = signature
        conflicts: list[str] = []
        for item in self._active_knowledge_items():
            existing = self._knowledge_signature(item)
            if existing is None:
                continue
            if (
                self._scopes_overlap(item, data)
                and existing[0] == kind
                and existing[1] == subject
                and existing[2] == predicate
                and existing[3:] != (value, object_value)
            ):
                conflicts.append(item["id"])
        return conflicts

    def _possible_duplicate_knowledge(self, data: dict) -> list[dict]:
        return self.soft_duplicates.possible_duplicates(data, self._active_knowledge_items())

    def create_activity(self, data: dict, actor: dict | None = None) -> dict:
        """Create a finalized activity object from explicit structured input.

        Args:
            data: Activity fields including kind, title, summary, refs, timestamps, and artifacts.
            actor: Optional actor metadata recorded as the patch source.

        Returns:
            Creation result with activity id, patch, audit, and projection metadata.
        """
        activity_id = new_id("act")
        timestamp = utc_now_iso()
        request = self._normalize_governance(
            mode="activity",
            data=data,
            payload={},
            status=data.get("status", "finalized"),
            confidence=1.0,
        )
        changes = {
            "kind": data["kind"],
            "title": data["title"],
            "summary": data["summary"],
            "status": request.status if request else data.get("status", "finalized"),
            "started_at": data.get("started_at", timestamp),
            "ended_at": data.get("ended_at", timestamp),
            "related_node_refs": data.get("related_node_refs", []),
            "related_work_item_refs": data.get("related_work_item_refs", []),
            "source_refs": data.get("source_refs", []),
            "produced_object_refs": data.get("produced_object_refs", []),
            "artifact_refs": data.get("artifact_refs", []),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        if request is not None:
            changes.update(
                {
                    "reason": request.reason,
                    "memory_source": request.memory_source,
                    "scope_refs": request.scope_refs,
                }
            )
        patch = MemoryPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "memory.remember.activity"},
            operations=[
                PatchOperation(
                    op="create_object",
                    object_type="activity",
                    object_id=activity_id,
                    changes=changes,
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        output = {
            "result_type": "remember_result",
            "object_type": "activity",
            "object_id": activity_id,
            "status": changes["status"],
            "patch_id": result["patch_id"],
            "activity_id": activity_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }
        if "graph_sync" in result:
            output["graph_sync"] = result["graph_sync"]
        return output

    def create_knowledge(self, data: dict, actor: dict | None = None) -> dict:
        """Create a candidate knowledge object from structured input.

        Args:
            data: Knowledge fields including kind, title, summary, subjects, evidence, payload, and status.
            actor: Optional actor metadata recorded as the patch source.

        Returns:
            Creation result with knowledge id, patch, audit, and projection metadata.
        """
        knowledge_id = new_id("know")
        timestamp = utc_now_iso()
        payload = data.get("payload", {})
        evidence_refs = data.get("evidence_refs", [])
        request = self._normalize_governance(
            mode="knowledge",
            data=data,
            payload=payload,
            status=data.get("status", "candidate"),
            confidence=data.get("confidence", 0.0),
            evidence_refs=evidence_refs,
        )
        evidence_contract = self._knowledge_evidence_contract(data, evidence_refs, request, timestamp)
        evidence_refs = evidence_contract["evidence_refs"]
        declaration_source = evidence_contract["generated_source"]
        candidate = {
            **data,
            "payload": payload,
            "evidence_refs": evidence_refs,
            "status": request.status if request else data.get("status", "candidate"),
        }
        temporary_lifecycle_state = self._temporary_lifecycle_state(candidate, str(candidate["status"]))
        if temporary_lifecycle_state is not None:
            candidate["status"] = "temporary"
            if declaration_source is not None:
                declaration_source["status"] = "temporary"
                declaration_source["lifecycle_state"] = temporary_lifecycle_state
                declaration_source["expires_at"] = data.get("expires_at")
        possible_duplicates = self._possible_duplicate_knowledge(candidate)
        if request is not None:
            additional_sources = {declaration_source["id"]: declaration_source} if declaration_source else {}
            self._validate_evidence_refs(evidence_refs, additional_sources=additional_sources)
            duplicate_ids = self._duplicate_knowledge_ids(candidate)
            if duplicate_ids and not data.get("allow_duplicate", False):
                raise ValueError(f"duplicate knowledge exists: {', '.join(duplicate_ids)}")
            conflict_ids = self._conflicting_knowledge_ids(candidate)
            payload = self._with_governance_metadata(payload, request)
            if conflict_ids:
                metadata = payload.get("metadata", {})
                payload["metadata"] = {**metadata, "conflicts_with": conflict_ids}
                candidate["status"] = "contested"
        else:
            conflict_ids = []
        identity_key = data.get("identity_key") or self._knowledge_identity_key(candidate)
        changes = {
            "kind": data["kind"],
            "title": data["title"],
            "summary": data["summary"],
            "identity_key": identity_key,
            "subject_refs": data.get("subject_refs", []),
            "evidence_refs": evidence_refs,
            "payload": payload,
            "status": candidate["status"],
            "confidence": data.get("confidence", 0.0),
            "valid_from": data.get("valid_from", timestamp),
            "valid_until": data.get("valid_until"),
            "lifecycle_state": temporary_lifecycle_state or data.get("lifecycle_state"),
            "expires_at": data.get("expires_at"),
            "last_verified_at": data.get("last_verified_at"),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        if request is not None:
            changes.update(
                {
                    "reason": request.reason,
                    "memory_source": request.memory_source,
                    "scope_refs": request.scope_refs,
                }
            )
            if conflict_ids:
                changes["conflicts_with"] = conflict_ids
        operations = []
        if declaration_source is not None:
            operations.append(
                PatchOperation(
                    op="create_object",
                    object_type="source",
                    object_id=declaration_source["id"],
                    changes={key: value for key, value in declaration_source.items() if key != "id"},
                )
            )
        operations.append(
            PatchOperation(
                op="create_object",
                object_type="knowledge",
                object_id=knowledge_id,
                changes=changes,
            )
        )
        patch = MemoryPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "memory.remember.knowledge"},
            operations=operations,
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        response_contract = {
            key: value
            for key, value in evidence_contract.items()
            if key not in {"evidence_refs", "generated_source"}
        }
        output = {
            "result_type": "remember_result",
            "object_type": "knowledge",
            "object_id": knowledge_id,
            "status": changes["status"],
            "patch_id": result["patch_id"],
            "knowledge_id": knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
            "possible_duplicates": possible_duplicates,
            "evidence_contract": response_contract,
        }
        if "graph_sync" in result:
            output["graph_sync"] = result["graph_sync"]
        return output

    def create_work_item(self, data: dict, actor: dict | None = None) -> dict:
        """Create an actionable work item from structured input.

        Args:
            data: Work item fields including kind, title, summary, status, priority, owners, and links.
            actor: Optional actor metadata recorded as the patch source.

        Returns:
            Creation result with work item id, patch, audit, and projection metadata.
        """
        work_item_id = new_id("work")
        timestamp = utc_now_iso()
        request = self._normalize_governance(
            mode="work_item",
            data=data,
            payload={},
            status=data.get("status", "open"),
            confidence=1.0,
        )
        changes = {
            "kind": data["kind"],
            "title": data["title"],
            "summary": data["summary"],
            "status": request.status if request else data.get("status", "open"),
            "lifecycle_state": data.get("lifecycle_state", "active"),
            "priority": data.get("priority", "medium"),
            "owner_refs": data.get("owner_refs", []),
            "related_node_refs": data.get("related_node_refs", []),
            "related_knowledge_refs": data.get("related_knowledge_refs", []),
            "source_refs": data.get("source_refs", []),
            "depends_on": data.get("depends_on", []),
            "blocked_by": data.get("blocked_by", []),
            "parent_ref": data.get("parent_ref"),
            "child_refs": data.get("child_refs", []),
            "resolution": data.get("resolution"),
            "due_at": data.get("due_at"),
            "opened_at": data.get("opened_at", timestamp),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        if request is not None:
            changes.update(
                {
                    "reason": request.reason,
                    "memory_source": request.memory_source,
                    "scope_refs": request.scope_refs,
                }
            )
        patch = MemoryPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "memory.remember.work_item"},
            operations=[
                PatchOperation(
                    op="create_object",
                    object_type="work_item",
                    object_id=work_item_id,
                    changes=changes,
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        output = {
            "result_type": "remember_result",
            "object_type": "work_item",
            "object_id": work_item_id,
            "status": changes["status"],
            "patch_id": result["patch_id"],
            "work_item_id": work_item_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }
        if "graph_sync" in result:
            output["graph_sync"] = result["graph_sync"]
        return output

    def update_work_item_status(self, data: dict, actor: dict | None = None) -> dict:
        """Update the status of an existing work item through an audited patch.

        Args:
            data: Status update fields including work_item_id, status, reason, and optional resolution.
            actor: Optional actor metadata recorded as the patch source.

        Returns:
            Mutation result with patch, audit, and projection metadata.
        """
        work_item_id = data["work_item_id"]
        status = data["status"]
        if status not in WORK_ITEM_STATUSES:
            raise ValueError(f"Unsupported work_item status: {status}")
        before = self.object_repository.get("work_item", work_item_id)
        if before is None:
            raise ValueError(f"Missing work_item: {work_item_id}")
        reason = str(data.get("reason") or "")
        if not reason:
            raise ValueError("reason is required for work_item_status")
        memory_source = str(data.get("memory_source") or "")
        if not memory_source:
            raise ValueError("memory_source is required for work_item_status")

        operations = [
            PatchOperation(
                op="change_status",
                object_type="work_item",
                object_id=work_item_id,
                changes={"status": status, "reason": reason},
            )
        ]
        if "resolution" in data:
            operations.append(
                PatchOperation(
                    op="update_object",
                    object_type="work_item",
                    object_id=work_item_id,
                    changes={"resolution": data.get("resolution")},
                )
            )
        patch = MemoryPatch(
            id=new_id("patch"),
            source=actor
            or {
                "type": "system",
                "id": "memory.remember.work_item_status",
                "memory_source": memory_source,
            },
            operations=operations,
            created_at=utc_now_iso(),
        )
        result = self._apply_and_project(patch)
        output = {
            "result_type": "remember_result",
            "object_type": "work_item",
            "object_id": work_item_id,
            "old_status": before.get("status"),
            "status": status,
            "patch_id": result["patch_id"],
            "work_item_id": work_item_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }
        if "graph_sync" in result:
            output["graph_sync"] = result["graph_sync"]
        return output

    def promote_knowledge(self, knowledge_id: str, actor: dict | None = None, reason: str = "") -> dict:
        """Promote one knowledge object to active status.

        Args:
            knowledge_id: Knowledge object identifier to promote.
            actor: Optional actor metadata recorded as the patch source.
            reason: Optional human-readable promotion reason.

        Returns:
            Promotion result with knowledge id, patch, audit, and projection metadata.
        """
        existing = self.object_repository.get("knowledge", knowledge_id)
        if existing is None:
            raise ValueError(f"Knowledge not found: {knowledge_id}")

        timestamp = utc_now_iso()
        patch = MemoryPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "memory.remember.promote"},
            operations=[
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=knowledge_id,
                    changes={
                        "status": "active",
                        "lifecycle_state": "active",
                        "expires_at": None,
                        "last_verified_at": timestamp,
                        "reason": reason or "promoted_to_active",
                    },
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        output = {
            "result_type": "remember_result",
            "object_type": "knowledge",
            "object_id": knowledge_id,
            "status": "active",
            "patch_id": result["patch_id"],
            "knowledge_id": knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }
        if "graph_sync" in result:
            output["graph_sync"] = result["graph_sync"]
        return output

    def contest_knowledge(self, knowledge_id: str, actor: dict | None = None, reason: str = "") -> dict:
        """Mark one knowledge object as contested.

        Args:
            knowledge_id: Knowledge object identifier to contest.
            actor: Optional actor metadata recorded as the patch source.
            reason: Optional human-readable contest reason.

        Returns:
            Contest result with knowledge id, patch, audit, and projection metadata.
        """
        existing = self.object_repository.get("knowledge", knowledge_id)
        if existing is None:
            raise ValueError(f"Knowledge not found: {knowledge_id}")

        timestamp = utc_now_iso()
        patch = MemoryPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "memory.remember.contest"},
            operations=[
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=knowledge_id,
                    changes={
                        "status": "contested",
                        "reason": reason or "contested",
                        "last_verified_at": existing.get("last_verified_at"),
                    },
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        output = {
            "result_type": "remember_result",
            "object_type": "knowledge",
            "object_id": knowledge_id,
            "status": "contested",
            "patch_id": result["patch_id"],
            "knowledge_id": knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }
        if "graph_sync" in result:
            output["graph_sync"] = result["graph_sync"]
        return output

    def batch(self, entries: list[dict], actor: dict | None = None) -> dict:
        """Run multiple remember create operations in sequence.

        Args:
            entries: Ordered remember entries with mode and input_data fields.
            actor: Optional actor metadata reused for each created patch.

        Returns:
            Batch result containing per-entry creation results.
        """
        results: list[dict] = []
        for entry in entries:
            mode = entry["mode"]
            data = entry.get("input_data", {})
            if mode == "activity":
                results.append(self.create_activity(data, actor=actor))
            elif mode == "knowledge":
                results.append(self.create_knowledge(data, actor=actor))
            elif mode == "work_item":
                results.append(self.create_work_item(data, actor=actor))
            else:
                raise ValueError(f"Unsupported batch remember mode: {mode}")
        return {
            "status": "completed",
            "created": len(results),
            "results": results,
        }

    def supersede_knowledge(
        self,
        old_knowledge_id: str,
        new_knowledge_id: str,
        actor: dict | None = None,
        reason: str = "",
    ) -> dict:
        """Supersede one knowledge object with a replacement knowledge object.

        Args:
            old_knowledge_id: Knowledge object identifier to mark superseded.
            new_knowledge_id: Replacement knowledge object identifier to activate.
            actor: Optional actor metadata recorded as the patch source.
            reason: Optional human-readable supersession reason.

        Returns:
            Supersession result with old and new knowledge ids, patch, audit, and projection metadata.
        """
        old_item = self.object_repository.get("knowledge", old_knowledge_id)
        new_item = self.object_repository.get("knowledge", new_knowledge_id)
        if old_item is None:
            raise ValueError(f"Knowledge not found: {old_knowledge_id}")
        if new_item is None:
            raise ValueError(f"Knowledge not found: {new_knowledge_id}")

        timestamp = utc_now_iso()
        patch = MemoryPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "memory.remember.supersede"},
            operations=[
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=old_knowledge_id,
                    changes={
                        "status": "superseded",
                        "valid_until": timestamp,
                        "reason": reason or f"superseded_by:{new_knowledge_id}",
                    },
                ),
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=new_knowledge_id,
                    changes={
                        "status": "active",
                        "valid_from": new_item.get("valid_from") or timestamp,
                        "last_verified_at": timestamp,
                        "reason": reason or f"supersedes:{old_knowledge_id}",
                    },
                ),
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        output = {
            "result_type": "remember_result",
            "object_type": "knowledge",
            "object_id": new_knowledge_id,
            "status": "active",
            "old_status": "superseded",
            "patch_id": result["patch_id"],
            "old_knowledge_id": old_knowledge_id,
            "new_knowledge_id": new_knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }
        if "graph_sync" in result:
            output["graph_sync"] = result["graph_sync"]
        return output
