from __future__ import annotations

from pathlib import Path

from wiki_memory.application.crystallize.service import CrystallizeService
from wiki_memory.application.dream.service import DreamService
from wiki_memory.application.ingest.service import IngestService
from wiki_memory.application.lint.service import LintService
from wiki_memory.application.query.service import QueryService


def resolve_root(root: str | Path | None) -> Path:
    """Resolve an optional MCP root argument to a concrete wiki-memory root.

    Args:
        root: Optional root path supplied by the host agent.

    Returns:
        Expanded wiki-memory root path, defaulting to ~/wiki-memory.
    """
    if root is None:
        return Path.home() / "wiki-memory"
    return Path(root).expanduser()


def wiki_ingest(root: str | Path | None, mode: str, input_data: dict, options: dict | None = None) -> dict:
    """Dispatch wiki_ingest MCP calls to repository, file, web, PDF, or conversation ingest.

    Args:
        root: Optional wiki-memory root directory; defaults to ~/wiki-memory when omitted.
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


def wiki_query(root: str | Path | None, mode: str, input_data: dict, options: dict | None = None) -> dict:
    """Dispatch wiki_query MCP calls to context, expansion, page, graph, recent, or search queries.

    Args:
        root: Optional wiki-memory root directory; defaults to ~/wiki-memory when omitted.
        mode: Query mode such as context, expand, page, recent, search, or graph.
        input_data: Mode-specific query payload validated by the MCP argument model.
        options: Optional query controls such as max_items and filters.

    Returns:
        Query result produced by the selected application service method.
    """
    options = options or {}
    service = QueryService(resolve_root(root))
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


def wiki_crystallize(root: str | Path | None, mode: str, input_data: dict, options: dict | None = None) -> dict:
    """Dispatch wiki_crystallize MCP calls that write durable memory objects.

    Args:
        root: Optional wiki-memory root directory; defaults to ~/wiki-memory when omitted.
        mode: Crystallize mode such as activity, knowledge, work_item, promote, supersede, contest, or batch.
        input_data: Mode-specific mutation payload validated by the MCP argument model.
        options: Optional execution flags reserved for future crystallize behavior.

    Returns:
        Mutation result with patch, audit, object, and projection metadata.
    """
    options = options or {}
    service = CrystallizeService(resolve_root(root))
    actor = input_data.get("actor")
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
    raise ValueError(f"Unsupported crystallize mode: {mode}")


def wiki_lint(root: str | Path | None, mode: str, input_data: dict | None = None, options: dict | None = None) -> dict:
    """Dispatch wiki_lint MCP calls for structure checks, audit reads, reindexing, and repair.

    Args:
        root: Optional wiki-memory root directory; defaults to ~/wiki-memory when omitted.
        mode: Lint mode such as structure, audit, reindex, or repair.
        input_data: Optional mode-specific payload; currently empty for supported lint modes.
        options: Optional controls such as max_items for audit reads.

    Returns:
        Lint, audit, reindex, or repair result for the selected mode.
    """
    input_data = input_data or {}
    options = options or {}
    service = LintService(resolve_root(root))
    if mode == "structure":
        return service.structure()
    if mode == "audit":
        return service.audit(max_items=options.get("max_items", 100))
    if mode == "reindex":
        return service.reindex()
    if mode == "repair":
        return service.repair()
    raise ValueError(f"Unsupported lint mode: {mode}")


def wiki_dream(root: str | Path | None, mode: str, input_data: dict | None = None, options: dict | None = None) -> dict:
    """Dispatch wiki_dream MCP calls for memory consolidation workflows.

    Args:
        root: Optional wiki-memory root directory; defaults to ~/wiki-memory when omitted.
        mode: Dream mode such as promote_candidates, merge_duplicates, decay_stale, cycle, or report.
        input_data: Optional mode-specific thresholds or reference timestamps.
        options: Optional execution flags reserved for future dream behavior.

    Returns:
        Dream report or mutation result for the selected consolidation mode.
    """
    input_data = input_data or {}
    options = options or {}
    service = DreamService(resolve_root(root))
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
    raise ValueError(f"Unsupported dream mode: {mode}")
