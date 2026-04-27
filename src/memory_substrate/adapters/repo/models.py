from __future__ import annotations

from dataclasses import dataclass, field

from memory_substrate.domain.objects.activity import Activity
from memory_substrate.domain.objects.knowledge import Knowledge
from memory_substrate.domain.objects.node import Node
from memory_substrate.domain.objects.source import Source


@dataclass(slots=True)
class RepoIngestOutput:
    source: Source
    nodes: list[Node] = field(default_factory=list)
    knowledge_items: list[Knowledge] = field(default_factory=list)
    activity: Activity | None = None
