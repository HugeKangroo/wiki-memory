from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.infrastructure.config.repository import MemoryConfigRepository


class MemoryConfigRepositoryTest(unittest.TestCase):
    def test_persists_default_graph_backend_under_memory_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = MemoryConfigRepository(tmp)

            result = repository.set_graph_backend("file")
            reloaded = MemoryConfigRepository(tmp)

            self.assertEqual(result["graph"]["backend"], "file")
            self.assertEqual(reloaded.graph_backend(), "file")
            self.assertTrue((Path(tmp) / "memory" / "config.json").exists())

    def test_persists_default_semantic_backend_under_memory_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = MemoryConfigRepository(tmp)

            result = repository.set_semantic_backend("lancedb")
            reloaded = MemoryConfigRepository(tmp)

            self.assertEqual(result["semantic"]["backend"], "lancedb")
            self.assertEqual(result["semantic"]["model"], "BAAI/bge-m3")
            self.assertEqual(reloaded.semantic_backend(), "lancedb")
            self.assertEqual(reloaded.semantic_model(), "BAAI/bge-m3")

    def test_persists_wiki_projection_target_under_memory_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki_path = root / "external-vault"
            repository = MemoryConfigRepository(root)

            result = repository.set_wiki_projection(path=str(wiki_path), format="obsidian")
            reloaded = MemoryConfigRepository(root)

            self.assertEqual(result["wiki_projection"]["path"], str(wiki_path.resolve()))
            self.assertEqual(result["wiki_projection"]["format"], "obsidian")
            self.assertEqual(
                reloaded.wiki_projection(),
                {"path": str(wiki_path.resolve()), "format": "obsidian"},
            )

    def test_rejects_unsupported_wiki_projection_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = MemoryConfigRepository(tmp)

            with self.assertRaisesRegex(ValueError, "Unsupported wiki projection format"):
                repository.set_wiki_projection(path=str(Path(tmp) / "vault"), format="wiki-first")


if __name__ == "__main__":
    unittest.main()
