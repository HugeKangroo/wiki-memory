from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..storage.fs_utils import append_jsonl
from ..storage.paths import StoragePaths


class FsAuditRepository:
    def __init__(self, root: str | Path) -> None:
        self.paths = StoragePaths(root)

    def append(self, event: Any) -> None:
        payload = asdict(event) if is_dataclass(event) else event
        append_jsonl(self.paths.audit_log_path(), payload)

    def list(self) -> list[dict[str, Any]]:
        path = self.paths.audit_log_path()
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
