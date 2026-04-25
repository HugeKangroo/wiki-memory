from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wiki_memory.application.crystallize.service import CrystallizeService
from wiki_memory.application.ingest.service import IngestService
from wiki_memory.application.lint.service import LintService
from wiki_memory.application.query.service import QueryService
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.infrastructure.storage.paths import StoragePaths


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
            self.assertTrue((paths.projections_root / "wiki" / "index.md").exists())
            self.assertTrue((paths.projections_root / "wiki" / "overview.md").exists())
            self.assertTrue(
                (paths.projections_root / "wiki" / "sources" / f"{result['source_id']}.md").exists()
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

    def test_query_filters_recent_search_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            document = root / "guide.md"
            document.write_text("# Guide\n\nInstall wiki memory.\n", encoding="utf-8")

            ingest = IngestService(root)
            ingest_result = ingest.ingest_markdown(document)
            crystallize = CrystallizeService(root)
            crystallize.create_knowledge(
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

    def test_phase1_crystallize_mutations_emit_audit_and_keep_lint_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = self._make_repo(root)

            ingest = IngestService(root)
            ingest_result = ingest.ingest_repo(repo)
            crystallize = CrystallizeService(root)
            lint = LintService(root)
            objects = FsObjectRepository(root)
            audit = FsAuditRepository(root)
            paths = StoragePaths(root)

            activity_result = crystallize.create_activity(
                {
                    "kind": "research",
                    "title": "Inspect demo repo",
                    "summary": "Captured reusable repo walkthrough.",
                    "source_refs": [ingest_result["source_id"]],
                    "related_node_refs": ingest_result["node_ids"][:1],
                }
            )
            knowledge_result = crystallize.create_knowledge(
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
            work_item_result = crystallize.create_work_item(
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

            report = lint.structure()
            self.assertEqual(report["result_type"], "lint_report")
            self.assertEqual(report["data"]["counts"]["warning"], 0)
            self.assertEqual(report["data"]["counts"]["error"], 0)

            audit_snapshot = lint.audit(max_items=50)
            self.assertEqual(audit_snapshot["result_type"], "audit_log")
            self.assertGreater(len(audit_snapshot["data"]["events"]), 0)


if __name__ == "__main__":
    unittest.main()
