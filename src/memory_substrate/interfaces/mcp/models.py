from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GraphBackendName = Literal["file", "kuzu"]
SemanticBackendName = Literal["lancedb"]
WikiProjectionFormatName = Literal["obsidian"]
MemorySourceName = Literal["user_declared", "human_curated", "agent_inferred", "system_generated", "imported"]
QueryDetailName = Literal["compact", "full"]


class StrictModel(BaseModel):
    """Base schema that rejects unknown MCP argument fields."""

    model_config = ConfigDict(extra="forbid")


class EmptyOptions(StrictModel):
    """Empty options object accepted when a mode has no optional controls."""

    pass


class BaseToolArgs(StrictModel):
    """Shared top-level MCP tool arguments."""

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
    hash: str | None = Field(default=None, description="Optional expected source segment hash for citation integrity checks.")


class KnowledgePayload(StrictModel):
    """Optional structured claim payload for fact-like knowledge."""

    subject: str | None = Field(default=None, description="Primary subject entity or object id for the claim.")
    predicate: str | None = Field(default=None, description="Relationship or property being asserted, such as primary_language.")
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
    include_temporary: bool = Field(default=False, description="Include temporary/scratch/evaluation knowledge in query results.")


class QueryContextOptions(StrictModel):
    """Options for memory_query context mode."""

    max_items: int | None = Field(default=None, ge=1, description="Maximum context items. Default: 12.")
    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend override.")


class QuerySearchOptions(StrictModel):
    """Options for memory_query search mode."""

    max_items: int | None = Field(default=None, ge=1, description="Maximum search hits. Default: 10.")
    filters: QueryFilters | None = Field(default=None, description="Optional structured result filters.")
    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend override.")
    semantic_backend: SemanticBackendName | None = Field(default=None, description="Optional semantic backend override.")


class QueryExpandOptions(StrictModel):
    """Options for memory_query expand mode."""

    max_items: int | None = Field(
        default=None,
        ge=1,
        description="Maximum related items and source segment snippets for one id; total item budget for ids. Default: 10 for id, 20 for ids.",
    )
    per_id_max_items: int | None = Field(default=None, ge=1, description="Maximum related items per id when input_data.ids is used. Default: 5.")
    include_segments: bool | None = Field(default=None, description="Include source segment snippets. Default: true.")
    snippet_chars: int | None = Field(default=None, ge=40, le=4000, description="Maximum segment excerpt length. Default: 360.")


class QuerySourceSliceOptions(StrictModel):
    """Options for memory_query source_slice mode."""

    max_lines: int | None = Field(default=None, ge=1, le=500, description="Maximum source lines to return. Default: 120.")
    snippet_chars: int | None = Field(default=None, ge=40, le=20000, description="Maximum source characters to return. Default: 8000.")


class QueryPageOptions(StrictModel):
    """Options for memory_query page mode."""

    detail: QueryDetailName | None = Field(
        default=None,
        description="Use compact by default. Set full only for bounded non-repo objects; repo sources return page_unavailable.",
    )
    max_items: int | None = Field(default=None, ge=1, description="For compact pages, maximum entries per returned list. Default: 10.")
    include_segments: bool | None = Field(default=None, description="For compact source pages, include source segment snippets. Default: false.")
    snippet_chars: int | None = Field(default=None, ge=40, le=4000, description="Maximum compact excerpt length. Default: 360.")


class QueryRecentOptions(StrictModel):
    """Options for memory_query recent mode."""

    max_items: int | None = Field(default=None, ge=1, description="Maximum recent items. Default: 10.")
    filters: QueryFilters | None = Field(default=None, description="Optional structured result filters.")


class QueryGraphOptions(StrictModel):
    """Options for memory_query graph mode."""

    max_items: int | None = Field(default=None, ge=1, description="Maximum graph nodes. Default: 10.")
    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend override.")


class RememberOptions(StrictModel):
    """Optional controls shared by memory_remember modes."""

    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend override to sync after durable writes.")


class AuditOptions(StrictModel):
    """Options for reading audit events."""

    max_items: int | None = Field(default=None, ge=1, description="Maximum audit events to return.")


class ReindexOptions(StrictModel):
    """Options for rebuilding projections and optional graph indexes."""

    graph_backend: GraphBackendName | None = Field(default=None, description="Optional graph backend override to rebuild from canonical objects.")
    semantic_backend: SemanticBackendName | None = Field(default=None, description="Optional semantic backend override to rebuild from canonical objects.")


class ApplyOptions(StrictModel):
    """Required confirmation for memory_maintain modes that mutate memory."""

    apply: Literal[True] = Field(description="Must be true. Required because this maintain mode mutates memory.")


