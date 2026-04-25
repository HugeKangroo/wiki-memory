from __future__ import annotations

from dataclasses import dataclass, field

from wiki_memory.domain.objects.activity import Activity
from wiki_memory.domain.objects.knowledge import Knowledge
from wiki_memory.domain.objects.node import Node
from wiki_memory.domain.objects.source import Source


@dataclass(slots=True)
class RepoIngestOutput:
    source: Source
    nodes: list[Node] = field(default_factory=list)
    knowledge_items: list[Knowledge] = field(default_factory=list)
    activity: Activity | None = None
