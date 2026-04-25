from __future__ import annotations

from pathlib import Path

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

    def rebuild(self) -> dict:
        ensure_directory(self.wiki_root)
        written: list[str] = []

        for object_type, directory in PROJECTION_DIRS.items():
            target_dir = self.wiki_root / directory
            ensure_directory(target_dir)
            for existing_path in target_dir.glob("*.md"):
                existing_path.unlink()
            for obj in self.repository.list(object_type):
                path = target_dir / f"{obj['id']}.md"
                path.write_text(self._render(object_type, obj), encoding="utf-8")
                written.append(str(path))

        index_path = self.wiki_root / "index.md"
        overview_path = self.wiki_root / "overview.md"
        index_path.write_text(self._render_index(), encoding="utf-8")
        overview_path.write_text(self._render_overview(), encoding="utf-8")
        written.extend([str(index_path), str(overview_path)])

        return {
            "status": "completed",
            "written": written,
            "count": len(written),
        }

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
                    lines.append(f"- [{title}]({directory}/{obj['id']}.md)")
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
