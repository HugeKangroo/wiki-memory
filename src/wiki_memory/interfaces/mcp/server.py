from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from wiki_memory.interfaces.mcp.models import CrystallizeToolArgs, DreamToolArgs, IngestToolArgs, LintToolArgs, QueryToolArgs
from wiki_memory.interfaces.mcp.tools import (
    wiki_crystallize as dispatch_crystallize,
    wiki_dream as dispatch_dream,
    wiki_ingest as dispatch_ingest,
    wiki_lint as dispatch_lint,
    wiki_query as dispatch_query,
)


SERVER_INSTRUCTIONS = (
    "Wiki Memory MCP server for ingesting repositories, querying accumulated context, "
    "crystallizing reusable outputs, linting structural integrity, and running dream "
    "consolidation workflows."
)


def _model_to_dict(value) -> dict:
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value


def create_server() -> FastMCP:
    mcp = FastMCP(name="wiki-memory", instructions=SERVER_INSTRUCTIONS)

    @mcp.tool(name="wiki_ingest", description="Ingest content into the wiki memory semantic store.")
    def wiki_ingest(args: IngestToolArgs) -> dict:
        return dispatch_ingest(args.root, args.mode, _model_to_dict(args.input_data), args.options)

    @mcp.tool(name="wiki_query", description="Query context, pages, recent items, and search results from wiki memory.")
    def wiki_query(args: QueryToolArgs) -> dict:
        return dispatch_query(args.root, args.mode, _model_to_dict(args.input_data), args.options)

    @mcp.tool(name="wiki_crystallize", description="Write activities, knowledge, and work items back into wiki memory.")
    def wiki_crystallize(args: CrystallizeToolArgs) -> dict:
        return dispatch_crystallize(args.root, args.mode, _model_to_dict(args.input_data), args.options)

    @mcp.tool(name="wiki_lint", description="Inspect and repair wiki memory structural health.")
    def wiki_lint(args: LintToolArgs) -> dict:
        return dispatch_lint(args.root, args.mode, _model_to_dict(args.input_data), args.options)

    @mcp.tool(name="wiki_dream", description="Run knowledge consolidation workflows across accumulated wiki memory.")
    def wiki_dream(args: DreamToolArgs) -> dict:
        return dispatch_dream(args.root, args.mode, _model_to_dict(args.input_data), args.options)

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
