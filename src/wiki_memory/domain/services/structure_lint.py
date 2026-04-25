from __future__ import annotations

from pathlib import Path

from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository


REFERENCE_FIELDS = {
    "knowledge": ("subject_refs",),
    "activity": ("related_node_refs", "related_work_item_refs", "source_refs", "produced_object_refs"),
    "work_item": ("owner_refs", "related_node_refs", "related_knowledge_refs", "source_refs", "depends_on", "blocked_by", "child_refs"),
}


class StructureLintRunner:
    def __init__(self, root: str | Path) -> None:
        self.repository = FsObjectRepository(root)

    def run(self) -> dict:
        issues: list[dict] = []
        issues.extend(self._missing_reference_issues())
        issues.extend(self._invalid_status_issues())
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
                                    "issue_id": f"lint:{object_type}:{obj['id']}:{field}:{ref}",
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
                            "issue_id": f"lint:work_item:{obj['id']}:parent_ref:{obj['parent_ref']}",
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
                                    "issue_id": f"lint:knowledge:{obj['id']}:evidence:{source_id}",
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

    def _invalid_status_issues(self) -> list[dict]:
        issues: list[dict] = []
        status_rules = {
            "source": {"active", "invalid", "archived"},
            "node": {"active", "merged", "archived"},
            "knowledge": {"candidate", "active", "contested", "superseded", "stale", "archived"},
            "activity": {"draft", "finalized", "archived"},
            "work_item": {"open", "in_progress", "blocked", "resolved", "closed", "cancelled"},
        }
        lifecycle_rules = {"work_item": {"active", "archived"}}

        for object_type, allowed in status_rules.items():
            for obj in self.repository.list(object_type):
                status = obj.get("status")
                if status not in allowed:
                    issues.append(
                        {
                            "issue_id": f"lint:{object_type}:{obj['id']}:status",
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
                                "issue_id": f"lint:{object_type}:{obj['id']}:lifecycle_state",
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
