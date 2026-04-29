from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from memory_substrate.domain.services.document_chunker import DocumentChunker


@dataclass(slots=True)
class ParsedModule:
    path: str
    language: str
    line_start: int = 1
    line_end: int = 1
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    symbols: list[dict] = field(default_factory=list)
    module_doc: str = ""
    class_docs: dict[str, str] = field(default_factory=dict)
    interfaces: list[dict] = field(default_factory=list)
    parser_backend: str = "fallback"


@dataclass(slots=True)
class ParsedDocumentSection:
    path: str
    heading: str
    level: int
    line_start: int
    line_end: int
    excerpt: str
    heading_path: list[str] = field(default_factory=list)
    chunk_kind: str = "section"
    parser_backend: str = "fallback"


class TreeSitterParser:
    """Single-primary parser boundary for repo ingest.

    Prefer `tree_sitter_language_pack` when it is installed. The stdlib and
    regex paths are safety fallbacks for local/default installs, not parallel
    semantic implementations.
    """

    def __init__(self) -> None:
        self._backend = "fallback"
        self._get_parser = None
        try:
            from tree_sitter_language_pack import get_parser  # type: ignore

            self._get_parser = get_parser
            self._backend = "tree_sitter_language_pack"
        except Exception:
            self._get_parser = None

    @property
    def backend(self) -> str:
        return self._backend

    def parse(self, root: Path, path: Path, language: str) -> ParsedModule | None:
        if self._backend == "tree_sitter_language_pack":
            parsed = self._parse_with_language_pack(root, path, language)
            if parsed is not None:
                return parsed
        if language == "python":
            return self._parse_python_ast(root, path)
        if language in {"typescript", "javascript"}:
            return self._parse_js_like(root, path, language)
        return None

    def parse_markdown(self, root: Path, path: Path) -> list[ParsedDocumentSection]:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        chunks = DocumentChunker().chunk_markdown(source)
        return [
            ParsedDocumentSection(
                path=str(path.relative_to(root)),
                heading=chunk.title,
                level=chunk.level,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                excerpt=chunk.excerpt,
                heading_path=chunk.heading_path,
                chunk_kind=chunk.kind,
                parser_backend="document_chunker.v1",
            )
            for chunk in chunks
        ]

    def _parse_with_language_pack(self, root: Path, path: Path, language: str) -> ParsedModule | None:
        if self._get_parser is None:
            return None
        ts_lang = self._tree_sitter_language_candidates(path, language)
        if not ts_lang:
            return None

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        try:
            parser = self._load_parser(ts_lang)
            if parser is None:
                return None
            tree = parser.parse(source.encode("utf-8"))
        except Exception:
            return None

        classes: list[str] = []
        functions: list[str] = []
        imports: list[str] = []
        symbols: list[dict] = []

        def walk(node, class_stack: list[str] | None = None) -> None:
            class_stack = class_stack or []
            node_type = node.type
            if node_type in {"class_definition", "class_declaration"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    name = source[name_node.start_byte:name_node.end_byte]
                    classes.append(name)
                    symbols.append(self._tree_sitter_symbol(name, "class", node))
                    for child in node.children:
                        walk(child, [*class_stack, name])
                    return
            elif node_type in {
                "function_definition",
                "function_declaration",
                "method_definition",
                "generator_function_declaration",
            }:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    name = source[name_node.start_byte:name_node.end_byte]
                    kind = "method" if class_stack or node_type == "method_definition" else "function"
                    if kind == "method" and class_stack and "." not in name:
                        name = f"{class_stack[-1]}.{name}"
                    functions.append(name)
                    symbols.append(self._tree_sitter_symbol(name, kind, node))
            elif node_type in {"interface_declaration", "type_alias_declaration"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    kind = "interface" if node_type == "interface_declaration" else "type"
                    name = source[name_node.start_byte:name_node.end_byte]
                    symbols.append(self._tree_sitter_symbol(name, kind, node))
            elif node_type in {"import_statement", "import_from_statement", "import_declaration"}:
                imports.append(source[node.start_byte:node.end_byte].strip())
            for child in node.children:
                walk(child, class_stack)

        walk(tree.root_node)
        if not classes and not functions and not imports:
            return None
        rich_python = self._parse_python_ast(root, path) if language == "python" else None
        if rich_python is not None:
            if not imports:
                imports = rich_python.imports
        return ParsedModule(
            path=str(path.relative_to(root)),
            language=language,
            line_start=1,
            line_end=max(1, len(source.splitlines())),
            classes=classes[:12],
            functions=functions[:20],
            imports=imports[:20],
            symbols=symbols[:40],
            module_doc=rich_python.module_doc if rich_python is not None else "",
            class_docs=rich_python.class_docs if rich_python is not None else {},
            interfaces=rich_python.interfaces[:30] if rich_python is not None else [],
            parser_backend="tree_sitter_language_pack",
        )

    def _tree_sitter_language_candidates(self, path: Path, language: str) -> list[str]:
        suffix = path.suffix.lower()
        if suffix == ".tsx":
            return ["tsx", "typescript"]
        if suffix == ".jsx":
            return ["javascript"]
        language_map = {
            "python": ["python"],
            "typescript": ["typescript"],
            "javascript": ["javascript"],
        }
        return language_map.get(language, [])

    def _load_parser(self, language_candidates: list[str]):
        if self._get_parser is None:
            return None
        for language in language_candidates:
            try:
                return self._get_parser(language)
            except Exception:
                continue
        return None

    def _tree_sitter_symbol(self, name: str, kind: str, node) -> dict:
        return {
            "name": name,
            "kind": kind,
            "line_start": self._point_line(node.start_point),
            "line_end": self._point_line(node.end_point),
        }

    def _point_line(self, point) -> int:
        if hasattr(point, "row"):
            return int(point.row) + 1
        return int(point[0]) + 1

    def _parse_markdown_with_language_pack(self, root: Path, path: Path) -> list[ParsedDocumentSection]:
        if self._get_parser is None:
            return []
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        try:
            parser = self._load_parser(["markdown"])
            if parser is None:
                return []
            tree = parser.parse(source.encode("utf-8"))
        except Exception:
            return []

        heading_rows: list[int] = []

        def walk(node) -> None:
            if node.type in {"atx_heading", "setext_heading"}:
                heading_rows.append(self._point_line(node.start_point) - 1)
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return self._markdown_sections_from_heading_rows(
            root=root,
            path=path,
            source=source,
            heading_rows=heading_rows,
            parser_backend="tree_sitter_language_pack",
        )

    def _parse_markdown_headings(
        self,
        root: Path,
        path: Path,
        parser_backend: str,
    ) -> list[ParsedDocumentSection]:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        heading_rows: list[int] = []
        fenced = False
        for index, line in enumerate(source.splitlines()):
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fenced = not fenced
                continue
            if fenced:
                continue
            if line.startswith("#"):
                heading_rows.append(index)
        return self._markdown_sections_from_heading_rows(
            root=root,
            path=path,
            source=source,
            heading_rows=heading_rows,
            parser_backend=parser_backend,
        )

    def _markdown_sections_from_heading_rows(
        self,
        root: Path,
        path: Path,
        source: str,
        heading_rows: list[int],
        parser_backend: str,
    ) -> list[ParsedDocumentSection]:
        lines = source.splitlines()
        if not lines:
            return []
        rows = sorted(set(row for row in heading_rows if 0 <= row < len(lines)))
        if not rows:
            rows = [0]
        sections: list[ParsedDocumentSection] = []
        for index, start_row in enumerate(rows):
            next_row = rows[index + 1] if index + 1 < len(rows) else len(lines)
            heading, level = self._markdown_heading(lines[start_row], fallback=path.stem)
            excerpt = "\n".join(lines[start_row:next_row]).strip()
            if not excerpt:
                continue
            sections.append(
                ParsedDocumentSection(
                    path=str(path.relative_to(root)),
                    heading=heading,
                    level=level,
                    line_start=start_row + 1,
                    line_end=max(start_row + 1, next_row),
                    excerpt=excerpt[:1600],
                    parser_backend=parser_backend,
                )
            )
        return sections

    def _markdown_heading(self, line: str, fallback: str) -> tuple[str, int]:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not match:
            return fallback, 1
        return match.group(2).strip() or fallback, len(match.group(1))

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
        class_docs: dict[str, str] = {}
        interfaces: list[dict] = []
        symbols: list[dict] = []
        module_doc = ast.get_docstring(tree) or ""
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
                class_docs[node.name] = ast.get_docstring(node) or ""
                symbols.append(self._python_symbol(node.name, "class", node))
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = f"{node.name}.{child.name}"
                        functions.append(method_name)
                        symbols.append(self._python_symbol(method_name, "method", child))
                        interfaces.append(self._python_interface(child, class_name=node.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
                symbols.append(self._python_symbol(node.name, "function", node))
                interfaces.append(self._python_interface(node))
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
            line_start=1,
            line_end=max(1, len(source.splitlines())),
            classes=classes[:12],
            functions=functions[:20],
            imports=imports[:20],
            symbols=symbols[:40],
            module_doc=module_doc.splitlines()[0] if module_doc else "",
            class_docs={key: value.splitlines()[0] for key, value in class_docs.items() if value},
            interfaces=interfaces[:30],
            parser_backend="ast",
        )

    def _python_symbol(self, name: str, kind: str, node: ast.AST) -> dict:
        return {
            "name": name,
            "kind": kind,
            "line_start": int(getattr(node, "lineno", 1)),
            "line_end": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
        }

    def _python_interface(self, node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str | None = None) -> dict:
        name = f"{class_name}.{node.name}" if class_name else node.name
        doc_info = self._parse_docstring(ast.get_docstring(node) or "")
        parameters = []
        defaults_by_arg = self._defaults_by_arg(node.args)
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            if class_name and arg.arg in {"self", "cls"}:
                continue
            parameters.append(
                {
                    "name": arg.arg,
                    "annotation": self._annotation(arg.annotation),
                    "default": defaults_by_arg.get(arg.arg),
                    "required": arg.arg not in defaults_by_arg,
                    "description": doc_info["params"].get(arg.arg, ""),
                }
            )
        signature_parameters = []
        for parameter in parameters:
            rendered = parameter["name"]
            if parameter["annotation"]:
                rendered += f": {parameter['annotation']}"
            if parameter["default"] is not None:
                rendered += f" = {parameter['default']}"
            signature_parameters.append(rendered)
        returns = self._annotation(node.returns)
        signature = f"{name}({', '.join(signature_parameters)})"
        if returns:
            signature += f" -> {returns}"
        return {
            "name": name,
            "kind": "method" if class_name else "function",
            "signature": signature,
            "parameters": parameters,
            "returns": returns,
            "return_description": doc_info["returns"],
            "doc": doc_info["summary"],
        }

    def _parse_docstring(self, doc: str) -> dict:
        if not doc:
            return {"summary": "", "params": {}, "returns": ""}
        lines = [line.rstrip() for line in doc.splitlines()]
        summary_lines: list[str] = []
        params: dict[str, str] = {}
        returns: list[str] = []
        section = "summary"
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered in {"args:", "arguments:", "parameters:"}:
                section = "args"
                continue
            if lowered in {"returns:", "return:"}:
                section = "returns"
                continue
            if section == "summary":
                summary_lines.append(line)
            elif section == "args":
                name, sep, description = line.partition(":")
                if sep:
                    params[name.strip()] = description.strip()
            elif section == "returns":
                returns.append(line)
        return {
            "summary": " ".join(summary_lines),
            "params": params,
            "returns": " ".join(returns),
        }

    def _defaults_by_arg(self, args: ast.arguments) -> dict[str, str]:
        names = [arg.arg for arg in args.args]
        defaults: dict[str, str] = {}
        for name, default in zip(names[-len(args.defaults):], args.defaults, strict=False):
            defaults[name] = self._expr(default)
        for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=False):
            if default is not None:
                defaults[arg.arg] = self._expr(default)
        return defaults

    def _annotation(self, node: ast.expr | None) -> str:
        if node is None:
            return ""
        return self._expr(node)

    def _expr(self, node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _parse_js_like(self, root: Path, path: Path, language: str) -> ParsedModule | None:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        class_matches = list(re.finditer(r"\bclass\s+([A-Za-z_$][\w$]*)", source))
        function_matches = [
            *re.finditer(r"\bfunction\s+([A-Za-z_$][\w$]*)", source),
            *re.finditer(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", source),
        ]
        interface_matches = list(re.finditer(r"\binterface\s+([A-Za-z_$][\w$]*)", source))
        type_matches = list(re.finditer(r"\btype\s+([A-Za-z_$][\w$]*)\s*=", source))
        classes = [match.group(1) for match in class_matches]
        functions = [match.group(1) for match in function_matches]
        symbols = [
            *(self._regex_symbol(match.group(1), "class", source, match.start()) for match in class_matches),
            *(self._regex_symbol(match.group(1), "function", source, match.start()) for match in function_matches),
            *(self._regex_symbol(match.group(1), "interface", source, match.start()) for match in interface_matches),
            *(self._regex_symbol(match.group(1), "type", source, match.start()) for match in type_matches),
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
            line_start=1,
            line_end=max(1, len(source.splitlines())),
            classes=classes[:12],
            functions=functions[:20],
            imports=imports[:20],
            symbols=symbols[:40],
            parser_backend="regex",
        )

    def _regex_symbol(self, name: str, kind: str, source: str, start_index: int) -> dict:
        line_number = source.count("\n", 0, start_index) + 1
        return {
            "name": name,
            "kind": kind,
            "line_start": line_number,
            "line_end": line_number,
        }
