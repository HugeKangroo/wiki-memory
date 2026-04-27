from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GraphBackendName = Literal["file", "kuzu"]


class StrictModel(BaseModel):
    """Base schema that rejects unknown MCP argument fields."""

    model_config = ConfigDict(extra="forbid")


class EmptyOptions(StrictModel):
    """Empty options object accepted when a mode has no optional controls."""

    pass


class BaseToolArgs(StrictModel):
    """Shared top-level MCP tool arguments."""

    root: str | None = Field(default=None, description="Memory root path. Defaults to ~/memory-substrate when omitted.")
    options: EmptyOptions | None = None


class ActorRef(StrictModel):
    """Actor metadata recorded in audit and patch sources."""

    type: str = Field(description="Actor category, such as user, agent, system, or host.")
    id: str = Field(description="Stable actor identifier.")
    name: str | None = Field(default=None, description="Optional display name.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional host-specific actor metadata.")


class EvidenceRef(StrictModel):
    """Citation reference to one ingested source segment."""

    source_id: str = Field(description="Source object id, normally prefixed with src:.")
    segment_id: str = Field(description="Segment id inside the source object.")
    locator: dict[str, Any] | None = Field(default=None, description="Optional line, page, URL, or span locator.")


class KnowledgePayload(StrictModel):
    """Structured claim payload for fact-like knowledge."""

    subject: str | None = Field(default=None, description="Primary subject entity or object id for the claim.")
    predicate: str = Field(description="Relationship or property being asserted, such as primary_language.")
    value: Any = Field(default=None, description="Literal claim value when the predicate points to a value.")
    object: Any = Field(default=None, description="Object-side entity/value when the predicate links two things.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional structured details that do not fit the core claim fields.")


class ConversationMessage(StrictModel):
    """One message in an ingested conversation transcript."""

    role: str = Field(description="Message role, such as user, assistant, system, or tool.")
    content: str = Field(description="Message text content.")
    name: str | None = Field(default=None, description="Optional speaker or tool name.")
    created_at: str | None = Field(default=None, description="Optional ISO timestamp.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional host-specific message metadata.")


class QueryFilters(StrictModel):
    """Structured filters accepted by memory_query recent, search, and context scope."""

    object_type: str | None = None
    object_types: list[str] = Field(default_factory=list)
    kind: str | None = None
    kinds: list[str] = Field(default_factory=list)
    status: str | None = None
    statuses: list[str] = Field(default_factory=list)
    node_id: str | None = None
    node_ids: list[str] = Field(default_factory=list)
    source_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class QueryOptions(StrictModel):
    """Query controls shared by memory_query modes."""

    max_items: int | None = Field(default=None, ge=1, description="Maximum result count. Mode defaults apply when omitted.")
    filters: QueryFilters | None = Field(default=None, description="Optional structured result filters.")
    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend for graph mode.")


class RememberOptions(StrictModel):
    """Optional controls shared by memory_remember modes."""

    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend to sync after durable writes.")


class AuditOptions(StrictModel):
    """Options for reading audit events."""

    max_items: int | None = Field(default=None, ge=1, description="Maximum audit events to return.")


class ReindexOptions(StrictModel):
    """Options for rebuilding projections and optional graph indexes."""

    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend to rebuild from canonical objects.")


class ApplyOptions(StrictModel):
    """Required confirmation for memory_maintain modes that mutate memory."""

    apply: Literal[True] = Field(description="Must be true. Required because this maintain mode mutates memory.")


class QueryContextInput(StrictModel):
    """Input payload for building a task-focused context pack."""

    task: str
    scope: QueryFilters | None = None


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


class QueryBaseArgs(BaseToolArgs):
    """Base MCP arguments for memory_query modes."""

    options: QueryOptions | None = None


class QueryContextArgs(QueryBaseArgs):
    """MCP arguments for memory_query context mode."""

    mode: Literal["context"]
    input_data: QueryContextInput


class QueryExpandArgs(QueryBaseArgs):
    """MCP arguments for memory_query expand mode."""

    mode: Literal["expand"]
    input_data: QueryExpandInput


class QueryPageArgs(QueryBaseArgs):
    """MCP arguments for memory_query page mode."""

    mode: Literal["page"]
    input_data: QueryPageInput


class QueryRecentArgs(QueryBaseArgs):
    """MCP arguments for memory_query recent mode."""

    mode: Literal["recent"]
    input_data: QueryRecentInput


class QuerySearchArgs(QueryBaseArgs):
    """MCP arguments for memory_query search mode."""

    mode: Literal["search"]
    input_data: QuerySearchInput


