from __future__ import annotations

from pathlib import Path
import re
import shutil

from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.infrastructure.storage.fs_utils import ensure_directory
from wiki_memory.infrastructure.storage.paths import StoragePaths


PROJECTION_DIRS = {
    "source": "sources",
    "node": "nodes",
    "knowledge": "knowledge",
    "activity": "activities",
    "work_item": "work_items",
}


class MarkdownProjector:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.paths = StoragePaths(self.root)
        self.repository = FsObjectRepository(self.root)
        self.wiki_root = self.paths.projections_root / "wiki"
        self.debug_root = self.paths.projections_root / "debug"

    def rebuild(self) -> dict:
        ensure_directory(self.wiki_root)
        ensure_directory(self.debug_root)
        written: list[str] = []

        for object_type, directory in PROJECTION_DIRS.items():
            target_dir = self.debug_root / directory
            ensure_directory(target_dir)
            for existing_path in target_dir.glob("*.md"):
                existing_path.unlink()
            for obj in self.repository.list(object_type):
                path = target_dir / f"{obj['id']}.md"
                path.write_text(self._render(object_type, obj), encoding="utf-8")
                written.append(str(path))

        written.extend(self._write_obsidian_views())

        for stale_root_page in ("index.md", "overview.md"):
            stale_path = self.wiki_root / stale_root_page
            if stale_path.exists():
                stale_path.unlink()

        index_path = self.debug_root / "index.md"
        overview_path = self.debug_root / "overview.md"
        index_path.write_text(self._render_index(), encoding="utf-8")
        overview_path.write_text(self._render_overview(), encoding="utf-8")
        written.extend([str(index_path), str(overview_path)])

        return {
            "status": "completed",
            "written": written,
            "count": len(written),
        }

    def _write_obsidian_views(self) -> list[str]:
        written: list[str] = []
        for directory in ("Readable", "Maps", "_raw", *PROJECTION_DIRS.values()):
            target = self.wiki_root / directory
            if target.exists():
                shutil.rmtree(target)

        for directory in ("Projects", "Knowledge", "Sources", "Activities", "Work_Items"):
            target = self.wiki_root / directory
            ensure_directory(target)
            for existing_path in target.glob("*.md"):
                existing_path.unlink()

        home_path = self.wiki_root / "Home.md"
        home_path.write_text(self._render_home(), encoding="utf-8")
        written.append(str(home_path))

        written.extend(self._write_project_pages())

        category_dirs = {
            "source": "Sources",
            "knowledge": "Knowledge",
            "activity": "Activities",
            "work_item": "Work_Items",
        }
        for object_type, directory in category_dirs.items():
            readable_dir = self.wiki_root / directory
            ensure_directory(readable_dir)
            for obj in self.repository.list(object_type):
                title = str(obj.get("title") or obj.get("name") or obj["id"])
                path = readable_dir / f"{self._safe_filename(title)}.md"
                path.write_text(self._render_readable_page(object_type, obj, title), encoding="utf-8")
                written.append(str(path))
        return written

    def _render(self, object_type: str, obj: dict) -> str:
        frontmatter = self._frontmatter(obj)
        body = self._body(object_type, obj)
        return f"---\n{frontmatter}\n---\n\n{body}\n"

    def _frontmatter(self, obj: dict) -> str:
        lines = []
        for key in ("id", "kind", "status", "lifecycle_state", "created_at", "updated_at"):
            value = obj.get(key)
            if value is not None:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _body(self, object_type: str, obj: dict) -> str:
        if object_type == "source":
            return self._render_source(obj)
        if object_type == "node":
            return self._render_node(obj)
        if object_type == "knowledge":
            return self._render_knowledge(obj)
        if object_type == "activity":
            return self._render_activity(obj)
        if object_type == "work_item":
            return self._render_work_item(obj)
        return f"# {obj['id']}\n"

    def _render_source(self, obj: dict) -> str:
        lines = [f"# {obj.get('title') or obj['id']}", "", "## Origin", "", f"`{obj.get('origin')}`", ""]
        payload = obj.get("payload", {})
        if payload:
            lines.extend(["## Payload", "", "```json", str(payload), "```", ""])
        segments = obj.get("segments", [])
        if segments:
            lines.extend(["## Segments", ""])
            for segment in segments:
                lines.append(f"- `{segment['segment_id']}`: {segment.get('excerpt', '')}")
        return "\n".join(lines)

    def _render_node(self, obj: dict) -> str:
        lines = [f"# {obj.get('name') or obj['id']}", ""]
        if obj.get("summary"):
            lines.extend([obj["summary"], ""])
        if obj.get("aliases"):
            lines.extend(["## Aliases", ""])
            lines.extend([f"- {alias}" for alias in obj["aliases"]])
        return "\n".join(lines)

    def _render_knowledge(self, obj: dict) -> str:
        lines = [f"# {obj.get('title') or obj['id']}", ""]
        if obj.get("summary"):
            lines.extend([obj["summary"], ""])
        lines.extend([f"- confidence: {obj.get('confidence', 0.0)}", f"- kind: {obj.get('kind')}", ""])
        payload = obj.get("payload", {})
        if payload:
            lines.extend(["## Payload", "", "```json", str(payload), "```", ""])
        refs = obj.get("subject_refs", [])
        if refs:
            lines.extend(["## Subjects", ""])
            lines.extend([f"- `{ref}`" for ref in refs])
            lines.append("")
        evidence_refs = obj.get("evidence_refs", [])
        if evidence_refs:
            lines.extend(["## Evidence", ""])
            lines.extend([f"- `{ref.get('source_id')}#{ref.get('segment_id')}`" for ref in evidence_refs])
        return "\n".join(lines)

    def _render_activity(self, obj: dict) -> str:
        lines = [f"# {obj.get('title') or obj['id']}", ""]
        if obj.get("summary"):
            lines.extend([obj["summary"], ""])
        for key in ("started_at", "ended_at"):
            if obj.get(key):
                lines.append(f"- {key}: {obj[key]}")
        lines.append("")
        for section, field in (
            ("Related Nodes", "related_node_refs"),
            ("Related Work Items", "related_work_item_refs"),
            ("Sources", "source_refs"),
            ("Produced Objects", "produced_object_refs"),
            ("Artifacts", "artifact_refs"),
        ):
            values = obj.get(field, [])
            if values:
                lines.extend([f"## {section}", ""])
                lines.extend([f"- `{value}`" for value in values])
                lines.append("")
        return "\n".join(lines)

    def _render_work_item(self, obj: dict) -> str:
        lines = [f"# {obj.get('title') or obj['id']}", ""]
        if obj.get("summary"):
            lines.extend([obj["summary"], ""])
        for key in ("kind", "status", "priority", "resolution", "due_at"):
            value = obj.get(key)
            if value:
                lines.append(f"- {key}: {value}")
        lines.append("")
        for section, field in (
            ("Related Nodes", "related_node_refs"),
            ("Related Knowledge", "related_knowledge_refs"),
            ("Sources", "source_refs"),
            ("Depends On", "depends_on"),
            ("Blocked By", "blocked_by"),
            ("Children", "child_refs"),
        ):
            values = obj.get(field, [])
            if values:
                lines.extend([f"## {section}", ""])
                lines.extend([f"- `{value}`" for value in values])
                lines.append("")
        if obj.get("parent_ref"):
            lines.extend(["## Parent", "", f"- `{obj['parent_ref']}`", ""])
        return "\n".join(lines)

    def _render_index(self) -> str:
        lines = ["# Wiki Index", ""]
        for object_type, directory in PROJECTION_DIRS.items():
            objects = self.repository.list(object_type)
            lines.extend([f"## {directory.title()}", ""])
            if not objects:
                lines.append("- (none)")
            else:
                for obj in objects:
                    title = obj.get("title") or obj.get("name") or obj["id"]
                    lines.append(f"- `{obj['id']}`: {title}")
            lines.append("")
        return "\n".join(lines)

    def _render_overview(self) -> str:
        counts = {
            object_type: len(self.repository.list(object_type))
            for object_type in PROJECTION_DIRS
        }
        lines = [
            "# Wiki Overview",
            "",
            "This wiki is a derived projection of the semantic object store.",
            "",
            f"- sources: {counts['source']}",
            f"- nodes: {counts['node']}",
            f"- knowledge items: {counts['knowledge']}",
            f"- activities: {counts['activity']}",
            f"- work items: {counts['work_item']}",
        ]
        return "\n".join(lines) + "\n"

    def _render_home(self) -> str:
        counts = {object_type: len(self.repository.list(object_type)) for object_type in PROJECTION_DIRS}
        project_links = []
        for node in self._project_nodes():
            title = str(node.get("name") or node.get("title") or node["id"])
            project_links.append(f"- [[Projects/{self._safe_filename(title)}|{title}]]")
        if not project_links:
            project_links.append("- (none)")
        return "\n".join(
            [
                "# Wiki Memory Home",
                "",
                "Start here when opening this vault in Obsidian.",
                "",
                "## Projects",
                "",
                *project_links,
                "",
                "## Counts",
                "",
                f"- Sources: {counts['source']}",
                f"- Nodes: {counts['node']}",
                f"- Knowledge: {counts['knowledge']}",
                f"- Activities: {counts['activity']}",
                f"- Work items: {counts['work_item']}",
                "",
                "## Readable Views",
                "",
                "- [[Knowledge]]",
                "- [[Sources]]",
                "- [[Activities]]",
                "- [[Work_Items]]",
                "",
                "## Editing Boundary",
                "",
                "Use MCP tools for durable edits. This vault is a generated reading view.",
            ]
        ) + "\n"

    def _write_project_pages(self) -> list[str]:
        written: list[str] = []
        project_dir = self.wiki_root / "Projects"
        for node in self._project_nodes():
            title = str(node.get("name") or node.get("title") or node["id"])
            path = project_dir / f"{self._safe_filename(title)}.md"
            path.write_text(self._render_project_page(node, title), encoding="utf-8")
            written.append(str(path))
        return written

    def _project_nodes(self) -> list[dict]:
        return [node for node in self.repository.list("node") if node.get("kind") in {"project", "repo"}]

    def _render_project_page(self, node: dict, title: str) -> str:
        repo_source = self._source_for_repo_title(title)
        lines = [
            f"# {title}",
            "",
            "## What This Is",
            "",
            str(node.get("summary") or "Project memory page generated from wiki-memory objects."),
            "",
            "## Repository Map",
            "",
        ]
        aliases = node.get("aliases") or []
        if aliases:
            lines.extend([f"- Alias: {alias}" for alias in aliases])
        else:
            lines.append("- No aliases recorded.")
        if repo_source is not None:
            lines.extend(self._render_code_interfaces(repo_source))
        lines.extend(
            [
                "",
                "## Machine Data",
                "",
                f"- Object ID: `{node['id']}`",
                f"- Kind: `{node.get('kind', 'node')}`",
                f"- Status: `{node.get('status', 'unknown')}`",
                "",
                "> Durable edits should go through MCP. Debug object mirrors live outside this vault.",
                "",
            ]
        )
        return "\n".join(lines)

    def _source_for_repo_title(self, title: str) -> dict | None:
        for source in self.repository.list("source"):
            if source.get("kind") != "repo":
                continue
            payload = source.get("payload", {})
            repo_name = payload.get("repo_name") if isinstance(payload, dict) else None
            if repo_name == title or source.get("title") == title:
                return source
        return None

    def _render_code_interfaces(self, source: dict) -> list[str]:
        payload = source.get("payload", {})
        if not isinstance(payload, dict):
            return []
        modules = payload.get("python_modules", [])
        if not modules:
            return []
        lines = ["", "## Code Interfaces", ""]
        for module in modules[:30]:
            path = module.get("path")
            if not path:
                continue
            lines.append(f"### `{path}`")
            classes = module.get("classes") or []
            functions = module.get("functions") or []
            imports = module.get("imports") or []
            if classes:
                lines.append(f"- Classes: {', '.join(f'`{name}`' for name in classes[:12])}")
            if functions:
                lines.append(f"- Functions: {', '.join(f'`{name}`' for name in functions[:20])}")
            if imports:
                lines.append(f"- Imports: {', '.join(f'`{name}`' for name in imports[:10])}")
            if not classes and not functions and not imports:
                lines.append("- No public interfaces detected.")
            lines.append("")
        return lines

    def _render_readable_page(self, object_type: str, obj: dict, title: str) -> str:
        lines = [
            f"# {title}",
            "",
            f"> Human-readable page generated from `{obj['id']}`.",
            "",
            f"- Type: `{object_type}`",
            f"- Kind: `{obj.get('kind', object_type)}`",
            f"- Status: `{obj.get('status') or obj.get('lifecycle_state') or 'unknown'}`",
            "",
        ]
        summary = obj.get("summary")
        if summary:
            lines.extend(["## Summary", "", str(summary), ""])
        if object_type == "source":
            payload = obj.get("payload", {})
            if obj.get("kind") == "repo" and isinstance(payload, dict):
                code_files = payload.get("code_files", [])
                if code_files:
                    lines.extend(["## Code Files", ""])
                    lines.extend([f"- `{path}`" for path in code_files[:80]])
                    lines.append("")
                lines.extend(self._render_code_interfaces(obj))
            if isinstance(payload, dict) and payload.get("text"):
                lines.extend(["## Text Preview", "", str(payload["text"])[:1200], ""])
        return "\n".join(lines)

    def _safe_filename(self, value: str) -> str:
        value = re.sub(r'[\\/:*?"<>|#^\[\]]+', "-", value).strip()
        value = re.sub(r"\s+", " ", value)
        return value[:120] or "untitled"
