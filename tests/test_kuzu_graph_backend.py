from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


@unittest.skipUnless(importlib.util.find_spec("kuzu"), "kuzu optional dependency is not installed")
class KuzuGraphBackendTest(unittest.TestCase):
    def test_persists_records_and_returns_neighborhood_after_reopen(self) -> None:
        from memory_substrate.infrastructure.graph.kuzu_graph_backend import KuzuGraphBackend

        with tempfile.TemporaryDirectory() as tmp:
            backend = KuzuGraphBackend(tmp)
            backend.upsert_entity(
                {
                    "id": "ent:memory-substrate",
                    "kind": "project",
                    "name": "memory-substrate",
                    "summary": "Local compounding memory substrate.",
                    "scope_refs": ["scope:project"],
                    "payload": {"backend": "kuzu"},
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
            backend.close()

            reloaded = KuzuGraphBackend(tmp)
            neighborhood = reloaded.neighborhood("know:graph-backend")
            reloaded.close()

            node_ids = {node["id"] for node in neighborhood["nodes"]}
            self.assertEqual(node_ids, {"know:graph-backend", "ent:memory-substrate"})
            self.assertEqual(neighborhood["relations"][0]["id"], "rel:applies-to")
            self.assertEqual(neighborhood["relations"][0]["relation_type"], "applies_to")

    def test_search_temporal_export_health_and_evidence_links(self) -> None:
        from memory_substrate.infrastructure.graph.kuzu_graph_backend import KuzuGraphBackend

        with tempfile.TemporaryDirectory() as tmp:
            backend = KuzuGraphBackend(tmp)
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
                    "payload": {"reason": "Kuzu runs locally without an LLM API key."},
                }
            )

            updated = backend.link_evidence(
                "knowledge",
                "know:current",
                [{"source_id": "src:research", "segment_id": "seg:2"}],
            )
            search_results = backend.search("Kuzu", scope_refs=["scope:project"])
            april = backend.temporal_lookup("2026-04-10T00:00:00+00:00", scope_refs=["scope:project"])
            may = backend.temporal_lookup("2026-05-01T00:00:00+00:00", scope_refs=["scope:project"])
            exported = backend.export_scope("scope:project")
            health = backend.health()
            rebuild = backend.rebuild()
            backend.close()

            self.assertEqual(updated["evidence_refs"], [{"source_id": "src:research", "segment_id": "seg:2"}])
            self.assertEqual([item["id"] for item in search_results], ["know:current"])
            self.assertEqual({item["id"] for item in april["knowledge"]}, {"know:old"})
            self.assertEqual({item["id"] for item in may["knowledge"]}, {"know:current"})
            self.assertEqual({item["id"] for item in exported["knowledge"]}, {"know:old", "know:current"})
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["counts"]["knowledge"], 2)
            self.assertEqual(rebuild["status"], "noop")


if __name__ == "__main__":
    unittest.main()
