from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from memory_substrate.interfaces.mcp.models import IngestToolArgs, MaintainToolArgs, QueryToolArgs, RememberToolArgs
from memory_substrate.interfaces.mcp.tools import (
    memory_ingest as dispatch_ingest,
    memory_maintain as dispatch_maintain,
    memory_query as dispatch_query,
    memory_remember as dispatch_remember,
)


SERVER_INSTRUCTIONS = (
    "Memory Substrate MCP server for capturing evidence, remembering durable knowledge, "
    "querying accumulated context, and maintaining memory lifecycle health.\n\n"
    "Recommended workflow: Task start: use memory_query to load existing context. "
    "New evidence: use memory_ingest to capture files, repos, web pages, PDFs, or conversations "
    "as citable evidence. Then analyze evidence outside ingest and call memory_remember only when "
    "the user or agent decides the extracted information should survive future sessions. "
    "Use memory_query before memory_remember to check related context, duplicates, and conflicts. "
    "Use memory_maintain configure to set root-level defaults such as graph_backend. "
    "Use memory_maintain report/structure for read-only checks before mutating maintenance. "
    "Mutating memory_maintain modes require options.apply=true."
)


def _model_to_dict(value) -> dict:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=True)
    return value


def create_server() -> FastMCP:
    mcp = FastMCP(name="memory-substrate", instructions=SERVER_INSTRUCTIONS)

    @mcp.tool(name="memory_ingest", description="Capture files, repos, web pages, PDFs, or conversations as citable evidence before deciding what to remember.")
    def memory_ingest(args: IngestToolArgs) -> dict:
        return dispatch_ingest(args.root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    @mcp.tool(name="memory_query", description="Query existing memory. Use at task start and before durable writes when checking context, duplicates, or conflicts.")
    def memory_query(args: QueryToolArgs) -> dict:
        return dispatch_query(args.root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    @mcp.tool(name="memory_remember", description="Govern durable memory writes for activities, claims, and work items after evidence has been captured or verified.")
    def memory_remember(args: RememberToolArgs) -> dict:
        return dispatch_remember(args.root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    @mcp.tool(name="memory_maintain", description="Validate, report, repair, reindex, and consolidate memory. Any mutating mode requires options.apply=true.")
    def memory_maintain(args: MaintainToolArgs) -> dict:
        return dispatch_maintain(args.root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
