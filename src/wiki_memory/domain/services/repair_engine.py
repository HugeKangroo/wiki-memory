from __future__ import annotations

from pathlib import Path

from wiki_memory.domain.protocols.wiki_patch import PatchOperation, WikiPatch
from wiki_memory.domain.services.ids import new_id
from wiki_memory.domain.services.patch_applier import PatchApplier, utc_now_iso
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from wiki_memory.projections.markdown.projector import MarkdownProjector


REFERENCE_LIST_FIELDS = (
    "owner_refs",
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


class RepairEngine:
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

    def repair_safe_missing_references(self) -> dict:
        all_ids = self._all_ids()
        operations: list[PatchOperation] = []

        for object_type in ("knowledge", "activity", "work_item"):
            for obj in self.object_repository.list(object_type):
                changes: dict = {}
                for field in REFERENCE_LIST_FIELDS:
                    values = obj.get(field)
                    if isinstance(values, list):
                        filtered = [value for value in values if value in all_ids]
                        if filtered != values:
                            changes[field] = filtered
                if object_type == "work_item" and obj.get("parent_ref") and obj["parent_ref"] not in all_ids:
                    changes["parent_ref"] = None
                if object_type == "knowledge":
                    evidence_refs = obj.get("evidence_refs", [])
                    filtered_evidence = [
                        evidence for evidence in evidence_refs
                        if isinstance(evidence, dict) and evidence.get("source_id") in all_ids
                    ]
                    if filtered_evidence != evidence_refs:
                        changes["evidence_refs"] = filtered_evidence
                if changes:
                    changes["reason"] = "safe_missing_reference_repair"
                    operations.append(
                        PatchOperation(
                            op="update_object",
                            object_type=object_type,
                            object_id=obj["id"],
                            changes=changes,
                        )
                    )

        if not operations:
            return {
                "status": "noop",
                "repaired": 0,
                "patch_id": None,
                "projection_count": 0,
            }

        patch = WikiPatch(
            id=new_id("patch"),
            source={"type": "system", "id": "wiki.lint.repair"},
            operations=operations,
            created_at=utc_now_iso(),
        )
        result = self.patch_applier.apply(patch)
        projection = self.projector.rebuild()
        return {
            "status": "completed",
            "repaired": len(operations),
            "patch_id": result.patch_id,
            "audit_event_ids": result.audit_event_ids,
            "projection_count": projection["count"],
        }

    def _all_ids(self) -> set[str]:
        ids: set[str] = set()
        for object_type in ("source", "node", "knowledge", "activity", "work_item"):
            ids.update(obj["id"] for obj in self.object_repository.list(object_type))
        return ids
