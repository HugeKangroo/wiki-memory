from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class SourceSegment:
    segment_id: str
    locator: dict | str
    excerpt: str
    hash: str


@dataclass(slots=True)
class Source(BaseObject):
    kind: str
    origin: dict
    title: str
    identity_key: str
    fingerprint: str
    content_type: str
    payload: dict | str
    segments: list[SourceSegment] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    status: str = "active"
