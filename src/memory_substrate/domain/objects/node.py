from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class Node(BaseObject):
    kind: str
    name: str
    slug: str
    identity_key: str
    aliases: list[str] = field(default_factory=list)
    summary: str = ""
    status: str = "active"
