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
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class FakeSemanticService:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def search(self, query: str, max_items: int = 20, filters: dict | None = None):
        self.calls.append({"query": query, "max_items": max_items, "filters": filters})
        return self.items[:max_items]


class FakeGraphBackend:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def search(self, query: str, max_items: int = 20):
        self.calls.append({"query": query, "max_items": max_items})
        return self.items[:max_items]


class QuerySemanticTest(unittest.TestCase):
    def test_search_includes_semantic_hits_when_lexical_search_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:dogfood",
                    "kind": "dogfood",
                    "title": "Codex can call memory-substrate MCP",
                    "summary": "A separate Codex workspace successfully used memory-substrate tools.",
                    "status": "candidate",
                    "confidence": 0.8,
                },
            )
            semantic = FakeSemanticService(
                [
                    {
                        "object_type": "knowledge",
                        "id": "know:dogfood",
                        "kind": "dogfood",
                        "title": "Codex can call memory-substrate MCP",
                        "status": "candidate",
                        "summary": "A separate Codex workspace successfully used memory-substrate tools.",
                        "score": 11.0,
                        "semantic_score": 0.7,
                        "retrieval_sources": ["semantic"],
                    }
                ]
            )

            result = QueryService(tmp, semantic_index=semantic).search("Codex dogfood MCP", max_items=5)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:dogfood"])
            self.assertEqual(result["data"]["items"][0]["retrieval_sources"], ["semantic"])
            self.assertEqual(result["data"]["semantic_backend"], "FakeSemanticService")
            self.assertEqual(semantic.calls[0]["query"], "Codex dogfood MCP")

    def test_search_merges_lexical_and_semantic_hits_for_same_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:policy",
                    "kind": "decision",
                    "title": "Memory Substrate is local-first",
                    "summary": "The project should not require a second hosted LLM API key.",
                    "status": "active",
                    "confidence": 0.9,
                },
            )
            semantic = FakeSemanticService(
                [
                    {
                        "object_type": "knowledge",
                        "id": "know:policy",
                        "kind": "decision",
                        "title": "Memory Substrate is local-first",
                        "status": "active",
                        "summary": "The project should not require a second hosted LLM API key.",
                        "score": 10.0,
                        "semantic_score": 0.6,
                        "retrieval_sources": ["semantic"],
                    }
                ]
            )

            result = QueryService(tmp, semantic_index=semantic).search("local-first", max_items=5)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:policy"])
            self.assertEqual(result["data"]["items"][0]["retrieval_sources"], ["lexical", "semantic"])
            self.assertIn("semantic_score", result["data"]["items"][0])

    def test_search_combines_graph_and_semantic_indexes_when_both_are_configured(self) -> None:
        graph = FakeGraphBackend(
            [
                {
                    "object_type": "knowledge",
                    "id": "know:graph",
                    "kind": "decision",
                    "title": "Graph backend result",
                    "status": "active",
                    "summary": "Found by the graph backend.",
                    "score": 20,
                }
            ]
        )
        semantic = FakeSemanticService(
            [
                {
                    "object_type": "knowledge",
                    "id": "know:semantic",
                    "kind": "decision",
                    "title": "Semantic backend result",
                    "status": "active",
                    "summary": "Found by the semantic index.",
                    "score": 11.0,
                    "semantic_score": 0.7,
                    "retrieval_sources": ["semantic"],
                }
            ]
        )

        result = QueryService(".", graph_backend=graph, semantic_index=semantic).search("Graph search", max_items=5)

        self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:graph", "know:semantic"])
        self.assertEqual(result["data"]["items"][0]["retrieval_sources"], ["graph"])
        self.assertEqual(result["data"]["items"][1]["retrieval_sources"], ["semantic"])
        self.assertEqual(semantic.calls[0]["query"], "Graph search")


if __name__ == "__main__":
    unittest.main()
