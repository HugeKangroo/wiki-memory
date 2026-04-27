from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class MemoryScope(BaseObject):
    kind: str
    name: str
    parent_refs: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
