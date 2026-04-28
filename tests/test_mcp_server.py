from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.interfaces.mcp.server import create_server, main


class McpServerTest(unittest.TestCase):
    def test_create_server_registers_exactly_four_tools(self) -> None:
        server = create_server()
        tool_names = sorted(tool.name for tool in server._tool_manager.list_tools())

        self.assertEqual(
            tool_names,
            ["memory_ingest", "memory_maintain", "memory_query", "memory_remember"],
        )

        query_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "memory_query")
        args_schema = query_tool.parameters["properties"]["args"]
        self.assertEqual(args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(args_schema["discriminator"]["mapping"].keys()),
            {"context", "expand", "page", "recent", "search", "graph"},
        )

        remember_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "memory_remember")
        remember_args_schema = remember_tool.parameters["properties"]["args"]
        self.assertEqual(remember_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(remember_args_schema["discriminator"]["mapping"].keys()),
            {"activity", "knowledge", "work_item", "promote", "supersede", "contest", "batch"},
        )

        maintain_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "memory_maintain")
        maintain_args_schema = maintain_tool.parameters["properties"]["args"]
        self.assertEqual(maintain_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(maintain_args_schema["discriminator"]["mapping"].keys()),
            {
                "configure",
                "structure",
                "audit",
                "reindex",
                "repair",
                "promote_candidates",
                "merge_duplicates",
                "decay_stale",
                "cycle",
                "report",
            },
        )

        ingest_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "memory_ingest")
        ingest_args_schema = ingest_tool.parameters["properties"]["args"]
        self.assertEqual(ingest_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(ingest_args_schema["discriminator"]["mapping"].keys()),
            {"repo", "file", "markdown", "web", "pdf", "conversation"},
        )

    def test_server_instructions_explain_agent_workflow_and_mutation_guard(self) -> None:
        server = create_server()
        self.assertIn("Recommended workflow", server.instructions)
        self.assertIn("Task start: use memory_query", server.instructions)
        self.assertIn("New evidence: use memory_ingest", server.instructions)
        self.assertIn("analyze evidence outside ingest", server.instructions)
        self.assertIn("memory_query before memory_remember", server.instructions)
        self.assertIn("reason, memory_source, and scope_refs", server.instructions)
        self.assertIn("Do not pass memory root paths", server.instructions)
        self.assertNotIn("memory_query before memory_ingest", server.instructions)
        self.assertIn("options.apply=true", server.instructions)

        descriptions = {tool.name: tool.description for tool in server._tool_manager.list_tools()}
        self.assertIn("Use at task start", descriptions["memory_query"])
        self.assertIn("before durable writes", descriptions["memory_query"])
        self.assertIn("requires options.apply=true", descriptions["memory_maintain"])

    def test_server_exposes_agent_policy_resources(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            resources = await server.list_resources()
            resource_uris = sorted(str(resource.uri) for resource in resources)

            self.assertEqual(
                resource_uris,
                ["memory://agent-playbook", "memory://mcp-api-summary", "memory://policy"],
            )

            policy = await server.read_resource("memory://policy")
            self.assertEqual(policy[0].mime_type, "text/markdown")
            self.assertIn("Structured Hard Governance", policy[0].content)
            self.assertIn("Unstructured Soft Governance", policy[0].content)
            self.assertIn("Query Policy", policy[0].content)

            playbook = await server.read_resource("memory://agent-playbook")
            self.assertIn("query expansion", playbook[0].content)
            self.assertIn("possible_duplicates", playbook[0].content)

        asyncio.run(run_smoke())

    def test_server_exposes_agent_workflow_prompts(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            prompts = await server.list_prompts()
            prompt_names = sorted(prompt.name for prompt in prompts)

            self.assertEqual(prompt_names, ["memory_review", "memory_task_start"])

            task_start = await server.get_prompt("memory_task_start", {"task": "查待办项"})
            self.assertIn("memory_query", task_start.messages[0].content.text)
            self.assertIn("query expansion", task_start.messages[0].content.text)

            review = await server.get_prompt("memory_review", {"outcome": "Kuzu remains local backend"})
            self.assertIn("memory_remember", review.messages[0].content.text)
            self.assertIn("possible_duplicates", review.messages[0].content.text)

        asyncio.run(run_smoke())

    def test_agent_facing_schema_uses_structured_nested_models(self) -> None:
        server = create_server()
        tools = {tool.name: tool for tool in server._tool_manager.list_tools()}

        remember_defs = tools["memory_remember"].parameters["$defs"]
        self.assertIn("EvidenceRef", remember_defs)
        self.assertIn("KnowledgePayload", remember_defs)
        self.assertIn("hash", remember_defs["EvidenceRef"]["properties"])
        self.assertEqual(
            remember_defs["RememberKnowledgeInput"]["properties"]["evidence_refs"]["items"]["$ref"],
            "#/$defs/EvidenceRef",
        )
        self.assertEqual(
            remember_defs["RememberKnowledgeInput"]["properties"]["payload"]["$ref"],
            "#/$defs/KnowledgePayload",
        )
        self.assertEqual(
            set(remember_defs["RememberKnowledgeInput"]["required"]),
            {
                "kind",
                "title",
                "summary",
                "reason",
                "memory_source",
                "scope_refs",
            },
        )
        self.assertNotIn("predicate", remember_defs["KnowledgePayload"].get("required", []))
        self.assertEqual(
            set(remember_defs["RememberActivityInput"]["required"]),
            {"kind", "title", "summary", "reason", "memory_source", "scope_refs"},
        )
        self.assertEqual(
            set(remember_defs["RememberWorkItemInput"]["required"]),
            {"kind", "title", "summary", "reason", "memory_source", "scope_refs"},
        )

        query_defs = tools["memory_query"].parameters["$defs"]
        self.assertIn("QueryOptions", query_defs)
        self.assertIn("QueryFilters", query_defs)
        recent_args = query_defs["QueryRecentArgs"]
        self.assertEqual(
            recent_args["properties"]["options"]["anyOf"][0]["$ref"],
            "#/$defs/QueryOptions",
        )

        ingest_defs = tools["memory_ingest"].parameters["$defs"]
        self.assertIn("ConversationMessage", ingest_defs)
        self.assertEqual(
            ingest_defs["IngestConversationInput"]["properties"]["messages"]["items"]["$ref"],
            "#/$defs/ConversationMessage",
        )

    def test_agent_facing_schema_does_not_expose_root_parameter(self) -> None:
        server = create_server()
        for tool in server._tool_manager.list_tools():
            for definition in tool.parameters.get("$defs", {}).values():
                properties = definition.get("properties", {})
                if "mode" not in properties:
                    continue
                self.assertNotIn("root", properties)

    def test_server_rejects_root_field_from_agent_calls(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "memory_query",
                    {"args": {"root": "/tmp/rogue-root", "mode": "recent", "input_data": {}}},
                )

        asyncio.run(run_smoke())

    def test_maintain_mutating_modes_require_explicit_apply_option(self) -> None:
        async def run_smoke() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                server = create_server(root=tmpdir)
                with self.assertRaisesRegex(Exception, "apply"):
                    await server.call_tool(
                        "memory_maintain",
                        {"args": {"mode": "merge_duplicates", "input_data": {}}},
                    )
                with self.assertRaisesRegex(Exception, "apply"):
                    await server.call_tool(
                        "memory_maintain",
                        {
                            "args": {
                                "mode": "configure",
                                "input_data": {"graph_backend": "file"},
                            }
                        },
                    )

                result = await server.call_tool(
                    "memory_maintain",
                    {
                        "args": {
                            "mode": "merge_duplicates",
                            "input_data": {},
                            "options": {"apply": True},
                        }
                    },
                )
                payload = json.loads(result[0].text)
                self.assertEqual(payload["status"], "noop")
                self.assertEqual(payload["merged"], 0)

        asyncio.run(run_smoke())

    def test_server_omits_unset_optional_model_fields_before_dispatch(self) -> None:
        async def run_smoke() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                server = create_server(root=tmpdir)
                recent_result = await server.call_tool(
                    "memory_query",
                    {
                        "args": {
                            "mode": "recent",
                            "input_data": {},
                            "options": {"filters": {"object_type": "knowledge"}},
                        }
                    },
                )
                recent_payload = json.loads(recent_result[0].text)
                self.assertEqual(recent_payload["result_type"], "recent")

                cycle_result = await server.call_tool(
                    "memory_maintain",
                    {
                        "args": {
                            "mode": "cycle",
                            "input_data": {"reference_time": "2026-04-24T00:00:00+00:00"},
                            "options": {"apply": True},
                        }
                    },
                )
                cycle_payload = json.loads(cycle_result[0].text)
                self.assertEqual(cycle_payload["status"], "completed")
                self.assertEqual(cycle_payload["promoted"], 0)

        asyncio.run(run_smoke())

    def test_main_runs_server(self) -> None:
        with patch("memory_substrate.interfaces.mcp.server.create_server") as create:
            server = create.return_value

            main()

            create.assert_called_once_with()
            server.run.assert_called_once_with()

    def test_server_smoke_lists_tools_and_calls_tool(self) -> None:
        async def run_smoke() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                server = create_server(root=tmpdir)
                tools = await server.list_tools()
                self.assertEqual(
                    sorted(tool.name for tool in tools),
                    ["memory_ingest", "memory_maintain", "memory_query", "memory_remember"],
                )

                structure_result = await server.call_tool(
                    "memory_maintain",
                    {"args": {"mode": "structure", "input_data": {}}},
                )
                structure_payload = json.loads(structure_result[0].text)
                self.assertEqual(structure_payload["result_type"], "structure_report")
                self.assertEqual(structure_payload["data"]["counts"]["warning"], 0)
                self.assertEqual(structure_payload["data"]["counts"]["error"], 0)

                query_result = await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "recent", "input_data": {}, "options": {"max_items": 5}}},
                )
                query_payload = json.loads(query_result[0].text)
                self.assertEqual(query_payload["result_type"], "recent")
                self.assertEqual(query_payload["data"]["items"], [])

        asyncio.run(run_smoke())

    def test_server_smoke_uses_default_root_when_omitted(self) -> None:
        async def run_smoke() -> None:
            with patch("memory_substrate.interfaces.mcp.tools.Path.home", return_value=Path("/tmp/fake-home")):
                server = create_server()
                query_result = await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "recent", "input_data": {}, "options": {"max_items": 5}}},
                )
            query_payload = json.loads(query_result[0].text)
            self.assertEqual(query_payload["result_type"], "recent")
            self.assertEqual(query_payload["data"]["items"], [])

        asyncio.run(run_smoke())

    def test_server_root_can_be_configured_from_environment(self) -> None:
        async def run_smoke() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.dict(os.environ, {"MEMORY_SUBSTRATE_ROOT": tmpdir}):
                    server = create_server()
                result = await server.call_tool(
                    "memory_maintain",
                    {
                        "args": {
                            "mode": "configure",
                            "input_data": {"graph_backend": "file"},
                            "options": {"apply": True},
                        }
                    },
                )
                payload = json.loads(result[0].text)
                self.assertEqual(payload["result_type"], "maintain_configure_result")
                self.assertTrue((Path(tmpdir) / "memory" / "config.json").exists())

        asyncio.run(run_smoke())

    def test_server_converts_mode_specific_input_models_before_dispatch(self) -> None:
        async def run_smoke() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                server = create_server(root=tmpdir)
                note = Path(tmpdir) / "note.md"
                note.write_text("# Note\n\nUseful context.\n", encoding="utf-8")
                ingest_result = await server.call_tool(
                    "memory_ingest",
                    {"args": {"mode": "markdown", "input_data": {"path": str(note)}}},
                )
                ingest_payload = json.loads(ingest_result[0].text)
                self.assertEqual(ingest_payload["segment_count"], 1)

                query_result = await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "search", "input_data": {"query": "missing"}}},
                )
                query_payload = json.loads(query_result[0].text)
                self.assertEqual(query_payload["result_type"], "search_results")
                self.assertEqual(query_payload["data"]["items"], [])

                maintain_result = await server.call_tool(
                    "memory_maintain",
                    {
                        "args": {
                            "mode": "promote_candidates",
                            "input_data": {"min_confidence": 0.8, "min_evidence": 2},
                            "options": {"apply": True},
                        }
                    },
                )
                maintain_payload = json.loads(maintain_result[0].text)
                self.assertEqual(maintain_payload["status"], "noop")
                self.assertEqual(maintain_payload["promoted"], 0)

        asyncio.run(run_smoke())

    def test_server_allows_unstructured_knowledge_payload_for_soft_duplicates(self) -> None:
        async def run_smoke() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                server = create_server(root=tmpdir)
                first_result = await server.call_tool(
                    "memory_remember",
                    {
                        "args": {
                            "mode": "knowledge",
                            "input_data": {
                                "kind": "decision",
                                "title": "Use Kuzu as the local graph backend",
                                "summary": "Kuzu is the selected local graph backend for lightweight prototypes.",
                                "reason": "This decision guides local backend work.",
                                "memory_source": "user_declared",
                                "scope_refs": ["scope:smoke"],
                                "status": "active",
                                "confidence": 1.0,
                            },
                        }
                    },
                )
                first_payload = json.loads(first_result[0].text)

                second_result = await server.call_tool(
                    "memory_remember",
                    {
                        "args": {
                            "mode": "knowledge",
                            "input_data": {
                                "kind": "decision",
                                "title": "Kuzu remains the local graph backend",
                                "summary": "The local prototype graph backend should stay on Kuzu.",
                                "reason": "This may duplicate an existing backend decision.",
                                "memory_source": "agent_inferred",
                                "scope_refs": ["scope:smoke"],
                                "payload": {},
                                "status": "candidate",
                                "confidence": 0.7,
                            },
                        }
                    },
                )
                second_payload = json.loads(second_result[0].text)

                self.assertEqual(second_payload["possible_duplicates"][0]["object_id"], first_payload["knowledge_id"])

        asyncio.run(run_smoke())

    def test_server_rejects_missing_input_data(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "input_data"):
                await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "recent", "options": {"max_items": 5}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_extra_fields_in_args(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "recent", "input_data": {}, "options": {"max_items": 5}, "legacy": 1}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_query_mode_specific_missing_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "query"):
                await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "search", "input_data": {}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_remember_mode_specific_missing_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "knowledge_id"):
                await server.call_tool(
                    "memory_remember",
                    {"args": {"mode": "promote", "input_data": {}}},
                )
            with self.assertRaisesRegex(Exception, "reason"):
                await server.call_tool(
                    "memory_remember",
                    {
                        "args": {
                            "mode": "knowledge",
                            "input_data": {
                                "kind": "fact",
                                "title": "Missing governance",
                                "summary": "This write should be rejected at the MCP boundary.",
                                "scope_refs": ["scope:test"],
                                "memory_source": "agent_inferred",
                                "payload": {"predicate": "missing_reason"},
                            },
                        }
                    },
                )

        asyncio.run(run_smoke())

    def test_server_rejects_maintain_lifecycle_mode_specific_extra_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "memory_maintain",
                    {"args": {"mode": "merge_duplicates", "input_data": {"legacy": 1}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_maintain_structure_mode_specific_extra_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "memory_maintain",
                    {"args": {"mode": "repair", "input_data": {"legacy": 1}}},
                )

        asyncio.run(run_smoke())

    def test_server_rejects_ingest_mode_specific_missing_fields(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "path"):
                await server.call_tool(
                    "memory_ingest",
                    {"args": {"mode": "repo", "input_data": {}}},
                )

        asyncio.run(run_smoke())


if __name__ == "__main__":
    unittest.main()
