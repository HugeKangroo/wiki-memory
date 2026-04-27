from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class DecisionPayload:
    question: str
    outcome: str
    rationale: str
    alternatives: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)
    revisit_conditions: list[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ProcedurePayload:
    goal: str
    steps: list[str]
    preconditions: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    failure_modes: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        return asdict(self)
