from __future__ import annotations

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ApiDocstringsTest(unittest.TestCase):
    def test_application_services_document_public_api_methods(self) -> None:
        service_files = [
            PROJECT_ROOT / "src/memory_substrate/application/ingest/service.py",
            PROJECT_ROOT / "src/memory_substrate/application/query/service.py",
            PROJECT_ROOT / "src/memory_substrate/application/maintain/service.py",
            PROJECT_ROOT / "src/memory_substrate/application/remember/service.py",
        ]

        missing: list[str] = []
        for path in service_files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.ClassDef) or not node.name.endswith("Service"):
                    continue
                for child in node.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if child.name.startswith("_") and child.name != "__init__":
                        continue
                    doc = ast.get_docstring(child) or ""
                    args = [*child.args.posonlyargs, *child.args.args, *child.args.kwonlyargs]
                    public_args = [arg.arg for arg in args if arg.arg not in {"self", "cls"}]
                    if "Returns:" not in doc or (public_args and "Args:" not in doc):
                        missing.append(f"{path.relative_to(PROJECT_ROOT)}:{node.name}.{child.name}")

        self.assertEqual([], missing)

    def test_mcp_tools_document_public_dispatch_functions(self) -> None:
        path = PROJECT_ROOT / "src/memory_substrate/interfaces/mcp/tools.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))

        missing: list[str] = []
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("memory_"):
                continue
            doc = ast.get_docstring(node) or ""
            if "Args:" not in doc or "Returns:" not in doc:
                missing.append(node.name)

        self.assertEqual([], missing)

    def test_mcp_models_document_schema_classes(self) -> None:
        path = PROJECT_ROOT / "src/memory_substrate/interfaces/mcp/models.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))

        missing: list[str] = []
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(isinstance(base, ast.Name) and base.id in {"StrictModel", "BaseToolArgs"} for base in node.bases):
                continue
            if not ast.get_docstring(node):
                missing.append(node.name)

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
