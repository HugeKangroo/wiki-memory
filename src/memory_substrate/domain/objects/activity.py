from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class Activity(BaseObject):
    kind: str
    title: str
    summary: str
    identity_key: str
    status: str = "draft"
    started_at: str | None = None
    ended_at: str | None = None
    related_node_refs: list[str] = field(default_factory=list)
    related_work_item_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    produced_object_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
