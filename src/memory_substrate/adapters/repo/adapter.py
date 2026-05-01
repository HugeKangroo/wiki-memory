from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from memory_substrate.adapters.repo.models import RepoIngestOutput, RepoPreflightOutput
from memory_substrate.adapters.repo.tree_sitter_parser import TreeSitterParser
from memory_substrate.domain.objects.activity import Activity
from memory_substrate.domain.objects.knowledge import EvidenceRef, Knowledge
from memory_substrate.domain.objects.node import Node
from memory_substrate.domain.objects.source import Source, SourceSegment
from memory_substrate.domain.services.ids import slugify, stable_id
from memory_substrate.domain.services.patch_applier import utc_now_iso


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".next",
    ".idea",
    ".pytest_cache",
}

AGENT_LOCAL_STATE_ENTRIES = {
    ".claude",
    ".codex",
    ".cursor",
    ".worktrees",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".md": "markdown",
}


@dataclass(slots=True)
class RepoScanSummary:
    file_count: int
    dir_count: int
    top_level_entries: list[str]
    language_counts: dict[str, int]
    readme_present: bool
    source_roots: list[str]
    code_files: list[str]
    code_index: list[dict]
    doc_index: list[dict]
    document_sections: list[dict]
    python_modules: list[dict]
    code_intelligence: dict
    module_dependencies: list[dict]
    inheritance_graph: list[dict]
    call_index: list[dict]
    framework_entries: list[dict]


