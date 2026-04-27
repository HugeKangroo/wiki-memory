from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.infrastructure.graph.factory import create_graph_backend
from memory_substrate.infrastructure.graph.file_graph_backend import FileGraphBackend


class GraphBackendFactoryTest(unittest.TestCase):
    def test_returns_none_when_backend_is_not_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(create_graph_backend(tmp, None))

    def test_creates_file_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsInstance(create_graph_backend(tmp, "file"), FileGraphBackend)

    def test_rejects_unknown_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Unsupported graph backend"):
                create_graph_backend(tmp, "unknown")


if __name__ == "__main__":
    unittest.main()
