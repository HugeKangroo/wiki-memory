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
    """MCP arguments for memory_query context mode."""

    mode: Literal["context"]
    input_data: QueryContextInput


class QueryExpandArgs(BaseToolArgs):
    """MCP arguments for memory_query expand mode."""

    mode: Literal["expand"]
    input_data: QueryExpandInput


class QueryPageArgs(BaseToolArgs):
    """MCP arguments for memory_query page mode."""

    mode: Literal["page"]
    input_data: QueryPageInput


class QueryRecentArgs(BaseToolArgs):
    """MCP arguments for memory_query recent mode."""

    mode: Literal["recent"]
    input_data: QueryRecentInput


class QuerySearchArgs(BaseToolArgs):
    """MCP arguments for memory_query search mode."""

    mode: Literal["search"]
    input_data: QuerySearchInput


class QueryGraphArgs(BaseToolArgs):
    """MCP arguments for memory_query graph mode."""

    mode: Literal["graph"]
    input_data: QueryGraphInput


QueryToolArgs = Annotated[
    QueryContextArgs | QueryExpandArgs | QueryPageArgs | QueryRecentArgs | QuerySearchArgs | QueryGraphArgs,
    Field(discriminator="mode"),
]


class RememberActivityInput(StrictModel):
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


class RememberKnowledgeInput(StrictModel):
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


class RememberWorkItemInput(StrictModel):
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


class RememberPromoteInput(StrictModel):
    """Input payload for promoting one knowledge object."""

    knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class RememberSupersedeInput(StrictModel):
    """Input payload for superseding one knowledge object with another."""

    old_knowledge_id: str
    new_knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class RememberContestInput(StrictModel):
    """Input payload for marking one knowledge object contested."""

    knowledge_id: str
    actor: dict | None = None
    reason: str | None = None


class RememberBatchEntryInput(StrictModel):
    """One create entry inside a remember batch request."""

    mode: Literal["activity", "knowledge", "work_item"]
    input_data: dict


class RememberBatchInput(StrictModel):
    """Input payload for running multiple remember create operations."""

    entries: list[RememberBatchEntryInput]
    actor: dict | None = None


class RememberActivityArgs(BaseToolArgs):
    """MCP arguments for memory_remember activity mode."""

    mode: Literal["activity"]
    input_data: RememberActivityInput


class RememberKnowledgeArgs(BaseToolArgs):
    """MCP arguments for memory_remember knowledge mode."""

    mode: Literal["knowledge"]
    input_data: RememberKnowledgeInput


class RememberWorkItemArgs(BaseToolArgs):
    """MCP arguments for memory_remember work_item mode."""

    mode: Literal["work_item"]
    input_data: RememberWorkItemInput


class RememberPromoteArgs(BaseToolArgs):
    """MCP arguments for memory_remember promote mode."""

    mode: Literal["promote"]
    input_data: RememberPromoteInput


class RememberSupersedeArgs(BaseToolArgs):
    """MCP arguments for memory_remember supersede mode."""

    mode: Literal["supersede"]
    input_data: RememberSupersedeInput


class RememberContestArgs(BaseToolArgs):
    """MCP arguments for memory_remember contest mode."""

    mode: Literal["contest"]
    input_data: RememberContestInput


class RememberBatchArgs(BaseToolArgs):
    """MCP arguments for memory_remember batch mode."""

    mode: Literal["batch"]
    input_data: RememberBatchInput


RememberToolArgs = Annotated[
    RememberActivityArgs
    | RememberKnowledgeArgs
    | RememberWorkItemArgs
    | RememberPromoteArgs
    | RememberSupersedeArgs
    | RememberContestArgs
    | RememberBatchArgs,
    Field(discriminator="mode"),
]


class MaintainLifecyclePromoteCandidatesInput(StrictModel):
    """Input payload for promoting eligible candidate knowledge."""

    min_confidence: float | None = None
    min_evidence: int | None = None


class MaintainLifecycleMergeDuplicatesInput(StrictModel):
    """Input payload for merging duplicate knowledge facts."""

    pass


class MaintainLifecycleDecayStaleInput(StrictModel):
    """Input payload for marking stale knowledge by age."""

    reference_time: str | None = None
    stale_after_days: int | None = None


class MaintainLifecycleCycleInput(StrictModel):
    """Input payload for running the full memory maintenance cycle."""

    min_confidence: float | None = None
    min_evidence: int | None = None
    reference_time: str | None = None
    stale_after_days: int | None = None


