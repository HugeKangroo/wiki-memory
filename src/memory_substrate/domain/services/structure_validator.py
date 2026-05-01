from __future__ import annotations

from pathlib import Path

from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


REFERENCE_FIELDS = {
    "knowledge": ("subject_refs",),
    "activity": ("related_node_refs", "related_work_item_refs", "source_refs", "produced_object_refs"),
    "work_item": ("owner_refs", "related_node_refs", "related_knowledge_refs", "source_refs", "depends_on", "blocked_by", "child_refs"),
}


class StructureValidator:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.repository = FsObjectRepository(root)

    def run(self) -> dict:
        issues: list[dict] = []
        issues.extend(self._missing_reference_issues())
        issues.extend(self._invalid_status_issues())
        issues.extend(self._duplicate_identity_issues())
        issues.extend(self._active_knowledge_without_evidence_issues())
        issues.extend(self._orphan_source_issues())
        issues.extend(self._projection_issues())
        return {
            "issues": issues,
            "counts": {
                "info": sum(1 for issue in issues if issue["severity"] == "info"),
                "warning": sum(1 for issue in issues if issue["severity"] == "warning"),
                "error": sum(1 for issue in issues if issue["severity"] == "error"),
            },
        }

    def _missing_reference_issues(self) -> list[dict]:
        issues: list[dict] = []
        all_ids = self._all_ids()
        for object_type, fields in REFERENCE_FIELDS.items():
            for obj in self.repository.list(object_type):
                for field in fields:
                    for ref in obj.get(field, []):
                        if ref not in all_ids:
                            issues.append(
                                {
                                    "issue_id": f"validator:{object_type}:{obj['id']}:{field}:{ref}",
                                    "kind": "missing_reference",
                                    "severity": "warning",
                                    "target_id": obj["id"],
                                    "summary": f"Missing object reference in {field}: {ref}",
                                    "details": {
                                        "field": field,
                                        "missing_ref": ref,
                                    },
                                    "repairable": True,
                                }
                            )
                if object_type == "work_item" and obj.get("parent_ref") and obj["parent_ref"] not in all_ids:
                    issues.append(
                        {
                            "issue_id": f"validator:work_item:{obj['id']}:parent_ref:{obj['parent_ref']}",
                            "kind": "missing_reference",
                            "severity": "warning",
                            "target_id": obj["id"],
                            "summary": f"Missing parent_ref: {obj['parent_ref']}",
                            "details": {
                                "field": "parent_ref",
                                "missing_ref": obj["parent_ref"],
                            },
                            "repairable": True,
                        }
                    )
                if object_type == "knowledge":
                    for evidence in obj.get("evidence_refs", []):
                        source_id = evidence.get("source_id")
                        if source_id and source_id not in all_ids:
                            issues.append(
                                {
                                    "issue_id": f"validator:knowledge:{obj['id']}:evidence:{source_id}",
                                    "kind": "missing_reference",
                                    "severity": "warning",
                                    "target_id": obj["id"],
                                    "summary": f"Missing evidence source: {source_id}",
                                    "details": {
                                        "field": "evidence_refs",
                                        "missing_ref": source_id,
                                    },
                                    "repairable": True,
                                }
                            )
        return issues

    def _duplicate_identity_issues(self) -> list[dict]:
        issues: list[dict] = []
        for object_type in ("source", "node", "knowledge", "activity", "work_item"):
            by_identity: dict[str, list[str]] = {}
            for obj in self.repository.list(object_type):
                identity_key = obj.get("identity_key")
                if not identity_key:
                    continue
                by_identity.setdefault(str(identity_key), []).append(obj["id"])
            for identity_key, object_ids in by_identity.items():
                if len(object_ids) < 2:
                    continue
                issues.append(
                    {
                        "issue_id": f"validator:{object_type}:duplicate_identity:{identity_key}",
                        "kind": "duplicate_identity",
                        "severity": "warning",
                        "target_id": object_ids[0],
                        "summary": f"Duplicate identity_key for {object_type}: {identity_key}",
                        "details": {"identity_key": identity_key, "object_ids": sorted(object_ids)},
                        "repairable": False,
                    }
                )
        return issues

    def _active_knowledge_without_evidence_issues(self) -> list[dict]:
        issues: list[dict] = []
        for obj in self.repository.list("knowledge"):
            if obj.get("status") != "active":
                continue
            if obj.get("evidence_refs"):
                continue
            issues.append(
                {
                    "issue_id": f"validator:knowledge:{obj['id']}:active_without_evidence",
                    "kind": "active_knowledge_without_evidence",
                    "severity": "warning",
                    "target_id": obj["id"],
                    "summary": "Active knowledge has no evidence_refs.",
                    "details": {"field": "evidence_refs"},
                    "repairable": False,
                }
            )
        return issues

    def _orphan_source_issues(self) -> list[dict]:
        issues: list[dict] = []
        referenced_sources: set[str] = set()
        for object_type in ("knowledge", "activity", "work_item"):
            for obj in self.repository.list(object_type):
                for source_id in obj.get("source_refs", []):
                    referenced_sources.add(str(source_id))
                for evidence in obj.get("evidence_refs", []):
                    if isinstance(evidence, dict) and evidence.get("source_id"):
                        referenced_sources.add(str(evidence["source_id"]))
        for source in self.repository.list("source"):
            if source.get("status") == "archived":
                continue
            if source["id"] in referenced_sources:
                continue
            issues.append(
                {
                    "issue_id": f"validator:source:{source['id']}:orphan",
                    "kind": "orphan_source",
                    "severity": "info",
                    "target_id": source["id"],
                    "summary": "Source is not referenced by knowledge, activity, or work items.",
                    "details": {},
                    "repairable": False,
                }
            )
        return issues

    def _projection_issues(self) -> list[dict]:
        issues: list[dict] = []
        projection_dirs = {
            "source": self.root / "memory" / "projections" / "debug" / "sources",
            "node": self.root / "memory" / "projections" / "debug" / "nodes",
            "knowledge": self.root / "memory" / "projections" / "debug" / "knowledge",
            "activity": self.root / "memory" / "projections" / "debug" / "activities",
            "work_item": self.root / "memory" / "projections" / "debug" / "work_items",
        }
        for object_type, directory in projection_dirs.items():
            expected = {f"{obj['id']}.md" for obj in self.repository.list(object_type)}
            actual = {path.name for path in directory.glob("*.md")} if directory.exists() else set()
            for missing in sorted(expected - actual):
                object_id = missing.removesuffix(".md")
                issues.append(
                    {
                        "issue_id": f"validator:{object_type}:{object_id}:missing_projection",
                        "kind": "missing_projection",
                        "severity": "warning",
                        "target_id": object_id,
                        "summary": f"Missing markdown projection for {object_type}: {object_id}",
                        "details": {"path": str(directory / missing)},
                        "repairable": True,
                    }
                )
            for stale in sorted(actual - expected):
                object_id = stale.removesuffix(".md")
                issues.append(
                    {
                        "issue_id": f"validator:{object_type}:{object_id}:stale_projection",
                        "kind": "stale_projection",
                        "severity": "warning",
                        "target_id": object_id,
                        "summary": f"Stale markdown projection for {object_type}: {object_id}",
                        "details": {"path": str(directory / stale)},
                        "repairable": True,
                    }
                )
        return issues

    def _invalid_status_issues(self) -> list[dict]:
        issues: list[dict] = []
        status_rules = {
            "source": {"active", "invalid", "archived"},
            "node": {"active", "merged", "archived"},
            "knowledge": {"candidate", "active", "contested", "superseded", "stale", "archived"},
            "activity": {"draft", "finalized", "completed", "archived"},
            "work_item": {"open", "in_progress", "blocked", "resolved", "closed", "cancelled"},
        }
        lifecycle_rules = {"work_item": {"active", "archived"}}

        for object_type, allowed in status_rules.items():
            for obj in self.repository.list(object_type):
                status = obj.get("status")
                if status not in allowed:
                    issues.append(
                        {
                            "issue_id": f"validator:{object_type}:{obj['id']}:status",
                            "kind": "invalid_status",
                            "severity": "error",
                            "target_id": obj["id"],
                            "summary": f"Invalid status '{status}' for {object_type}",
                            "details": {"allowed": sorted(allowed)},
                            "repairable": False,
                        }
                    )
                lifecycle_allowed = lifecycle_rules.get(object_type)
                if lifecycle_allowed is not None:
                    lifecycle_state = obj.get("lifecycle_state")
                    if lifecycle_state not in lifecycle_allowed:
                        issues.append(
                            {
                                "issue_id": f"validator:{object_type}:{obj['id']}:lifecycle_state",
                                "kind": "invalid_status",
                                "severity": "error",
                                "target_id": obj["id"],
                                "summary": f"Invalid lifecycle_state '{lifecycle_state}' for {object_type}",
                                "details": {"allowed": sorted(lifecycle_allowed)},
                                "repairable": False,
                            }
                        )
        return issues

    def _all_ids(self) -> set[str]:
        ids: set[str] = set()
        for object_type in ("source", "node", "knowledge", "activity", "work_item"):
            ids.update(obj["id"] for obj in self.repository.list(object_type))
        return ids