class IngestOptions(StrictModel):
    """Optional controls shared by memory_ingest modes."""

    force: bool = Field(
        default=False,
        description="For repo ingest, proceed with writes even when preflight warnings require an explicit decision.",
    )


class QueryContextInput(StrictModel):
    """Input payload for building a task-focused context pack."""

    task: str
    scope: QueryFilters | None = None


class QueryExpandInput(StrictModel):
    """Input payload for expanding one or more memory objects."""

    id: str | None = Field(default=None, description="Single source, node, knowledge, activity, or work item id to expand.")
    ids: list[str] = Field(default_factory=list, description="Multiple ids to expand in one bounded grouped result.")


class QueryPageInput(StrictModel):
    """Input payload for fetching one memory object page."""

    id: str


class QuerySourceSliceInput(StrictModel):
    """Input payload for hydrating a bounded source slice."""

    source_id: str = Field(description="Source object id, normally prefixed with src:.")
    path: str | None = Field(default=None, description="Repo-relative source path. Required for repo sources.")
    line_start: int | None = Field(default=None, ge=1, description="1-based inclusive start line.")
    line_end: int | None = Field(default=None, ge=1, description="1-based inclusive end line.")
    segment_id: str | None = Field(default=None, description="Optional source segment id whose locator supplies default line bounds.")


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

    pass


class QueryContextArgs(QueryBaseArgs):
    """MCP arguments for memory_query context mode."""

    mode: Literal["context"]
    input_data: QueryContextInput
    options: QueryContextOptions | None = None


class QueryExpandArgs(QueryBaseArgs):
    """MCP arguments for memory_query expand mode."""

    mode: Literal["expand"]
    input_data: QueryExpandInput
    options: QueryExpandOptions | None = None


class QueryPageArgs(QueryBaseArgs):
    """MCP arguments for memory_query page mode."""

    mode: Literal["page"]
    input_data: QueryPageInput
    options: QueryPageOptions | None = None


class QuerySourceSliceArgs(QueryBaseArgs):
    """MCP arguments for memory_query source_slice mode."""

    mode: Literal["source_slice"]
    input_data: QuerySourceSliceInput
    options: QuerySourceSliceOptions | None = None


class QueryRecentArgs(QueryBaseArgs):
    """MCP arguments for memory_query recent mode."""

    mode: Literal["recent"]
    input_data: QueryRecentInput
    options: QueryRecentOptions | None = None


class QuerySearchArgs(QueryBaseArgs):
    """MCP arguments for memory_query search mode."""

    mode: Literal["search"]
    input_data: QuerySearchInput
    options: QuerySearchOptions | None = None


class QueryGraphArgs(QueryBaseArgs):
    """MCP arguments for memory_query graph mode."""

    mode: Literal["graph"]
    input_data: QueryGraphInput
    options: QueryGraphOptions | None = None


QueryToolArgs = Annotated[
    QueryContextArgs
    | QueryExpandArgs
    | QueryPageArgs
    | QuerySourceSliceArgs
    | QueryRecentArgs
    | QuerySearchArgs
    | QueryGraphArgs,
    Field(discriminator="mode"),
]


class RememberActivityInput(StrictModel):
    """Input payload for creating an activity memory object."""

    kind: str
    title: str
    summary: str
    reason: str = Field(description="Durable write reason explaining why this activity should survive future sessions.")
    memory_source: MemorySourceName = Field(description="Where the remembered activity came from.")
    scope_refs: list[str] = Field(min_length=1, description="Memory scopes this activity belongs to, such as project, user, repo, or topic scopes.")
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
    reason: str = Field(description="Durable write reason explaining why this knowledge should survive future sessions.")
    memory_source: MemorySourceName = Field(description="Where the remembered knowledge came from.")
    scope_refs: list[str] = Field(min_length=1, description="Memory scopes this knowledge belongs to, such as project, user, repo, or topic scopes.")
    actor: ActorRef | None = None
    subject_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source_text: str | None = Field(
        default=None,
        description="Optional raw declaration text to preserve as a source when no evidence_refs are supplied.",
    )
    source_title: str | None = Field(
        default=None,
        description="Optional title for the generated declaration source.",
    )
    payload: KnowledgePayload = Field(
        default_factory=KnowledgePayload,
        description="Optional structured payload. Omit for unstructured title/summary-only knowledge; include subject, predicate, value, or object for structured claims.",
    )
    status: str | None = None
    lifecycle_state: str | None = Field(default=None, description="Optional lifecycle state, such as temporary, scratch, evaluation, or active.")
    expires_at: str | None = Field(default=None, description="Optional expiry/review time for temporary memory.")
    confidence: float | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    last_verified_at: str | None = None
    allow_duplicate: bool = Field(default=False, description="Set true only for imports or tests that intentionally seed duplicate knowledge.")


