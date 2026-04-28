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
            self.assertEqual([item["id"] for item in result["data"]["open_work"]], ["work:next-review"])
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


if __name__ == "__main__":
    unittest.main()
