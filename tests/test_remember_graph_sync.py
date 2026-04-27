from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.remember.service import RememberService
from memory_substrate.infrastructure.graph.file_graph_backend import FileGraphBackend
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class RememberGraphSyncTest(unittest.TestCase):
    def test_create_knowledge_syncs_created_memory_to_graph_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = FileGraphBackend(root)
            objects = FsObjectRepository(root)
            objects.save(
                "node",
                {
                    "id": "node:project",
                    "kind": "project",
                    "name": "memory-substrate",
                    "summary": "Local memory substrate.",
                    "created_at": "2026-04-28T00:00:00+00:00",
                    "updated_at": "2026-04-28T00:00:00+00:00",
                },
            )

            result = RememberService(root, graph_backend=backend).create_knowledge(
                {
                    "kind": "decision",
                    "title": "Remember syncs graph backend",
                    "summary": "Durable knowledge is indexed into the configured graph backend.",
                    "subject_refs": ["node:project"],
                    "payload": {"predicate": "syncs", "value": "graph_backend"},
                    "status": "active",
                    "confidence": 0.9,
                }
            )

            neighborhood = backend.neighborhood(result["knowledge_id"])

            self.assertEqual(result["graph_sync"]["synced_objects"], 1)
            self.assertEqual({node["id"] for node in neighborhood["nodes"]}, {result["knowledge_id"], "node:project"})
            self.assertEqual(neighborhood["relations"][0]["relation_type"], "subject")


if __name__ == "__main__":
    unittest.main()
