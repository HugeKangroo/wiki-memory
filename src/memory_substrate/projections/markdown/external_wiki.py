from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from memory_substrate.infrastructure.config.repository import MemoryConfigRepository
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.infrastructure.storage.fs_utils import ensure_directory, read_json, write_json
from memory_substrate.projections.markdown.frontmatter import render_frontmatter
from memory_substrate.projections.markdown.projector import MarkdownProjector


MANIFEST_NAME = ".memory-substrate-projection.json"


class ExternalWikiProjectionService:
    """Render and inspect one configured external wiki projection target."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.config = MemoryConfigRepository(self.root)
        self.repository = FsObjectRepository(self.root)
        self.projector = MarkdownProjector(self.root)

    def render(self) -> dict[str, Any]:
        """Render canonical memory into the configured external wiki target.

        Returns:
            Projection render result with written files, manifest path, stale removals, and conflicts.
        """
        target, format_name = self._configured_target()
        ensure_directory(target)
        manifest_path = target / MANIFEST_NAME
        previous_manifest = self._read_manifest(manifest_path)
        previous_files = self._manifest_files(previous_manifest)
        generated = self._generated_pages(format_name)
        written: list[str] = []
        removed: list[str] = []
        conflicts: list[dict[str, Any]] = []
        next_files: dict[str, dict[str, Any]] = {}

        for rel_path, previous in previous_files.items():
            if rel_path in generated:
                continue
            path = self._target_file(target, rel_path)
            if path.exists():
                path.unlink()
                removed.append(rel_path)

        for rel_path, page in generated.items():
            path = self._target_file(target, rel_path)
            content = str(page["content"])
            content_hash = self._hash_text(content)
            previous = previous_files.get(rel_path)
            if path.exists() and previous is None:
                conflicts.append(
                    {
                        "kind": "unmanaged_path_conflict",
                        "path": rel_path,
                        "summary": "Target path already exists but is not listed in the Memory Substrate projection manifest.",
                    }
                )
                continue
            if path.exists() and previous is not None and self._hash_file(path) != previous.get("hash"):
                conflicts.append(
                    {
                        "kind": "modified_generated_file",
                        "path": rel_path,
                        "summary": "Previously generated projection file has local edits; reconcile before overwriting.",
                    }
                )
                next_files[rel_path] = previous
                continue
            ensure_directory(path.parent)
            path.write_text(content, encoding="utf-8")
            written.append(rel_path)
            next_files[rel_path] = self._manifest_entry(rel_path, page, content_hash)

        manifest = {
            "schema_version": 1,
            "format": format_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files": [next_files[path] for path in sorted(next_files)],
        }
        write_json(manifest_path, manifest)
        return {
            "status": "completed_with_conflicts" if conflicts else "completed",
            "target_path": str(target),
            "format": format_name,
            "manifest_path": str(manifest_path),
            "written": written,
            "removed": removed,
            "conflicts": conflicts,
            "count": len(written),
            "warnings": ["projection_conflicts_require_reconcile"] if conflicts else [],
        }

    def reconcile(self) -> dict[str, Any]:
        """Report differences from the configured external wiki without mutating memory.

        Returns:
            Reconcile report with modified generated files and unmanaged markdown candidates.
        """
        target, format_name = self._configured_target()
        manifest_path = target / MANIFEST_NAME
        manifest = self._read_manifest(manifest_path)
        manifest_files = self._manifest_files(manifest)
        conflicts: list[dict[str, Any]] = []
        remember_candidates: list[dict[str, Any]] = []

        for rel_path, entry in manifest_files.items():
            path = self._target_file(target, rel_path)
            if not path.exists():
                conflicts.append(
                    {
                        "kind": "missing_generated_file",
                        "path": rel_path,
                        "summary": "Manifest lists a generated projection file that is missing from the target.",
                    }
                )
                continue
            if self._hash_file(path) != entry.get("hash"):
                conflicts.append(
                    {
                        "kind": "modified_generated_file",
                        "path": rel_path,
                        "summary": "Generated projection file differs from the manifest hash.",
                    }
                )

        if target.exists():
            for path in sorted(target.rglob("*.md")):
                rel_path = self._relative_path(target, path)
                if rel_path in manifest_files:
                    continue
                remember_candidates.append(self._remember_candidate(target, rel_path, path))

        return {
            "status": "completed",
            "target_path": str(target),
            "format": format_name,
            "manifest_path": str(manifest_path),
            "canonical_mutation": False,
            "conflicts": conflicts,
            "remember_candidates": remember_candidates,
            "counts": {
                "manifest_files": len(manifest_files),
                "conflicts": len(conflicts),
                "remember_candidates": len(remember_candidates),
            },
            "next_actions": [
                "review_projection_conflicts",
                "ingest_or_remember_external_wiki_candidates_after_review",
                "rerun_render_projection_after_conflicts_are_resolved",
            ],
        }

    def _configured_target(self) -> tuple[Path, str]:
        config = self.config.wiki_projection()
        if not config:
            raise ValueError("wiki_projection is not configured. Use memory_maintain configure first.")
        return Path(config["path"]).expanduser().resolve(), config["format"]

    def _generated_pages(self, format_name: str) -> dict[str, dict[str, Any]]:
        if format_name != "obsidian":
            raise ValueError(f"Unsupported wiki projection format: {format_name}")
        pages: dict[str, dict[str, Any]] = {
            "Home.md": {
                "content": self._with_projection_frontmatter(
                    self.projector._render_home(),
                    object_type="index",
                    object_id="external-wiki-home",
                    title="Memory Substrate Home",
                ),
                "object_type": "index",
                "object_id": "external-wiki-home",
            }
        }
        for node in self.projector._project_nodes():
            title = str(node.get("name") or node.get("title") or node["id"])
            rel_path = f"Projects/{self.projector._safe_filename(title)}.md"
            pages[rel_path] = {
                "content": self._with_projection_frontmatter(
                    self.projector._render_project_page(node, title),
                    object_type="node",
                    object_id=str(node["id"]),
                    title=title,
                ),
                "object_type": "node",
                "object_id": str(node["id"]),
            }

        category_dirs = {
            "source": "Sources",
            "knowledge": "Knowledge",
            "activity": "Activities",
            "work_item": "Work_Items",
        }
        for object_type, directory in category_dirs.items():
            for obj in self.repository.list(object_type):
                title = str(obj.get("title") or obj.get("name") or obj["id"])
                rel_path = f"{directory}/{self.projector._safe_filename(title)}.md"
                pages[rel_path] = {
                    "content": self._with_projection_frontmatter(
                        self.projector._render_readable_page(object_type, obj, title),
                        object_type=object_type,
                        object_id=str(obj["id"]),
                        title=title,
                    ),
                    "object_type": object_type,
                    "object_id": str(obj["id"]),
                }
        return pages

    def _with_projection_frontmatter(self, body: str, *, object_type: str, object_id: str, title: str) -> str:
        metadata = {
            "memory_substrate_projection": True,
            "projection_schema": 1,
            "projection_format": "obsidian",
            "object_type": object_type,
            "object_id": object_id,
            "title": title,
        }
        return f"---\n{render_frontmatter(metadata)}\n---\n\n{body.rstrip()}\n"

    def _remember_candidate(self, target: Path, rel_path: str, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        title = self._title_from_markdown(text) or Path(rel_path).stem
        summary = self._summary_from_markdown(text)
        return {
            "path": rel_path,
            "title": title,
            "summary": summary,
            "suggested_memory": {
                "mode": "knowledge",
                "kind": "note",
                "status": "candidate",
                "input_data": {
                    "kind": "note",
                    "title": title,
                    "summary": summary or f"External wiki note from {rel_path}.",
                    "reason": "External wiki reconciliation surfaced this note for reviewed memory import.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:external-wiki"],
                    "status": "candidate",
                    "payload": {
                        "projection_path": rel_path,
                        "projection_target": str(target),
                    },
                },
            },
            "next_actions": [
                "review_note_content",
                "ingest_source_or_call_memory_remember_if_durable",
                "skip_if_not_memory",
            ],
        }

    def _title_from_markdown(self, text: str) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip() or None
        return None

    def _summary_from_markdown(self, text: str) -> str:
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped == "---":
                continue
            if ":" in stripped and not lines:
                continue
            lines.append(stripped)
            if len(" ".join(lines)) > 240:
                break
        return " ".join(lines)[:360]

    def _read_manifest(self, manifest_path: Path) -> dict[str, Any]:
        if not manifest_path.exists():
            return {"schema_version": 1, "files": []}
        return read_json(manifest_path)

    def _manifest_files(self, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for entry in manifest.get("files", []) or []:
            if not isinstance(entry, dict) or not entry.get("path"):
                continue
            result[str(entry["path"])] = entry
        return result

    def _manifest_entry(self, rel_path: str, page: dict[str, Any], content_hash: str) -> dict[str, Any]:
        return {
            "path": rel_path,
            "hash": content_hash,
            "object_type": page.get("object_type"),
            "object_id": page.get("object_id"),
        }

    def _target_file(self, target: Path, rel_path: str) -> Path:
        path = (target / rel_path).resolve()
        path.relative_to(target)
        return path

    def _relative_path(self, target: Path, path: Path) -> str:
        return path.resolve().relative_to(target.resolve()).as_posix()

    def _hash_file(self, path: Path) -> str:
        return self._hash_text(path.read_text(encoding="utf-8"))

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
