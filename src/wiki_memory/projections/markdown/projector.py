from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

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
        self.doxygen_root = self.paths.projections_root / "doxygen"

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
        written.extend(self._write_doxygen_projection())

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

        for directory in ("Projects", "Knowledge", "Sources", "Activities", "Work_Items", "API"):
            target = self.wiki_root / directory
            ensure_directory(target)
            for existing_path in target.rglob("*.md"):
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
                "- [[API_Docs|API Docs]]",
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

    def _write_doxygen_projection(self) -> list[str]:
        repo_source = self._primary_repo_source()
        if repo_source is None:
            return []
        payload = repo_source.get("payload", {})
        origin = repo_source.get("origin", {})
        repo_name = str(payload.get("repo_name") or repo_source.get("title") or "wiki-memory") if isinstance(payload, dict) else str(repo_source.get("title") or "wiki-memory")
        repo_path = Path(str(origin.get("path", ""))) if isinstance(origin, dict) else Path()
        if not repo_path:
            return []

        ensure_directory(self.doxygen_root)
        doxyfile = self.doxygen_root / "Doxyfile"
        doxyfile.write_text(self._render_doxyfile(repo_name, repo_path), encoding="utf-8")

        status = "not generated: doxygen is not installed"
        doxygen = shutil.which("doxygen")
        if doxygen:
            result = subprocess.run(
                [doxygen, str(doxyfile)],
                cwd=str(self.doxygen_root),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            status = "generated" if result.returncode == 0 else f"failed: {result.stderr.strip() or result.stdout.strip()}"

        api_docs = self.wiki_root / "API_Docs.md"
        api_docs.write_text(self._render_doxygen_entry(repo_name, repo_path, status, repo_source), encoding="utf-8")
        written = [str(doxyfile), str(api_docs)]
        written.extend(self._write_obsidian_api_pages(repo_source))
        return written

    def _primary_repo_source(self) -> dict | None:
        for source in self.repository.list("source"):
            if source.get("kind") == "repo":
                return source
        return None

    def _render_doxyfile(self, repo_name: str, repo_path: Path) -> str:
        return "\n".join(
            [
                f'PROJECT_NAME = "{repo_name}"',
                f"INPUT = {repo_path}",
                f"OUTPUT_DIRECTORY = {self.doxygen_root}",
                "HTML_OUTPUT = html",
                "GENERATE_HTML = YES",
                "GENERATE_XML = NO",
                "RECURSIVE = YES",
                "EXTRACT_ALL = YES",
                "EXTRACT_PRIVATE = NO",
                "JAVADOC_AUTOBRIEF = YES",
                "QUIET = YES",
                "WARN_IF_UNDOCUMENTED = NO",
            ]
        ) + "\n"

    def _render_doxygen_entry(self, repo_name: str, repo_path: Path, status: str, repo_source: dict) -> str:
        html_path = self.doxygen_root / "html" / "index.html"
        doxyfile_path = self.doxygen_root / "Doxyfile"
        lines = [
            "# API Docs",
            "",
            f"- Project: `{repo_name}`",
            f"- Source: `{repo_path}`",
            f"- Status: `{status}`",
            f"- Doxyfile: `../doxygen/Doxyfile`",
            f"- HTML entry: `../doxygen/html/index.html`",
            f"- HTML absolute path: `{html_path}`",
            "",
            "## Obsidian API Reference",
            "",
            "- [[API/Home|Obsidian API Reference]]",
        ]
        lines.extend(
            [
                "",
                "## Optional Doxygen HTML",
                "",
                "- [Open Doxygen HTML](../doxygen/html/index.html)",
                f"- [Open Doxygen HTML (file URI)]({html_path.as_uri()})",
                "- [Doxyfile](../doxygen/Doxyfile)",
                f"- [Doxyfile (file URI)]({doxyfile_path.as_uri()})",
                "",
                "> Obsidian reads the API pages above directly. Doxygen HTML is an optional browser artifact.",
                "",
            ]
        )
        return "\n".join(lines)

    def _write_obsidian_api_pages(self, repo_source: dict) -> list[str]:
        payload = repo_source.get("payload", {})
        if not isinstance(payload, dict):
            return []
        modules = payload.get("python_modules", [])
        if not modules:
            return []

        api_root = self.wiki_root / "API"
        modules_root = api_root / "Modules"
        classes_root = api_root / "Classes"
        ensure_directory(modules_root)
        ensure_directory(classes_root)

        written: list[str] = []
        module_links: list[tuple[str, str, str]] = []
        class_pages: dict[str, list[dict]] = {}

        for module in sorted(modules, key=self._module_sort_key)[:30]:
            path = str(module.get("path") or "")
            if not path:
                continue
            category = self._module_category(path)
            slug = self._api_module_slug(category, path)
            module_path = modules_root / f"{slug}.md"
            module_path.write_text(self._render_api_module_page(module, category), encoding="utf-8")
            written.append(str(module_path))
            module_links.append((path, category, slug))

            for class_name in module.get("classes", [])[:12]:
                class_pages.setdefault(str(class_name), []).append(module)

        for class_name, class_modules in sorted(class_pages.items()):
            class_path = classes_root / f"{self._safe_filename(class_name)}.md"
            class_path.write_text(self._render_api_class_page(class_name, class_modules), encoding="utf-8")
            written.append(str(class_path))

        home_path = api_root / "Home.md"
        home_path.write_text(self._render_api_home(module_links, sorted(class_pages)), encoding="utf-8")
        written.append(str(home_path))
        written.extend(self._write_obsidian_css_snippet())
        return written

    def _render_api_home(self, module_links: list[tuple[str, str, str]], class_names: list[str]) -> str:
        categories = self._ordered_api_categories({category for _, category, _ in module_links})
        lines = [
            "# API Reference",
            "",
            "> [!abstract] API Reference",
            "> Obsidian-native API documentation generated from repository ingest.",
            f"> Modules: `{len(module_links)}` | Classes: `{len(class_names)}` | Categories: `{len(categories)}`",
            "",
            "## Modules",
            "",
            "> [!info] Modules",
            "> Public repository modules grouped by coarse architecture category.",
            "",
        ]
        for category in categories:
            lines.extend(["", f"### {category}", ""])
            for path, module_category, slug in module_links:
                if module_category == category:
                    lines.append(f"- [[API/Modules/{slug}|{path}]]")
        lines.extend(["", "## Classes", "", "> [!example] Classes", "> Public classes detected during repository ingest.", ""])
        if class_names:
            lines.extend([f"- [[API/Classes/{self._safe_filename(name)}|{name}]]" for name in class_names])
        else:
            lines.append("- (none)")
        return "\n".join(lines) + "\n"

    def _ordered_api_categories(self, categories: set[str]) -> list[str]:
        priority = {
            "Application": 0,
            "Interface": 1,
            "Adapter": 2,
            "Domain": 3,
            "Infrastructure": 4,
            "Projection": 5,
            "Code": 6,
            "Test": 9,
        }
        return sorted(categories, key=lambda category: (priority.get(category, 8), category))

    def _write_obsidian_css_snippet(self) -> list[str]:
        snippets_root = self.wiki_root / ".obsidian" / "snippets"
        ensure_directory(snippets_root)
        path = snippets_root / "wiki-memory-api.css"
        path.write_text(self._render_obsidian_css_snippet(), encoding="utf-8")
        return [str(path)]

    def _render_obsidian_css_snippet(self) -> str:
        return "\n".join(
            [
                "/* Optional wiki-memory API doc polish for Obsidian. */",
                ".markdown-preview-view .callout[data-callout=\"abstract\"] {",
                "  --callout-color: 72, 96, 120;",
                "}",
                "",
                ".markdown-preview-view .callout[data-callout=\"info\"] {",
                "  --callout-color: 42, 110, 160;",
                "}",
                "",
                ".markdown-preview-view .callout[data-callout=\"example\"] {",
                "  --callout-color: 96, 120, 96;",
                "  margin-block: 0.85rem;",
                "}",
                "",
                ".markdown-preview-view table {",
                "  --table-border-color: var(--background-modifier-border);",
                "  font-size: 0.92em;",
                "}",
                "",
                ".markdown-preview-view code {",
                "  font-size: 0.92em;",
                "}",
                "",
            ]
        )

    def _render_api_module_page(self, module: dict, category: str) -> str:
        path = str(module.get("path") or "")
        lines = [
            f"# {category} Module",
            "",
            "> [!abstract] Module Summary",
            f"> Category: `{category}`",
            f"> Defined in: `{path}`",
            "",
            f"**Defined in:** `{path}`",
        ]
        module_doc = module.get("module_doc")
        if module_doc:
            lines.extend(["", f"**Brief:** {module_doc}"])
        classes = module.get("classes") or []
        if classes:
            lines.append("")
            lines.append("**Classes:** " + ", ".join(f"[[API/Classes/{self._safe_filename(str(name))}|{name}]]" for name in classes[:12]))
            class_docs = module.get("class_docs") or {}
            for name in classes[:12]:
                if class_docs.get(name):
                    lines.append(f"> `{name}`: {class_docs[name]}")
        interfaces = [item for item in module.get("interfaces", []) if self._is_public_interface(item)]
        functions = [item for item in interfaces if item.get("kind") == "function"]
        methods = [item for item in interfaces if item.get("kind") == "method"]
        if functions or methods:
            lines.extend(
                [
                    "",
                    "> [!info] Public Interfaces",
                    f"> Functions: `{len(functions)}` | Methods: `{len(methods)}`",
                ]
            )
        lines.extend(self._render_api_summary_and_details([*functions[:20], *methods[:20]]))
        imports = module.get("imports") or []
        if imports:
            lines.extend(["", "## Imports"])
            lines.extend([f"- `{name}`" for name in imports[:10]])
        return "\n".join(lines) + "\n"

    def _render_api_class_page(self, class_name: str, modules: list[dict]) -> str:
        lines = [
            f"# Class `{class_name}`",
            "",
            "> [!abstract] Class Summary",
            f"> Class: `{class_name}`",
            "",
        ]
        interfaces: list[dict] = []
        for module in modules:
            path = str(module.get("path") or "")
            category = self._module_category(path)
            slug = self._api_module_slug(category, path)
            lines.append(f"- Module: [[API/Modules/{slug}|{path}]]")
            class_doc = (module.get("class_docs") or {}).get(class_name)
            if class_doc:
                lines.extend(["", class_doc, ""])
            interfaces.extend(
                item
                for item in module.get("interfaces", [])
                if item.get("kind") == "method" and str(item.get("name", "")).startswith(f"{class_name}.") and self._is_public_interface(item)
            )
        lines.extend(self._render_api_summary_and_details(interfaces[:30]))
        return "\n".join(lines) + "\n"

    def _render_api_method_card(self, interface: dict) -> list[str]:
        name = str(interface.get("name") or "")
        signature = str(interface.get("signature") or name)
        doc = self._interface_description(interface)
        lines = [
            f"> [!example]- `{name}`",
            f"> Purpose: {doc}",
            ">",
            "> **Declaration**",
            ">",
            f"> `{signature}`",
        ]
        parameters = interface.get("parameters") or []
        if parameters:
            lines.extend(
                [
                    ">",
                    "> **Parameters**",
                    ">",
                    "> | Parameter | Type | Default | Description |",
                    "> | --- | --- | --- | --- |",
                ]
            )
            for parameter in parameters:
                default = "required" if parameter.get("required") else f"`{parameter.get('default') or ''}`"
                annotation = parameter.get("annotation") or "unknown"
                description = parameter.get("description") or "-"
                lines.append(f"> | `{parameter.get('name')}` | `{annotation}` | {default} | {description} |")
        returns = interface.get("returns")
        if returns:
            rendered_return = f"`{returns}`"
            if interface.get("return_description"):
                rendered_return += f" - {interface['return_description']}"
            lines.extend([">", "> **Returns**", ">", f"> {rendered_return}"])
        lines.append("")
        return lines

    def _render_api_summary_and_details(self, interfaces: list[dict]) -> list[str]:
        if not interfaces:
            return []
        lines = ["", "| API | Kind | Brief |", "| --- | --- | --- |"]
        for interface in interfaces:
            brief = interface.get("doc") or "-"
            lines.append(f"| `{interface.get('name')}` | {interface.get('kind')} | {brief} |")
        lines.append("")
        for interface in interfaces:
            lines.extend(self._render_api_method_card(interface))
        return lines

    def _api_module_slug(self, category: str, path: str) -> str:
        return self._safe_filename(f"{category}-{path.replace('/', '-').replace('.', '-')}")

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
        lines = ["", "## API Reference", ""]
        for module in sorted(modules, key=self._module_sort_key)[:30]:
            path = module.get("path")
            if not path:
                continue
            lines.append(f"### {self._module_category(path)} Module")
            lines.extend(["", f"**Defined in:** `{path}`"])
            module_doc = module.get("module_doc")
            if module_doc:
                lines.extend(["", f"**Brief:** {module_doc}"])
            classes = module.get("classes") or []
            interfaces = [item for item in module.get("interfaces", []) if self._is_public_interface(item)]
            functions = [item for item in interfaces if item.get("kind") == "function"]
            methods = [item for item in interfaces if item.get("kind") == "method"]
            imports = module.get("imports") or []
            if classes:
                class_docs = module.get("class_docs") or {}
                lines.append("")
                lines.append(f"**Classes:** {', '.join(f'`{name}`' for name in classes[:12])}")
                class_docs = module.get("class_docs") or {}
                for name in classes[:12]:
                    if class_docs.get(name):
                        lines.append(f"> `{name}`: {class_docs[name]}")
            if functions or methods:
                lines.extend(["", "| API | Kind | Brief |", "| --- | --- | --- |"])
                for interface in [*functions[:20], *methods[:20]]:
                    brief = interface.get("doc") or "-"
                    lines.append(f"| `{interface.get('name')}` | {interface.get('kind')} | {brief} |")
                lines.append("")
                for interface in [*functions[:20], *methods[:20]]:
                    lines.extend(self._render_interface(interface))
            if imports:
                lines.extend(["", "**Imports:**"])
                lines.extend([f"- `{name}`" for name in imports[:10]])
            if not classes and not functions and not methods and not imports:
                lines.append("- No public interfaces detected.")
            lines.append("")
        return lines

    def _is_public_interface(self, interface: dict) -> bool:
        name = str(interface.get("name") or "")
        short_name = name.rsplit(".", 1)[-1]
        return not short_name.startswith("_") or short_name == "__init__"

    def _module_category(self, path: str) -> str:
        if "/application/" in path:
            return "Application"
        if "/interfaces/" in path:
            return "Interface"
        if "/adapters/" in path:
            return "Adapter"
        if "/domain/" in path:
            return "Domain"
        if "/infrastructure/" in path:
            return "Infrastructure"
        if "/projections/" in path:
            return "Projection"
        if path.startswith("tests/"):
            return "Test"
        if path.startswith("src/"):
            return "Application"
        return "Code"

    def _render_interface(self, interface: dict) -> list[str]:
        lines = ["<details>", f"<summary><code>{interface.get('name')}</code></summary>", ""]
        lines.extend(["", f"**Purpose**: {self._interface_description(interface)}"])
        if interface.get("signature"):
            lines.extend(
                [
                    "",
                    "**Declaration**",
                    "",
                    f"`{interface['signature']}`",
                ]
            )
        parameters = interface.get("parameters") or []
        if parameters:
            lines.extend(["", "**Parameters**", "", "| Parameter | Type | Default | Description |", "| --- | --- | --- | --- |"])
            for parameter in parameters:
                default = "required" if parameter.get("required") else f"`{parameter.get('default') or ''}`"
                annotation = parameter.get("annotation") or "unknown"
                description = parameter.get("description") or "-"
                lines.append(f"| `{parameter.get('name')}` | `{annotation}` | {default} | {description} |")
        returns = interface.get("returns")
        if returns:
            return_description = interface.get("return_description")
            rendered_return = f"`{returns}`"
            if return_description:
                rendered_return += f" - {return_description}"
            lines.extend(["", "**Returns**", "", rendered_return])
        lines.extend(["", "</details>", ""])
        return lines

    def _interface_description(self, interface: dict) -> str:
        doc = interface.get("doc")
        if doc:
            return str(doc)
        name = str(interface.get("name") or "interface").rsplit(".", 1)[-1]
        words = name.strip("_").replace("_", " ")
        if not words:
            words = "interface"
        return f"{words[:1].upper()}{words[1:]} operation."

    def _module_sort_key(self, module: dict) -> tuple[int, str]:
        path = str(module.get("path") or "")
        if path.startswith("src/"):
            priority = 0
        elif path.startswith("app/") or path.startswith("lib/") or path.startswith("packages/"):
            priority = 1
        elif path.startswith("tests/"):
            priority = 3
        else:
            priority = 2
        return priority, path

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
