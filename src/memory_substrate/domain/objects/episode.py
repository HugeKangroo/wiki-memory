from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class Episode(BaseObject):
    source_ref: str
    kind: str
    observed_at: str
    ingested_at: str
    actor: dict
    summary: str
    scope_refs: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
