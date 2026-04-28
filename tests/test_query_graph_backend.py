from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.query.service import QueryService
from memory_substrate.infrastructure.graph.file_graph_backend import FileGraphBackend


class QueryGraphBackendTest(unittest.TestCase):
    def test_search_can_read_from_configured_graph_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = FileGraphBackend(tmp)
            backend.upsert_knowledge(
                {
                    "id": "know:graph-search",
                    "kind": "decision",
                    "title": "Graph search uses backend",
                    "summary": "Search can read a configured graph backend.",
                }
            )

            result = QueryService(tmp, graph_backend=backend).search("Graph search")

            self.assertEqual(result["result_type"], "search_results")
            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:graph-search"])
            self.assertEqual(result["data"]["items"][0]["object_type"], "knowledge")

    def test_context_can_start_from_configured_graph_backend_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = FileGraphBackend(tmp)
            backend.upsert_knowledge(
                {
                    "id": "know:graph-context",
                    "kind": "decision",
                    "title": "Graph context uses backend",
                    "summary": "Context can start from graph backend search results.",
                    "status": "active",
                    "evidence_refs": [{"source_id": "src:design", "segment_id": "seg:1"}],
                }
            )

            result = QueryService(tmp, graph_backend=backend).context("Graph context", max_items=5)

            self.assertEqual(result["result_type"], "context_pack")
            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:graph-context"])
            self.assertEqual(result["data"]["decisions"][0]["id"], "know:graph-context")
            self.assertEqual(
                result["data"]["citations"],
                [{"source_id": "src:design", "segment_id": "seg:1", "object_id": "know:graph-context"}],
            )
            self.assertFalse(result["data"]["missing_context"])

    def test_graph_mode_can_read_from_configured_graph_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = FileGraphBackend(tmp)
            backend.upsert_knowledge(
                {
                    "id": "know:graph",
                    "kind": "decision",
                    "title": "Graph query uses backend",
                    "summary": "The query service can read a graph backend.",
                }
            )
            backend.upsert_entity(
                {
                    "id": "node:backend",
                    "kind": "component",
                    "name": "GraphBackend",
                    "summary": "Project-owned graph contract.",
                }
            )
            backend.upsert_relation(
                {
                    "id": "rel:graph-backend",
                    "source_id": "know:graph",
                    "target_id": "node:backend",
                    "relation_type": "applies_to",
                }
            )

            result = QueryService(tmp, graph_backend=backend).graph("know:graph")

            self.assertEqual(result["result_type"], "graph")
            self.assertEqual(result["data"]["root_id"], "know:graph")
            self.assertEqual({node["id"] for node in result["data"]["nodes"]}, {"know:graph", "node:backend"})
            self.assertEqual(result["data"]["edges"][0]["relation"], "applies_to")
            self.assertEqual(result["warnings"], [])


if __name__ == "__main__":
    unittest.main()
