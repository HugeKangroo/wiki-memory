from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from memory_substrate.interfaces.mcp.models import IngestToolArgs, MaintainToolArgs, QueryToolArgs, RememberToolArgs
from memory_substrate.interfaces.mcp.resources import register_agent_resources
from memory_substrate.interfaces.mcp.tools import (
    memory_ingest as dispatch_ingest,
    memory_maintain as dispatch_maintain,
    memory_query as dispatch_query,
    memory_remember as dispatch_remember,
    resolve_root,
)


SERVER_ROOT_ENV_VAR = "MEMORY_SUBSTRATE_ROOT"

SERVER_INSTRUCTIONS = (
    "Memory Substrate MCP server. Recommended workflow: Task start: use memory_query. "
    "New evidence: use memory_ingest, analyze evidence outside ingest, then use memory_remember only for durable writes "
    "with reason, memory_source, and scope_refs. Use memory_query before memory_remember to check context, "
    "duplicates, and conflicts. Do not pass memory root paths; the host fixes the server root. "
    "Use memory_maintain for configure/report/structure/reindex; mutating memory_maintain modes require "
    "options.apply=true."
)


def resolve_server_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return resolve_root(root)
    env_root = os.environ.get(SERVER_ROOT_ENV_VAR)
    if env_root:
        return resolve_root(env_root)
    return resolve_root(None)


def _model_to_dict(value) -> dict:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=True)
    return value


def create_server(root: str | Path | None = None) -> FastMCP:
    server_root = resolve_server_root(root)
    mcp = FastMCP(name="memory-substrate", instructions=SERVER_INSTRUCTIONS)
    register_agent_resources(mcp)

    @mcp.tool(name="memory_ingest", description="Capture files, repos, web pages, PDFs, or conversations as citable evidence before deciding what to remember.")
    def memory_ingest(args: IngestToolArgs) -> dict:
        return dispatch_ingest(server_root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    @mcp.tool(name="memory_query", description="Query existing memory. Use at task start and before durable writes when checking context, duplicates, or conflicts.")
    def memory_query(args: QueryToolArgs) -> dict:
        return dispatch_query(server_root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    @mcp.tool(name="memory_remember", description="Govern durable memory writes for activities, claims, and work items after evidence has been captured or verified.")
    def memory_remember(args: RememberToolArgs) -> dict:
        return dispatch_remember(server_root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    @mcp.tool(name="memory_maintain", description="Validate, report, repair, reindex, and consolidate memory. Any mutating mode requires options.apply=true.")
    def memory_maintain(args: MaintainToolArgs) -> dict:
        return dispatch_maintain(server_root, args.mode, _model_to_dict(args.input_data), _model_to_dict(args.options))

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
