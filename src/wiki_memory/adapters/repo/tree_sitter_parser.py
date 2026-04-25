from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ParsedModule:
    path: str
    language: str
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    parser_backend: str = "fallback"


class TreeSitterParser:
    """Optional parsing boundary for repo ingest.

    Uses tree-sitter if available, otherwise falls back to lightweight parsing
    for Python via stdlib `ast`.
    """

    def __init__(self) -> None:
        self._backend = "fallback"
        self._parser = None
        self._languages = None
        try:
            from tree_sitter import Parser  # type: ignore
            from tree_sitter_languages import get_language  # type: ignore

            self._parser = Parser
            self._get_language = get_language
            self._backend = "tree_sitter"
        except Exception:
            self._parser = None
            self._get_language = None

    @property
    def backend(self) -> str:
        return self._backend

    def parse(self, root: Path, path: Path, language: str) -> ParsedModule | None:
        if self._backend == "tree_sitter":
            parsed = self._parse_with_tree_sitter(root, path, language)
            if parsed is not None:
                return parsed
        if language == "python":
            return self._parse_python_ast(root, path)
        if language in {"typescript", "javascript"}:
            return self._parse_js_like(root, path, language)
        return None

    def _parse_with_tree_sitter(self, root: Path, path: Path, language: str) -> ParsedModule | None:
        if self._parser is None or self._get_language is None:
            return None
        language_map = {
            "python": "python",
            "typescript": "typescript",
            "javascript": "javascript",
        }
        ts_lang = language_map.get(language)
        if ts_lang is None:
            return None

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        try:
            parser = self._parser()
            parser.set_language(self._get_language(ts_lang))
            tree = parser.parse(source.encode("utf-8"))
        except Exception:
            return None

        classes: list[str] = []
        functions: list[str] = []
        imports: list[str] = []

        def walk(node) -> None:
            node_type = node.type
            if node_type in {"class_definition", "class_declaration"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    classes.append(source[name_node.start_byte:name_node.end_byte])
            elif node_type in {"function_definition", "function_declaration", "method_definition"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    functions.append(source[name_node.start_byte:name_node.end_byte])
            elif node_type in {"import_statement", "import_from_statement"}:
                imports.append(source[node.start_byte:node.end_byte].strip())
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        if not classes and not functions and not imports:
            return None
        return ParsedModule(
            path=str(path.relative_to(root)),
            language=language,
            classes=classes[:12],
            functions=functions[:20],
            imports=imports[:20],
            parser_backend="tree_sitter",
        )

    def _parse_python_ast(self, root: Path, path: Path) -> ParsedModule | None:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        classes: list[str] = []
        functions: list[str] = []
        imports: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(module)

        if not classes and not functions and not imports:
            return None

        return ParsedModule(
            path=str(path.relative_to(root)),
            language="python",
            classes=classes[:12],
            functions=functions[:20],
            imports=imports[:20],
            parser_backend="ast",
        )

    def _parse_js_like(self, root: Path, path: Path, language: str) -> ParsedModule | None:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        classes = re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", source)
        functions = [
            *re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)", source),
            *re.findall(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", source),
        ]
        imports = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("export ")
        ]

        if not classes and not functions and not imports:
            return None

        return ParsedModule(
            path=str(path.relative_to(root)),
            language=language,
            classes=classes[:12],
            functions=functions[:20],
            imports=imports[:20],
            parser_backend="regex",
        )
