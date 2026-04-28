from __future__ import annotations

from pathlib import Path

from memory_substrate.application.remember.service import RememberService
from memory_substrate.application.ingest.service import IngestService
from memory_substrate.application.maintain.service import MaintainService
from memory_substrate.application.query.service import QueryService
from memory_substrate.infrastructure.config.repository import MemoryConfigRepository
from memory_substrate.infrastructure.graph.factory import create_graph_backend
from memory_substrate.infrastructure.semantic.factory import create_semantic_index_service


MUTATING_MAINTAIN_MODES = {"configure", "repair", "promote_candidates", "merge_duplicates", "decay_stale", "cycle"}


def resolve_root(root: str | Path | None) -> Path:
    """Resolve an optional server or direct-dispatch root to a concrete memory-substrate root.

    Args:
        root: Optional root path supplied by server configuration or direct tests.

    Returns:
        Expanded memory-substrate root path, defaulting to ~/memory-substrate.
    """
    if root is None:
        return Path.home() / "memory-substrate"
    return Path(root).expanduser()


def _require_apply(mode: str, options: dict | None) -> None:
    if mode not in MUTATING_MAINTAIN_MODES:
        return
    if not options or options.get("apply") is not True:
        raise ValueError(f"memory_maintain mode '{mode}' mutates memory and requires options.apply=true")


def _requested_graph_backend(root: Path, options: dict | None) -> str | None:
    if options and options.get("graph_backend"):
        return options["graph_backend"]
    return MemoryConfigRepository(root).graph_backend()


def _requested_semantic_backend(root: Path, options: dict | None) -> str | None:
    if options and options.get("semantic_backend"):
        return options["semantic_backend"]
    return MemoryConfigRepository(root).semantic_backend()


def _close_graph_backend(graph_backend) -> None:
    close = getattr(graph_backend, "close", None)
    if callable(close):
        close()


def memory_ingest(root: str | Path | None, mode: str, input_data: dict, options: dict | None = None) -> dict:
    """Dispatch memory_ingest MCP calls to repository, file, web, PDF, or conversation ingest.

    Args:
        root: Optional memory-substrate root directory from server configuration; defaults to ~/memory-substrate when omitted.
        mode: Ingest mode such as repo, file, markdown, web, pdf, or conversation.
        input_data: Mode-specific payload validated by the MCP argument model.
        options: Optional execution flags reserved for future ingest behavior.

    Returns:
        Ingest result produced by the selected application service method.
    """
    options = options or {}
    service = IngestService(resolve_root(root))
    if mode == "repo":
        return service.ingest_repo(input_data["path"])
    if mode == "file":
        return service.ingest_file(input_data["path"])
    if mode == "markdown":
        return service.ingest_markdown(input_data["path"])
    if mode == "web":
        return service.ingest_web(input_data["url"])
    if mode == "pdf":
        return service.ingest_pdf(input_data["path"])
    if mode == "conversation":
        return service.ingest_conversation(
            title=input_data["title"],
            messages=input_data["messages"],
            origin=input_data.get("origin"),
        )
    raise ValueError(f"Unsupported ingest mode: {mode}")


def memory_query(root: str | Path | None, mode: str, input_data: dict, options: dict | None = None) -> dict:
    """Dispatch memory_query MCP calls to context, expansion, page, graph, recent, or search queries.

    Args:
        root: Optional memory-substrate root directory from server configuration; defaults to ~/memory-substrate when omitted.
        mode: Query mode such as context, expand, page, recent, search, or graph.
        input_data: Mode-specific query payload validated by the MCP argument model.
        options: Optional query controls such as max_items and filters.

    Returns:
        Query result produced by the selected application service method.
    """
    options = options or {}
    resolved_root = resolve_root(root)
    graph_backend = create_graph_backend(resolved_root, _requested_graph_backend(resolved_root, options))
    semantic_index = create_semantic_index_service(resolved_root, _requested_semantic_backend(resolved_root, options))
    service_kwargs = {}
    if graph_backend is not None:
        service_kwargs["graph_backend"] = graph_backend
    if semantic_index is not None:
        service_kwargs["semantic_index"] = semantic_index
    service = QueryService(resolved_root, **service_kwargs)
    try:
        if mode == "context":
            return service.context(
                task=input_data["task"],
                scope=input_data.get("scope"),
                max_items=options.get("max_items", 12),
            )
        if mode == "expand":
            return service.expand(
                object_id=input_data["id"],
                max_items=options.get("max_items", 10),
            )
        if mode == "page":
            return service.page(object_id=input_data["id"])
        if mode == "recent":
            return service.recent(max_items=options.get("max_items", 20), filters=options.get("filters"))
        if mode == "search":
            return service.search(query=input_data["query"], max_items=options.get("max_items", 20), filters=options.get("filters"))
        if mode == "graph":
            return service.graph(object_id=input_data["id"], max_items=options.get("max_items", 20))
        raise ValueError(f"Unsupported query mode: {mode}")
    finally:
        _close_graph_backend(graph_backend)


