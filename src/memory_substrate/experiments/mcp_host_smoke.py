from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOL_NAMES = ["memory_ingest", "memory_maintain", "memory_query", "memory_remember"]
EXPECTED_RESOURCE_URIS = ["memory://policy", "memory://agent-playbook", "memory://mcp-api-summary"]


def run_mcp_host_smoke(
    root: str | Path,
    *,
    command: str | None = None,
    args: Sequence[str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run a real MCP stdio host smoke against a temporary or local memory root.

    The helper intentionally talks to the server through the MCP client protocol
    instead of direct function dispatch. It verifies host-facing behavior: server
    startup, initialization, tool/resource discovery, root binding through the
    environment, and representative tool calls without passing a root argument.
    """
    return asyncio.run(
        run_mcp_host_smoke_async(
            root=root,
            command=command,
            args=args,
            cwd=cwd,
            env=env,
        )
    )


async def run_mcp_host_smoke_async(
    root: str | Path,
    *,
    command: str | None = None,
    args: Sequence[str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root_path = Path(root).expanduser()
    root_path.mkdir(parents=True, exist_ok=True)

    server_command = command or sys.executable
    server_args = list(args) if args is not None else ["-m", "memory_substrate.interfaces.mcp.server"]
    process_env = dict(os.environ)
    if env:
        process_env.update(env)
    process_env["MEMORY_SUBSTRATE_ROOT"] = str(root_path)

    params = StdioServerParameters(
        command=server_command,
        args=server_args,
        cwd=str(cwd) if cwd is not None else None,
        env=process_env,
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tool_names = sorted(tool.name for tool in tools_result.tools)

                resources_result = await session.list_resources()
                resource_uris = sorted(str(resource.uri) for resource in resources_result.resources)
                policy = await session.read_resource("memory://policy")
                policy_text = _resource_text(policy)

                recent = _tool_json(
                    await session.call_tool(
                        "memory_query",
                        {"args": {"mode": "recent", "input_data": {}, "options": {"max_items": 3}}},
                    )
                )
                configure = _tool_json(
                    await session.call_tool(
                        "memory_maintain",
                        {
                            "args": {
                                "mode": "configure",
                                "input_data": {"graph_backend": "file"},
                                "options": {"apply": True},
                            }
                        },
                    )
                )
                structure = _tool_json(
                    await session.call_tool(
                        "memory_maintain",
                        {"args": {"mode": "structure", "input_data": {}}},
                    )
                )

    root_config_exists = (root_path / "memory" / "config.json").exists()
    observed = {
        "recent_result_type": recent.get("result_type"),
        "configure_result_type": configure.get("result_type"),
        "structure_result_type": structure.get("result_type"),
        "structure_error_count": structure.get("data", {}).get("counts", {}).get("error"),
        "policy_mentions_memory_substrate": "Memory Substrate" in policy_text,
    }
    checks = [
        _check("expected_tool_names", EXPECTED_TOOL_NAMES, tool_names),
        _check_resource_subset("expected_resource_uris", EXPECTED_RESOURCE_URIS, resource_uris),
        _check("policy_resource_readable", True, observed["policy_mentions_memory_substrate"]),
        _check("recent_tool_call_succeeds", "recent", observed["recent_result_type"]),
        _check("configure_tool_call_succeeds", "maintain_configure_result", observed["configure_result_type"]),
        _check("structure_tool_call_succeeds", "structure_report", observed["structure_result_type"]),
        _check("structure_has_no_errors", 0, observed["structure_error_count"]),
        _check("env_root_was_used", True, root_config_exists),
    ]
    failed_checks = [check for check in checks if not check["passed"]]
    return {
        "status": "completed" if not failed_checks else "failed",
        "tool_names": tool_names,
        "resource_uris": resource_uris,
        "root": str(root_path),
        "root_config_exists": root_config_exists,
        "observed": observed,
        "checks": checks,
        "failed_checks": failed_checks,
        "next_actions": (
            ["mcp_host_smoke_passed"]
            if not failed_checks
            else ["inspect_failed_checks", "inspect_stdio_server_command", "inspect_memory_root_binding"]
        ),
    }


def _tool_json(result) -> dict[str, Any]:
    if result.isError:
        return {"is_error": True, "content": [content.model_dump() for content in result.content]}
    if not result.content:
        return {}
    text = getattr(result.content[0], "text", "")
    return json.loads(text)


def _resource_text(result) -> str:
    return "\n".join(getattr(content, "text", "") for content in result.contents)


def _check(name: str, expected, actual) -> dict[str, Any]:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def _check_resource_subset(name: str, expected: list[str], actual: list[str]) -> dict[str, Any]:
    missing = [uri for uri in expected if uri not in actual]
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "missing": missing,
        "passed": not missing,
    }
