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
from memory_substrate.application.query.service import QueryService
from memory_substrate.application.remember.service import RememberService
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.interfaces.mcp.tools import memory_maintain


class TemporaryMemoryLifecycleTest(unittest.TestCase):
    def _remember_temporary(self, root: Path) -> str:
        result = RememberService(root).create_knowledge(
            {
                "kind": "design_note",
                "title": "Temporary parser evaluation note",
                "summary": "This scratch note should not be normal active memory.",
                "reason": "This is a temporary evaluation note pending review.",
                "memory_source": "user_declared",
                "scope_refs": ["scope:memory-substrate"],
                "source_text": "Temporary parser evaluation note raw context.",
                "status": "active",
                "lifecycle_state": "temporary",
                "confidence": 0.8,
            }
        )
        return result["knowledge_id"]

    def test_temporary_knowledge_is_not_returned_by_default_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            knowledge_id = self._remember_temporary(root)
            stored = FsObjectRepository(root).get("knowledge", knowledge_id)
            source_id = stored["evidence_refs"][0]["source_id"]
            source = FsObjectRepository(root).get("source", source_id)

            default_search = QueryService(root).search("Temporary parser evaluation", max_items=10)
            include_search = QueryService(root).search(
                "Temporary parser evaluation",
                max_items=10,
                filters={"include_temporary": True},
            )
            explicit_status_search = QueryService(root).search(
                "Temporary parser evaluation",
                max_items=10,
                filters={"statuses": ["temporary"]},
            )

            self.assertEqual(stored["status"], "temporary")
            self.assertEqual(stored["lifecycle_state"], "temporary")
            self.assertEqual(source["status"], "temporary")
            self.assertEqual(source["lifecycle_state"], "temporary")
            self.assertEqual(default_search["data"]["items"], [])
            self.assertNotIn(knowledge_id, {item["id"] for item in default_search["data"]["items"]})
            self.assertIn(knowledge_id, {item["id"] for item in include_search["data"]["items"]})
            self.assertIn(knowledge_id, {item["id"] for item in explicit_status_search["data"]["items"]})

    def test_temporary_knowledge_is_not_returned_by_default_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            knowledge_id = self._remember_temporary(root)
            source_id = FsObjectRepository(root).get("knowledge", knowledge_id)["evidence_refs"][0]["source_id"]

            default_context = QueryService(root).context("Temporary parser evaluation", max_items=10)
            include_context = QueryService(root).context(
                "Temporary parser evaluation",
                scope={"include_temporary": True},
                max_items=10,
            )

            self.assertNotIn(knowledge_id, {item["id"] for item in default_context["data"]["items"]})
            self.assertNotIn(source_id, {item["id"] for item in default_context["data"]["items"]})
            self.assertIn(knowledge_id, {item["id"] for item in include_context["data"]["items"]})

    def test_maintain_reports_promotes_and_archives_temporary_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            knowledge_id = self._remember_temporary(root)

            report = MaintainService(root).report()
            promoted = RememberService(root).promote_knowledge(
                knowledge_id,
                reason="Reviewed temporary note and made it durable.",
            )

            self.assertIn(knowledge_id, report["data"]["temporary_memory_ids"])
            self.assertEqual(report["data"]["counts"]["temporary_memories"], 1)
            self.assertEqual(promoted["status"], "active")
            promoted_item = FsObjectRepository(root).get("knowledge", knowledge_id)
            self.assertEqual(promoted_item["status"], "active")
            self.assertEqual(promoted_item["lifecycle_state"], "active")

            archived = memory_maintain(
                root,
                "archive_knowledge",
                {
                    "knowledge_id": knowledge_id,
                    "reason": "Temporary note is no longer useful.",
                },
                {"apply": True},
            )
            archived_item = FsObjectRepository(root).get("knowledge", knowledge_id)

            self.assertEqual(archived["result_type"], "archive_knowledge_result")
            self.assertEqual(archived["archived_knowledge_id"], knowledge_id)
            self.assertEqual(archived_item["status"], "archived")
            self.assertEqual(archived_item["lifecycle_state"], "archived")


if __name__ == "__main__":
    unittest.main()