def memory_remember(root: str | Path | None, mode: str, input_data: dict, options: dict | None = None) -> dict:
    """Dispatch memory_remember MCP calls that write durable memory objects.

    Args:
        root: Optional memory-substrate root directory from server configuration; defaults to ~/memory-substrate when omitted.
        mode: Remember mode such as activity, knowledge, work_item, promote, supersede, contest, or batch.
        input_data: Mode-specific mutation payload validated by the MCP argument model.
        options: Optional execution flags reserved for future remember behavior.

    Returns:
        Mutation result with patch, audit, object, and projection metadata.
    """
    options = options or {}
    resolved_root = resolve_root(root)
    graph_backend = create_graph_backend(resolved_root, _requested_graph_backend(resolved_root, options))
    service = (
        RememberService(resolved_root, graph_backend=graph_backend)
        if graph_backend is not None
        else RememberService(resolved_root)
    )
    actor = input_data.get("actor")
    try:
        if mode == "activity":
            return service.create_activity(input_data, actor=actor)
        if mode == "knowledge":
            return service.create_knowledge(input_data, actor=actor)
        if mode == "work_item":
            return service.create_work_item(input_data, actor=actor)
        if mode == "promote":
            return service.promote_knowledge(
                knowledge_id=input_data["knowledge_id"],
                actor=actor,
                reason=input_data.get("reason", ""),
            )
        if mode == "supersede":
            return service.supersede_knowledge(
                old_knowledge_id=input_data["old_knowledge_id"],
                new_knowledge_id=input_data["new_knowledge_id"],
                actor=actor,
                reason=input_data.get("reason", ""),
            )
        if mode == "contest":
            return service.contest_knowledge(
                knowledge_id=input_data["knowledge_id"],
                actor=actor,
                reason=input_data.get("reason", ""),
            )
        if mode == "batch":
            return service.batch(
                entries=input_data["entries"],
                actor=actor,
            )
        raise ValueError(f"Unsupported remember mode: {mode}")
    finally:
        _close_graph_backend(graph_backend)


def memory_maintain(root: str | Path | None, mode: str, input_data: dict | None = None, options: dict | None = None) -> dict:
    """Dispatch memory_maintain MCP calls for validation, repair, reindexing, and lifecycle workflows.

    Args:
        root: Optional memory-substrate root directory from server configuration; defaults to ~/memory-substrate when omitted.
        mode: Maintain mode such as structure, audit, reindex, repair, promote_candidates, cycle, or report.
        input_data: Optional mode-specific payload.
        options: Optional controls such as max_items for audit reads.

    Returns:
        Maintenance result for the selected mode.
    """
    input_data = input_data or {}
    options = options or {}
    _require_apply(mode, options)
    resolved_root = resolve_root(root)
    if mode == "configure":
        repository = MemoryConfigRepository(resolved_root)
        config = repository.get()
        if input_data.get("graph_backend"):
            config = repository.set_graph_backend(input_data["graph_backend"])
        if input_data.get("semantic_backend"):
            config = repository.set_semantic_backend(input_data["semantic_backend"])
        return {
            "result_type": "maintain_configure_result",
            "data": {"config": config},
            "warnings": [],
        }
    graph_backend = create_graph_backend(resolved_root, _requested_graph_backend(resolved_root, options))
    semantic_index = create_semantic_index_service(resolved_root, _requested_semantic_backend(resolved_root, options))
    service_kwargs = {}
    if graph_backend is not None:
        service_kwargs["graph_backend"] = graph_backend
    if semantic_index is not None:
        service_kwargs["semantic_index"] = semantic_index
    service = MaintainService(resolved_root, **service_kwargs)
    try:
        if mode == "structure":
            return service.structure()
        if mode == "audit":
            return service.audit(max_items=options.get("max_items", 100))
        if mode == "reindex":
            return service.reindex()
        if mode == "repair":
            return service.repair()
        if mode == "promote_candidates":
            return service.promote_candidates(
                min_confidence=input_data.get("min_confidence", 0.75),
                min_evidence=input_data.get("min_evidence", 1),
            )
        if mode == "merge_duplicates":
            return service.merge_duplicates()
        if mode == "decay_stale":
            return service.decay_stale(
                reference_time=input_data.get("reference_time"),
                stale_after_days=input_data.get("stale_after_days", 30),
            )
        if mode == "cycle":
            return service.cycle(
                min_confidence=input_data.get("min_confidence", 0.75),
                min_evidence=input_data.get("min_evidence", 1),
                reference_time=input_data.get("reference_time"),
                stale_after_days=input_data.get("stale_after_days", 30),
            )
        if mode == "report":
            return service.report(
                min_confidence=input_data.get("min_confidence", 0.75),
                min_evidence=input_data.get("min_evidence", 1),
                reference_time=input_data.get("reference_time"),
                stale_after_days=input_data.get("stale_after_days", 30),
            )
        raise ValueError(f"Unsupported maintain mode: {mode}")
    finally:
        _close_graph_backend(graph_backend)
