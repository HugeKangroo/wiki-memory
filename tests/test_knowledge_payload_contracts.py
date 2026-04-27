from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.domain.protocols.knowledge_payloads import DecisionPayload, ProcedurePayload


class KnowledgePayloadContractsTest(unittest.TestCase):
    def test_decision_payload_serializes_required_shape(self) -> None:
        payload = DecisionPayload(
            question="Which backend abstraction should own graph integration?",
            outcome="Use GraphBackend",
            rationale="Avoid binding MCP and memory semantics to one library.",
            alternatives=["Graphiti direct", "Raw Neo4j"],
        )

        self.assertEqual(
            payload.to_payload(),
            {
                "question": "Which backend abstraction should own graph integration?",
                "outcome": "Use GraphBackend",
                "rationale": "Avoid binding MCP and memory semantics to one library.",
                "alternatives": ["Graphiti direct", "Raw Neo4j"],
                "constraints": [],
                "consequences": [],
                "revisit_conditions": [],
            },
        )

    def test_procedure_payload_serializes_defaults(self) -> None:
        payload = ProcedurePayload(
            goal="Evaluate a memory backend library",
            steps=["Run the same GraphBackend contract tests"],
        )

        self.assertEqual(payload.to_payload()["goal"], "Evaluate a memory backend library")
        self.assertEqual(payload.to_payload()["steps"], ["Run the same GraphBackend contract tests"])
        self.assertEqual(payload.to_payload()["preconditions"], [])
        self.assertEqual(payload.to_payload()["expected_outcome"], "")
        self.assertEqual(payload.to_payload()["failure_modes"], [])
        self.assertEqual(payload.to_payload()["examples"], [])


if __name__ == "__main__":
    unittest.main()
