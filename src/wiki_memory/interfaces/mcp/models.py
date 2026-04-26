from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base schema that rejects unknown MCP argument fields."""

    model_config = ConfigDict(extra="forbid")


class BaseToolArgs(StrictModel):
    """Shared top-level MCP tool arguments."""

    root: str | None = None
    options: dict | None = None


class GenericToolArgs(BaseToolArgs):
    """Legacy-compatible tool arguments with an unconstrained mode payload."""

    mode: str
    input_data: dict


class QueryContextInput(StrictModel):
    """Input payload for building a task-focused context pack."""

    task: str
    scope: dict | None = None


class QueryExpandInput(StrictModel):
    """Input payload for expanding one memory object."""

    id: str


class QueryPageInput(StrictModel):
    """Input payload for fetching one memory object page."""

    id: str


class QueryRecentInput(StrictModel):
    """Input payload for listing recent memory objects."""

    pass


class QuerySearchInput(StrictModel):
    """Input payload for searching memory objects."""

    query: str


class QueryGraphInput(StrictModel):
    """Input payload for building a relationship graph."""

    id: str


class QueryContextArgs(BaseToolArgs):
    """MCP arguments for wiki_query context mode."""

    mode: Literal["context"]
    input_data: QueryContextInput


class QueryExpandArgs(BaseToolArgs):
    """MCP arguments for wiki_query expand mode."""

    mode: Literal["expand"]
    input_data: QueryExpandInput


class QueryPageArgs(BaseToolArgs):
    """MCP arguments for wiki_query page mode."""

    mode: Literal["page"]
    input_data: QueryPageInput


class QueryRecentArgs(BaseToolArgs):
    """MCP arguments for wiki_query recent mode."""

    mode: Literal["recent"]
    input_data: QueryRecentInput


class QuerySearchArgs(BaseToolArgs):
    """MCP arguments for wiki_query search mode."""

    mode: Literal["search"]
    input_data: QuerySearchInput


class QueryGraphArgs(BaseToolArgs):
    """MCP arguments for wiki_query graph mode."""

    mode: Literal["graph"]
    input_data: QueryGraphInput


QueryToolArgs = Annotated[
    QueryContextArgs | QueryExpandArgs | QueryPageArgs | QueryRecentArgs | QuerySearchArgs | QueryGraphArgs,
    Field(discriminator="mode"),
]


class CrystallizeActivityInput(StrictModel):
    """Input payload for creating an activity memory object."""

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
    """Input payload for creating a knowledge memory object."""

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
    """Input payload for creating a work item memory object."""

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
    """Input payload for promoting one knowledge object."""

    knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class CrystallizeSupersedeInput(StrictModel):
    """Input payload for superseding one knowledge object with another."""

    old_knowledge_id: str
    new_knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class CrystallizeContestInput(StrictModel):
    """Input payload for marking one knowledge object contested."""

    knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class CrystallizeBatchEntryInput(StrictModel):
    """One create entry inside a crystallize batch request."""

    mode: Literal["activity", "knowledge", "work_item"]
    input_data: dict


class CrystallizeBatchInput(StrictModel):
    """Input payload for running multiple crystallize create operations."""

    entries: list[CrystallizeBatchEntryInput]
    actor: dict | None = None


class CrystallizeActivityArgs(BaseToolArgs):
    """MCP arguments for wiki_crystallize activity mode."""

    mode: Literal["activity"]
    input_data: CrystallizeActivityInput


class CrystallizeKnowledgeArgs(BaseToolArgs):
    """MCP arguments for wiki_crystallize knowledge mode."""

    mode: Literal["knowledge"]
    input_data: CrystallizeKnowledgeInput


class CrystallizeWorkItemArgs(BaseToolArgs):
    """MCP arguments for wiki_crystallize work_item mode."""

    mode: Literal["work_item"]
    input_data: CrystallizeWorkItemInput


class CrystallizePromoteArgs(BaseToolArgs):
    """MCP arguments for wiki_crystallize promote mode."""

    mode: Literal["promote"]
    input_data: CrystallizePromoteInput


class CrystallizeSupersedeArgs(BaseToolArgs):
    """MCP arguments for wiki_crystallize supersede mode."""

    mode: Literal["supersede"]
    input_data: CrystallizeSupersedeInput


class CrystallizeContestArgs(BaseToolArgs):
    """MCP arguments for wiki_crystallize contest mode."""

    mode: Literal["contest"]
    input_data: CrystallizeContestInput


class CrystallizeBatchArgs(BaseToolArgs):
    """MCP arguments for wiki_crystallize batch mode."""

    mode: Literal["batch"]
    input_data: CrystallizeBatchInput


CrystallizeToolArgs = Annotated[
    CrystallizeActivityArgs
    | CrystallizeKnowledgeArgs
    | CrystallizeWorkItemArgs
    | CrystallizePromoteArgs
    | CrystallizeSupersedeArgs
    | CrystallizeContestArgs
    | CrystallizeBatchArgs,
    Field(discriminator="mode"),
]


class DreamPromoteCandidatesInput(StrictModel):
    """Input payload for promoting eligible candidate knowledge."""

    min_confidence: float | None = None
    min_evidence: int | None = None


class DreamMergeDuplicatesInput(StrictModel):
    """Input payload for merging duplicate knowledge facts."""

    pass


class DreamDecayStaleInput(StrictModel):
    """Input payload for marking stale knowledge by age."""

    reference_time: str | None = None
    stale_after_days: int | None = None


class DreamCycleInput(StrictModel):
    """Input payload for running the full dream maintenance cycle."""

    min_confidence: float | None = None
    min_evidence: int | None = None
    reference_time: str | None = None
    stale_after_days: int | None = None


class DreamReportInput(StrictModel):
    """Input payload for reporting dream maintenance opportunities."""

    min_confidence: float | None = None
    min_evidence: int | None = None
    reference_time: str | None = None
    stale_after_days: int | None = None


class DreamPromoteCandidatesArgs(BaseToolArgs):
    """MCP arguments for wiki_dream promote_candidates mode."""

    mode: Literal["promote_candidates"]
    input_data: DreamPromoteCandidatesInput


class DreamMergeDuplicatesArgs(BaseToolArgs):
    """MCP arguments for wiki_dream merge_duplicates mode."""

    mode: Literal["merge_duplicates"]
    input_data: DreamMergeDuplicatesInput


class DreamDecayStaleArgs(BaseToolArgs):
    """MCP arguments for wiki_dream decay_stale mode."""

    mode: Literal["decay_stale"]
    input_data: DreamDecayStaleInput


class DreamCycleArgs(BaseToolArgs):
    """MCP arguments for wiki_dream cycle mode."""

    mode: Literal["cycle"]
    input_data: DreamCycleInput


class DreamReportArgs(BaseToolArgs):
    """MCP arguments for wiki_dream report mode."""

    mode: Literal["report"]
    input_data: DreamReportInput


DreamToolArgs = Annotated[
    DreamPromoteCandidatesArgs | DreamMergeDuplicatesArgs | DreamDecayStaleArgs | DreamCycleArgs | DreamReportArgs,
    Field(discriminator="mode"),
]


class LintStructureInput(StrictModel):
    """Input payload for structural lint checks."""

    pass


class LintAuditInput(StrictModel):
    """Input payload for reading audit events."""

    pass


class LintReindexInput(StrictModel):
    """Input payload for rebuilding projections."""

    pass


class LintRepairInput(StrictModel):
    """Input payload for safe automatic repairs."""

    pass


class LintStructureArgs(BaseToolArgs):
    """MCP arguments for wiki_lint structure mode."""

    mode: Literal["structure"]
    input_data: LintStructureInput


class LintAuditArgs(BaseToolArgs):
    """MCP arguments for wiki_lint audit mode."""

    mode: Literal["audit"]
    input_data: LintAuditInput


class LintReindexArgs(BaseToolArgs):
    """MCP arguments for wiki_lint reindex mode."""

    mode: Literal["reindex"]
    input_data: LintReindexInput


class LintRepairArgs(BaseToolArgs):
    """MCP arguments for wiki_lint repair mode."""

    mode: Literal["repair"]
    input_data: LintRepairInput


LintToolArgs = Annotated[
    LintStructureArgs | LintAuditArgs | LintReindexArgs | LintRepairArgs,
    Field(discriminator="mode"),
]


class IngestRepoInput(StrictModel):
    """Input payload for ingesting a repository."""

    path: str


class IngestFileInput(StrictModel):
    """Input payload for ingesting a plain text file."""

    path: str


class IngestMarkdownInput(StrictModel):
    """Input payload for ingesting a Markdown file."""

    path: str


class IngestWebInput(StrictModel):
    """Input payload for ingesting a web URL."""

    url: str


class IngestPdfInput(StrictModel):
    """Input payload for ingesting a PDF file."""

    path: str


class IngestConversationInput(StrictModel):
    """Input payload for ingesting a conversation transcript."""

    title: str
    messages: list[dict]
    origin: dict | None = None


class IngestRepoArgs(BaseToolArgs):
    """MCP arguments for wiki_ingest repo mode."""

    mode: Literal["repo"]
    input_data: IngestRepoInput


class IngestFileArgs(BaseToolArgs):
    """MCP arguments for wiki_ingest file mode."""

    mode: Literal["file"]
    input_data: IngestFileInput


class IngestMarkdownArgs(BaseToolArgs):
    """MCP arguments for wiki_ingest markdown mode."""

    mode: Literal["markdown"]
    input_data: IngestMarkdownInput


class IngestWebArgs(BaseToolArgs):
    """MCP arguments for wiki_ingest web mode."""

    mode: Literal["web"]
    input_data: IngestWebInput


class IngestPdfArgs(BaseToolArgs):
    """MCP arguments for wiki_ingest pdf mode."""

    mode: Literal["pdf"]
    input_data: IngestPdfInput


class IngestConversationArgs(BaseToolArgs):
    """MCP arguments for wiki_ingest conversation mode."""

    mode: Literal["conversation"]
    input_data: IngestConversationInput


IngestToolArgs = Annotated[
    IngestRepoArgs | IngestFileArgs | IngestMarkdownArgs | IngestWebArgs | IngestPdfArgs | IngestConversationArgs,
    Field(discriminator="mode"),
]
