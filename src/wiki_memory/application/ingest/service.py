from __future__ import annotations

from pathlib import Path

from wiki_memory.adapters.repo.adapter import RepoAdapter
from wiki_memory.domain.protocols.wiki_patch import PatchOperation, WikiPatch
from wiki_memory.domain.services.ids import new_id
from wiki_memory.domain.services.patch_applier import PatchApplier, utc_now_iso
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from wiki_memory.projections.markdown.projector import MarkdownProjector


class IngestService:
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
        self.repo_adapter = RepoAdapter()
        self.projector = MarkdownProjector(self.root)

    def ingest_repo(self, repo_path: str | Path) -> dict:
        output = self.repo_adapter.ingest(repo_path)
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

        patch = WikiPatch(
            id=new_id("patch"),
            source={
                "type": "system",
                "id": "wiki.ingest.repo",
                "repo_path": str(Path(repo_path).resolve()),
            },
            operations=operations,
            created_at=utc_now_iso(),
        )
        apply_result = self.patch_applier.apply(patch)
        projection_result = self.projector.rebuild()
        return {
            "patch_id": apply_result.patch_id,
            "source_id": output.source.id,
            "node_ids": [node.id for node in output.nodes],
            "knowledge_ids": [item.id for item in output.knowledge_items],
            "activity_id": output.activity.id if output.activity else None,
            "applied_operations": apply_result.applied_operations,
            "audit_event_ids": apply_result.audit_event_ids,
            "projection_count": projection_result["count"],
        }

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
