from __future__ import annotations

from dataclasses import dataclass, field, replace


USER_CURATED_SOURCES = {"user_declared", "human_curated"}
VALID_MEMORY_SOURCES = {*USER_CURATED_SOURCES, "agent_inferred", "system_generated", "imported"}


@dataclass(slots=True)
class RememberRequest:
    mode: str
    reason: str
    memory_source: str
    scope_refs: list[str]
    status: str
    confidence: float
    payload: dict
    evidence_refs: list[dict] = field(default_factory=list)
    actor: dict | None = None
    metadata: dict = field(default_factory=dict)

    def validate_governance(self) -> "RememberRequest":
        if not self.reason.strip():
            raise ValueError("remember request requires reason")
        if self.memory_source not in VALID_MEMORY_SOURCES:
            raise ValueError(f"remember request has unsupported memory_source: {self.memory_source}")
        if not self.scope_refs:
            raise ValueError("remember request requires scope_refs")
        if self.status == "active" and self.mode == "knowledge":
            if not self.evidence_refs and self.memory_source not in USER_CURATED_SOURCES:
                raise ValueError("active knowledge requires evidence_refs unless user-declared or human-curated")
        return self

    def normalize(self) -> "RememberRequest":
        status = self.status
        if self.mode == "knowledge" and self.memory_source == "agent_inferred" and self.status == "active":
            status = "candidate"
        return replace(self, status=status).validate_governance()
