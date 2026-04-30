from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.remember.service import RememberService
from memory_substrate.application.ingest.service import IngestService
from memory_substrate.application.maintain.service import MaintainService
from memory_substrate.application.query.service import QueryService
from memory_substrate.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.infrastructure.storage.paths import StoragePaths


class Phase1AcceptanceTest(unittest.TestCase):
    def _make_repo(self, root: Path) -> Path:
        repo = root / "demo-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
        src_dir = repo / "src"
        src_dir.mkdir()
        (src_dir / "demo.py").write_text(
            "def hello(name: str) -> str:\n"
            "    return f'hello, {name}'\n",
            encoding="utf-8",
        )
        return repo

    def _make_typescript_repo(self, root: Path) -> Path:
        repo = root / "ts-repo"
        repo.mkdir()
        src_dir = repo / "src"
        src_dir.mkdir()
        (src_dir / "index.ts").write_text(
            "export function hello(name: string): string {\n"
            "  return `hello, ${name}`;\n"
            "}\n",
            encoding="utf-8",
        )
        return repo

    def test_phase1_repo_ingest_query_and_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            objects = FsObjectRepository(root)
            query = QueryService(root)
            paths = StoragePaths(root)

            self.assertIsNotNone(objects.get("source", result["source_id"]))
            self.assertTrue(result["node_ids"])
            self.assertTrue(result["knowledge_ids"])
            self.assertIsNotNone(objects.get("activity", result["activity_id"]))

            context = query.context(task="understand demo repo", max_items=6)
            self.assertEqual(context["result_type"], "context_pack")
            self.assertGreater(len(context["data"]["items"]), 0)
            self.assertFalse(context["data"]["missing_context"])

            expanded = query.expand(result["source_id"], max_items=6)
            self.assertEqual(expanded["result_type"], "expanded_context")
            self.assertGreater(len(expanded["data"]["items"]), 1)
            self.assertGreater(len(expanded["data"]["source_segments"]), 0)

            self.assertTrue((paths.patch_path(result["patch_id"])).exists())
            self.assertEqual(result["applied_operations"], len(result["audit_event_ids"]))
            self.assertTrue((paths.projections_root / "debug" / "index.md").exists())
            self.assertTrue((paths.projections_root / "debug" / "overview.md").exists())
            self.assertTrue(
                (paths.projections_root / "debug" / "sources" / f"{result['source_id']}.md").exists()
            )

    def test_repo_ingest_only_emits_lightweight_structural_candidate_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            objects = FsObjectRepository(root)

            knowledge_items = [objects.get("knowledge", knowledge_id) for knowledge_id in result["knowledge_ids"]]
            predicates = {
                item["payload"].get("predicate")
                for item in knowledge_items
                if item and isinstance(item.get("payload"), dict)
            }

            self.assertIn("source_roots", predicates)
            self.assertNotIn("primary_language", predicates)
            self.assertNotIn("module_summary", predicates)

    def test_repo_ingest_returns_advisory_concept_candidates_for_agent_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "concept-repo"
            repo.mkdir()
            (repo / "README.md").write_text(
                "# Concept Repo\n"
                "\n"
                "Context Pack is the working set that agents should load before implementation.\n"
                "\n"
                "## Context Pack\n"
                "\n"
                "The Context Pack contains decisions, procedures, evidence, and open work.\n",
                encoding="utf-8",
            )
            src = repo / "src"
            src.mkdir()
            (src / "main.py").write_text("def build_context_pack():\n    return {}\n", encoding="utf-8")

            result = IngestService(root).ingest_repo(repo)

            suggestions = result["memory_suggestions"]
            candidates = suggestions["concept_candidates"]
            self.assertIn("run_memory_maintain_report_for_cross_source_candidates", suggestions["next_actions"])
            self.assertIn("candidate_diagnostics", suggestions)
            self.assertIn("Context Pack", {candidate["title"] for candidate in candidates})
            self.assertNotIn("Concept Repo", {candidate["title"] for candidate in candidates})
            candidate = next(item for item in candidates if item["title"] == "Context Pack")
            self.assertEqual(candidate["candidate_type"], "concept")
            self.assertIn("ranking_signals", candidate)
            self.assertEqual(candidate["suggested_memory"]["kind"], "concept")
            self.assertIn("review_guidance", candidate)
            self.assertIn("remember_as_concept", {outcome["action"] for outcome in candidate["review_guidance"]["outcomes"]})
            self.assertIn("skip_candidate", {outcome["action"] for outcome in candidate["review_guidance"]["outcomes"]})
            self.assertTrue(candidate["evidence_refs"])
            suggested_input = candidate["suggested_memory"]["input_data"]
            self.assertEqual(suggested_input["kind"], "concept")
            self.assertEqual(suggested_input["title"], "Context Pack")
            self.assertEqual(suggested_input["status"], "candidate")
            self.assertEqual(suggested_input["memory_source"], "agent_inferred")
            self.assertIn(result["node_ids"][0], suggested_input["scope_refs"])
            self.assertEqual(suggested_input["evidence_refs"], candidate["evidence_refs"])
            self.assertIn("reviewed candidate", suggested_input["reason"])

    def test_ingest_returns_agent_extraction_protocol_for_durable_memory_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)

            result = IngestService(root).ingest_repo(repo)
            protocol = result["memory_suggestions"]["agent_extraction"]

            self.assertEqual(protocol["protocol"], "agent_extraction.v1")
            self.assertEqual(protocol["source_id"], result["source_id"])
            self.assertEqual(protocol["resource"], "memory://agent-playbook")
            self.assertEqual(
                protocol["summary"],
                "Ingest captured evidence; agent analyzes it and uses memory_remember for durable writes.",
            )
            self.assertEqual(
                protocol["required_steps"],
                ["inspect_source", "query_existing_memory", "prepare_durable_candidates", "commit_reviewed_memory"],
            )
            self.assertIn("call_memory_remember_if_durable", protocol["next_actions"])
            write_contract = protocol["remember_write_contract"]
            self.assertIn("reason", write_contract["required_fields"])
            self.assertIn("memory_source", write_contract["required_fields"])
            self.assertIn("scope_refs", write_contract["required_fields"])
            self.assertIn("evidence_refs", write_contract["recommended_fields"])

    def test_repo_ingest_labels_non_python_modules_by_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_typescript_repo(root)

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            objects = FsObjectRepository(root)
            nodes = [objects.get("node", node_id) for node_id in result["node_ids"]]

            module = next(item for item in nodes if item and item.get("aliases") == ["src/index.ts"])
            self.assertEqual(module["name"], "src.index")
            self.assertIn("TypeScript module", module["summary"])

    def test_repo_ingest_noops_when_repo_fingerprint_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)
            paths = StoragePaths(root)
            ingest = IngestService(root)
            objects = FsObjectRepository(root)
            audit = FsAuditRepository(root)

            first = ingest.ingest_repo(repo)
            first_source = objects.get("source", first["source_id"])
            first_patch_count = len(list(paths.patches_root.glob("*.json")))
            first_audit_count = len(audit.list())

            second = ingest.ingest_repo(repo)
            second_source = objects.get("source", first["source_id"])

            self.assertEqual(second["status"], "noop")
            self.assertEqual(second["applied_operations"], 0)
            self.assertIsNone(second["patch_id"])
            self.assertEqual(second["audit_event_ids"], [])
            self.assertEqual(second["projection_count"], 0)
            self.assertEqual(len(list(paths.patches_root.glob("*.json"))), first_patch_count)
            self.assertEqual(len(audit.list()), first_audit_count)
            self.assertEqual(second_source, first_source)

    def test_repo_ingest_rewrites_when_repo_fingerprint_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)
            ingest = IngestService(root)

            first = ingest.ingest_repo(repo)
            (repo / "src" / "extra.py").write_text("def extra():\n    return True\n", encoding="utf-8")
            second = ingest.ingest_repo(repo)

            self.assertEqual(first["status"], "completed")
            self.assertEqual(second["status"], "completed")
            self.assertGreater(second["applied_operations"], 0)

    def test_repo_ingest_skips_rust_target_build_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "tauri-repo"
            repo.mkdir()
            (repo / ".codex").write_text("", encoding="utf-8")
            (repo / ".worktrees").mkdir()
            app_src = repo / "src"
            app_src.mkdir()
            (app_src / "App.tsx").write_text("export function App() { return null; }\n", encoding="utf-8")
            target = repo / "src-tauri" / "target" / "debug"
            target.mkdir(parents=True)
            (target / "generated.ts").write_text("export const generated = true;\n", encoding="utf-8")

            result = IngestService(root).ingest_repo(repo, exclude_patterns=[".codex", ".worktrees"])
            source = FsObjectRepository(root).get("source", result["source_id"])

            self.assertIsNotNone(source)
            self.assertNotIn(".codex", source["payload"]["top_level_entries"])
            self.assertNotIn(".worktrees", source["payload"]["top_level_entries"])
            self.assertIn("src/App.tsx", source["payload"]["code_files"])
            self.assertNotIn("src-tauri/target/debug/generated.ts", source["payload"]["code_files"])

    def test_repo_ingest_writes_clean_view_and_returns_pending_agent_local_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "agent-state-repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Agent State Repo\n", encoding="utf-8")
            (repo / ".codex").mkdir()
            (repo / ".codex" / "session.json").write_text("{}", encoding="utf-8")
            (repo / ".worktrees").mkdir()
            (repo / ".worktrees" / "scratch.txt").write_text("temporary worktree state\n", encoding="utf-8")

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            source = FsObjectRepository(root).get("source", result["source_id"])

            self.assertEqual(result["status"], "completed_with_pending_decisions")
            self.assertTrue(result["requires_decision"])
            self.assertGreater(result["applied_operations"], 0)
            self.assertIsNotNone(source)
            self.assertNotIn(".codex", source["payload"]["top_level_entries"])
            self.assertNotIn(".worktrees", source["payload"]["top_level_entries"])
            self.assertEqual(result["excluded_by_preflight"], [".codex", ".worktrees"])
            self.assertIn(".codex", result["suggested_exclude_patterns"])
            self.assertIn(".worktrees", result["suggested_exclude_patterns"])
            self.assertEqual(
                [item["path"] for item in result["pending_decisions"]],
                [".codex", ".worktrees"],
            )
            self.assertTrue(result["warnings"])
            self.assertIn("local/agent state", result["warnings"][0])
            self.assertEqual(
                source["metadata"]["repo_ingest"]["excluded_by_preflight"],
                [".codex", ".worktrees"],
            )

            filtered = ingest.ingest_repo(repo, exclude_patterns=[".worktrees", ".codex"])

            self.assertEqual(filtered["status"], "noop")
            self.assertFalse(filtered["requires_decision"])
            self.assertEqual(filtered["pending_decisions"], [])
            self.assertEqual(filtered["excluded_by_preflight"], [])
            self.assertEqual(filtered["suggested_exclude_patterns"], [])
            self.assertEqual(filtered["warnings"], [])
            self.assertTrue(FsObjectRepository(root).get("source", filtered["source_id"]))

    def test_repo_ingest_records_adapter_metadata_and_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)

            result = IngestService(root).ingest_repo(repo)
            source = FsObjectRepository(root).get("source", result["source_id"])
            adapter = source["metadata"]["adapter"]
            freshness = source["metadata"]["freshness"]

            self.assertEqual(adapter["name"], "repo")
            self.assertEqual(adapter["version"], "repo-adapter.v1")
            self.assertEqual(adapter["mode"], "repo")
            self.assertEqual(adapter["default_privacy_class"], "local_repo")
            self.assertEqual(adapter["origin_classification"], "local_repo")
            self.assertIn("repo_map", adapter["declared_transformations"])
            self.assertIn("document_sections", adapter["declared_transformations"])
            self.assertTrue(freshness["is_current"])
            self.assertEqual(freshness["fingerprint"], source["fingerprint"])

    def test_repo_ingest_can_force_include_agent_local_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "forced-agent-state-repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Forced Agent State Repo\n", encoding="utf-8")
            (repo / ".codex").mkdir()
            (repo / ".codex" / "session.json").write_text("{}", encoding="utf-8")

            result = IngestService(root).ingest_repo(repo, force=True)
            source = FsObjectRepository(root).get("source", result["source_id"])

            self.assertEqual(result["status"], "completed")
            self.assertFalse(result["requires_decision"])
            self.assertIn(".codex", result["suggested_exclude_patterns"])
            self.assertTrue(result["warnings"])
            self.assertIn(".codex", source["payload"]["top_level_entries"])

    def test_repo_ingest_captures_python_class_methods_as_code_interfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "method-repo"
            repo.mkdir()
            src = repo / "src"
            src.mkdir()
            (src / "service.py").write_text(
                "class Service:\n"
                "    def run(self):\n"
                "        return True\n",
                encoding="utf-8",
            )

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            objects = FsObjectRepository(root)

            source = objects.get("source", result["source_id"])
            module = next(item for item in source["payload"]["python_modules"] if item["path"] == "src/service.py")
            self.assertIn("Service", module["classes"])
            self.assertIn("Service.run", module["functions"])

    def test_repo_ingest_prioritizes_interface_modules_before_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "priority-repo"
            repo.mkdir()
            app = repo / "src" / "pkg" / "application"
            interface = repo / "src" / "pkg" / "interfaces" / "mcp"
            tests = repo / "tests"
            app.mkdir(parents=True)
            interface.mkdir(parents=True)
            tests.mkdir()
            for index in range(25):
                (tests / f"test_{index}.py").write_text(f"def test_{index}():\n    return None\n", encoding="utf-8")
            (app / "service.py").write_text("def run():\n    return True\n", encoding="utf-8")
            (interface / "tools.py").write_text("def memory_query():\n    return {}\n", encoding="utf-8")

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            objects = FsObjectRepository(root)

            source = objects.get("source", result["source_id"])
            module_paths = [module["path"] for module in source["payload"]["python_modules"]]
            self.assertIn("src/pkg/application/service.py", module_paths)
            self.assertIn("src/pkg/interfaces/mcp/tools.py", module_paths)
            self.assertLess(
                module_paths.index("src/pkg/interfaces/mcp/tools.py"),
                next((idx for idx, path in enumerate(module_paths) if path.startswith("tests/")), len(module_paths)),
            )

    def test_repo_ingest_captures_code_file_segments_for_query_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            objects = FsObjectRepository(root)

            source = objects.get("source", result["source_id"])
            segment_by_path = {
                segment["locator"].get("path"): segment
                for segment in source["segments"]
                if isinstance(segment.get("locator"), dict)
            }

            self.assertIn("src/demo.py", source["payload"]["code_files"])
            self.assertIn("src/demo.py", segment_by_path)
            self.assertIn("def hello", segment_by_path["src/demo.py"]["excerpt"])

            search = QueryService(root).search("def hello", max_items=5)
            self.assertTrue(any(item["id"] == result["source_id"] for item in search["data"]["items"]))

    def test_file_ingest_creates_document_source_node_activity_and_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            document = root / "notes.txt"
            document.write_text(
                "Alpha decision\n\n"
                "This note captures the first reusable finding.\n\n"
                "Beta follow up\n",
                encoding="utf-8",
            )

            ingest = IngestService(root)
            result = ingest.ingest_file(document)
            objects = FsObjectRepository(root)
            query = QueryService(root)

            source = objects.get("source", result["source_id"])
            node = objects.get("node", result["node_id"])
            activity = objects.get("activity", result["activity_id"])

            self.assertEqual(source["kind"], "file")
            self.assertEqual(source["content_type"], "text")
            self.assertGreaterEqual(len(source["segments"]), 2)
            self.assertEqual(node["kind"], "document")
            self.assertEqual(node["name"], "notes.txt")
            self.assertEqual(activity["source_refs"], [source["id"]])

            expanded = query.expand(result["source_id"])
            self.assertGreaterEqual(len(expanded["data"]["source_segments"]), 2)

    def test_markdown_ingest_uses_headings_as_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            document = root / "guide.md"
            document.write_text(
                "# Guide\n\n"
                "Opening context.\n\n"
                "## Install\n\n"
                "Run the installer.\n\n"
                "## Use\n\n"
                "Call the MCP tools.\n",
                encoding="utf-8",
            )

            ingest = IngestService(root)
            result = ingest.ingest_markdown(document)
            objects = FsObjectRepository(root)

            source = objects.get("source", result["source_id"])
            excerpts = [segment["excerpt"] for segment in source["segments"]]

            self.assertEqual(source["kind"], "markdown")
            self.assertEqual(source["content_type"], "markdown")
            self.assertTrue(any("Guide" in excerpt for excerpt in excerpts))
            self.assertTrue(any("Install" in excerpt for excerpt in excerpts))

    def test_markdown_ingest_records_line_locators_heading_breadcrumbs_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            document = root / "guide.md"
            document.write_text(
                "---\n"
                "title: Guide\n"
                "---\n\n"
                "# Guide\n\n"
                "Opening context.\n\n"
                "## Install\n\n"
                "Run the installer.\n",
                encoding="utf-8",
            )

            result = IngestService(root).ingest_markdown(document)
            source = FsObjectRepository(root).get("source", result["source_id"])
            install = next(segment for segment in source["segments"] if segment["locator"].get("heading_path") == ["Guide", "Install"])

            self.assertEqual(install["locator"]["chunk_kind"], "section")
            self.assertEqual(install["locator"]["line_start"], 9)
            self.assertEqual(install["locator"]["line_end"], 11)
            self.assertEqual(install["hash"], hashlib.sha256(install["excerpt"].encode("utf-8")).hexdigest())
            self.assertEqual(source["payload"]["chunking"]["strategy"], "document_chunker.v1")
            adapter = source["metadata"]["adapter"]
            freshness = source["metadata"]["freshness"]
            self.assertEqual(adapter["name"], "document")
            self.assertEqual(adapter["version"], "document-adapter.v1")
            self.assertEqual(adapter["mode"], "markdown")
            self.assertEqual(adapter["default_privacy_class"], "local_file")
            self.assertEqual(adapter["origin_classification"], "local_file")
            self.assertIn("document_chunker.v1", adapter["declared_transformations"])
            self.assertTrue(freshness["is_current"])
            self.assertEqual(freshness["fingerprint"], source["fingerprint"])

    def test_web_pdf_and_conversation_ingest_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            html = root / "page.html"
            html.write_text("<html><body><h1>Web Title</h1><p>Reusable web context.</p></body></html>", encoding="utf-8")
            pdf = root / "doc.pdf"
            pdf.write_bytes(b"%PDF-1.4\n% synthetic pdf placeholder\n")
            ingest = IngestService(root)
            objects = FsObjectRepository(root)

            web_result = ingest.ingest_web(html.as_uri())
            pdf_result = ingest.ingest_pdf(pdf)
            conversation_result = ingest.ingest_conversation(
                title="Planning chat",
                messages=[
                    {"role": "user", "content": "What should we build?"},
                    {"role": "assistant", "content": "Build the MCP memory server."},
                ],
            )

            self.assertEqual(objects.get("source", web_result["source_id"])["kind"], "web")
            self.assertIn("Web Title", objects.get("source", web_result["source_id"])["payload"]["text"])
            self.assertEqual(objects.get("source", pdf_result["source_id"])["kind"], "pdf")
            self.assertEqual(objects.get("source", pdf_result["source_id"])["content_type"], "binary_stub")
            self.assertEqual(objects.get("source", conversation_result["source_id"])["kind"], "conversation")
            self.assertEqual(conversation_result["segment_count"], 2)
            self.assertEqual(conversation_result["result_type"], "source_ingest_result")
            self.assertEqual(conversation_result["status"], "completed")
            self.assertEqual(conversation_result["warnings"], [])
            self.assertIn("call_memory_remember_if_durable", conversation_result["next_actions"])

    def test_query_filters_recent_search_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            document = root / "guide.md"
            document.write_text("# Guide\n\nInstall memory substrate.\n", encoding="utf-8")

            ingest = IngestService(root)
            ingest_result = ingest.ingest_markdown(document)
            remember = RememberService(root)
            remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Guide install command",
                    "summary": "The guide explains installation.",
                    "subject_refs": [ingest_result["node_id"]],
                    "evidence_refs": [{"source_id": ingest_result["source_id"], "segment_id": "1-guide"}],
                    "payload": {
                        "subject": ingest_result["node_id"],
                        "predicate": "describes",
                        "value": "installation",
                        "object": None,
                    },
                    "status": "active",
                    "confidence": 0.9,
                }
            )

            query = QueryService(root)
            recent = query.recent(max_items=20, filters={"object_type": "knowledge", "status": "active"})
            self.assertEqual({item["object_type"] for item in recent["data"]["items"]}, {"knowledge"})
            self.assertEqual({item["status"] for item in recent["data"]["items"]}, {"active"})

            search = query.search("guide", max_items=20, filters={"object_type": "source"})
            self.assertEqual([item["object_type"] for item in search["data"]["items"]], ["source"])

            context = query.context(
                task="install",
                scope={"node_ids": [ingest_result["node_id"]], "object_types": ["knowledge"]},
                max_items=10,
            )
            self.assertEqual({item["object_type"] for item in context["data"]["items"]}, {"knowledge"})
            self.assertTrue(context["data"]["citations"])

    def test_query_graph_returns_neighbor_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            document = root / "guide.md"
            document.write_text("# Guide\n\nInstall memory substrate.\n", encoding="utf-8")
            ingest_result = IngestService(root).ingest_markdown(document)
            knowledge = RememberService(root).create_knowledge(
                {
                    "kind": "fact",
                    "title": "Guide graph fact",
                    "summary": "Graph relation.",
                    "subject_refs": [ingest_result["node_id"]],
                    "evidence_refs": [{"source_id": ingest_result["source_id"], "segment_id": "1-guide"}],
                    "payload": {"subject": ingest_result["node_id"], "predicate": "documents", "value": "graph", "object": None},
                    "confidence": 0.8,
                }
            )

            graph = QueryService(root).graph(ingest_result["node_id"], max_items=10)
            node_ids = {node["id"] for node in graph["data"]["nodes"]}
            edge_targets = {edge["target_id"] for edge in graph["data"]["edges"]}

            self.assertEqual(graph["result_type"], "graph")
            self.assertIn(ingest_result["node_id"], node_ids)
            self.assertIn(knowledge["knowledge_id"], edge_targets)

    def test_phase1_remember_mutations_emit_audit_and_keep_structure_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)

            ingest = IngestService(root)
            ingest_result = ingest.ingest_repo(repo)
            remember = RememberService(root)
            validator = MaintainService(root)
            objects = FsObjectRepository(root)
            audit = FsAuditRepository(root)
            paths = StoragePaths(root)

            activity_result = remember.create_activity(
                {
                    "kind": "research",
                    "title": "Inspect demo repo",
                    "summary": "Captured reusable repo walkthrough.",
                    "source_refs": [ingest_result["source_id"]],
                    "related_node_refs": ingest_result["node_ids"][:1],
                }
            )
            knowledge_result = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Demo repo exposes hello",
                    "summary": "The demo repo exports a hello function.",
                    "subject_refs": ingest_result["node_ids"][:1],
                    "evidence_refs": [
                        {
                            "source_id": ingest_result["source_id"],
                            "segment_id": "src-demo-py",
                        }
                    ],
                    "payload": {
                        "subject": ingest_result["node_ids"][0],
                        "predicate": "exports_function",
                        "value": "hello",
                        "object": None,
                    },
                    "confidence": 0.8,
                }
            )
            work_item_result = remember.create_work_item(
                {
                    "kind": "task",
                    "title": "Follow up on demo repo",
                    "summary": "Track the next inspection step.",
                    "source_refs": [ingest_result["source_id"]],
                    "related_node_refs": ingest_result["node_ids"][:1],
                    "related_knowledge_refs": [knowledge_result["knowledge_id"]],
                }
            )

            self.assertIsNotNone(objects.get("activity", activity_result["activity_id"]))
            self.assertIsNotNone(objects.get("knowledge", knowledge_result["knowledge_id"]))
            self.assertIsNotNone(objects.get("work_item", work_item_result["work_item_id"]))
            self.assertEqual(activity_result["object_id"], activity_result["activity_id"])
            self.assertEqual(knowledge_result["object_id"], knowledge_result["knowledge_id"])
            self.assertEqual(work_item_result["object_id"], work_item_result["work_item_id"])
            self.assertEqual(knowledge_result["object_type"], "knowledge")
            self.assertEqual(work_item_result["status"], "open")

            for patch_id in (
                activity_result["patch_id"],
                knowledge_result["patch_id"],
                work_item_result["patch_id"],
            ):
                self.assertTrue(paths.patch_path(patch_id).exists())

            audit_events = audit.list()
            self.assertGreaterEqual(
                len(audit_events),
                activity_result["applied_operations"]
                + knowledge_result["applied_operations"]
                + work_item_result["applied_operations"],
            )

            report = validator.structure()
            self.assertEqual(report["result_type"], "structure_report")
            self.assertEqual(report["data"]["counts"]["warning"], 0)
            self.assertEqual(report["data"]["counts"]["error"], 0)

            audit_snapshot = validator.audit(max_items=50)
            self.assertEqual(audit_snapshot["result_type"], "audit_log")
            self.assertGreater(len(audit_snapshot["data"]["events"]), 0)

    def test_remember_batch_and_contest_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)
            ingest_result = IngestService(root).ingest_repo(repo)
            remember = RememberService(root)
            objects = FsObjectRepository(root)

            batch = remember.batch(
                [
                    {
                        "mode": "knowledge",
                        "input_data": {
                            "kind": "fact",
                            "title": "Batch fact",
                            "summary": "Created from batch.",
                            "subject_refs": ingest_result["node_ids"][:1],
                            "evidence_refs": [{"source_id": ingest_result["source_id"], "segment_id": "src"}],
                            "payload": {"subject": ingest_result["node_ids"][0], "predicate": "batched", "value": True, "object": None},
                            "confidence": 0.8,
                        },
                    },
                    {
                        "mode": "work_item",
                        "input_data": {
                            "kind": "task",
                            "title": "Batch task",
                            "summary": "Created from batch.",
                            "related_node_refs": ingest_result["node_ids"][:1],
                        },
                    },
                ]
            )
            knowledge_id = batch["results"][0]["knowledge_id"]
            contest = remember.contest_knowledge(knowledge_id, reason="Conflicting source found.")

            self.assertEqual(batch["created"], 2)
            self.assertEqual(contest["knowledge_id"], knowledge_id)
            self.assertEqual(objects.get("knowledge", knowledge_id)["status"], "contested")
            self.assertEqual(objects.get("knowledge", knowledge_id)["reason"], "Conflicting source found.")


if __name__ == "__main__":
    unittest.main()
