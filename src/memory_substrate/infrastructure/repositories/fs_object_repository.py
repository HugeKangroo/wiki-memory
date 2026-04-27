from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..storage.fs_utils import read_json, write_json
from ..storage.paths import StoragePaths


class FsObjectRepository:
    """Simple file-backed object repository for the semantic core."""

    def __init__(self, root: str | Path) -> None:
        self.paths = StoragePaths(root)

    def save(self, object_type: str, obj: Any) -> None:
        payload = asdict(obj) if is_dataclass(obj) else obj
        object_id = payload["id"]
        write_json(self.paths.object_path(object_type, object_id), payload)

    def get(self, object_type: str, object_id: str) -> dict[str, Any] | None:
        path = self.paths.object_path(object_type, object_id)
        if not path.exists():
            return None
        return read_json(path)

    def delete(self, object_type: str, object_id: str) -> bool:
        path = self.paths.object_path(object_type, object_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list(self, object_type: str) -> list[dict[str, Any]]:
        directory = self.paths.object_dir(object_type)
        if not directory.exists():
            return []
        return [read_json(path) for path in sorted(directory.glob("*.json"))]

    def exists(self, object_type: str, object_id: str) -> bool:
        return self.paths.object_path(object_type, object_id).exists()
