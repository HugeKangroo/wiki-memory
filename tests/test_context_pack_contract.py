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


if __name__ == "__main__":
    unittest.main()
