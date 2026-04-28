from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.interfaces.mcp.server import create_server


@contextmanager
def temporary_env(updates: dict[str, str | None]) -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def run_demo(root: Path, offline: bool) -> dict:
    env = {"MEMORY_SUBSTRATE_ROOT": str(root)}
    if offline:
        env["HF_HUB_OFFLINE"] = "1"
    with temporary_env(env):
        server = create_server()

    root_rejection = await _check_root_rejection(server)
    configure = await server.call_tool(
        "memory_maintain",
        {
            "args": {
                "mode": "configure",
                "input_data": {"semantic_backend": "lancedb"},
                "options": {"apply": True},
            }
        },
    )
    remember = await server.call_tool(
        "memory_remember",
        {
            "args": {
                "mode": "knowledge",
                "input_data": {
                    "kind": "procedure",
                    "title": "MCP semantic demo without root args",
                    "summary": (
                        "Memory Substrate MCP binds the storage root through server configuration, "
                        "rejects root in agent tool calls, and retrieves this knowledge through "
                        "LanceDB semantic search."
                    ),
                    "reason": "Reusable smoke demo for root isolation and semantic retrieval.",
                    "memory_source": "agent_inferred",
                    "scope_refs": ["scope:mcp-semantic-demo"],
                    "status": "candidate",
                    "confidence": 0.8,
                },
            }
        },
    )
    reindex = await server.call_tool(
        "memory_maintain",
        {"args": {"mode": "reindex", "input_data": {}}},
    )
    search = await server.call_tool(
        "memory_query",
        {
            "args": {
                "mode": "search",
                "input_data": {"query": "server configured root semantic retrieval mcp demo"},
                "options": {"max_items": 5},
            }
        },
    )

    configure_payload = json.loads(configure[0].text)
    remember_payload = json.loads(remember[0].text)
    reindex_payload = json.loads(reindex[0].text)
    search_payload = json.loads(search[0].text)
    knowledge_id = remember_payload["knowledge_id"]
    match = next((item for item in search_payload["data"]["items"] if item["id"] == knowledge_id), None)

    assert root_rejection["rejected"] is True, root_rejection
    assert configure_payload["data"]["config"]["semantic"]["backend"] == "lancedb"
    assert reindex_payload["data"]["semantic_index"]["chunk_count"] >= 1
    assert match is not None, json.dumps(search_payload, ensure_ascii=False, indent=2)
    assert "semantic" in match.get("retrieval_sources", []), match

    return {
        "root": str(root),
        "offline": offline,
        "root_rejection": root_rejection,
        "knowledge_id": knowledge_id,
        "semantic_index": reindex_payload["data"].get("semantic_index"),
        "top_match": {
            "id": match["id"],
            "title": match["title"],
            "sources": match.get("retrieval_sources"),
            "semantic_score": match.get("semantic_score"),
        },
    }


async def _check_root_rejection(server) -> dict:
    try:
        await server.call_tool(
            "memory_query",
            {"args": {"root": "/tmp/rogue-memory-root", "mode": "recent", "input_data": {}}},
        )
    except Exception as exc:
        message = str(exc)
        return {"rejected": "Extra inputs are not permitted" in message, "message": message.splitlines()[0]}
    return {"rejected": False, "message": "root field was accepted"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real MCP semantic smoke demo.")
    parser.add_argument("--root", type=Path, default=None, help="Memory root to use. Defaults to a temporary directory.")
    parser.add_argument("--offline", action="store_true", help="Set HF_HUB_OFFLINE=1 for cached model loads.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.root is not None:
        args.root.mkdir(parents=True, exist_ok=True)
        result = asyncio.run(run_demo(args.root, args.offline))
    else:
        with tempfile.TemporaryDirectory() as directory:
            result = asyncio.run(run_demo(Path(directory), args.offline))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
