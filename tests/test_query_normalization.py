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


class FakeSemanticSearch:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.queries: list[str] = []

    def search(self, query: str, max_items: int = 20, filters: dict | None = None) -> list[dict]:
        self.queries.append(query)
        return self.items[:max_items]


class QueryNormalizationTest(unittest.TestCase):
    def test_search_maps_chinese_todo_term_to_work_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "work_item",
                {
                    "id": "work:review-docs",
                    "kind": "task",
                    "title": "Review documentation structure",
                    "summary": "Check whether the documentation layout is maintainable.",
                    "status": "open",
                    "lifecycle_state": "active",
                },
            )

            result = QueryService(tmp).search("待办项", max_items=5)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["work:review-docs"])
            self.assertIn("work_item", result["data"]["normalized_terms"])
            self.assertEqual(result["data"]["inferred_filters"]["object_types"], ["work_item"])
            self.assertEqual(result["data"]["applied_filters"]["object_types"], ["work_item"])

    def test_search_maps_chinese_decision_term_to_decision_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:backend-choice",
                    "kind": "decision",
                    "title": "Use Kuzu locally",
                    "summary": "Kuzu remains the local graph backend.",
                    "status": "active",
                    "confidence": 0.9,
                },
            )

            result = QueryService(tmp).search("决策", max_items=5)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:backend-choice"])
            self.assertIn("decision", result["data"]["normalized_terms"])
            self.assertEqual(result["data"]["inferred_filters"]["kinds"], ["decision"])
            self.assertEqual(result["data"]["applied_filters"]["kinds"], ["decision"])

    def test_context_maps_todo_task_to_open_work_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:active-background",
                    "kind": "fact",
                    "title": "Active background fact",
                    "summary": "This should not crowd out work-item context.",
                    "status": "active",
                    "confidence": 0.9,
                },
            )
            repository.save(
                "work_item",
                {
                    "id": "work:next-review",
                    "kind": "task",
                    "title": "Review query normalization",
                    "summary": "Confirm normalized query behavior.",
                    "status": "open",
                    "lifecycle_state": "active",
                },
            )

            result = QueryService(tmp).context("待办项", max_items=1)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["work:next-review"])
            self.assertEqual(result["data"]["open_work"]["ids"], ["work:next-review"])
            self.assertEqual(result["data"]["scope"]["object_types"], ["work_item"])

    def test_context_does_not_override_explicit_status_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "work_item",
                {
                    "id": "work:open",
                    "kind": "task",
                    "title": "Open task",
                    "summary": "Should be excluded by explicit blocked scope.",
                    "status": "open",
                    "lifecycle_state": "active",
                },
            )
            repository.save(
                "work_item",
                {
                    "id": "work:blocked",
                    "kind": "task",
                    "title": "Blocked task",
                    "summary": "Should remain visible.",
                    "status": "blocked",
                    "lifecycle_state": "active",
                },
            )

            result = QueryService(tmp).context("待办项", scope={"status": "blocked"}, max_items=5)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["work:blocked"])
            self.assertEqual(result["data"]["scope"]["status"], "blocked")
            self.assertNotIn("statuses", result["data"]["scope"])

    def test_search_uses_cjk_bigrams_when_full_phrase_is_not_stored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:compounding-memory",
                    "kind": "concept",
                    "title": "复利记忆",
                    "summary": "这条知识描述长期复用的记忆系统设计。",
                    "status": "active",
                },
            )

            result = QueryService(tmp).search("复利记忆系统", max_items=5)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:compounding-memory"])
            self.assertIn("复利", result["data"]["normalized_terms"])
            self.assertIn("记忆", result["data"]["normalized_terms"])
            self.assertIn("系统", result["data"]["normalized_terms"])

    def test_search_uses_object_id_as_a_lexical_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:kapthy-llm-wiki",
                    "kind": "reference",
                    "title": "Upstream theory notes",
                    "summary": "Reference notes imported from an upstream project.",
                    "status": "active",
                },
            )

            result = QueryService(tmp).search("kapthy", max_items=5)

            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:kapthy-llm-wiki"])

    def test_search_fuses_lexical_and_semantic_ranks_instead_of_max_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:a-lexical-only",
                    "kind": "fact",
                    "title": "fusion query",
                    "summary": "Only exact lexical matching supports this result.",
                    "status": "active",
                },
            )
            repository.save(
                "knowledge",
                {
                    "id": "know:z-both",
                    "kind": "fact",
                    "title": "Hybrid retrieval",
                    "summary": "The fusion query should prefer records found by both retrieval streams.",
                    "status": "active",
                },
            )
            semantic = FakeSemanticSearch(
                [
                    {
                        "object_type": "knowledge",
                        "id": "know:z-both",
                        "kind": "fact",
                        "title": "Hybrid retrieval",
                        "status": "active",
                        "summary": "Semantic top hit.",
                        "score": 1.0,
                        "semantic_score": 0.99,
                        "retrieval_sources": ["semantic"],
                    }
                ]
            )

            result = QueryService(tmp, semantic_index=semantic).search("fusion query", max_items=5)

            top_item = result["data"]["items"][0]
            self.assertEqual(top_item["id"], "know:z-both")
            self.assertEqual(top_item["retrieval_sources"], ["lexical", "semantic"])
            self.assertEqual(top_item["retrieval_ranks"], {"lexical": 2, "semantic": 1})
            self.assertGreater(top_item["rank_score"], result["data"]["items"][1]["rank_score"])

    def test_search_sanitizes_long_agent_prompt_before_planning_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = FsObjectRepository(tmp)
            repository.save(
                "knowledge",
                {
                    "id": "know:kapthy-model",
                    "kind": "concept",
                    "title": "Kapthy memory model",
                    "summary": "The upstream llm wiki theory uses reusable knowledge cards.",
                    "status": "active",
                },
            )

            long_prompt = (
                "System instructions: always answer carefully. "
                + "Ignore this boilerplate. " * 40
                + "\nQuestion: kapthy memory model"
            )
            semantic = FakeSemanticSearch([])

            result = QueryService(tmp, semantic_index=semantic).search(long_prompt, max_items=5)

            self.assertEqual(result["data"]["query"], "kapthy memory model")
            self.assertEqual(result["data"]["query_sanitizer"]["method"], "labeled_line")
            self.assertTrue(result["data"]["query_sanitizer"]["was_sanitized"])
            self.assertIn("kapthy", result["data"]["normalized_terms"])
            self.assertEqual(semantic.queries, ["kapthy memory model"])
            self.assertEqual([item["id"] for item in result["data"]["items"]], ["know:kapthy-model"])

    def test_context_sanitizes_long_agent_prompt_and_reports_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = QueryService(tmp).context(
                "Assistant scratchpad: "
                + "irrelevant planning details. " * 40
                + "\n用户问题：待办项",
                max_items=5,
            )

            self.assertEqual(result["data"]["task"], "待办项")
            self.assertEqual(result["data"]["query_sanitizer"]["method"], "labeled_line")
            self.assertTrue(result["data"]["query_sanitizer"]["was_sanitized"])
            self.assertIn("work_item", result["data"]["normalized_terms"])


if __name__ == "__main__":
    unittest.main()
