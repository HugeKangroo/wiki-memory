from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.graph.sync import GraphSyncService
from memory_substrate.infrastructure.graph.file_graph_backend import FileGraphBackend
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class GraphSyncServiceTest(unittest.TestCase):
    def test_sync_all_projects_canonical_objects_into_graph_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            objects = FsObjectRepository(root)
            backend = FileGraphBackend(root)
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
            objects.save(
                "source",
                {
                    "id": "src:design",
                    "kind": "conversation",
                    "title": "Design discussion",
                    "summary": "Backend design evidence.",
                    "payload": {"text": "Kuzu runs locally."},
                    "segments": [{"segment_id": "seg:1", "excerpt": "Kuzu runs locally."}],
                    "created_at": "2026-04-28T00:00:00+00:00",
                    "updated_at": "2026-04-28T00:00:00+00:00",
                },
            )
            objects.save(
                "knowledge",
                {
                    "id": "know:kuzu",
                    "kind": "decision",
                    "title": "Use optional Kuzu backend",
                    "summary": "Kuzu is optional and local-first.",
                    "subject_refs": ["node:project"],
                    "evidence_refs": [{"source_id": "src:design", "segment_id": "seg:1"}],
                    "payload": {"predicate": "backend", "value": "kuzu"},
                    "status": "active",
                    "confidence": 0.9,
                    "valid_from": "2026-04-28T00:00:00+00:00",
                    "created_at": "2026-04-28T00:00:00+00:00",
                    "updated_at": "2026-04-28T00:00:00+00:00",
                },
            )

            result = GraphSyncService(root, backend).sync_all()
            neighborhood = backend.neighborhood("know:kuzu")

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["synced_objects"], 3)
            self.assertGreaterEqual(result["synced_relations"], 2)
            self.assertEqual(
                {node["id"] for node in neighborhood["nodes"]},
                {"know:kuzu", "node:project", "src:design"},
            )
            self.assertEqual(
                {relation["relation_type"] for relation in neighborhood["relations"]},
                {"subject", "evidence"},
            )

    def test_sync_knowledge_payload_object_relation_uses_predicate_as_edge_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            objects = FsObjectRepository(root)
            backend = FileGraphBackend(root)
            for node_id, name in (("node:memory", "memory-substrate"), ("node:kuzu", "Kuzu")):
                objects.save(
                    "node",
                    {
                        "id": node_id,
                        "kind": "concept",
                        "name": name,
                        "summary": name,
                        "created_at": "2026-04-28T00:00:00+00:00",
                        "updated_at": "2026-04-28T00:00:00+00:00",
                    },
                )
            objects.save(
                "knowledge",
                {
                    "id": "know:uses-kuzu",
                    "kind": "fact",
                    "title": "Memory substrate uses Kuzu",
                    "summary": "Kuzu is the optional local graph backend.",
                    "subject_refs": ["node:memory"],
                    "payload": {
                        "subject": "node:memory",
                        "predicate": "uses",
                        "object": "node:kuzu",
                        "value": None,
                    },
                    "status": "active",
                    "confidence": 0.9,
                    "created_at": "2026-04-28T00:00:00+00:00",
                    "updated_at": "2026-04-28T00:00:00+00:00",
                },
            )

            result = GraphSyncService(root, backend).sync_all()
            neighborhood = backend.neighborhood("node:memory")
            predicate_edges = [
                relation
                for relation in neighborhood["relations"]
                if relation["source_id"] == "node:memory"
                and relation["target_id"] == "node:kuzu"
                and relation["relation_type"] == "uses"
            ]

            self.assertEqual(result["status"], "completed")
            self.assertEqual(len(predicate_edges), 1)
            self.assertEqual(predicate_edges[0]["payload"]["knowledge_id"], "know:uses-kuzu")


if __name__ == "__main__":
    unittest.main()
