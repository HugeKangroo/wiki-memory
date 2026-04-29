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

    def test_maintain_report_surfaces_actionable_graph_insights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = FileGraphBackend(root)
            for node_id, scope_refs in (
                ("node:a", ["scope:chain"]),
                ("node:b", ["scope:chain"]),
                ("node:c", ["scope:chain"]),
                ("node:d", ["scope:chain"]),
                ("node:isolated", ["scope:chain"]),
                ("node:g1", ["scope:gamma"]),
                ("node:g2", ["scope:gamma"]),
            ):
                backend.upsert_entity(
                    {
                        "id": node_id,
                        "kind": "concept",
                        "name": node_id,
                        "status": "active",
                        "scope_refs": scope_refs,
                    }
                )
            for source_id, target_id in (("node:a", "node:b"), ("node:b", "node:c"), ("node:c", "node:d")):
                backend.upsert_relation(
                    {
                        "id": f"rel:{source_id}:{target_id}",
                        "source_id": source_id,
                        "target_id": target_id,
                        "relation_type": "depends_on",
                        "status": "active",
                        "scope_refs": ["scope:chain"],
                    }
                )

            graph = MaintainService(root, graph_backend=backend).report()["data"]["graph"]
            insights = graph["insights"]

            isolated_ids = {item["id"] for item in insights["isolated_nodes"]}
            bridge_ids = {item["id"] for item in insights["bridge_nodes"]}
            weak_scopes = {item["scope_ref"] for item in insights["weakly_connected_scopes"]}

            self.assertIn("node:isolated", isolated_ids)
            self.assertIn("node:g1", isolated_ids)
            self.assertIn("node:b", bridge_ids)
            self.assertIn("node:c", bridge_ids)
            self.assertTrue(any({"node:a", "node:b", "node:c", "node:d"}.issubset(cluster["node_ids"]) for cluster in insights["sparse_clusters"]))
            self.assertIn("scope:gamma", weak_scopes)


if __name__ == "__main__":
    unittest.main()
