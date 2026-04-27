from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class Relation(BaseObject):
    source_ref: str
    target_ref: str
    relation_type: str
    scope_refs: list[str] = field(default_factory=list)
    evidence_refs: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "candidate"
    valid_from: str | None = None
    valid_until: str | None = None
    metadata: dict = field(default_factory=dict)
