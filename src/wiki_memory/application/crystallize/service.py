from __future__ import annotations

from pathlib import Path

from wiki_memory.domain.protocols.wiki_patch import PatchOperation, WikiPatch
from wiki_memory.domain.services.ids import new_id
from wiki_memory.domain.services.patch_applier import PatchApplier, utc_now_iso
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from wiki_memory.projections.markdown.projector import MarkdownProjector


class CrystallizeService:
    def __init__(self, root: str | Path) -> None:
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

    def _apply_and_project(self, patch: WikiPatch) -> dict:
        result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "patch_id": result.patch_id,
            "applied_operations": result.applied_operations,
            "audit_event_ids": result.audit_event_ids,
            "projection_count": projection_result["count"],
            "affected_object_ids": result.affected_object_ids,
        }

    def create_activity(self, data: dict, actor: dict | None = None) -> dict:
        activity_id = new_id("act")
        timestamp = utc_now_iso()
        patch = WikiPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "wiki.crystallize.activity"},
            operations=[
                PatchOperation(
                    op="create_object",
                    object_type="activity",
                    object_id=activity_id,
                    changes={
                        "kind": data["kind"],
                        "title": data["title"],
                        "summary": data["summary"],
                        "status": data.get("status", "finalized"),
                        "started_at": data.get("started_at", timestamp),
                        "ended_at": data.get("ended_at", timestamp),
                        "related_node_refs": data.get("related_node_refs", []),
                        "related_work_item_refs": data.get("related_work_item_refs", []),
                        "source_refs": data.get("source_refs", []),
                        "produced_object_refs": data.get("produced_object_refs", []),
                        "artifact_refs": data.get("artifact_refs", []),
                        "created_at": timestamp,
                        "updated_at": timestamp,
                    },
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        return {
            "patch_id": result["patch_id"],
            "activity_id": activity_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }

    def create_knowledge(self, data: dict, actor: dict | None = None) -> dict:
        knowledge_id = new_id("know")
        timestamp = utc_now_iso()
        patch = WikiPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "wiki.crystallize.knowledge"},
            operations=[
                PatchOperation(
                    op="create_object",
                    object_type="knowledge",
                    object_id=knowledge_id,
                    changes={
                        "kind": data["kind"],
                        "title": data["title"],
                        "summary": data["summary"],
                        "subject_refs": data.get("subject_refs", []),
                        "evidence_refs": data.get("evidence_refs", []),
                        "payload": data.get("payload", {}),
                        "status": data.get("status", "candidate"),
                        "confidence": data.get("confidence", 0.0),
                        "valid_from": data.get("valid_from", timestamp),
                        "valid_until": data.get("valid_until"),
                        "last_verified_at": data.get("last_verified_at"),
                        "created_at": timestamp,
                        "updated_at": timestamp,
                    },
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        return {
            "patch_id": result["patch_id"],
            "knowledge_id": knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }

    def create_work_item(self, data: dict, actor: dict | None = None) -> dict:
        work_item_id = new_id("work")
        timestamp = utc_now_iso()
        patch = WikiPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "wiki.crystallize.work_item"},
            operations=[
                PatchOperation(
                    op="create_object",
                    object_type="work_item",
                    object_id=work_item_id,
                    changes={
                        "kind": data["kind"],
                        "title": data["title"],
                        "summary": data["summary"],
                        "status": data.get("status", "open"),
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
                    },
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        return {
            "patch_id": result["patch_id"],
            "work_item_id": work_item_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }

    def promote_knowledge(self, knowledge_id: str, actor: dict | None = None, reason: str = "") -> dict:
        existing = self.object_repository.get("knowledge", knowledge_id)
        if existing is None:
            raise ValueError(f"Knowledge not found: {knowledge_id}")

        timestamp = utc_now_iso()
        patch = WikiPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "wiki.crystallize.promote"},
            operations=[
                PatchOperation(
                    op="update_object",
                    object_type="knowledge",
                    object_id=knowledge_id,
                    changes={
                        "status": "active",
                        "last_verified_at": timestamp,
                        "reason": reason or "promoted_to_active",
                    },
                )
            ],
            created_at=timestamp,
        )
        result = self._apply_and_project(patch)
        return {
            "patch_id": result["patch_id"],
            "knowledge_id": knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }

    def contest_knowledge(self, knowledge_id: str, actor: dict | None = None, reason: str = "") -> dict:
        existing = self.object_repository.get("knowledge", knowledge_id)
        if existing is None:
            raise ValueError(f"Knowledge not found: {knowledge_id}")

        timestamp = utc_now_iso()
        patch = WikiPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "wiki.crystallize.contest"},
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
        return {
            "patch_id": result["patch_id"],
            "knowledge_id": knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }

    def batch(self, entries: list[dict], actor: dict | None = None) -> dict:
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
                raise ValueError(f"Unsupported batch crystallize mode: {mode}")
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
        old_item = self.object_repository.get("knowledge", old_knowledge_id)
        new_item = self.object_repository.get("knowledge", new_knowledge_id)
        if old_item is None:
            raise ValueError(f"Knowledge not found: {old_knowledge_id}")
        if new_item is None:
            raise ValueError(f"Knowledge not found: {new_knowledge_id}")

        timestamp = utc_now_iso()
        patch = WikiPatch(
            id=new_id("patch"),
            source=actor or {"type": "system", "id": "wiki.crystallize.supersede"},
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
        return {
            "patch_id": result["patch_id"],
            "old_knowledge_id": old_knowledge_id,
            "new_knowledge_id": new_knowledge_id,
            "applied_operations": result["applied_operations"],
            "audit_event_ids": result["audit_event_ids"],
            "projection_count": result["projection_count"],
        }
