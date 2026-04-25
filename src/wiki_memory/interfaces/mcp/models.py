from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BaseToolArgs(StrictModel):
    root: str | None = None
    options: dict | None = None


class GenericToolArgs(BaseToolArgs):
    mode: str
    input_data: dict


class QueryContextInput(StrictModel):
    task: str
    scope: dict | None = None


class QueryExpandInput(StrictModel):
    id: str


class QueryPageInput(StrictModel):
    id: str


class QueryRecentInput(StrictModel):
    pass


class QuerySearchInput(StrictModel):
    query: str


class QueryContextArgs(BaseToolArgs):
    mode: Literal["context"]
    input_data: QueryContextInput


class QueryExpandArgs(BaseToolArgs):
    mode: Literal["expand"]
    input_data: QueryExpandInput


class QueryPageArgs(BaseToolArgs):
    mode: Literal["page"]
    input_data: QueryPageInput


class QueryRecentArgs(BaseToolArgs):
    mode: Literal["recent"]
    input_data: QueryRecentInput


class QuerySearchArgs(BaseToolArgs):
    mode: Literal["search"]
    input_data: QuerySearchInput


QueryToolArgs = Annotated[
    QueryContextArgs | QueryExpandArgs | QueryPageArgs | QueryRecentArgs | QuerySearchArgs,
    Field(discriminator="mode"),
]


class CrystallizeActivityInput(StrictModel):
    kind: str
    title: str
    summary: str
    actor: dict | None = None
    status: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    related_node_refs: list[str] = []
    related_work_item_refs: list[str] = []
    source_refs: list[str] = []
    produced_object_refs: list[str] = []
    artifact_refs: list[str] = []


class CrystallizeKnowledgeInput(StrictModel):
    kind: str
    title: str
    summary: str
    actor: dict | None = None
    subject_refs: list[str] = []
    evidence_refs: list[dict] = []
    payload: dict = {}
    status: str | None = None
    confidence: float | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    last_verified_at: str | None = None


class CrystallizeWorkItemInput(StrictModel):
    kind: str
    title: str
    summary: str
    actor: dict | None = None
    status: str | None = None
    lifecycle_state: str | None = None
    priority: str | None = None
    owner_refs: list[str] = []
    related_node_refs: list[str] = []
    related_knowledge_refs: list[str] = []
    source_refs: list[str] = []
    depends_on: list[str] = []
    blocked_by: list[str] = []
    parent_ref: str | None = None
    child_refs: list[str] = []
    resolution: str | None = None
    due_at: str | None = None
    opened_at: str | None = None


class CrystallizePromoteInput(StrictModel):
    knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class CrystallizeSupersedeInput(StrictModel):
    old_knowledge_id: str
    new_knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class CrystallizeActivityArgs(BaseToolArgs):
    mode: Literal["activity"]
    input_data: CrystallizeActivityInput


class CrystallizeKnowledgeArgs(BaseToolArgs):
    mode: Literal["knowledge"]
    input_data: CrystallizeKnowledgeInput


class CrystallizeWorkItemArgs(BaseToolArgs):
    mode: Literal["work_item"]
    input_data: CrystallizeWorkItemInput


class CrystallizePromoteArgs(BaseToolArgs):
    mode: Literal["promote"]
    input_data: CrystallizePromoteInput


class CrystallizeSupersedeArgs(BaseToolArgs):
    mode: Literal["supersede"]
    input_data: CrystallizeSupersedeInput


CrystallizeToolArgs = Annotated[
    CrystallizeActivityArgs
    | CrystallizeKnowledgeArgs
    | CrystallizeWorkItemArgs
    | CrystallizePromoteArgs
    | CrystallizeSupersedeArgs,
    Field(discriminator="mode"),
]


class DreamPromoteCandidatesInput(StrictModel):
    min_confidence: float | None = None
    min_evidence: int | None = None


class DreamMergeDuplicatesInput(StrictModel):
    pass


class DreamDecayStaleInput(StrictModel):
    reference_time: str | None = None
    stale_after_days: int | None = None


class DreamCycleInput(StrictModel):
    min_confidence: float | None = None
    min_evidence: int | None = None
    reference_time: str | None = None
    stale_after_days: int | None = None


class DreamPromoteCandidatesArgs(BaseToolArgs):
    mode: Literal["promote_candidates"]
    input_data: DreamPromoteCandidatesInput


class DreamMergeDuplicatesArgs(BaseToolArgs):
    mode: Literal["merge_duplicates"]
    input_data: DreamMergeDuplicatesInput


class DreamDecayStaleArgs(BaseToolArgs):
    mode: Literal["decay_stale"]
    input_data: DreamDecayStaleInput


class DreamCycleArgs(BaseToolArgs):
    mode: Literal["cycle"]
    input_data: DreamCycleInput


DreamToolArgs = Annotated[
    DreamPromoteCandidatesArgs | DreamMergeDuplicatesArgs | DreamDecayStaleArgs | DreamCycleArgs,
    Field(discriminator="mode"),
]


class LintStructureInput(StrictModel):
    pass


class LintAuditInput(StrictModel):
    pass


class LintReindexInput(StrictModel):
    pass


class LintRepairInput(StrictModel):
    pass


class LintStructureArgs(BaseToolArgs):
    mode: Literal["structure"]
    input_data: LintStructureInput


class LintAuditArgs(BaseToolArgs):
    mode: Literal["audit"]
    input_data: LintAuditInput


class LintReindexArgs(BaseToolArgs):
    mode: Literal["reindex"]
    input_data: LintReindexInput


class LintRepairArgs(BaseToolArgs):
    mode: Literal["repair"]
    input_data: LintRepairInput


LintToolArgs = Annotated[
    LintStructureArgs | LintAuditArgs | LintReindexArgs | LintRepairArgs,
    Field(discriminator="mode"),
]


class IngestRepoInput(StrictModel):
    path: str


class IngestRepoArgs(BaseToolArgs):
    mode: Literal["repo"]
    input_data: IngestRepoInput


IngestToolArgs = Annotated[
    IngestRepoArgs,
    Field(discriminator="mode"),
]
