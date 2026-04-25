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

            IngestService(root).ingest_repo(repo)
            MarkdownProjector(root).rebuild()

            wiki_root = root / "memory" / "projections" / "wiki"
            home = (wiki_root / "Home.md").read_text(encoding="utf-8")
            maps = (wiki_root / "Maps" / "Projects.md").read_text(encoding="utf-8")
            human_pages = list((wiki_root / "Readable" / "Nodes").glob("*.md"))

            self.assertIn("# Wiki Memory Home", home)
            self.assertIn("[[Maps/Projects|Projects]]", home)
            self.assertIn("wiki-memory", maps)
            self.assertTrue(any(path.name.startswith("wiki-memory") for path in human_pages))


if __name__ == "__main__":
    unittest.main()
