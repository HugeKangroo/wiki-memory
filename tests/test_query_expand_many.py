from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.ingest.service import IngestService
from memory_substrate.application.query.service import QueryService
from memory_substrate.application.remember.service import RememberService
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.interfaces.mcp.tools import memory_query


class QueryExpandManyTest(unittest.TestCase):
    def _seed_memory(self, root: Path) -> dict:
        document = root / "guide.md"
        document.write_text("# Guide\n\nInstall memory substrate.\n\nUse source evidence.\n", encoding="utf-8")
        ingest_result = IngestService(root).ingest_markdown(document)
        source = FsObjectRepository(root).get("source", ingest_result["source_id"])
        assert source is not None
        segment_id = source["segments"][0]["segment_id"]
        knowledge_result = RememberService(root).create_knowledge(
            {
                "kind": "fact",
                "title": "Guide uses source evidence",
                "summary": "The guide explains that source evidence should be used.",
                "subject_refs": [ingest_result["node_id"]],
                "evidence_refs": [{"source_id": ingest_result["source_id"], "segment_id": segment_id}],
                "payload": {
                    "subject": ingest_result["node_id"],
                    "predicate": "describes",
                    "value": "source evidence",
                },
                "status": "active",
                "confidence": 0.9,
            }
        )
        work_item_result = RememberService(root).create_work_item(
            {
                "kind": "task",
                "title": "Review source evidence workflow",
                "summary": "Check the multi-id expand path.",
                "status": "open",
                "related_node_refs": [ingest_result["node_id"]],
            }
        )
        return {
            "source_id": ingest_result["source_id"],
            "knowledge_id": knowledge_result["knowledge_id"],
            "work_item_id": work_item_result["work_item_id"],
        }

    def test_expand_many_groups_results_by_root_and_reports_missing_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ids = self._seed_memory(root)

            result = QueryService(root).expand_many(
                [ids["knowledge_id"], ids["source_id"], "know:missing"],
                max_items=8,
                per_id_max_items=3,
                include_segments=True,
                snippet_chars=80,
            )

            self.assertEqual(result["result_type"], "expanded_context_many")
            self.assertEqual(result["data"]["root_ids"], [ids["knowledge_id"], ids["source_id"], "know:missing"])
            self.assertEqual(result["data"]["groups"][ids["knowledge_id"]]["status"], "ok")
            self.assertEqual(result["data"]["groups"][ids["source_id"]]["status"], "ok")
            self.assertEqual(result["data"]["groups"]["know:missing"]["status"], "not_found")
            self.assertIn("Object not found: know:missing", result["warnings"])
            self.assertGreater(len(result["data"]["groups"][ids["knowledge_id"]]["items"]), 0)
            self.assertGreater(len(result["data"]["source_segments"]), 0)
            self.assertLessEqual(result["data"]["context_budget"]["returned_items"], 8)
            self.assertEqual(result["data"]["context_budget"]["per_id_max_items"], 3)

    def test_expand_many_respects_total_item_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ids = self._seed_memory(root)

            result = QueryService(root).expand_many(
                [ids["knowledge_id"], ids["source_id"], ids["work_item_id"]],
                max_items=2,
                per_id_max_items=2,
            )

            group_statuses = [group["status"] for group in result["data"]["groups"].values()]

            self.assertEqual(result["data"]["context_budget"]["returned_items"], 2)
            self.assertIn("budget_exhausted", group_statuses)
            self.assertIn("Global expand item budget exhausted before all ids were expanded.", result["warnings"])

    def test_memory_query_expand_accepts_ids_for_mcp_callers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ids = self._seed_memory(root)

            result = memory_query(
                root,
                "expand",
                {"ids": [ids["knowledge_id"], ids["source_id"]]},
                {"max_items": 6, "per_id_max_items": 3},
            )

            self.assertEqual(result["result_type"], "expanded_context_many")
            self.assertEqual(set(result["data"]["groups"].keys()), {ids["knowledge_id"], ids["source_id"]})


if __name__ == "__main__":
    unittest.main()
