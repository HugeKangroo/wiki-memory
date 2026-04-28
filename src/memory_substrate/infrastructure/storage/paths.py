from __future__ import annotations

from pathlib import Path


OBJECT_DIRS = {
    "memory_scope": "memory_scopes",
    "episode": "episodes",
    "entity": "entities",
    "relation": "relations",
    "source": "sources",
    "node": "nodes",
    "knowledge": "knowledge",
    "activity": "activities",
    "work_item": "work_items",
}


class StoragePaths:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.memory_root = self.root / "memory"
        self.objects_root = self.memory_root / "objects"
        self.patches_root = self.memory_root / "patches"
        self.audit_root = self.memory_root / "audit"
        self.projections_root = self.memory_root / "projections"
        self.indexes_root = self.memory_root / "indexes"
        self.config_path = self.memory_root / "config.json"

    def object_dir(self, object_type: str) -> Path:
        directory = OBJECT_DIRS[object_type]
        return self.objects_root / directory

    def object_path(self, object_type: str, object_id: str) -> Path:
        return self.object_dir(object_type) / f"{object_id}.json"

    def patch_path(self, patch_id: str) -> Path:
        return self.patches_root / f"{patch_id}.json"

    def audit_log_path(self) -> Path:
        return self.audit_root / "events.jsonl"