class RememberWorkItemInput(StrictModel):
    """Input payload for creating a work item memory object."""

    kind: str
    title: str
    summary: str
    reason: str = Field(description="Durable write reason explaining why this work item should survive future sessions.")
    memory_source: MemorySourceName = Field(description="Where the remembered work item came from.")
    scope_refs: list[str] = Field(min_length=1, description="Memory scopes this work item belongs to, such as project, user, repo, or topic scopes.")
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


class RememberWorkItemStatusInput(StrictModel):
    """Input payload for updating an existing work item status."""

    work_item_id: str = Field(description="Existing work item id to update, normally prefixed with work:.")
    status: Literal["open", "in_progress", "blocked", "resolved", "closed", "cancelled"] = Field(
        description="New work item lifecycle status."
    )
    reason: str = Field(min_length=1, description="Audit reason explaining why the work item status changed.")
    memory_source: MemorySourceName = Field(description="Where the status update came from.")
    actor: ActorRef | None = None
    resolution: str | None = Field(
        default=None,
        description="Optional resolution summary, especially for resolved, closed, or cancelled work items.",
    )


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


class RememberWorkItemStatusArgs(RememberBaseArgs):
    """MCP arguments for memory_remember work_item_status mode."""

    mode: Literal["work_item_status"]
    input_data: RememberWorkItemStatusInput


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
    | RememberWorkItemStatusArgs
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


class MaintainDuplicateResolutionUpdate(StrictModel):
    """One keep_both clarification for a reviewed soft duplicate."""

    knowledge_id: str = Field(description="Knowledge object id to update.")
    summary: str | None = Field(default=None, description="Optional clarified summary.")
    scope_refs: list[str] | None = Field(default=None, description="Optional clarified durable scope refs.")


class MaintainLifecycleResolveDuplicatesInput(StrictModel):
    """Input payload for explicitly resolving a soft duplicate candidate."""

    outcome: Literal["supersede", "keep_both", "contest"] = Field(description="Explicit review outcome for the candidate.")
    knowledge_ids: list[str] = Field(min_length=2, description="Knowledge ids from a reported soft duplicate candidate.")
    reason: str = Field(min_length=1, description="Audit reason explaining the reviewed outcome.")
    canonical_knowledge_id: str | None = Field(default=None, description="Required winner id when outcome is supersede.")
    updates: list[MaintainDuplicateResolutionUpdate] | None = Field(
        default=None,
        description="Required for keep_both when summaries or scopes need clarification.",
    )


class MaintainLifecycleDecayStaleInput(StrictModel):
    """Input payload for marking stale knowledge by age."""

    reference_time: str | None = None
    stale_after_days: int | None = None


class MaintainLifecycleArchiveSourceInput(StrictModel):
    """Input payload for archiving a source and reporting affected knowledge."""

    source_id: str = Field(description="Source object id to archive, normally prefixed with src:.")
    reason: str = Field(min_length=1, description="Durable audit reason explaining why this source is retired.")


class MaintainLifecycleArchiveKnowledgeInput(StrictModel):
    """Input payload for archiving one knowledge item after review."""

    knowledge_id: str = Field(description="Knowledge object id to archive, normally prefixed with know:.")
    reason: str = Field(min_length=1, description="Durable audit reason explaining why this knowledge is archived.")


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


class WikiProjectionConfig(StrictModel):
    """External wiki projection target stored under memory/config.json."""

    path: str = Field(description="External wiki/vault directory path for generated projection files.")
    format: WikiProjectionFormatName = Field(default="obsidian", description="External wiki projection format. Currently obsidian.")


class MaintainConfigureInput(StrictModel):
    """Input payload for setting root-level memory defaults."""

    graph_backend: GraphBackendName | None = Field(default=None, description="Default graph backend used when tool options omit graph_backend.")
    semantic_backend: SemanticBackendName | None = Field(default=None, description="Default semantic backend used when tool options omit semantic_backend.")
    wiki_projection: WikiProjectionConfig | None = Field(default=None, description="External wiki projection target configuration.")


class MaintainApplyArgs(BaseToolArgs):
    """Base MCP arguments for memory_maintain modes that mutate memory."""

    options: ApplyOptions | None = None


class MaintainConfigureArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain configure mode."""

    mode: Literal["configure"]
    input_data: MaintainConfigureInput


class MaintainLifecyclePromoteCandidatesArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain promote_candidates mode."""

    mode: Literal["promote_candidates"]
    input_data: MaintainLifecyclePromoteCandidatesInput


class MaintainLifecycleMergeDuplicatesArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain merge_duplicates mode."""

    mode: Literal["merge_duplicates"]
    input_data: MaintainLifecycleMergeDuplicatesInput


class MaintainLifecycleResolveDuplicatesArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain resolve_duplicates mode."""

    mode: Literal["resolve_duplicates"]
    input_data: MaintainLifecycleResolveDuplicatesInput


class MaintainLifecycleDecayStaleArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain decay_stale mode."""

    mode: Literal["decay_stale"]
    input_data: MaintainLifecycleDecayStaleInput


class MaintainLifecycleArchiveSourceArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain archive_source mode."""

    mode: Literal["archive_source"]
    input_data: MaintainLifecycleArchiveSourceInput


class MaintainLifecycleArchiveKnowledgeArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain archive_knowledge mode."""

    mode: Literal["archive_knowledge"]
    input_data: MaintainLifecycleArchiveKnowledgeInput


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


class MaintainRenderProjectionInput(StrictModel):
    """Input payload for rendering the configured external wiki projection."""

    pass


class MaintainReconcileProjectionInput(StrictModel):
    """Input payload for reporting configured external wiki projection changes."""

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


class MaintainRenderProjectionArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain render_projection mode."""

    mode: Literal["render_projection"]
    input_data: MaintainRenderProjectionInput


class MaintainReconcileProjectionArgs(BaseToolArgs):
    """MCP arguments for memory_maintain reconcile_projection mode."""

    mode: Literal["reconcile_projection"]
    input_data: MaintainReconcileProjectionInput


class MaintainStructureRepairArgs(MaintainApplyArgs):
    """MCP arguments for memory_maintain repair mode."""

    mode: Literal["repair"]
    input_data: MaintainStructureRepairInput


MaintainToolArgs = Annotated[
    MaintainConfigureArgs
    | MaintainStructureArgs
    | MaintainStructureAuditArgs
    | MaintainStructureReindexArgs
    | MaintainRenderProjectionArgs
    | MaintainReconcileProjectionArgs
    | MaintainStructureRepairArgs
    | MaintainLifecyclePromoteCandidatesArgs
    | MaintainLifecycleMergeDuplicatesArgs
    | MaintainLifecycleResolveDuplicatesArgs
    | MaintainLifecycleArchiveKnowledgeArgs
    | MaintainLifecycleArchiveSourceArgs
    | MaintainLifecycleDecayStaleArgs
    | MaintainLifecycleCycleArgs
    | MaintainLifecycleReportArgs,
    Field(discriminator="mode"),
]


class IngestRepoInput(StrictModel):
    """Input payload for ingesting a repository."""

    path: str
    include_patterns: list[str] = Field(default_factory=list, description="Optional glob-like relative path patterns to include.")
    exclude_patterns: list[str] = Field(default_factory=list, description="Optional glob-like relative path patterns to exclude.")


class IngestBaseArgs(BaseToolArgs):
    """Base MCP arguments for memory_ingest modes."""

    options: IngestOptions | None = None


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


class IngestRepoArgs(IngestBaseArgs):
    """MCP arguments for memory_ingest repo mode."""

    mode: Literal["repo"]
    input_data: IngestRepoInput


class IngestFileArgs(IngestBaseArgs):
    """MCP arguments for memory_ingest file mode."""

    mode: Literal["file"]
    input_data: IngestFileInput


class IngestMarkdownArgs(IngestBaseArgs):
    """MCP arguments for memory_ingest markdown mode."""

    mode: Literal["markdown"]
    input_data: IngestMarkdownInput


class IngestWebArgs(IngestBaseArgs):
    """MCP arguments for memory_ingest web mode."""

    mode: Literal["web"]
    input_data: IngestWebInput


class IngestPdfArgs(IngestBaseArgs):
    """MCP arguments for memory_ingest pdf mode."""

    mode: Literal["pdf"]
    input_data: IngestPdfInput


class IngestConversationArgs(IngestBaseArgs):
    """MCP arguments for memory_ingest conversation mode."""

    mode: Literal["conversation"]
    input_data: IngestConversationInput


IngestToolArgs = Annotated[
    IngestRepoArgs | IngestFileArgs | IngestMarkdownArgs | IngestWebArgs | IngestPdfArgs | IngestConversationArgs,
    Field(discriminator="mode"),
]
