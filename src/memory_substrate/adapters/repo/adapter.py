from __future__ import annotations
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
    python_modules: list[dict]


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
                "python_modules": summary.python_modules,
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
                if language != "markdown" and len(code_files) < 80:
                    code_files.append(str(path.relative_to(root)))
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
                            "classes": module_info.classes,
                            "functions": module_info.functions,
                            "imports": module_info.imports,
                            "module_doc": module_info.module_doc,
                            "class_docs": module_info.class_docs,
                            "interfaces": module_info.interfaces,
                            "parser_backend": module_info.parser_backend,
                        }
                    )
        parsed_modules.sort(key=lambda module: self._module_priority(str(module["path"])))

        return RepoScanSummary(
            file_count=file_count,
            dir_count=dir_count,
            top_level_entries=top_level_entries[:25],
            language_counts=dict(language_counter.most_common()),
            readme_present=readme_present,
            source_roots=source_roots,
            code_files=code_files,
            python_modules=parsed_modules[:60],
        )

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
            f"{entries}. Re-run memory_ingest repo with exclude_patterns to skip them."
        ]

    def _fingerprint(self, summary: RepoScanSummary) -> str:
        parts = [
            str(summary.file_count),
            str(summary.dir_count),
            ",".join(summary.top_level_entries),
            ",".join(f"{key}:{value}" for key, value in sorted(summary.language_counts.items())),
            str(summary.readme_present),
            ",".join(summary.source_roots),
            ",".join(summary.code_files[:40]),
            ",".join(module["path"] for module in summary.python_modules[:10]),
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
        for module in summary.python_modules[:10]:
            segments.append(
                SourceSegment(
                    segment_id=slugify(module["path"]),
                    locator={"kind": "path", "path": str(root / module["path"])},
                    excerpt=f'{module["path"]}: classes={len(module["classes"])}, functions={len(module["functions"])}',
                    hash=module["path"],
                )
            )
        for code_file in summary.code_files[:40]:
            path = root / code_file
            excerpt = self._code_excerpt(path)
            if not excerpt:
                continue
            segments.append(
                SourceSegment(
                    segment_id=f"code-{slugify(code_file)}",
                    locator={"kind": "code_file", "path": code_file},
                    excerpt=excerpt,
                    hash=code_file,
                )
            )
        return segments

    def _code_excerpt(self, path: Path) -> str:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""
        lines = text.splitlines()
        return "\n".join(lines[:80])[:4000]

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
        for module in summary.python_modules[:10]:
            stem = self._module_name(module["path"])
            language_label = self._language_label(module["language"])
            nodes.append(
                Node(
                    id=stable_id("node", f'node|module|{root}|{module["path"]}'),
                    kind="module",
                    name=stem,
                    slug=slugify(stem),
                    identity_key=f'node|module|{root}|{module["path"]}',
                    aliases=[module["path"]],
                    summary=f'{language_label} module with {len(module["classes"])} classes and {len(module["functions"])} functions.',
                    status="active",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        return nodes

    def _module_name(self, module_path: str) -> str:
        return str(Path(module_path).with_suffix("")).replace("/", ".")

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
