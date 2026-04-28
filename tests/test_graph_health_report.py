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


class GraphHealthReportTest(unittest.TestCase):
    def test_maintain_report_includes_graph_health_when_backend_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            objects = FsObjectRepository(root)
            backend = FileGraphBackend(root)
            objects.save(
                "knowledge",
                {
                    "id": "know:canonical",
                    "kind": "fact",
                    "title": "Canonical knowledge",
                    "summary": "This exists only in the object store.",
                    "payload": {"predicate": "stored", "value": True},
                    "status": "active",
                    "confidence": 0.9,
                    "created_at": "2026-04-28T00:00:00+00:00",
                    "updated_at": "2026-04-28T00:00:00+00:00",
                },
            )
            backend.upsert_entity(
                {
                    "id": "node:stub",
                    "kind": "stub",
                    "name": "node:stub",
                    "status": "stub",
                }
            )

            report = MaintainService(root, graph_backend=backend).report()

            graph = report["data"]["graph"]
            self.assertEqual(graph["status"], "ok")
            self.assertEqual(graph["backend"], "FileGraphBackend")
            self.assertEqual(graph["canonical_counts"]["knowledge"], 1)
            self.assertEqual(graph["backend_counts"]["knowledge"], 0)
            self.assertEqual(graph["missing_from_backend"]["knowledge"], 1)
            self.assertEqual(graph["stub_nodes"], 1)


if __name__ == "__main__":
    unittest.main()