class QueryGraphArgs(QueryBaseArgs):
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
    actor: ActorRef | None = None
    status: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    related_node_refs: list[str] = Field(default_factory=list)
    related_work_item_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    produced_object_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class RememberKnowledgeInput(StrictModel):
    """Input payload for creating a knowledge memory object."""

    kind: str
    title: str
    summary: str
    actor: ActorRef | None = None
    subject_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    payload: KnowledgePayload
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
    actor: ActorRef | None = None
    status: str | None = None
    lifecycle_state: str | None = None
    priority: str | None = None
    owner_refs: list[str] = Field(default_factory=list)
    related_node_refs: list[str] = Field(default_factory=list)
    related_knowledge_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    parent_ref: str | None = None
    child_refs: list[str] = Field(default_factory=list)
    resolution: str | None = None
    due_at: str | None = None
    opened_at: str | None = None


class RememberPromoteInput(StrictModel):
    """Input payload for promoting one knowledge object."""

    knowledge_id: str
    actor: ActorRef | None = None
    reason: str | None = None


class RememberSupersedeInput(StrictModel):
    """Input payload for superseding one knowledge object with another."""

    old_knowledge_id: str
    new_knowledge_id: str
    actor: ActorRef | None = None
    reason: str | None = None


class RememberContestInput(StrictModel):
    """Input payload for marking one knowledge object contested."""

    knowledge_id: str
    actor: ActorRef | None = None
    reason: str | None = None


class RememberBatchActivityEntryInput(StrictModel):
    """One activity create entry inside a remember batch request."""

    mode: Literal["activity"]
    input_data: RememberActivityInput


class RememberBatchKnowledgeEntryInput(StrictModel):
    """One knowledge create entry inside a remember batch request."""

    mode: Literal["knowledge"]
    input_data: RememberKnowledgeInput


class RememberBatchWorkItemEntryInput(StrictModel):
    """One work item create entry inside a remember batch request."""

    mode: Literal["work_item"]
    input_data: RememberWorkItemInput


RememberBatchEntryInput = Annotated[
    RememberBatchActivityEntryInput | RememberBatchKnowledgeEntryInput | RememberBatchWorkItemEntryInput,
    Field(discriminator="mode"),
]


class RememberBatchInput(StrictModel):
    """Input payload for running multiple remember create operations."""

    entries: list[RememberBatchEntryInput]
    actor: ActorRef | None = None


class RememberBaseArgs(BaseToolArgs):
    """Base MCP arguments for memory_remember modes."""

    options: RememberOptions | None = None


class RememberActivityArgs(RememberBaseArgs):
    """MCP arguments for memory_remember activity mode."""

    mode: Literal["activity"]
    input_data: RememberActivityInput


class RememberKnowledgeArgs(RememberBaseArgs):
    """MCP arguments for memory_remember knowledge mode."""

    mode: Literal["knowledge"]
    input_data: RememberKnowledgeInput


class RememberWorkItemArgs(RememberBaseArgs):
    """MCP arguments for memory_remember work_item mode."""

    mode: Literal["work_item"]
    input_data: RememberWorkItemInput


class RememberPromoteArgs(RememberBaseArgs):
    """MCP arguments for memory_remember promote mode."""

    mode: Literal["promote"]
    input_data: RememberPromoteInput


class RememberSupersedeArgs(RememberBaseArgs):
    """MCP arguments for memory_remember supersede mode."""

    mode: Literal["supersede"]
    input_data: RememberSupersedeInput


class RememberContestArgs(RememberBaseArgs):
    """MCP arguments for memory_remember contest mode."""

    mode: Literal["contest"]
    input_data: RememberContestInput


class RememberBatchArgs(RememberBaseArgs):
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


class MaintainApplyArgs(BaseToolArgs):
    """Base MCP arguments for memory_maintain modes that mutate memory."""

    options: ApplyOptions | None = None


class MaintainLifecyclePromoteCandidatesArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain promote_candidates mode."""

    mode: Literal["promote_candidates"]
    input_data: MaintainLifecyclePromoteCandidatesInput


class MaintainLifecycleMergeDuplicatesArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain merge_duplicates mode."""

    mode: Literal["merge_duplicates"]
    input_data: MaintainLifecycleMergeDuplicatesInput


class MaintainLifecycleDecayStaleArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain decay_stale mode."""

    mode: Literal["decay_stale"]
    input_data: MaintainLifecycleDecayStaleInput


class MaintainLifecycleCycleArgs(MaintainApplyArgs):
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
    options: AuditOptions | None = None


class MaintainStructureReindexArgs(BaseToolArgs):
    """MCP arguments for memory_maintain reindex mode."""

    mode: Literal["reindex"]
    input_data: MaintainStructureReindexInput
    options: ReindexOptions | None = None


class MaintainStructureRepairArgs(MaintainApplyArgs):
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
    messages: list[ConversationMessage]
    origin: dict[str, Any] | None = None


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
