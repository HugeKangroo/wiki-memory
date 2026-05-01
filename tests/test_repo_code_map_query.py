from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.ingest.service import IngestService
from memory_substrate.application.query.service import QueryService
from memory_substrate.adapters.repo.tree_sitter_parser import TreeSitterParser
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class RepoCodeMapQueryTest(unittest.TestCase):
    def test_parser_prefers_tree_sitter_language_pack_when_available(self) -> None:
        source = (
            "class MemoryServer:\n"
            "    def run(self) -> bool:\n"
            "        return True\n"
            "\n"
            "def memory_query(task: str) -> dict:\n"
            "    return {\"task\": task}\n"
        )

        class FakeNode:
            def __init__(
                self,
                node_type: str,
                start_byte: int,
                end_byte: int,
                start_line: int,
                end_line: int,
                children: list | None = None,
                fields: dict | None = None,
            ) -> None:
                self.type = node_type
                self.start_byte = start_byte
                self.end_byte = end_byte
                self.start_point = (start_line - 1, 0)
                self.end_point = (end_line - 1, 0)
                self.children = children or []
                self._fields = fields or {}

            def child_by_field_name(self, name: str):
                return self._fields.get(name)

        def name_node(name: str, line: int) -> FakeNode:
            start = source.index(name)
            return FakeNode("identifier", start, start + len(name), line, line)

        method = FakeNode(
            "function_definition",
            source.index("def run"),
            source.index("        return True") + len("        return True"),
            2,
            3,
            fields={"name": name_node("run", 2)},
        )
        klass = FakeNode(
            "class_definition",
            source.index("class MemoryServer"),
            source.index("def memory_query"),
            1,
            3,
            children=[method],
            fields={"name": name_node("MemoryServer", 1)},
        )
        function = FakeNode(
            "function_definition",
            source.index("def memory_query"),
            len(source),
            5,
            6,
            fields={"name": name_node("memory_query", 5)},
        )
        root_node = FakeNode("module", 0, len(source), 1, 6, children=[klass, function])

        class FakeTree:
            def __init__(self) -> None:
                self.root_node = root_node

        class FakeParser:
            def parse(self, _raw: bytes) -> FakeTree:
                return FakeTree()

        fake_module = types.ModuleType("tree_sitter_language_pack")
        fake_module.get_parser = lambda _language: FakeParser()
        previous_module = sys.modules.get("tree_sitter_language_pack")
        sys.modules["tree_sitter_language_pack"] = fake_module
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                path = root / "server.py"
                path.write_text(source, encoding="utf-8")

                parser = TreeSitterParser()
                parsed = parser.parse(root, path, "python")
        finally:
            if previous_module is None:
                sys.modules.pop("tree_sitter_language_pack", None)
            else:
                sys.modules["tree_sitter_language_pack"] = previous_module

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parser.backend, "tree_sitter_language_pack")
        self.assertEqual(parsed.parser_backend, "tree_sitter_language_pack")
        self.assertIn("MemoryServer", parsed.classes)
        self.assertIn("MemoryServer.run", parsed.functions)
        self.assertIn("memory_query", parsed.functions)

    def test_tree_sitter_js_parse_keeps_static_enrichments_when_available(self) -> None:
        source = (
            "import { BaseController } from './base'\n"
            "class UserController extends BaseController {}\n"
            "app.get('/users', listUsers)\n"
        )

        class FakeNode:
            def __init__(
                self,
                node_type: str,
                start_byte: int,
                end_byte: int,
                start_line: int,
                end_line: int,
                children: list | None = None,
                fields: dict | None = None,
            ) -> None:
                self.type = node_type
                self.start_byte = start_byte
                self.end_byte = end_byte
                self.start_point = (start_line - 1, 0)
                self.end_point = (end_line - 1, 0)
                self.children = children or []
                self._fields = fields or {}

            def child_by_field_name(self, name: str):
                return self._fields.get(name)

        def name_node(name: str, line: int) -> FakeNode:
            start = source.index(name)
            return FakeNode("identifier", start, start + len(name), line, line)

        import_node = FakeNode("import_declaration", 0, source.index("\n"), 1, 1)
        class_node = FakeNode(
            "class_declaration",
            source.index("class UserController"),
            source.index("app.get"),
            2,
            2,
            fields={"name": name_node("UserController", 2)},
        )
        root_node = FakeNode("program", 0, len(source), 1, 3, children=[import_node, class_node])

        class FakeTree:
            def __init__(self) -> None:
                self.root_node = root_node

        class FakeParser:
            def parse(self, _raw: bytes) -> FakeTree:
                return FakeTree()

        fake_module = types.ModuleType("tree_sitter_language_pack")
        fake_module.get_parser = lambda _language: FakeParser()
        previous_module = sys.modules.get("tree_sitter_language_pack")
        sys.modules["tree_sitter_language_pack"] = fake_module
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                path = root / "server.js"
                path.write_text(source, encoding="utf-8")

                parser = TreeSitterParser()
                parsed = parser.parse(root, path, "javascript")
        finally:
            if previous_module is None:
                sys.modules.pop("tree_sitter_language_pack", None)
            else:
                sys.modules["tree_sitter_language_pack"] = previous_module

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.parser_backend, "tree_sitter_language_pack")
        self.assertIn("UserController", parsed.classes)
        self.assertTrue(
            any(
                edge["class"] == "UserController" and edge["base"] == "BaseController"
                for edge in parsed.inheritance
            )
        )
        self.assertTrue(
            any(
                entry["framework"] == "express"
                and entry["method"] == "GET"
                and entry["route"] == "/users"
                for entry in parsed.framework_entries
            )
        )

    def test_tree_sitter_js_parse_keeps_framework_only_modules(self) -> None:
        source = "app.get('/health', healthCheck)\n"

        class FakeNode:
            def __init__(self) -> None:
                self.type = "program"
                self.start_byte = 0
                self.end_byte = len(source)
                self.start_point = (0, 0)
                self.end_point = (0, 0)
                self.children = []

            def child_by_field_name(self, _name: str):
                return None

        class FakeTree:
            def __init__(self) -> None:
                self.root_node = FakeNode()

        class FakeParser:
            def parse(self, _raw: bytes) -> FakeTree:
                return FakeTree()

        fake_module = types.ModuleType("tree_sitter_language_pack")
        fake_module.get_parser = lambda _language: FakeParser()
        previous_module = sys.modules.get("tree_sitter_language_pack")
        sys.modules["tree_sitter_language_pack"] = fake_module
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                path = root / "routes.js"
                path.write_text(source, encoding="utf-8")

                parser = TreeSitterParser()
                parsed = parser.parse(root, path, "javascript")
        finally:
            if previous_module is None:
                sys.modules.pop("tree_sitter_language_pack", None)
            else:
                sys.modules["tree_sitter_language_pack"] = previous_module

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.framework_entries[0]["route"], "/health")
        self.assertEqual(parsed.framework_entries[0]["method"], "GET")

    def test_python_call_site_index_does_not_attribute_nested_function_calls_to_outer_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "service.py"
            path.write_text(
                "def outer() -> None:\n"
                "    def inner() -> None:\n"
                "        hidden_call()\n"
                "    visible_call()\n",
                encoding="utf-8",
            )

            parsed = TreeSitterParser()._parse_python_ast(root, path)

        self.assertIsNotNone(parsed)
        assert parsed is not None
        outer_calls = [call["callee"] for call in parsed.call_sites if call["caller"] == "outer"]
        self.assertEqual(outer_calls, ["visible_call"])

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

    def test_repo_ingest_builds_code_intelligence_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "code-intelligence-repo"
            repo.mkdir()
            src = repo / "src"
            src.mkdir()
            (src / "__init__.py").write_text("", encoding="utf-8")
            (src / "repository.py").write_text(
                "class BaseRepository:\n"
                "    pass\n"
                "\n"
                "class UserRepository(BaseRepository):\n"
                "    def get_user(self, user_id: str) -> dict:\n"
                "        return {\"id\": user_id}\n",
                encoding="utf-8",
            )
            (src / "service.py").write_text(
                "from src.repository import UserRepository\n"
                "\n"
                "class UserService:\n"
                "    def __init__(self) -> None:\n"
                "        self.repo = UserRepository()\n"
                "\n"
                "    def load(self, user_id: str) -> dict:\n"
                "        return self.repo.get_user(user_id)\n",
                encoding="utf-8",
            )
            (src / "api.py").write_text(
                "from fastapi import FastAPI\n"
                "from src.service import UserService\n"
                "\n"
                "app = FastAPI()\n"
                "\n"
                "@app.get('/users/{user_id}')\n"
                "def get_user(user_id: str) -> dict:\n"
                "    return UserService().load(user_id)\n",
                encoding="utf-8",
            )

            result = IngestService(root).ingest_repo(repo)
            source = FsObjectRepository(root).get("source", result["source_id"])

            self.assertIsNotNone(source)
            assert source is not None
            payload = source["payload"]
            dependency = next(
                edge
                for edge in payload["module_dependencies"]
                if edge["from_path"] == "src/service.py" and edge["imported_module"] == "src.repository"
            )
            inheritance = next(
                edge
                for edge in payload["inheritance_graph"]
                if edge["class"] == "UserRepository" and edge["base"] == "BaseRepository"
            )
            call_site = next(
                call
                for call in payload["call_index"]
                if call["caller"] == "UserService.load" and call["callee"] == "self.repo.get_user"
            )
            route = next(
                item
                for item in payload["framework_entries"]
                if item["framework"] == "fastapi" and item["kind"] == "route"
            )

            self.assertEqual(payload["code_intelligence"]["schema_version"], "code_intelligence.v1")
            self.assertIn("partial_static_analysis", payload["code_intelligence"]["limitations"])
            self.assertEqual(dependency["to_path"], "src/repository.py")
            self.assertEqual(dependency["resolution"], "internal")
            self.assertEqual(dependency["imported_name"], "UserRepository")
            self.assertEqual(inheritance["path"], "src/repository.py")
            self.assertEqual(inheritance["resolution"], "local_symbol")
            self.assertEqual(call_site["line_start"], 8)
            self.assertEqual(route["method"], "GET")
            self.assertEqual(route["route"], "/users/{user_id}")
            self.assertEqual(route["handler"], "get_user")

    def test_query_page_exposes_compact_code_intelligence_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "compact-code-intel-repo"
            repo.mkdir()
            src = repo / "src"
            src.mkdir()
            (src / "__init__.py").write_text("", encoding="utf-8")
            (src / "a.py").write_text(
                "from src.b import B\n"
                "from src import b\n"
                "\n"
                "class A(B):\n"
                "    def run(self) -> None:\n"
                "        B().run()\n",
                encoding="utf-8",
            )
            (src / "b.py").write_text(
                "class B:\n"
                "    def run(self) -> None:\n"
                "        return None\n",
                encoding="utf-8",
            )

            result = IngestService(root).ingest_repo(repo)
            page = QueryService(root).page(result["source_id"], max_items=1)

            payload = page["data"]["object"]["payload"]
            self.assertEqual(page["data"]["detail"], "compact")
            self.assertEqual(payload["code_intelligence"]["schema_version"], "code_intelligence.v1")
            self.assertEqual(len(payload["module_dependencies"]), 1)
            self.assertEqual(len(payload["inheritance_graph"]), 1)
            self.assertEqual(len(payload["call_index"]), 1)
            self.assertIn("payload.module_dependencies", page["data"]["truncated"])
            self.assertIn("payload.call_index", page["data"]["truncated"])

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

    def test_repo_ingest_indexes_markdown_sections_for_theory_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "llm-wiki-like"
            repo.mkdir()
            (repo / "README.md").write_text(
                "# LLM Wiki\n"
                "\n"
                "This project implements Karpathy's LLM Wiki pattern as a persistent wiki.\n"
                "\n"
                "```markdown\n"
                "# Not A Real Heading\n"
                "```\n"
                "\n"
                "## Core Implementation\n"
                "\n"
                "Two-step ingest analyzes source material, then generates wiki pages with citations.\n",
                encoding="utf-8",
            )
            src = repo / "src" / "lib"
            src.mkdir(parents=True)
            (src / "ingest.py").write_text(
                "def analyze_source(text: str) -> dict:\n"
                "    return {\"summary\": text[:20]}\n",
                encoding="utf-8",
            )

            result = IngestService(root).ingest_repo(repo)
            source = FsObjectRepository(root).get("source", result["source_id"])
            query = QueryService(root)

            self.assertIsNotNone(source)
            assert source is not None
            doc_index = source["payload"]["doc_index"]
            document_sections = source["payload"]["document_sections"]
            headings = {section["heading"] for section in document_sections}
            document_segment = next(
                segment
                for segment in source["segments"]
                if segment["locator"].get("kind") == "document_section"
            )
            search = query.search("Karpathy persistent wiki", max_items=8, filters={"status": "active"})
            context = query.context("How does Karpathy LLM Wiki theory become implementation?", max_items=8)
            compact_page = query.page(result["source_id"], max_items=1, include_segments=True, snippet_chars=80)
            full_page = query.page(result["source_id"], detail="full")

            self.assertTrue(any(item["path"] == "README.md" for item in doc_index))
            self.assertIn("LLM Wiki", headings)
            self.assertIn("Core Implementation", headings)
            self.assertNotIn("Not A Real Heading", headings)
            self.assertEqual(document_segment["locator"]["path"], "README.md")
            self.assertIn("Karpathy", document_segment["excerpt"])
            self.assertIn(result["source_id"], {item["id"] for item in search["data"]["items"]})
            self.assertIn(result["source_id"], {item["id"] for item in context["data"]["items"]})
            self.assertEqual(compact_page["data"]["detail"], "compact")
            self.assertEqual(len(compact_page["data"]["object"]["payload"]["doc_index"]), 1)
            self.assertEqual(len(compact_page["data"]["object"]["payload"]["document_sections"]), 1)
            self.assertEqual(len(compact_page["data"]["object"]["segments"]), 1)
            self.assertIn("payload.document_sections", compact_page["data"]["truncated"])
            self.assertNotIn("detail='full'", " ".join(compact_page["warnings"]))
            self.assertNotIn("blocked", json.dumps(compact_page).lower())
            self.assertIn("local file reads", " ".join(compact_page["warnings"]))
            self.assertEqual(full_page["result_type"], "page_unavailable")
            self.assertEqual(full_page["status"], "unsupported")
            self.assertEqual(full_page["data"]["object_type"], "source")
            self.assertEqual(full_page["data"]["object_id"], result["source_id"])
            self.assertEqual(full_page["data"]["requested_detail"], "full")
            self.assertEqual(full_page["data"]["unsupported_detail"], "repo_source_full")
            self.assertEqual(full_page["data"]["supported_details"], ["compact"])
            self.assertNotIn("object", full_page["data"])
            self.assertNotIn("full_detail_blocked", full_page["data"])
            self.assertNotIn("blocked", json.dumps(full_page).lower())


if __name__ == "__main__":
    unittest.main()
