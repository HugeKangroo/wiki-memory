from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AuditEvent:
    id: str
    event_type: str
    actor: dict
    target: dict
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    reason: str = ""
    timestamp: str = ""