class RepoAdapter:
    def preflight(
        self,
        repo_path: str | Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> RepoPreflightOutput:
        root = self._resolve_root(repo_path)
        include_patterns = include_patterns or []
        exclude_patterns = exclude_patterns or []
        suggested_exclude_patterns = self._suggested_exclude_patterns(root, include_patterns, exclude_patterns)
        return RepoPreflightOutput(
            warnings=self._warnings(suggested_exclude_patterns),
            suggested_exclude_patterns=suggested_exclude_patterns,
        )

    def ingest(
        self,
        repo_path: str | Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> RepoIngestOutput:
        root = self._resolve_root(repo_path)
        include_patterns = include_patterns or []
        exclude_patterns = exclude_patterns or []
        parser = TreeSitterParser()
        suggested_exclude_patterns = self._suggested_exclude_patterns(root, include_patterns, exclude_patterns)
        summary = self._scan(root, parser=parser, include_patterns=include_patterns, exclude_patterns=exclude_patterns)
        timestamp = utc_now_iso()

        source_identity_key = f"source|repo|{root}"
        source_id = stable_id("src", source_identity_key)
        repo_slug = slugify(root.name)
        source = Source(
            id=source_id,
            kind="repo",
            origin={"path": str(root)},
            title=root.name,
            identity_key=source_identity_key,
            fingerprint=self._fingerprint(summary),
            content_type="repo_map",
            payload={
                "repo_name": root.name,
                "file_count": summary.file_count,
                "dir_count": summary.dir_count,
                "top_level_entries": summary.top_level_entries,
                "language_counts": summary.language_counts,
                "readme_present": summary.readme_present,
                "source_roots": summary.source_roots,
                "code_files": summary.code_files,
                "code_index": summary.code_index,
                "doc_index": summary.doc_index,
                "document_sections": summary.document_sections,
                "code_modules": summary.python_modules,
                "python_modules": summary.python_modules,
                "code_intelligence": summary.code_intelligence,
                "module_dependencies": summary.module_dependencies,
                "inheritance_graph": summary.inheritance_graph,
                "call_index": summary.call_index,
                "framework_entries": summary.framework_entries,
                "parser_backend": parser.backend,
            },
            segments=self._segments(root, summary),
            metadata={
                "scanned_at": timestamp,
                "repo_ingest": {
                    "include_patterns": list(include_patterns),
                    "exclude_patterns": list(exclude_patterns),
                },
            },
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )

        repo_node_identity_key = f"node|repo|{root}"
        repo_node = Node(
            id=stable_id("node", repo_node_identity_key),
            kind="repo",
            name=root.name,
            slug=repo_slug,
            identity_key=repo_node_identity_key,
            aliases=[],
            summary=f"Repository {root.name} with {summary.file_count} files.",
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )

        nodes = [repo_node, *self._module_nodes(root, summary, timestamp)]
        evidence = self._default_evidence(source)
        knowledge_items = self._knowledge(root, repo_node, summary, evidence, timestamp)

        activity = Activity(
            id=stable_id("act", f"activity|repo_ingest|{root}|{source.fingerprint}"),
            kind="research",
            title=f"Initial repo ingest: {root.name}",
            summary="Scanned repository structure and generated initial repo context objects.",
            identity_key=f"activity|repo_ingest|{root}|{source.fingerprint}",
            status="finalized",
            started_at=timestamp,
            ended_at=timestamp,
            related_node_refs=[node.id for node in nodes],
            related_work_item_refs=[],
            source_refs=[source.id],
            produced_object_refs=[*([node.id for node in nodes]), *([item.id for item in knowledge_items])],
            artifact_refs=[str(root)],
            created_at=timestamp,
            updated_at=timestamp,
        )

        return RepoIngestOutput(
            source=source,
            nodes=nodes,
            knowledge_items=knowledge_items,
            activity=activity,
            warnings=self._warnings(suggested_exclude_patterns),
            suggested_exclude_patterns=suggested_exclude_patterns,
        )

    def _resolve_root(self, repo_path: str | Path) -> Path:
        root = Path(repo_path).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Repo path is not a directory: {root}")
        return root

    def _scan(
        self,
        root: Path,
        parser: TreeSitterParser,
        include_patterns: list[str],
        exclude_patterns: list[str],
    ) -> RepoScanSummary:
        file_count = 0
        dir_count = 0
        language_counter: Counter[str] = Counter()
        readme_present = False
        top_level_entries: list[str] = []
        source_roots: list[str] = []
        code_files: list[str] = []
        code_index: list[dict] = []
        doc_index: list[dict] = []
        document_sections: list[dict] = []
        parsed_modules: list[dict] = []

        for child in sorted(root.iterdir()):
            if self._is_excluded(root, child, exclude_patterns):
                continue
            if not self._is_included(root, child, include_patterns):
                continue
            top_level_entries.append(child.name)
            if child.is_dir() and child.name in {"src", "app", "lib", "packages"}:
                source_roots.append(child.name)

        for path in root.rglob("*"):
            if self._is_excluded(root, path, exclude_patterns):
                if path.is_dir():
                    continue
                continue
            if not self._is_included(root, path, include_patterns):
                continue
            if path.is_dir():
                dir_count += 1
                continue
            file_count += 1
            suffix = path.suffix.lower()
            if suffix in LANGUAGE_BY_SUFFIX:
                language = LANGUAGE_BY_SUFFIX[suffix]
                language_counter[language] += 1
                if language == "markdown":
                    if len(doc_index) < 300:
                        doc_index.append(self._document_index_entry(root, path))
                    if len(document_sections) < 400:
                        for section in parser.parse_markdown(root, path):
                            document_sections.append(
                                {
                                    "path": section.path,
                                    "heading": section.heading,
                                    "level": section.level,
                                    "line_start": section.line_start,
                                    "line_end": section.line_end,
                                    "excerpt": section.excerpt,
                                    "heading_path": section.heading_path,
                                    "chunk_kind": section.chunk_kind,
                                    "parser_backend": section.parser_backend,
                                }
                            )
                            if len(document_sections) >= 400:
                                break
                else:
                    relative_path = str(path.relative_to(root))
                    if len(code_files) < 300:
                        code_files.append(relative_path)
                    if len(code_index) < 500:
                        code_index.append(self._code_index_entry(root, path, language))
            if path.name.lower() in {"readme.md", "readme"}:
                readme_present = True
            language = LANGUAGE_BY_SUFFIX.get(suffix)
            if language in {"python", "typescript", "javascript"}:
                module_info = parser.parse(root, path, language)
                if module_info is not None:
                    parsed_modules.append(
                        {
                            "path": module_info.path,
                            "language": module_info.language,
                            "line_start": module_info.line_start,
                            "line_end": module_info.line_end,
                            "classes": module_info.classes,
                            "functions": module_info.functions,
                            "imports": module_info.imports,
                            "import_details": module_info.import_details,
                            "symbols": module_info.symbols,
                            "inheritance": module_info.inheritance,
                            "call_sites": module_info.call_sites,
                            "framework_entries": module_info.framework_entries,
                            "module_doc": module_info.module_doc,
                            "class_docs": module_info.class_docs,
                            "interfaces": module_info.interfaces,
                            "parser_backend": module_info.parser_backend,
                        }
                    )
        parsed_modules.sort(key=lambda module: self._module_priority(str(module["path"])))
        code_intelligence = self._code_intelligence(parser.backend, parsed_modules)

        return RepoScanSummary(
            file_count=file_count,
            dir_count=dir_count,
            top_level_entries=top_level_entries[:25],
            language_counts=dict(language_counter.most_common()),
            readme_present=readme_present,
            source_roots=source_roots,
            code_files=code_files,
            code_index=code_index,
            doc_index=doc_index,
            document_sections=document_sections,
            python_modules=parsed_modules[:200],
            code_intelligence=code_intelligence["summary"],
            module_dependencies=code_intelligence["module_dependencies"],
            inheritance_graph=code_intelligence["inheritance_graph"],
            call_index=code_intelligence["call_index"],
            framework_entries=code_intelligence["framework_entries"],
        )

    def _code_index_entry(self, root: Path, path: Path, language: str) -> dict:
        relative_path = str(path.relative_to(root))
        try:
            raw = path.read_bytes()
        except OSError:
            raw = b""
        try:
            line_count = len(raw.decode("utf-8").splitlines())
        except UnicodeDecodeError:
            line_count = 0
        return {
            "path": relative_path,
            "language": language,
            "line_count": line_count,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _document_index_entry(self, root: Path, path: Path) -> dict:
        relative_path = str(path.relative_to(root))
        try:
            raw = path.read_bytes()
        except OSError:
            raw = b""
        try:
            line_count = len(raw.decode("utf-8").splitlines())
        except UnicodeDecodeError:
            line_count = 0
        return {
            "path": relative_path,
            "content_type": "markdown",
            "line_count": line_count,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _is_excluded(self, root: Path, path: Path, exclude_patterns: list[str]) -> bool:
        relative = self._relative_posix(root, path)
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            return True
        return any(self._matches_pattern(relative, path.name, pattern) for pattern in exclude_patterns)

    def _is_included(self, root: Path, path: Path, include_patterns: list[str]) -> bool:
        if not include_patterns:
            return True
        relative = self._relative_posix(root, path)
        return any(self._matches_pattern(relative, path.name, pattern) for pattern in include_patterns)

    def _matches_pattern(self, relative: str, name: str, pattern: str) -> bool:
        normalized = pattern.strip().strip("/")
        if not normalized:
            return False
        return (
            fnmatch(relative, normalized)
            or fnmatch(name, normalized)
            or relative.startswith(f"{normalized}/")
        )

    def _relative_posix(self, root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()

    def _suggested_exclude_patterns(
        self,
        root: Path,
        include_patterns: list[str],
        exclude_patterns: list[str],
    ) -> list[str]:
        suggestions: list[str] = []
        for entry in sorted(AGENT_LOCAL_STATE_ENTRIES):
            path = root / entry
            if not path.exists():
                continue
            if self._is_excluded(root, path, exclude_patterns):
                continue
            if not self._is_included(root, path, include_patterns):
                continue
            suggestions.append(entry)
        return suggestions

    def _warnings(self, suggested_exclude_patterns: list[str]) -> list[str]:
        if not suggested_exclude_patterns:
            return []
        entries = ", ".join(suggested_exclude_patterns)
        return [
            "Repository contains local/agent state entries that may not belong in memory: "
            f"{entries}. They are excluded from the clean repo ingest unless options.force=true is used."
        ]

    def _fingerprint(self, summary: RepoScanSummary) -> str:
        parts = [
            str(summary.file_count),
            str(summary.dir_count),
            ",".join(summary.top_level_entries),
            ",".join(f"{key}:{value}" for key, value in sorted(summary.language_counts.items())),
            str(summary.readme_present),
            ",".join(summary.source_roots),
            ",".join(f'{item["path"]}:{item["sha256"]}' for item in summary.code_index[:300]),
            ",".join(f'{item["path"]}:{item["sha256"]}' for item in summary.doc_index[:300]),
            ",".join(
                f'{module["path"]}:'
                f'{",".join(symbol["name"] for symbol in module.get("symbols", [])[:20])}'
                for module in summary.python_modules[:120]
            ),
        ]
        return "|".join(parts)

    def _segments(self, root: Path, summary: RepoScanSummary) -> list[SourceSegment]:
        segments: list[SourceSegment] = []
        for entry in summary.top_level_entries[:20]:
            segments.append(
                SourceSegment(
                    segment_id=slugify(entry),
                    locator={"kind": "path", "path": str(root / entry)},
                    excerpt=entry,
                    hash=entry,
                )
            )
        for module in summary.python_modules[:120]:
            segments.append(
                SourceSegment(
                    segment_id=slugify(module["path"]),
                    locator={
                        "kind": "code_module",
                        "path": module["path"],
                        "line_start": module.get("line_start", 1),
                        "line_end": module.get("line_end", 1),
                    },
                    excerpt=self._module_excerpt(module),
                    hash=module["path"],
                )
            )
        for section in summary.document_sections[:120]:
            segment_key = f'{section["path"]}:{section["line_start"]}:{section["heading"]}'
            segments.append(
                SourceSegment(
                    segment_id=f"doc-{slugify(segment_key)}",
                    locator={
                        "kind": "document_section",
                        "path": section["path"],
                        "heading": section["heading"],
                        "heading_path": section.get("heading_path", []),
                        "chunk_kind": section.get("chunk_kind", "section"),
                        "line_start": section["line_start"],
                        "line_end": section["line_end"],
                    },
                    excerpt=section["excerpt"],
                    hash=hashlib.sha256(section["excerpt"].encode("utf-8")).hexdigest(),
                )
            )
        for entry in summary.code_index[:120]:
            code_file = entry["path"]
            path = root / code_file
            excerpt, line_end = self._code_excerpt(path)
            if not excerpt:
                continue
            segments.append(
                SourceSegment(
                    segment_id=f"code-{slugify(code_file)}",
                    locator={
                        "kind": "code_file",
                        "path": code_file,
                        "line_start": 1,
                        "line_end": line_end,
                    },
                    excerpt=excerpt,
                    hash=entry["sha256"],
                )
            )
        return segments

    def _module_excerpt(self, module: dict) -> str:
        symbol_names = [symbol["name"] for symbol in module.get("symbols", [])[:12] if symbol.get("name")]
        parts = [
            f'{module["path"]}: {module["language"]} module',
            f'classes={len(module["classes"])}, functions={len(module["functions"])}',
        ]
        if symbol_names:
            parts.append(f'symbols={", ".join(symbol_names)}')
        return "; ".join(parts)

    def _code_excerpt(self, path: Path) -> tuple[str, int]:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return "", 0
        lines = text.splitlines()
        excerpt_lines = lines[:80]
        return "\n".join(excerpt_lines)[:4000], len(excerpt_lines)

    def _module_nodes(self, root: Path, summary: RepoScanSummary, timestamp: str) -> list[Node]:
        nodes: list[Node] = []
        for entry in summary.top_level_entries[:10]:
            path = root / entry
            if path.is_dir():
                kind = "module"
                summary_text = f"Top-level directory in {root.name}."
            elif path.suffix.lower() == ".md":
                kind = "document"
                summary_text = f"Top-level document in {root.name}."
            else:
                kind = "component"
                summary_text = f"Top-level file in {root.name}."
            nodes.append(
                Node(
                    id=stable_id("node", f"node|repo_entry|{root}|{entry}"),
                    kind=kind,
                    name=entry,
                    slug=slugify(entry),
                    identity_key=f"node|repo_entry|{root}|{entry}",
                    aliases=[],
                    summary=summary_text,
                    status="active",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        for module in summary.python_modules[:120]:
            stem = self._module_name(module["path"])
            language_label = self._language_label(module["language"])
            symbol_names = [symbol["name"] for symbol in module.get("symbols", [])[:8] if symbol.get("name")]
            symbol_summary = f" Symbols: {', '.join(symbol_names)}." if symbol_names else ""
            nodes.append(
                Node(
                    id=stable_id("node", f'node|module|{root}|{module["path"]}'),
                    kind="module",
                    name=stem,
                    slug=slugify(stem),
                    identity_key=f'node|module|{root}|{module["path"]}',
                    aliases=[module["path"]],
                    summary=(
                        f'{language_label} module at {module["path"]} with '
                        f'{len(module["classes"])} classes and {len(module["functions"])} functions.'
                        f"{symbol_summary}"
                    ),
                    status="active",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        return nodes

    def _module_name(self, module_path: str) -> str:
        return str(Path(module_path).with_suffix("")).replace("/", ".")

    def _code_intelligence(self, parser_backend: str, modules: list[dict]) -> dict:
        module_by_name = self._module_lookup(modules)
        class_by_name = self._class_lookup(modules)
        module_dependencies = self._module_dependencies(modules, module_by_name)
        inheritance_graph = self._inheritance_graph(modules, class_by_name)
        call_index = self._call_index(modules)
        framework_entries = self._framework_entries(modules)
        return {
            "summary": {
                "schema_version": "code_intelligence.v1",
                "parser_backend": parser_backend,
                "module_count": len(modules),
                "symbol_count": sum(len(module.get("symbols", [])) for module in modules),
                "dependency_count": len(module_dependencies),
                "inheritance_count": len(inheritance_graph),
                "call_site_count": len(call_index),
                "framework_entry_count": len(framework_entries),
                "limitations": [
                    "partial_static_analysis",
                    "dynamic_dispatch_not_resolved",
                    "runtime_configuration_not_evaluated",
                ],
            },
            "module_dependencies": module_dependencies[:500],
            "inheritance_graph": inheritance_graph[:300],
            "call_index": call_index[:500],
            "framework_entries": framework_entries[:200],
        }

    def _module_lookup(self, modules: list[dict]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for module in modules:
            path = str(module["path"])
            dotted = self._module_name(path)
            lookup[dotted] = path
            if dotted.endswith(".__init__"):
                lookup[dotted.removesuffix(".__init__")] = path
        return lookup

    def _class_lookup(self, modules: list[dict]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for module in modules:
            path = str(module["path"])
            module_name = self._module_name(path)
            for class_name in module.get("classes", []):
                lookup.setdefault(str(class_name), path)
                lookup[f"{module_name}.{class_name}"] = path
        return lookup

    def _module_dependencies(self, modules: list[dict], module_by_name: dict[str, str]) -> list[dict]:
        dependencies: list[dict] = []
        for module in modules:
            from_path = str(module["path"])
            from_module = self._module_name(from_path)
            for detail in module.get("import_details", []):
                imported_module = self._resolve_relative_import(from_module, detail)
                imported_name = detail.get("imported_name")
                to_path = self._resolve_import_path(imported_module, imported_name, module_by_name)
                dependencies.append(
                    {
                        "from_path": from_path,
                        "imported_module": imported_module,
                        "imported_name": imported_name,
                        "alias": detail.get("alias"),
                        "line_start": detail.get("line_start"),
                        "to_path": to_path,
                        "resolution": "internal" if to_path else "external_or_unresolved",
                    }
                )
        dependencies.sort(key=lambda item: (item["from_path"], item["imported_module"], str(item.get("imported_name"))))
        return dependencies

    def _resolve_relative_import(self, from_module: str, detail: dict) -> str:
        module = str(detail.get("module") or "")
        level = int(detail.get("level") or 0)
        if level <= 0:
            return module
        package_parts = from_module.split(".")[:-1]
        if level > 1:
            package_parts = package_parts[: -(level - 1)] if level - 1 <= len(package_parts) else []
        parts = [*package_parts]
        if module:
            parts.extend(module.split("."))
        return ".".join(part for part in parts if part)

    def _resolve_import_path(
        self,
        imported_module: str,
        imported_name: str | None,
        module_by_name: dict[str, str],
    ) -> str | None:
        if imported_module in module_by_name:
            return module_by_name[imported_module]
        if imported_name:
            candidate = f"{imported_module}.{imported_name}" if imported_module else imported_name
            if candidate in module_by_name:
                return module_by_name[candidate]
        return None

    def _inheritance_graph(self, modules: list[dict], class_by_name: dict[str, str]) -> list[dict]:
        edges: list[dict] = []
        for module in modules:
            path = str(module["path"])
            for edge in module.get("inheritance", []):
                base = str(edge.get("base") or "")
                target_path = class_by_name.get(base) or class_by_name.get(base.split(".")[-1])
                edges.append(
                    {
                        "path": path,
                        "class": edge.get("class"),
                        "base": base,
                        "line_start": edge.get("line_start"),
                        "target_path": target_path,
                        "resolution": "local_symbol" if target_path else "external_or_unresolved",
                    }
                )
        edges.sort(key=lambda item: (item["path"], str(item.get("class")), str(item.get("base"))))
        return edges

    def _call_index(self, modules: list[dict]) -> list[dict]:
        calls: list[dict] = []
        for module in modules:
            path = str(module["path"])
            for call in module.get("call_sites", []):
                calls.append(
                    {
                        "path": path,
                        "caller": call.get("caller"),
                        "callee": call.get("callee"),
                        "line_start": call.get("line_start"),
                        "kind": call.get("kind", "call"),
                        "analysis": call.get("analysis", "partial_static_analysis"),
                    }
                )
        calls.sort(key=lambda item: (item["path"], int(item.get("line_start") or 0), str(item.get("caller"))))
        return calls

    def _framework_entries(self, modules: list[dict]) -> list[dict]:
        entries: list[dict] = []
        for module in modules:
            path = str(module["path"])
            for entry in module.get("framework_entries", []):
                entries.append({"path": path, **entry})
        entries.sort(key=lambda item: (item["path"], str(item.get("framework")), int(item.get("line_start") or 0)))
        return entries

    def _module_priority(self, module_path: str) -> tuple[int, str]:
        if "/application/" in module_path:
            return 0, module_path
        if "/interfaces/" in module_path:
            return 1, module_path
        if "/adapters/" in module_path:
            return 2, module_path
        if "/domain/" in module_path:
            return 3, module_path
        if "/infrastructure/" in module_path:
            return 4, module_path
        if "/projections/" in module_path:
            return 5, module_path
        if module_path.startswith("src/"):
            return 6, module_path
        if module_path.startswith("tests/"):
            return 9, module_path
        return 8, module_path

    def _language_label(self, language: str) -> str:
        labels = {
            "python": "Python",
            "typescript": "TypeScript",
            "javascript": "JavaScript",
        }
        return labels.get(language, language.title())

    def _default_evidence(self, source: Source) -> list[EvidenceRef]:
        if not source.segments:
            return []
        return [EvidenceRef(source_id=source.id, segment_id=segment.segment_id) for segment in source.segments[:3]]

    def _knowledge(
        self,
        root: Path,
        repo_node: Node,
        summary: RepoScanSummary,
        evidence_refs: list[EvidenceRef],
        timestamp: str,
    ) -> list[Knowledge]:
        items: list[Knowledge] = []
        if summary.source_roots:
            items.append(
                Knowledge(
                    id=stable_id("know", f"knowledge|repo|{root}|source_roots"),
                    kind="fact",
                    title=f"{root.name} source roots",
                    summary=f"Primary source roots detected: {', '.join(summary.source_roots)}.",
                    identity_key=f"knowledge|repo|{root}|source_roots",
                    subject_refs=[repo_node.id],
                    evidence_refs=evidence_refs,
                    payload={
                        "subject": repo_node.id,
                        "predicate": "source_roots",
                        "value": summary.source_roots,
                        "object": None,
                    },
                    status="candidate",
                    confidence=0.65,
                    valid_from=timestamp,
                    valid_until=None,
                    last_verified_at=timestamp,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        return items
