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

    def test_user_declared_knowledge_without_evidence_gets_declaration_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)

            result = service.create_knowledge(
                {
                    "kind": "preference",
                    "title": "Prefer local memory backends",
                    "summary": "The user prefers local-first memory backends.",
                    "reason": "This preference should guide future backend choices.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:memory-substrate"],
                    "status": "active",
                    "confidence": 1.0,
                }
            )
            stored = FsObjectRepository(root).get("knowledge", result["knowledge_id"])
            assert stored is not None
            evidence_ref = stored["evidence_refs"][0]
            declaration_source = FsObjectRepository(root).get("source", evidence_ref["source_id"])

            self.assertEqual(result["evidence_contract"]["provenance"], "declaration_source_created")
            self.assertEqual(stored["status"], "active")
            self.assertEqual(len(stored["evidence_refs"]), 1)
            self.assertIsNotNone(declaration_source)
            assert declaration_source is not None
            self.assertEqual(declaration_source["kind"], "declaration")
            self.assertIn("Prefer local memory backends", declaration_source["payload"]["text"])
            self.assertEqual(evidence_ref["segment_id"], declaration_source["segments"][0]["segment_id"])
            self.assertEqual(evidence_ref["hash"], declaration_source["segments"][0]["hash"])

    def test_long_user_declared_knowledge_preserves_source_text_as_declaration_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_text = (
                "Temporary review note:\n"
                "The remember API should preserve the raw user statement before compressing it into knowledge.\n"
                "The derived knowledge can be short, but the fact layer should remain citeable.\n"
            )

            result = RememberService(root).create_knowledge(
                {
                    "kind": "design_note",
                    "title": "Remember preserves raw declaration evidence",
                    "summary": "Remember creates declaration evidence before storing a compressed knowledge item.",
                    "reason": "This design changes the future remember contract.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:memory-substrate"],
                    "source_text": source_text,
                    "status": "active",
                    "confidence": 0.95,
                }
            )
            stored = FsObjectRepository(root).get("knowledge", result["knowledge_id"])
            assert stored is not None
            evidence_ref = stored["evidence_refs"][0]
            declaration_source = FsObjectRepository(root).get("source", evidence_ref["source_id"])

            self.assertEqual(result["evidence_contract"]["provenance"], "declaration_source_created")
            self.assertIsNotNone(declaration_source)
            assert declaration_source is not None
            self.assertEqual(declaration_source["payload"]["text"], source_text)
            self.assertEqual(declaration_source["segments"][0]["locator"]["line_end"], 3)
            self.assertEqual(stored["evidence_refs"], [evidence_ref])

    def test_agent_inferred_source_text_is_preserved_but_remains_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_text = (
                "Agent analysis draft:\n"
                "The memory system should preserve raw long-form analysis before summarizing it.\n"
            )

            result = RememberService(root).create_knowledge(
                {
                    "kind": "design_note",
                    "title": "Long agent analysis should keep source text",
                    "summary": "Long agent-inferred remember inputs are preserved as source evidence.",
                    "reason": "The source layer is needed for later review.",
                    "memory_source": "agent_inferred",
                    "scope_refs": ["scope:memory-substrate"],
                    "source_text": source_text,
                    "status": "active",
                    "confidence": 0.74,
                }
            )
            stored = FsObjectRepository(root).get("knowledge", result["knowledge_id"])
            assert stored is not None
            evidence_ref = stored["evidence_refs"][0]
            source = FsObjectRepository(root).get("source", evidence_ref["source_id"])

            self.assertEqual(result["status"], "candidate")
            self.assertEqual(result["evidence_contract"]["provenance"], "remember_input_source_created")
            self.assertIsNotNone(source)
            assert source is not None
            self.assertEqual(source["payload"]["text"], source_text)
            self.assertEqual(stored["status"], "candidate")
            self.assertEqual(stored["evidence_refs"], [evidence_ref])

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

    def test_create_knowledge_allows_same_signature_for_different_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)
            base_payload = {
                "subject": "node:memory-substrate",
                "predicate": "uses_graph_backend",
                "object": "node:kuzu",
            }
            fact = service.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Memory uses Kuzu",
                    "summary": "Kuzu is the local graph backend.",
                    "reason": "The backend spike selected Kuzu for local graph storage.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:memory-substrate"],
                    "payload": base_payload,
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            decision = service.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Use Kuzu locally",
                    "summary": "This records the decision behind the local graph backend.",
                    "reason": "The decision rationale should survive future backend work.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:memory-substrate"],
                    "payload": base_payload,
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            self.assertNotEqual(fact["knowledge_id"], decision["knowledge_id"])

    def test_create_knowledge_allows_same_signature_in_different_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)
            payload = {
                "subject": "node:agent",
                "predicate": "prefers",
                "value": "local graph backend",
            }
            first = service.create_knowledge(
                {
                    "kind": "preference",
                    "title": "Project A prefers local graph backend",
                    "summary": "The preference applies to project A.",
                    "reason": "Project A should keep local-first backend defaults.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:project-a"],
                    "subject_refs": ["node:agent"],
                    "payload": payload,
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            second = service.create_knowledge(
                {
                    "kind": "preference",
                    "title": "Project B prefers local graph backend",
                    "summary": "The preference applies to project B.",
                    "reason": "Project B independently uses local-first backend defaults.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:project-b"],
                    "subject_refs": ["node:agent"],
                    "payload": payload,
                    "status": "active",
                    "confidence": 1.0,
                }
            )
            repository = FsObjectRepository(root)

            self.assertNotEqual(first["knowledge_id"], second["knowledge_id"])
            self.assertNotEqual(
                repository.get("knowledge", first["knowledge_id"])["identity_key"],
                repository.get("knowledge", second["knowledge_id"])["identity_key"],
            )

    def test_create_knowledge_marks_conflicting_preference_in_same_scope_as_contested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)
            first = service.create_knowledge(
                {
                    "kind": "preference",
                    "title": "Agent prefers Kuzu",
                    "summary": "The agent preference applies in this project.",
                    "reason": "The user selected a local graph backend.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:agent"],
                    "payload": {
                        "subject": "node:agent",
                        "predicate": "prefers_graph_backend",
                        "object": "node:kuzu",
                    },
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            second = service.create_knowledge(
                {
                    "kind": "preference",
                    "title": "Agent prefers Neo4j",
                    "summary": "This conflicts with the existing project preference.",
                    "reason": "The inferred preference conflicts with the user-selected backend.",
                    "memory_source": "agent_inferred",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:agent"],
                    "payload": {
                        "subject": "node:agent",
                        "predicate": "prefers_graph_backend",
                        "object": "node:neo4j",
                    },
                    "status": "candidate",
                    "confidence": 0.7,
                }
            )
            stored = FsObjectRepository(root).get("knowledge", second["knowledge_id"])

            self.assertEqual(stored["status"], "contested")
            self.assertEqual(stored["conflicts_with"], [first["knowledge_id"]])

    def test_create_unstructured_knowledge_returns_possible_duplicate_without_rejecting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)
            first = service.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Use Kuzu as the local graph backend",
                    "summary": "Kuzu is the selected local graph backend for lightweight prototypes.",
                    "reason": "This decision should guide backend work.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:memory-substrate"],
                    "payload": {},
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            second = service.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Kuzu remains the local graph backend",
                    "summary": "The local prototype graph backend should stay on Kuzu.",
                    "reason": "This may duplicate an existing backend decision.",
                    "memory_source": "agent_inferred",
                    "scope_refs": ["scope:memory-substrate"],
                    "payload": {},
                    "status": "candidate",
                    "confidence": 0.7,
                }
            )
            stored = FsObjectRepository(root).get("knowledge", second["knowledge_id"])

            self.assertEqual(stored["status"], "candidate")
            self.assertEqual(second["possible_duplicates"][0]["object_id"], first["knowledge_id"])
            self.assertGreaterEqual(second["possible_duplicates"][0]["score"], 0.5)
            self.assertIn("title_overlap", second["possible_duplicates"][0]["reasons"])
            self.assertIn("summary_overlap", second["possible_duplicates"][0]["reasons"])

    def test_unstructured_possible_duplicates_respect_scope_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = RememberService(root)
            service.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Use Kuzu as the local graph backend",
                    "summary": "Kuzu is the selected local graph backend for lightweight prototypes.",
                    "reason": "This decision applies only to project A.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:project-a"],
                    "payload": {},
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            second = service.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Kuzu remains the local graph backend",
                    "summary": "The local prototype graph backend should stay on Kuzu.",
                    "reason": "This similar decision applies to project B.",
                    "memory_source": "user_declared",
                    "scope_refs": ["scope:project-b"],
                    "payload": {},
                    "status": "active",
                    "confidence": 1.0,
                }
            )

            self.assertEqual(second["possible_duplicates"], [])

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

    def test_create_knowledge_accepts_matching_evidence_locator_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_source(root)
            service = RememberService(root)
            evidence_ref = {
                "source_id": source_id,
                "segment_id": "seg:valid",
                "locator": {"kind": "message", "index": 1},
                "hash": "valid",
            }

            result = service.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Governance evidence details are traceable",
                    "summary": "Valid locator and hash details are accepted.",
                    "reason": "This verifies detailed evidence validation.",
                    "memory_source": "system_generated",
                    "scope_refs": ["scope:memory-substrate"],
                    "subject_refs": ["node:remember"],
                    "evidence_refs": [evidence_ref],
                    "payload": {
                        "subject": "node:remember",
                        "predicate": "has_detailed_evidence",
                        "value": True,
                    },
                    "status": "active",
                    "confidence": 0.95,
                }
            )

            stored = FsObjectRepository(root).get("knowledge", result["knowledge_id"])

            self.assertEqual(stored["evidence_refs"], [evidence_ref])

    def test_create_knowledge_rejects_mismatched_evidence_locator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_source(root)
            service = RememberService(root)

            with self.assertRaisesRegex(ValueError, f"locator mismatch: {source_id}#seg:valid"):
                service.create_knowledge(
                    {
                        "kind": "fact",
                        "title": "Mismatched locator evidence",
                        "summary": "This evidence locator does not match the source segment.",
                        "reason": "Invalid evidence details must not enter durable memory.",
                        "memory_source": "system_generated",
                        "scope_refs": ["scope:memory-substrate"],
                        "subject_refs": ["node:remember"],
                        "evidence_refs": [
                            {
                                "source_id": source_id,
                                "segment_id": "seg:valid",
                                "locator": {"kind": "message", "index": 2},
                            }
                        ],
                        "payload": {
                            "subject": "node:remember",
                            "predicate": "has_detailed_evidence",
                            "value": False,
                        },
                        "status": "candidate",
                        "confidence": 0.5,
                    }
                )

    def test_create_knowledge_rejects_mismatched_evidence_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_source(root)
            service = RememberService(root)

            with self.assertRaisesRegex(ValueError, f"hash mismatch: {source_id}#seg:valid"):
                service.create_knowledge(
                    {
                        "kind": "fact",
                        "title": "Mismatched hash evidence",
                        "summary": "This evidence hash does not match the source segment.",
                        "reason": "Invalid evidence details must not enter durable memory.",
                        "memory_source": "system_generated",
                        "scope_refs": ["scope:memory-substrate"],
                        "subject_refs": ["node:remember"],
                        "evidence_refs": [
                            {
                                "source_id": source_id,
                                "segment_id": "seg:valid",
                                "hash": "wrong",
                            }
                        ],
                        "payload": {
                            "subject": "node:remember",
                            "predicate": "has_detailed_evidence",
                            "value": False,
                        },
                        "status": "candidate",
                        "confidence": 0.5,
                    }
                )

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
