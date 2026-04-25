from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ContextItem:
    object_type: str
    id: str
    kind: str
    title: str
    status: str
    summary: str


@dataclass(slots=True)
class ContextPack:
    id: str
    task: str
    summary: str
    scope: dict = field(default_factory=dict)
    items: list[ContextItem] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)
    recommended_next_reads: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    generated_at: str = ""
    expires_at: str | None = None
