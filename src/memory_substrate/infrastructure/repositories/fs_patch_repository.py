from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..storage.fs_utils import read_json, write_json
from ..storage.paths import StoragePaths


class FsPatchRepository:
    def __init__(self, root: str | Path) -> None:
        self.paths = StoragePaths(root)

    def save(self, patch: Any) -> None:
        payload = asdict(patch) if is_dataclass(patch) else patch
        write_json(self.paths.patch_path(payload["id"]), payload)

    def get(self, patch_id: str) -> dict[str, Any] | None:
        path = self.paths.patch_path(patch_id)
        if not path.exists():
            return None
        return read_json(path)
