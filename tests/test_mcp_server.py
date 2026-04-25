from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wiki_memory.interfaces.mcp.server import create_server, main


class McpServerTest(unittest.TestCase):
    def test_create_server_registers_exactly_five_tools(self) -> None:
        server = create_server()
        tool_names = sorted(tool.name for tool in server._tool_manager.list_tools())

        self.assertEqual(
            tool_names,
            ["wiki_crystallize", "wiki_dream", "wiki_ingest", "wiki_lint", "wiki_query"],
        )

        query_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "wiki_query")
        args_schema = query_tool.parameters["properties"]["args"]
        self.assertEqual(args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(args_schema["discriminator"]["mapping"].keys()),
            {"context", "expand", "page", "recent", "search"},
        )

        crystallize_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "wiki_crystallize")
        crystallize_args_schema = crystallize_tool.parameters["properties"]["args"]
        self.assertEqual(crystallize_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(crystallize_args_schema["discriminator"]["mapping"].keys()),
            {"activity", "knowledge", "work_item", "promote", "supersede"},
        )

        dream_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "wiki_dream")
        dream_args_schema = dream_tool.parameters["properties"]["args"]
        self.assertEqual(dream_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(dream_args_schema["discriminator"]["mapping"].keys()),
            {"promote_candidates", "merge_duplicates", "decay_stale", "cycle", "report"},
        )

        lint_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "wiki_lint")
        lint_args_schema = lint_tool.parameters["properties"]["args"]
        self.assertEqual(lint_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(lint_args_schema["discriminator"]["mapping"].keys()),
            {"structure", "audit", "reindex", "repair"},
        )

        ingest_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "wiki_ingest")
        ingest_args_schema = ingest_tool.parameters["properties"]["args"]
        self.assertEqual(ingest_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(ingest_args_schema["discriminator"]["mapping"].keys()),
            {"repo", "file", "markdown"},
        )

    def test_main_runs_server(self) -> None:
        with patch("wiki_memory.interfaces.mcp.server.create_server") as create:
            server = create.return_value

            main()

            create.assert_called_once_with()
            server.run.assert_called_once_with()

    def test_server_smoke_lists_tools_and_calls_tool(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            tools = await server.list_tools()
            self.assertEqual(
                sorted(tool.name for tool in tools),
                ["wiki_crystallize", "wiki_dream", "wiki_ingest", "wiki_lint", "wiki_query"],
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                lint_result = await server.call_tool(
                    "wiki_lint",
                    {"args": {"root": tmpdir, "mode": "structure", "input_data": {}}},
                )
                lint_payload = json.loads(lint_result[0].text)
                self.assertEqual(lint_payload["result_type"], "lint_report")
                self.assertEqual(lint_payload["data"]["counts"]["warning"], 0)
                self.assertEqual(lint_payload["data"]["counts"]["error"], 0)

                query_result = await server.call_tool(
                    "wiki_query",
                    {"args": {"root": tmpdir, "mode": "recent", "input_data": {}, "options": {"max_items": 5}}},
                )
                query_payload = json.loads(query_result[0].text)
                self.assertEqual(query_payload["result_type"], "recent")
                self.assertEqual(query_payload["data"]["items"], [])

        asyncio.run(run_smoke())

    def test_server_smoke_uses_default_root_when_omitted(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with patch("wiki_memory.interfaces.mcp.tools.Path.home", return_value=Path("/tmp/fake-home")):
                query_result = await server.call_tool(
                    "wiki_query",
                    {"args": {"mode": "recent", "input_data": {}, "options": {"max_items": 5}}},
                )
            query_payload = json.loads(query_result[0].text)
            self.assertEqual(query_payload["result_type"], "recent")
            self.assertEqual(query_payload["data"]["items"], [])

        asyncio.run(run_smoke())

    def test_server_converts_mode_specific_input_models_before_dispatch(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with tempfile.TemporaryDirectory() as tmpdir:
                note = Path(tmpdir) / "note.md"
                note.write_text("# Note\n\nUseful context.\n", encoding="utf-8")
                ingest_result = await server.call_tool(
                    "wiki_ingest",
                    {"args": {"root": tmpdir, "mode": "markdown", "input_data": {"path": str(note)}}},
                )
                ingest_payload = json.loads(ingest_result[0].text)
                self.assertEqual(ingest_payload["segment_count"], 1)

                query_result = await server.call_tool(
                    "wiki_query",
                    {"args": {"root": tmpdir, "mode": "search", "input_data": {"query": "missing"}}},
                )
                query_payload = json.loads(query_result[0].text)
                self.assertEqual(query_payload["result_type"], "search_results")
                self.assertEqual(query_payload["data"]["items"], [])

                dream_result = await server.call_tool(
                    "wiki_dream",
                    {
                        "args": {
                            "root": tmpdir,
                            "mode": "promote_candidates",
                            "input_data": {"min_confidence": 0.8, "min_evidence": 2},
                        }
                    },
                )
                dream_payload = json.loads(dream_result[0].text)
                self.assertEqual(dream_payload["status"], "noop")
                self.assertEqual(dream_payload["promoted"], 0)

        asyncio.run(run_smoke())

    def test_server_rejects_missing_input_data(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "input_data"):
                await server.call_tool(
                    "wiki_query",
                    {"args": {"mode": "recent", "options": {"max_items": 5}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_extra_fields_in_args(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "wiki_query",
                    {"args": {"mode": "recent", "input_data": {}, "options": {"max_items": 5}, "legacy": 1}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_query_mode_specific_missing_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "query"):
                await server.call_tool(
                    "wiki_query",
                    {"args": {"mode": "search", "input_data": {}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_crystallize_mode_specific_missing_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "knowledge_id"):
                await server.call_tool(
                    "wiki_crystallize",
                    {"args": {"mode": "promote", "input_data": {}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_dream_mode_specific_extra_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "wiki_dream",
                    {"args": {"mode": "merge_duplicates", "input_data": {"legacy": 1}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_lint_mode_specific_extra_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "wiki_lint",
                    {"args": {"mode": "repair", "input_data": {"legacy": 1}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_ingest_mode_specific_missing_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "path"):
                await server.call_tool(
                    "wiki_ingest",
                    {"args": {"mode": "repo", "input_data": {}}},
                )

        asyncio.run(run_smoke())


if __name__ == "__main__":
    unittest.main()
