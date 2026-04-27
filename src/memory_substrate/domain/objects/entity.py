from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class Entity(BaseObject):
    kind: str
    name: str
    scope_refs: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    summary: str = ""
    status: str = "active"
    metadata: dict = field(default_factory=dict)
