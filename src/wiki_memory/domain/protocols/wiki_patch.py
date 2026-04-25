from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PatchOperation:
    op: str
    object_type: str
    object_id: str
    changes: dict = field(default_factory=dict)


@dataclass(slots=True)
class WikiPatch:
    id: str
    source: dict
    operations: list[PatchOperation] = field(default_factory=list)
    created_at: str = ""
