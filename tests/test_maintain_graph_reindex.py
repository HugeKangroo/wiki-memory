from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.maintain.service import MaintainService
from memory_substrate.infrastructure.graph.file_graph_backend import FileGraphBackend
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class MaintainGraphReindexTest(unittest.TestCase):
    def test_reindex_rebuilds_configured_graph_backend_from_canonical_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = FileGraphBackend(root)
            FsObjectRepository(root).save(
                "knowledge",
                {
                    "id": "know:reindex",
                    "kind": "fact",
                    "title": "Reindex syncs graph",
                    "summary": "Maintain reindex rebuilds the configured graph backend.",
                    "payload": {"predicate": "syncs", "value": "graph"},
                    "created_at": "2026-04-28T00:00:00+00:00",
                    "updated_at": "2026-04-28T00:00:00+00:00",
                },
            )

            result = MaintainService(root, graph_backend=backend).reindex()

            self.assertEqual(result["result_type"], "reindex_result")
            self.assertEqual(result["data"]["graph_sync"]["synced_objects"], 1)
            self.assertEqual(backend.search("Reindex")[0]["id"], "know:reindex")


if __name__ == "__main__":
    unittest.main()
