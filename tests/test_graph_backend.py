from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.infrastructure.graph.file_graph_backend import FileGraphBackend


class FileGraphBackendTest(unittest.TestCase):
    def test_persists_records_and_returns_neighborhood(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = FileGraphBackend(tmp)
            backend.upsert_entity(
                {
                    "id": "ent:memory-substrate",
                    "kind": "project",
                    "name": "memory-substrate",
                    "summary": "Local compounding memory substrate.",
                    "scope_refs": ["scope:project"],
                }
            )
            backend.upsert_knowledge(
                {
                    "id": "know:graph-backend",
                    "kind": "decision",
                    "title": "GraphBackend is project-owned",
                    "summary": "Memory Substrate owns graph backend semantics behind an interface.",
                    "scope_refs": ["scope:project"],
                    "valid_from": "2026-04-28T00:00:00+00:00",
                }
            )
            backend.upsert_relation(
                {
                    "id": "rel:applies-to",
                    "source_id": "know:graph-backend",
                    "target_id": "ent:memory-substrate",
                    "relation_type": "applies_to",
                    "scope_refs": ["scope:project"],
                    "evidence_refs": [{"source_id": "src:design", "segment_id": "seg:1"}],
                }
            )

            reloaded = FileGraphBackend(tmp)
            neighborhood = reloaded.neighborhood("know:graph-backend")

            node_ids = {node["id"] for node in neighborhood["nodes"]}
            self.assertEqual(node_ids, {"know:graph-backend", "ent:memory-substrate"})
            self.assertEqual(neighborhood["relations"][0]["id"], "rel:applies-to")
            self.assertEqual(neighborhood["relations"][0]["relation_type"], "applies_to")

    def test_search_scores_text_and_filters_by_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = FileGraphBackend(tmp)
            backend.upsert_entity(
                {
                    "id": "ent:a",
                    "kind": "concept",
                    "name": "GraphBackend contract",
                    "summary": "A graph interface for memory.",
                    "scope_refs": ["scope:a"],
                }
            )
            backend.upsert_entity(
                {
                    "id": "ent:b",
                    "kind": "concept",
                    "name": "GraphBackend unrelated",
                    "summary": "A graph interface in a different scope.",
                    "scope_refs": ["scope:b"],
                }
            )

            results = backend.search("GraphBackend", scope_refs=["scope:a"])

            self.assertEqual([item["id"] for item in results], ["ent:a"])
            self.assertGreater(results[0]["score"], 0)
            self.assertEqual(results[0]["object_type"], "entity")

    def test_temporal_lookup_respects_validity_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = FileGraphBackend(tmp)
            backend.upsert_knowledge(
                {
                    "id": "know:old",
                    "kind": "fact",
                    "title": "Old backend decision",
                    "summary": "This decision was true only in April.",
                    "valid_from": "2026-04-01T00:00:00+00:00",
                    "valid_until": "2026-04-20T00:00:00+00:00",
                    "scope_refs": ["scope:project"],
                }
            )
            backend.upsert_knowledge(
                {
                    "id": "know:current",
                    "kind": "fact",
                    "title": "Current backend decision",
                    "summary": "This decision remains true.",
                    "valid_from": "2026-04-21T00:00:00+00:00",
                    "scope_refs": ["scope:project"],
                }
            )

            april = backend.temporal_lookup("2026-04-10T00:00:00+00:00", scope_refs=["scope:project"])
            may = backend.temporal_lookup("2026-05-01T00:00:00+00:00", scope_refs=["scope:project"])

            self.assertEqual({item["id"] for item in april["knowledge"]}, {"know:old"})
            self.assertEqual({item["id"] for item in may["knowledge"]}, {"know:current"})

    def test_link_evidence_export_scope_health_and_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backend = FileGraphBackend(tmp)
            backend.upsert_knowledge(
                {
                    "id": "know:evidence",
                    "kind": "fact",
                    "title": "Evidence linked later",
                    "summary": "Evidence refs can be attached after upsert.",
                    "scope_refs": ["scope:project"],
                }
            )

            updated = backend.link_evidence(
                "knowledge",
                "know:evidence",
                [{"source_id": "src:research", "segment_id": "seg:9"}],
            )
            exported = backend.export_scope("scope:project")
            health = backend.health()
            rebuild = backend.rebuild()

            self.assertEqual(updated["evidence_refs"], [{"source_id": "src:research", "segment_id": "seg:9"}])
            self.assertEqual(exported["knowledge"][0]["id"], "know:evidence")
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["counts"]["knowledge"], 1)
            self.assertEqual(rebuild["status"], "noop")


if __name__ == "__main__":
    unittest.main()
