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
                "class MemoryApi:\n"
                "    pass\n\n"
                "def ingest_repo(path):\n"
                "    return path\n",
                encoding="utf-8",
            )

            IngestService(root).ingest_repo(repo)
            MarkdownProjector(root).rebuild()

            wiki_root = root / "memory" / "projections" / "wiki"
            debug_root = root / "memory" / "projections" / "debug"
            home = (wiki_root / "Home.md").read_text(encoding="utf-8")
            maps = (wiki_root / "Projects" / "wiki-memory.md").read_text(encoding="utf-8")
            source = (wiki_root / "Sources" / "wiki-memory.md").read_text(encoding="utf-8")
            debug_pages = list((debug_root / "nodes").glob("*.md"))

            self.assertIn("# Wiki Memory Home", home)
            self.assertIn("[[Projects/wiki-memory|wiki-memory]]", home)
            self.assertIn("## What This Is", maps)
            self.assertIn("## Repository Map", maps)
            self.assertIn("## API Reference", maps)
            self.assertIn("### Module `src/api.py`", maps)
            self.assertIn("#### Classes", maps)
            self.assertIn("- `MemoryApi`", maps)
            self.assertIn("#### Functions and Methods", maps)
            self.assertIn("- `ingest_repo`", maps)
            self.assertIn("src/api.py", source)
            self.assertIn("## Machine Data", maps)
            self.assertIn("## Code Files", source)
            self.assertIn("src/api.py", source)
            self.assertIn("## API Reference", source)
            self.assertIn("### Module `src/api.py`", source)
            self.assertIn("- `MemoryApi`", source)
            self.assertIn("- `ingest_repo`", source)
            self.assertTrue(debug_pages)
            self.assertFalse((wiki_root / "index.md").exists())
            self.assertFalse((wiki_root / "overview.md").exists())
            self.assertFalse((wiki_root / "_raw").exists())
            self.assertFalse((wiki_root / "nodes").exists())


if __name__ == "__main__":
    unittest.main()
