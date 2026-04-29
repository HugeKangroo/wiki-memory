from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.remember.service import RememberService
from memory_substrate.application.query.service import QueryService
from memory_substrate.domain.protocols.context_pack import ContextPack


class ContextPackContractTest(unittest.TestCase):
    def test_context_pack_defaults_include_memory_core_sections(self) -> None:
        pack = ContextPack(id="ctx:test", task="test", summary="summary")

        self.assertEqual(pack.evidence, [])
        self.assertEqual(pack.decisions, [])
        self.assertEqual(pack.procedures, [])
        self.assertEqual(pack.open_work, [])
        self.assertEqual(pack.freshness, {})
        self.assertEqual(pack.context_tiers, {})
        self.assertEqual(pack.context_budget, {})

    def test_query_context_returns_work_ready_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            remember = RememberService(tmp)
            decision = remember.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Use GraphBackend boundary",
                    "summary": "Graph integrations sit behind a project-owned backend boundary.",
                    "payload": {"question": "How should graph libraries integrate?", "outcome": "Use GraphBackend"},
                    "status": "candidate",
                    "confidence": 0.8,
                    "evidence_refs": [{"source_id": "src:design", "segment_id": "seg:1"}],
                }
            )
            procedure = remember.create_knowledge(
                {
                    "kind": "procedure",
                    "title": "Run backend spike",
                    "summary": "Evaluate each backend through the same GraphBackend contract.",
                    "payload": {"goal": "Compare memory backend libraries", "steps": ["Use the contract"]},
                    "status": "candidate",
                    "confidence": 0.7,
                }
            )
            work_item = remember.create_work_item(
                {
                    "kind": "implementation",
                    "title": "Implement Graphiti spike",
                    "summary": "Run the Graphiti backend spike behind the contract.",
                    "status": "open",
                    "priority": "medium",
                    "related_knowledge_refs": [decision["knowledge_id"], procedure["knowledge_id"]],
                }
            )

            context = QueryService(tmp).context("choose graph backend", max_items=10)
            data = context["data"]

            self.assertIn("evidence", data)
            self.assertIn("decisions", data)
            self.assertIn("procedures", data)
            self.assertIn("open_work", data)
            self.assertIn("freshness", data)
            self.assertEqual(data["decisions"][0]["id"], decision["knowledge_id"])
            self.assertEqual(data["procedures"][0]["id"], procedure["knowledge_id"])
            self.assertEqual(data["open_work"][0]["id"], work_item["work_item_id"])
            self.assertEqual(data["evidence"], data["citations"])
            self.assertEqual(data["freshness"]["generated_at"], data["generated_at"])

    def test_query_context_returns_tiered_budgeted_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            remember = RememberService(tmp)
            decision = remember.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Keep canonical data separate",
                    "summary": "Indexes are derived and rebuildable.",
                    "status": "candidate",
                    "confidence": 0.8,
                }
            )
            work = remember.create_work_item(
                {
                    "kind": "implementation",
                    "title": "Add context tiers",
                    "summary": "Expose context tiers for MCP agents.",
                    "status": "open",
                }
            )

            data = QueryService(tmp).context("context tier design", max_items=4)["data"]

            self.assertEqual(data["context_budget"]["max_items"], 4)
            self.assertEqual(data["context_budget"]["returned_items"], len(data["items"]))
            self.assertEqual(data["context_budget"]["detail"], "compact")
            self.assertIn("active_task", data["context_tiers"])
            self.assertIn("decisions", data["context_tiers"])
            self.assertIn("open_work", data["context_tiers"])
            self.assertIn("deep_search_hints", data["context_tiers"])
            self.assertEqual(data["context_tiers"]["active_task"]["task"], "context tier design")
            self.assertEqual(data["context_tiers"]["decisions"][0]["id"], decision["knowledge_id"])
            self.assertEqual(data["context_tiers"]["open_work"][0]["id"], work["work_item_id"])
            self.assertEqual(data["context_tiers"]["deep_search_hints"][0]["tool"], "memory_query")


if __name__ == "__main__":
    unittest.main()
