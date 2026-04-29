from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.semantic.service import SemanticIndexService
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class FakeSemanticIndex:
    backend_name = "fake"
    model_name = "fake-model"

    def __init__(self) -> None:
        self.rebuilt_chunks = []
        self.hits = []
        self.count = 0

    def rebuild(self, chunks):
        self.rebuilt_chunks = list(chunks)
        self.count = len(self.rebuilt_chunks)
        return {"backend": self.backend_name, "model": self.model_name, "chunk_count": len(self.rebuilt_chunks)}

    def search(self, query: str, limit: int = 20):
        return self.hits[:limit]

    def count_chunks(self) -> int:
        return self.count


class SemanticIndexServiceTest(unittest.TestCase):
    def test_rebuild_projects_canonical_objects_and_source_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:local-first",
                    "kind": "decision",
                    "title": "Memory is local-first",
                    "summary": "Do not require a second hosted LLM API key.",
                    "status": "active",
                    "scope_refs": ["scope:memory-substrate"],
                    "payload": {"metadata": {"reason": "Project policy."}},
                },
            )
            repository.save(
                "source",
                {
                    "id": "src:note",
                    "kind": "markdown",
                    "title": "Design note",
                    "status": "active",
                    "segments": [
                        {
                            "segment_id": "seg-1",
                            "excerpt": "LanceDB is a derived vector index.",
                            "locator": {"path": "note.md", "heading_path": ["Design", "Semantic"]},
                            "hash": "h1",
                        }
                    ],
                },
            )
            fake = FakeSemanticIndex()

            result = SemanticIndexService(tmp, fake).rebuild()

            self.assertEqual(result["backend"], "fake")
            self.assertEqual(result["chunk_count"], 2)
            chunk_ids = {chunk.chunk_id for chunk in fake.rebuilt_chunks}
            self.assertEqual(chunk_ids, {"know:local-first#object", "src:note#seg-1"})
            knowledge_chunk = next(chunk for chunk in fake.rebuilt_chunks if chunk.object_id == "know:local-first")
            self.assertEqual(knowledge_chunk.object_type, "knowledge")
            self.assertIn("second hosted LLM API key", knowledge_chunk.text)
            self.assertEqual(knowledge_chunk.scope_refs, ["scope:memory-substrate"])
            source_chunk = next(chunk for chunk in fake.rebuilt_chunks if chunk.object_id == "src:note")
            self.assertEqual(source_chunk.locator, {"path": "note.md", "heading_path": ["Design", "Semantic"]})
            self.assertEqual(source_chunk.heading_path, ["Design", "Semantic"])
            self.assertIn("Design > Semantic", source_chunk.text)

    def test_search_maps_semantic_hits_back_to_canonical_objects_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:dogfood",
                    "kind": "dogfood",
                    "title": "Codex can call memory-substrate MCP",
                    "summary": "Dogfood verified a separate Codex workspace can call memory-substrate.",
                    "status": "candidate",
                    "scope_refs": ["scope:dogfood"],
                },
            )
            fake = FakeSemanticIndex()
            fake.hits = [{"object_id": "know:dogfood", "chunk_id": "know:dogfood#object", "distance": 0.25}]

            result = SemanticIndexService(tmp, fake).search(
                "Codex dogfood MCP",
                max_items=5,
                filters={"object_types": ["knowledge"], "kinds": ["dogfood"]},
            )

            self.assertEqual([item["id"] for item in result], ["know:dogfood"])
            self.assertEqual(result[0]["object_type"], "knowledge")
            self.assertEqual(result[0]["retrieval_sources"], ["semantic"])
            self.assertGreater(result[0]["semantic_score"], 0.0)

    def test_search_returns_matched_source_chunks_with_locators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "source",
                {
                    "id": "src:design-note",
                    "kind": "markdown",
                    "title": "Design note",
                    "status": "active",
                    "segments": [
                        {
                            "segment_id": "seg-1",
                            "excerpt": "Hybrid retrieval should expose source locators for agent follow-up.",
                            "locator": {"path": "docs/design.md", "line_start": 12, "line_end": 18},
                            "hash": "h1",
                        },
                        {
                            "segment_id": "seg-2",
                            "excerpt": "Other content.",
                            "locator": {"path": "docs/design.md", "line_start": 30},
                            "hash": "h2",
                        },
                    ],
                },
            )
            fake = FakeSemanticIndex()
            fake.hits = [{"object_id": "src:design-note", "chunk_id": "src:design-note#seg-1", "distance": 0.1}]

            result = SemanticIndexService(tmp, fake).search("where is hybrid retrieval described", max_items=5)

            self.assertEqual([item["id"] for item in result], ["src:design-note"])
            self.assertEqual(
                result[0]["matched_chunks"],
                [
                    {
                        "chunk_id": "src:design-note#seg-1",
                        "segment_id": "seg-1",
                        "semantic_score": 0.9,
                        "distance": 0.1,
                        "locator": {"path": "docs/design.md", "line_start": 12, "line_end": 18},
                        "excerpt": "Hybrid retrieval should expose source locators for agent follow-up.",
                        "hash": "h1",
                    }
                ],
            )

    def test_diagnostics_compares_canonical_chunks_to_index_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:indexed",
                    "kind": "fact",
                    "title": "Indexed fact",
                    "summary": "Should be in the semantic index.",
                    "status": "active",
                },
            )
            fake = FakeSemanticIndex()
            fake.count = 0

            diagnostics = SemanticIndexService(tmp, fake).diagnostics()

            self.assertEqual(diagnostics["canonical_chunk_count"], 1)
            self.assertEqual(diagnostics["indexed_chunk_count"], 0)
            self.assertEqual(diagnostics["missing_from_index"], 1)
            self.assertTrue(diagnostics["stale_index"])


if __name__ == "__main__":
    unittest.main()
