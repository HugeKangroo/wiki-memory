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
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class RememberGovernanceTest(unittest.TestCase):
    def _seed_source(self, root: Path) -> str:
        source_id = "src:governance"
        FsObjectRepository(root).save(
            "source",
            {
                "id": source_id,
                "kind": "conversation",
                "origin": {"host": "test"},
                "title": "Governance source",
                "identity_key": "source|test|governance",
                "fingerprint": "governance",
                "content_type": "text",
                "payload": {},
                "segments": [
                    {
                        "segment_id": "seg:valid",
                        "locator": {"kind": "message", "index": 1},
                        "excerpt": "Governance evidence.",
                        "hash": "valid",
                    }
                ],
                "created_at": "2026-04-28T00:00:00+00:00",
                "updated_at": "2026-04-28T00:00:00+00:00",
            },
        )
        return source_id

    def test_create_knowledge_persists_governance_and_normalizes_agent_active_to_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)

            result = service.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Governed memory writes",
                    "summary": "Remember writes include reason, source, and scope.",
                    "reason": "This constrains future agent memory writes.",
                    "memory_source": "agent_inferred",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:remember"],
                    "payload": {
                        "subject": "node:remember",
                        "predicate": "requires",
                        "value": "governance",
                    },
                    "status": "active",
                    "confidence": 0.9,
                }
            )

            stored = FsObjectRepository(root).get("knowledge", result["knowledge_id"])

            self.assertEqual(stored["status"], "candidate")
            self.assertEqual(stored["reason"], "This constrains future agent memory writes.")
            self.assertEqual(stored["memory_source"], "agent_inferred")
            self.assertEqual(stored["scope_refs"], ["scope:memory-substrate"])
            self.assertEqual(stored["payload"]["metadata"]["memory_source"], "agent_inferred")
            self.assertTrue(stored["identity_key"].startswith("knowledge|decision|"))

    def test_create_knowledge_rejects_duplicate_fact_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)
            data = {
                "kind": "fact",
                "title": "Memory uses Kuzu",
                "summary": "Kuzu is the local graph backend.",
                "reason": "The backend spike selected Kuzu for local graph storage.",
                "memory_source": "user_declared",
                "scope_refs": ["scope:memory-substrate"],
                "subject_refs": ["node:memory-substrate"],
                "payload": {
                    "subject": "node:memory-substrate",
                    "predicate": "uses_graph_backend",
                    "object": "node:kuzu",
                },
                "status": "active",
                "confidence": 1.0,
            }

            first = service.create_knowledge(data)

            with self.assertRaisesRegex(ValueError, first["knowledge_id"]):
                service.create_knowledge(data)

    def test_create_knowledge_marks_conflicting_fact_as_contested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)
            first = service.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Memory graph backend is Kuzu",
                    "summary": "Kuzu is the local graph backend.",
                    "reason": "The user selected Kuzu for local graph storage.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:memory-substrate"],
                    "payload": {
                        "subject": "node:memory-substrate",
                        "predicate": "uses_graph_backend",
                        "object": "node:kuzu",
                    },
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            second = service.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Memory graph backend is Neo4j",
                    "summary": "Neo4j is the local graph backend.",
                    "reason": "A later claim conflicts with the selected local graph backend.",
                    "memory_source": "agent_inferred",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:memory-substrate"],
                    "payload": {
                        "subject": "node:memory-substrate",
                        "predicate": "uses_graph_backend",
                        "object": "node:neo4j",
                    },
                    "status": "candidate",
                    "confidence": 0.6,
                }
            )
            stored = FsObjectRepository(root).get("knowledge", second["knowledge_id"])

            self.assertEqual(stored["status"], "contested")
            self.assertEqual(stored["conflicts_with"], [first["knowledge_id"]])
            self.assertEqual(stored["payload"]["metadata"]["conflicts_with"], [first["knowledge_id"]])

    def test_create_knowledge_accepts_active_with_valid_evidence_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_source(root)
            service = RememberService(root)

            result = service.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Governance evidence is traceable",
                    "summary": "Valid evidence refs allow active system-generated knowledge.",
                    "reason": "This verifies evidence reference validation.",
                    "memory_source": "system_generated",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:remember"],
                    "evidence_refs": [{"source_id": source_id, "segment_id": "seg:valid"}],
                    "payload": {
                        "subject": "node:remember",
                        "predicate": "has_traceable_evidence",
                        "value": True,
                    },
                    "status": "active",
                    "confidence": 0.95,
                }
            )

            stored = FsObjectRepository(root).get("knowledge", result["knowledge_id"])

            self.assertEqual(stored["status"], "active")
            self.assertEqual(stored["evidence_refs"], [{"source_id": source_id, "segment_id": "seg:valid"}])

    def test_create_knowledge_rejects_missing_evidence_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)

            with self.assertRaisesRegex(ValueError, "source not found: src:missing"):
                service.create_knowledge(
                    {
                        "kind": "fact",
                        "title": "Missing source evidence",
                        "summary": "This evidence ref points nowhere.",
                        "reason": "Invalid evidence must not enter durable memory.",
                        "memory_source": "system_generated",
                        "scope_refs": ["scope:memory-substrate"],
                        "subject_refs": ["node:remember"],
                        "evidence_refs": [{"source_id": "src:missing", "segment_id": "seg:valid"}],
                        "payload": {
                            "subject": "node:remember",
                            "predicate": "has_traceable_evidence",
                            "value": False,
                        },
                        "status": "candidate",
                        "confidence": 0.5,
                    }
                )

    def test_create_knowledge_rejects_missing_evidence_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_source(root)
            service = RememberService(root)

            with self.assertRaisesRegex(ValueError, f"segment not found: {source_id}#seg:missing"):
                service.create_knowledge(
                    {
                        "kind": "fact",
                        "title": "Missing segment evidence",
                        "summary": "This evidence ref points to a missing source segment.",
                        "reason": "Invalid evidence must not enter durable memory.",
                        "memory_source": "system_generated",
                        "scope_refs": ["scope:memory-substrate"],
                        "subject_refs": ["node:remember"],
                        "evidence_refs": [{"source_id": source_id, "segment_id": "seg:missing"}],
                        "payload": {
                            "subject": "node:remember",
                            "predicate": "has_traceable_evidence",
                            "value": False,
                        },
                        "status": "candidate",
                        "confidence": 0.5,
                    }
                )


if __name__ == "__main__":
    unittest.main()
