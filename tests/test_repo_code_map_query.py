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

from memory_substrate.application.ingest.service import IngestService
from memory_substrate.application.query.service import QueryService
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class RepoCodeMapQueryTest(unittest.TestCase):
    def test_repo_ingest_builds_symbol_code_map_without_full_source_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "code-map-repo"
            repo.mkdir()
            src = repo / "src" / "interfaces" / "mcp"
            src.mkdir(parents=True)
            (src / "tools.py").write_text(
                "class MemoryServer:\n"
                "    def run(self) -> bool:\n"
                "        return True\n"
                "\n"
                "def memory_query(task: str) -> dict:\n"
                "    return {\"task\": task}\n",
                encoding="utf-8",
            )

            result = IngestService(root).ingest_repo(repo)
            source = FsObjectRepository(root).get("source", result["source_id"])

            self.assertIsNotNone(source)
            code_index = source["payload"]["code_index"]
            code_modules = source["payload"]["code_modules"]
            index_entry = next(item for item in code_index if item["path"] == "src/interfaces/mcp/tools.py")
            module = next(item for item in code_modules if item["path"] == "src/interfaces/mcp/tools.py")
            symbols = {symbol["name"]: symbol for symbol in module["symbols"]}

            self.assertEqual(index_entry["language"], "python")
            self.assertEqual(index_entry["line_count"], 6)
            self.assertIn("sha256", index_entry)
            self.assertNotIn("source", index_entry)
            self.assertNotIn("text", index_entry)
            self.assertIn("MemoryServer", symbols)
            self.assertEqual(symbols["MemoryServer"]["line_start"], 1)
            self.assertIn("MemoryServer.run", symbols)
            self.assertIn("memory_query", symbols)

            payload_json = json.dumps(source["payload"], ensure_ascii=False)
            self.assertNotIn("return {\"task\": task}", payload_json)

            segment = next(
                item
                for item in source["segments"]
                if item["locator"].get("path") == "src/interfaces/mcp/tools.py"
            )
            self.assertEqual(segment["locator"]["line_start"], 1)
            self.assertGreaterEqual(segment["locator"]["line_end"], 5)

    def test_repo_ingest_rewrites_when_symbol_changes_in_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "rewrite-repo"
            repo.mkdir()
            src = repo / "src"
            src.mkdir()
            service = src / "service.py"
            service.write_text("def run() -> bool:\n    return True\n", encoding="utf-8")

            first = IngestService(root).ingest_repo(repo)
            service.write_text("def execute() -> bool:\n    return True\n", encoding="utf-8")
            second = IngestService(root).ingest_repo(repo)
            source = FsObjectRepository(root).get("source", first["source_id"])
            module = next(item for item in source["payload"]["code_modules"] if item["path"] == "src/service.py")

            self.assertEqual(first["status"], "completed")
            self.assertEqual(second["status"], "completed")
            self.assertGreater(second["applied_operations"], 0)
            self.assertIn("execute", module["functions"])
            self.assertNotIn("run", module["functions"])

    def test_query_finds_repo_modules_by_multiword_path_and_symbol_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "architecture-repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Architecture Repo\n", encoding="utf-8")
            app = repo / "src" / "application" / "query"
            mcp = repo / "src" / "interfaces" / "mcp"
            app.mkdir(parents=True)
            mcp.mkdir(parents=True)
            (app / "service.py").write_text(
                "def build_context_pack(task: str) -> dict:\n"
                "    return {\"task\": task}\n",
                encoding="utf-8",
            )
            (mcp / "tools.py").write_text(
                "def memory_query(task: str) -> dict:\n"
                "    return build_context_pack(task)\n",
                encoding="utf-8",
            )

            ingest = IngestService(root)
            result = ingest.ingest_repo(repo)
            query = QueryService(root)

            multiword = query.search("mcp tools", max_items=8, filters={"status": "active"})
            symbol = query.search("memory_query", max_items=8, filters={"status": "active"})
            context = query.context("draw architecture diagram for mcp tools and query service", max_items=8)

            multiword_ids = {item["id"] for item in multiword["data"]["items"]}
            symbol_titles = {item["title"] for item in symbol["data"]["items"]}
            context_ids = {item["id"] for item in context["data"]["items"]}

            self.assertIn(result["source_id"], multiword_ids)
            self.assertTrue(any("src.interfaces.mcp.tools" == title for title in symbol_titles))
            self.assertIn(result["source_id"], context_ids)
            self.assertLessEqual(
                {item["object_type"] for item in context["data"]["items"]},
                {"source", "node"},
            )
            self.assertTrue(
                any(item["title"] == "src.interfaces.mcp.tools" for item in context["data"]["items"])
            )


if __name__ == "__main__":
    unittest.main()
