from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wiki_memory.application.ingest.service import IngestService
from wiki_memory.projections.markdown.projector import MarkdownProjector


class ObsidianProjectionTest(unittest.TestCase):
    def test_rebuild_writes_human_readable_home_and_alias_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "wiki-memory"
            repo.mkdir()
            (repo / "README.md").write_text("# wiki-memory\n", encoding="utf-8")
            src = repo / "src"
            src.mkdir()
            (src / "api.py").write_text(
                '"""Public memory API endpoints."""\n\n'
                "class MemoryApi:\n"
                '    """Facade for memory operations."""\n'
                "    def search(self, query: str, limit: int = 10) -> list[str]:\n"
                "        return []\n\n"
                "    def _private_helper(self) -> None:\n"
                "        return None\n\n"
                "\n"
                "def ingest_repo(path: str, force: bool = False) -> dict:\n"
                '    """Ingest a repository path into memory.\n\n'
                "    Args:\n"
                "        path: Repository path to scan.\n"
                "        force: Rebuild even if the repository fingerprint is unchanged.\n\n"
                "    Returns:\n"
                "        Ingest result with source and node identifiers.\n"
                '    """\n'
                "    return {}\n\n",
                encoding="utf-8",
            )

            IngestService(root).ingest_repo(repo)
            MarkdownProjector(root).rebuild()

            wiki_root = root / "memory" / "projections" / "wiki"
            debug_root = root / "memory" / "projections" / "debug"
            home = (wiki_root / "Home.md").read_text(encoding="utf-8")
            maps = (wiki_root / "Projects" / "wiki-memory.md").read_text(encoding="utf-8")
            source = (wiki_root / "Sources" / "wiki-memory.md").read_text(encoding="utf-8")
            api_docs = (wiki_root / "API_Docs.md").read_text(encoding="utf-8")
            doxyfile = (root / "memory" / "projections" / "doxygen" / "Doxyfile").read_text(encoding="utf-8")
            debug_pages = list((debug_root / "nodes").glob("*.md"))

            self.assertIn("# Wiki Memory Home", home)
            self.assertIn("[[Projects/wiki-memory|wiki-memory]]", home)
            self.assertIn("[[API_Docs|Doxygen API Docs]]", home)
            self.assertIn("# Doxygen API Docs", api_docs)
            self.assertIn("[Open Doxygen HTML](../doxygen/html/index.html)", api_docs)
            self.assertIn("[Doxyfile](../doxygen/Doxyfile)", api_docs)
            self.assertIn("<iframe", api_docs)
            self.assertIn("../doxygen/html/index.html", api_docs)
            self.assertIn("PROJECT_NAME = \"wiki-memory\"", doxyfile)
            self.assertIn("RECURSIVE = YES", doxyfile)
            self.assertIn(f"INPUT = {repo}", doxyfile)
            self.assertIn("## What This Is", maps)
            self.assertIn("## Repository Map", maps)
            self.assertIn("## API Reference", maps)
            self.assertIn("### Application Module", maps)
            self.assertIn("**Defined in:** `src/api.py`", maps)
            self.assertIn("Public memory API endpoints.", maps)
            self.assertIn("**Classes:** `MemoryApi`", maps)
            self.assertIn("Facade for memory operations.", maps)
            self.assertIn("| API | Kind | Brief |", maps)
            self.assertIn("| `ingest_repo` | function | Ingest a repository path into memory. |", maps)
            self.assertIn("<details>", maps)
            self.assertIn("<summary><code>ingest_repo</code></summary>", maps)
            self.assertIn("**Declaration**", maps)
            self.assertIn("`ingest_repo(path: str, force: bool = False) -> dict`", maps)
            self.assertIn("| `path` | `str` | required | Repository path to scan. |", maps)
            self.assertIn("| `force` | `bool` | `False` | Rebuild even if the repository fingerprint is unchanged. |", maps)
            self.assertIn("**Returns**", maps)
            self.assertIn("`dict` - Ingest result with source and node identifiers.", maps)
            self.assertIn("| `MemoryApi.search` | method | - |", maps)
            self.assertIn("<summary><code>MemoryApi.search</code></summary>", maps)
            self.assertIn("`MemoryApi.search(query: str, limit: int = 10) -> list[str]`", maps)
            self.assertNotIn("| `self` |", maps)
            self.assertNotIn("MemoryApi._private_helper", maps)
            self.assertIn("src/api.py", source)
            self.assertIn("## Machine Data", maps)
            self.assertIn("## Code Files", source)
            self.assertIn("src/api.py", source)
            self.assertIn("## API Reference", source)
            self.assertIn("### Application Module", source)
            self.assertIn("**Defined in:** `src/api.py`", source)
            self.assertIn("<summary><code>ingest_repo</code></summary>", source)
            self.assertTrue(debug_pages)
            self.assertFalse((wiki_root / "index.md").exists())
            self.assertFalse((wiki_root / "overview.md").exists())
            self.assertFalse((wiki_root / "_raw").exists())
            self.assertFalse((wiki_root / "nodes").exists())


if __name__ == "__main__":
    unittest.main()
