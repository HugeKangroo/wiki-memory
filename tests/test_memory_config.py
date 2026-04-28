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


if __name__ == "__main__":
    unittest.main()
