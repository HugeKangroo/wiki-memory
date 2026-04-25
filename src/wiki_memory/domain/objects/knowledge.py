from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class EvidenceRef:
    source_id: str
    segment_id: str


@dataclass(slots=True)
class Knowledge(BaseObject):
    kind: str
    title: str
    summary: str
    identity_key: str
    subject_refs: list[str] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    status: str = "candidate"
    confidence: float = 0.0
    valid_from: str | None = None
    valid_until: str | None = None
    last_verified_at: str | None = None