class MaintainLifecycleReportInput(StrictModel):
    """Input payload for reporting memory maintenance opportunities."""

    min_confidence: float | None = None
    min_evidence: int | None = None
    reference_time: str | None = None
    stale_after_days: int | None = None


class MaintainLifecyclePromoteCandidatesArgs(BaseToolArgs):
    """MCP arguments for memory_maintain promote_candidates mode."""

    mode: Literal["promote_candidates"]
    input_data: MaintainLifecyclePromoteCandidatesInput


class MaintainLifecycleMergeDuplicatesArgs(BaseToolArgs):
    """MCP arguments for memory_maintain merge_duplicates mode."""

    mode: Literal["merge_duplicates"]
    input_data: MaintainLifecycleMergeDuplicatesInput


class MaintainLifecycleDecayStaleArgs(BaseToolArgs):
    """MCP arguments for memory_maintain decay_stale mode."""

    mode: Literal["decay_stale"]
    input_data: MaintainLifecycleDecayStaleInput


class MaintainLifecycleCycleArgs(BaseToolArgs):
    """MCP arguments for memory_maintain cycle mode."""

    mode: Literal["cycle"]
    input_data: MaintainLifecycleCycleInput


class MaintainLifecycleReportArgs(BaseToolArgs):
    """MCP arguments for memory_maintain report mode."""

    mode: Literal["report"]
    input_data: MaintainLifecycleReportInput


class MaintainStructureInput(StrictModel):
    """Input payload for structural validation checks."""

    pass


class MaintainStructureAuditInput(StrictModel):
    """Input payload for reading audit events."""

    pass


class MaintainStructureReindexInput(StrictModel):
    """Input payload for rebuilding projections."""

    pass


class MaintainStructureRepairInput(StrictModel):
    """Input payload for safe automatic repairs."""

    pass


class MaintainStructureArgs(BaseToolArgs):
    """MCP arguments for memory_maintain structure mode."""

    mode: Literal["structure"]
    input_data: MaintainStructureInput


class MaintainStructureAuditArgs(BaseToolArgs):
    """MCP arguments for memory_maintain audit mode."""

    mode: Literal["audit"]
    input_data: MaintainStructureAuditInput


class MaintainStructureReindexArgs(BaseToolArgs):
    """MCP arguments for memory_maintain reindex mode."""

    mode: Literal["reindex"]
    input_data: MaintainStructureReindexInput


class MaintainStructureRepairArgs(BaseToolArgs):
    """MCP arguments for memory_maintain repair mode."""

    mode: Literal["repair"]
    input_data: MaintainStructureRepairInput


MaintainToolArgs = Annotated[
    MaintainStructureArgs
    | MaintainStructureAuditArgs
    | MaintainStructureReindexArgs
    | MaintainStructureRepairArgs
    | MaintainLifecyclePromoteCandidatesArgs
    | MaintainLifecycleMergeDuplicatesArgs
    | MaintainLifecycleDecayStaleArgs
    | MaintainLifecycleCycleArgs
    | MaintainLifecycleReportArgs,
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
    """MCP arguments for memory_ingest repo mode."""

    mode: Literal["repo"]
    input_data: IngestRepoInput


class IngestFileArgs(BaseToolArgs):
    """MCP arguments for memory_ingest file mode."""

    mode: Literal["file"]
    input_data: IngestFileInput


class IngestMarkdownArgs(BaseToolArgs):
    """MCP arguments for memory_ingest markdown mode."""

    mode: Literal["markdown"]
    input_data: IngestMarkdownInput


class IngestWebArgs(BaseToolArgs):
    """MCP arguments for memory_ingest web mode."""

    mode: Literal["web"]
    input_data: IngestWebInput


class IngestPdfArgs(BaseToolArgs):
    """MCP arguments for memory_ingest pdf mode."""

    mode: Literal["pdf"]
    input_data: IngestPdfInput


class IngestConversationArgs(BaseToolArgs):
    """MCP arguments for memory_ingest conversation mode."""

    mode: Literal["conversation"]
    input_data: IngestConversationInput


IngestToolArgs = Annotated[
    IngestRepoArgs | IngestFileArgs | IngestMarkdownArgs | IngestWebArgs | IngestPdfArgs | IngestConversationArgs,
    Field(discriminator="mode"),
]
