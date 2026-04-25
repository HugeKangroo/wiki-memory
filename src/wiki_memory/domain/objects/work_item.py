from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseObject


@dataclass(slots=True)
class WorkItem(BaseObject):
    kind: str
    title: str
    summary: str
    status: str = "open"
    lifecycle_state: str = "active"
    priority: str = "medium"
    owner_refs: list[str] = field(default_factory=list)
    related_node_refs: list[str] = field(default_factory=list)
    related_knowledge_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    parent_ref: str | None = None
    child_refs: list[str] = field(default_factory=list)
    resolution: str | None = None
    due_at: str | None = None
    opened_at: str | None = None
