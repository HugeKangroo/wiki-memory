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
            {"context", "expand", "page", "recent", "search", "graph", "source_slice"},
        )

        remember_tool = next(tool for tool in server._tool_manager.list_tools() if tool.name == "memory_remember")
        remember_args_schema = remember_tool.parameters["properties"]["args"]
        self.assertEqual(remember_args_schema["discriminator"]["propertyName"], "mode")
        self.assertEqual(
            set(remember_args_schema["discriminator"]["mapping"].keys()),
            {"activity", "knowledge", "work_item", "work_item_status", "promote", "supersede", "contest", "batch"},
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
                "render_projection",
                "reconcile_projection",
                "promote_candidates",
                "merge_duplicates",
                "resolve_duplicates",
                "archive_knowledge",
                "archive_source",
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
        self.assertIn("persistent agent memory", server.instructions)
        self.assertIn("deferred", server.instructions)
        self.assertIn("tool search", server.instructions)
        self.assertIn("memory-substrate", server.instructions)
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
        self.assertIn("persistent agent memory", descriptions["memory_query"])
        self.assertIn("context packs", descriptions["memory_query"])
        self.assertIn("Use at task start", descriptions["memory_query"])
        self.assertIn("before durable writes", descriptions["memory_query"])
        self.assertIn("evidence", descriptions["memory_ingest"])
        self.assertIn("persistent agent memory", descriptions["memory_remember"])
        self.assertIn("projection", descriptions["memory_maintain"])
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
            self.assertIn("Tool Discovery", playbook[0].content)
            self.assertIn("tool search", playbook[0].content)
            self.assertIn("memory-substrate", playbook[0].content)
            self.assertIn("api_inventory", playbook[0].content)
            self.assertIn("source_slice", playbook[0].content)
            self.assertIn("input_data.ids", playbook[0].content)
            self.assertIn("declaration_source_created", playbook[0].content)
            self.assertIn("archive_knowledge", playbook[0].content)
            self.assertIn("include_temporary", playbook[0].content)
            self.assertIn("render_projection", playbook[0].content)
            self.assertIn("reconcile_projection", playbook[0].content)
            self.assertIn("query expansion", playbook[0].content)
            self.assertIn("possible_duplicates", playbook[0].content)
            self.assertIn('status: "completed_with_pending_decisions"', playbook[0].content)
            self.assertIn('status: "noop"', playbook[0].content)

            api_summary = await server.read_resource("memory://mcp-api-summary")
            self.assertIn("Repo ingest statuses", api_summary[0].content)
            self.assertIn("completed_with_pending_decisions", api_summary[0].content)
            self.assertIn("noop", api_summary[0].content)
            self.assertIn("source_slice", api_summary[0].content)
            self.assertIn("API inventory", api_summary[0].content)
            self.assertIn("expanded_context_many", api_summary[0].content)
            self.assertIn("evidence_contract", api_summary[0].content)
            self.assertIn("Temporary memory", api_summary[0].content)
            self.assertIn("wiki_projection.path", api_summary[0].content)
            self.assertIn("render_projection", api_summary[0].content)

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
        self.assertIn("source_text", remember_defs["RememberKnowledgeInput"]["properties"])
        self.assertIn("source_title", remember_defs["RememberKnowledgeInput"]["properties"])
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
        self.assertEqual(
            set(remember_defs["RememberWorkItemStatusInput"]["required"]),
            {"work_item_id", "status", "reason", "memory_source"},
        )

        query_defs = tools["memory_query"].parameters["$defs"]
        self.assertIn("QuerySearchOptions", query_defs)
        self.assertIn("QueryPageOptions", query_defs)
        self.assertIn("QueryExpandOptions", query_defs)
        self.assertIn("QuerySourceSliceInput", query_defs)
        self.assertIn("QuerySourceSliceOptions", query_defs)
        self.assertIn("QueryFilters", query_defs)
        expand_input = query_defs["QueryExpandInput"]["properties"]
        self.assertIn("id", expand_input)
        self.assertIn("ids", expand_input)
        expand_options = query_defs["QueryExpandOptions"]["properties"]
        self.assertIn("per_id_max_items", expand_options)
        recent_args = query_defs["QueryRecentArgs"]
        self.assertEqual(
            recent_args["properties"]["options"]["anyOf"][0]["$ref"],
            "#/$defs/QueryRecentOptions",
        )
        search_options = query_defs["QuerySearchOptions"]["properties"]
        self.assertNotIn("detail", search_options)
        page_options = query_defs["QueryPageOptions"]["properties"]
        self.assertIn("detail", page_options)
        self.assertIn("include_segments", page_options)

        maintain_defs = tools["memory_maintain"].parameters["$defs"]
        configure_input = maintain_defs["MaintainConfigureInput"]["properties"]
        self.assertIn("wiki_projection", configure_input)
        self.assertIn("MaintainRenderProjectionArgs", maintain_defs)
        self.assertIn("MaintainReconcileProjectionArgs", maintain_defs)

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

    def test_query_rejects_mode_invalid_options(self) -> None:
        async def run_smoke() -> None:
            server = create_server()
            with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
                await server.call_tool(
                    "memory_query",
                    {
                        "args": {
                            "mode": "search",
                            "input_data": {"query": "memory"},
                            "options": {"detail": "full"},
                        }
                    },
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

    def test_server_runs_repo_ingest_remember_query_workflow(self) -> None:
        async def run_workflow() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                server = create_server(root=tmpdir)
                repo = Path(tmpdir) / "workflow-repo"
                src = repo / "src"
                codex_state = repo / ".codex"
                src.mkdir(parents=True)
                codex_state.mkdir()
                (repo / "README.md").write_text("# Workflow Repo\n\nMCP workflow marker.\n", encoding="utf-8")
                (src / "workflow.py").write_text("def marker():\n    return 'mcp-workflow'\n", encoding="utf-8")
                (codex_state / "session.json").write_text("{}", encoding="utf-8")

                initial_query = await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "search", "input_data": {"query": "mcp workflow marker"}}},
                )
                initial_payload = json.loads(initial_query[0].text)
                self.assertEqual(initial_payload["data"]["items"], [])

                pending_ingest = await server.call_tool(
                    "memory_ingest",
                    {"args": {"mode": "repo", "input_data": {"path": str(repo)}}},
                )
                pending_payload = json.loads(pending_ingest[0].text)
                self.assertEqual(pending_payload["status"], "completed_with_pending_decisions")
                self.assertGreater(pending_payload["applied_operations"], 0)
                self.assertEqual(pending_payload["suggested_exclude_patterns"], [".codex"])
                self.assertEqual(pending_payload["excluded_by_preflight"], [".codex"])
                self.assertEqual(pending_payload["pending_decisions"][0]["path"], ".codex")

                noop_ingest = await server.call_tool(
                    "memory_ingest",
                    {
                        "args": {
                            "mode": "repo",
                            "input_data": {
                                "path": str(repo),
                                "exclude_patterns": pending_payload["suggested_exclude_patterns"],
                            },
                        }
                    },
                )
                noop_payload = json.loads(noop_ingest[0].text)
                self.assertEqual(noop_payload["status"], "noop")
                self.assertEqual(noop_payload["applied_operations"], 0)

                repeated_pending_ingest = await server.call_tool(
                    "memory_ingest",
                    {"args": {"mode": "repo", "input_data": {"path": str(repo)}}},
                )
                repeated_pending_payload = json.loads(repeated_pending_ingest[0].text)
                self.assertEqual(repeated_pending_payload["status"], "noop")
                self.assertEqual(repeated_pending_payload["pending_decisions"][0]["path"], ".codex")

                page = await server.call_tool(
                    "memory_query",
                    {
                        "args": {
                            "mode": "page",
                            "input_data": {"id": pending_payload["source_id"]},
                            "options": {"include_segments": True},
                        }
                    },
                )
                page_payload = json.loads(page[0].text)
                source = page_payload["data"]["object"]
                self.assertNotIn(".codex", source["payload"]["top_level_entries"])
                evidence = source["segments"][0]

                remembered = await server.call_tool(
                    "memory_remember",
                    {
                        "args": {
                            "mode": "knowledge",
                            "input_data": {
                                "kind": "fact",
                                "title": "Workflow repo exposes an MCP workflow marker",
                                "summary": "The workflow repo README and source mention an MCP workflow marker.",
                                "reason": "This durable fact verifies the query-ingest-remember-query MCP workflow.",
                                "memory_source": "user_declared",
                                "scope_refs": ["scope:mcp-workflow-test"],
                                "status": "active",
                                "confidence": 1.0,
                                "subject_refs": [pending_payload["node_ids"][0]],
                                "evidence_refs": [
                                    {
                                        "source_id": pending_payload["source_id"],
                                        "segment_id": evidence["segment_id"],
                                    }
                                ],
                                "payload": {
                                    "subject": pending_payload["node_ids"][0],
                                    "predicate": "workflow_marker",
                                    "value": "mcp-workflow",
                                    "object": None,
                                    "metadata": {},
                                },
                            },
                        }
                    },
                )
                remembered_payload = json.loads(remembered[0].text)
                self.assertTrue(remembered_payload["knowledge_id"].startswith("know:"))
                self.assertEqual(remembered_payload["possible_duplicates"], [])

                final_query = await server.call_tool(
                    "memory_query",
                    {"args": {"mode": "search", "input_data": {"query": "workflow marker"}}},
                )
                final_payload = json.loads(final_query[0].text)
                item_ids = {item["id"] for item in final_payload["data"]["items"]}
                self.assertIn(remembered_payload["knowledge_id"], item_ids)

        asyncio.run(run_workflow())

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

    def test_server_updates_work_item_status(self) -> None:
        async def run_smoke() -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                server = create_server(root=tmpdir)
                created = await server.call_tool(
                    "memory_remember",
                    {
                        "args": {
                            "mode": "work_item",
                            "input_data": {
                                "kind": "task",
                                "title": "Clone Isaac Sim",
                                "summary": "Clone the official Isaac Sim repository.",
                                "reason": "The task should persist until resolved.",
                                "memory_source": "user_declared",
                                "scope_refs": ["project:digital-twin"],
                            },
                        }
                    },
                )
                created_payload = json.loads(created[0].text)

                updated = await server.call_tool(
                    "memory_remember",
                    {
                        "args": {
                            "mode": "work_item_status",
                            "input_data": {
                                "work_item_id": created_payload["work_item_id"],
                                "status": "resolved",
                                "resolution": "The repository was cloned and verified.",
                                "reason": "The completed activity satisfies this task.",
                                "memory_source": "agent_inferred",
                            },
                        }
                    },
                )
                updated_payload = json.loads(updated[0].text)

                page = await server.call_tool(
                    "memory_query",
                    {
                        "args": {
                            "mode": "page",
                            "input_data": {"id": created_payload["work_item_id"]},
                            "options": {"detail": "full"},
                        }
                    },
                )
                page_payload = json.loads(page[0].text)

                self.assertEqual(updated_payload["status"], "resolved")
                self.assertEqual(page_payload["data"]["object"]["status"], "resolved")
                self.assertEqual(page_payload["data"]["object"]["resolution"], "The repository was cloned and verified.")

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
