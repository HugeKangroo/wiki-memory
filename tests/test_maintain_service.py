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
from memory_substrate.application.maintain.service import MaintainService
from memory_substrate.application.maintain.lifecycle import MaintenanceLifecycle
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.infrastructure.storage.paths import StoragePaths


class MaintenanceLifecycleTest(unittest.TestCase):
    def _seed_source(self, root: Path, source_id: str) -> str:
        repository = FsObjectRepository(root)
        repository.save(
            "source",
            {
                "id": source_id,
                "kind": "note",
                "origin": {"path": f"/tmp/{source_id}.md"},
                "title": source_id,
                "identity_key": f"source|test|{source_id}",
                "fingerprint": source_id,
                "content_type": "markdown",
                "payload": {"title": source_id},
                "segments": [{"segment_id": "seg-1", "locator": {"kind": "line", "line": 1}, "excerpt": source_id, "hash": source_id}],
                "metadata": {},
                "status": "active",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        )
        return source_id

    def _seed_node(self, root: Path, node_id: str = "node:test-subject") -> str:
        repository = FsObjectRepository(root)
        repository.save(
            "node",
            {
                "id": node_id,
                "kind": "project",
                "name": "Test Subject",
                "slug": "test-subject",
                "identity_key": f"node|test|{node_id}",
                "aliases": [],
                "summary": "Synthetic subject for maintain tests.",
                "status": "active",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        )
        return node_id

    def test_promote_candidates_activates_eligible_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            source_id = self._seed_source(root, "src:test")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)

            knowledge = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Qualified candidate",
                    "summary": "Candidate with enough evidence and confidence.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_id, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "supports",
                        "value": "promotion",
                        "object": None,
                    },
                    "confidence": 0.9,
                }
            )

            result = maintain.promote_candidates(min_confidence=0.75, min_evidence=1)
            stored = FsObjectRepository(root).get("knowledge", knowledge["knowledge_id"])

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["promoted"], 1)
            self.assertEqual(stored["status"], "active")
            self.assertEqual(stored["reason"], "maintain_promote_candidates")
            self.assertTrue(stored["last_verified_at"])

    def test_merge_duplicates_supersedes_loser_and_merges_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            source_one = self._seed_source(root, "src:one")
            source_two = self._seed_source(root, "src:two")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)
            repository = FsObjectRepository(root)

            older = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Primary language older",
                    "summary": "Older duplicate fact.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_one, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "primary_language",
                        "value": "python",
                        "object": None,
                    },
                    "confidence": 0.7,
                }
            )
            newer = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Primary language newer",
                    "summary": "Newer duplicate fact.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_two, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "primary_language",
                        "value": "python",
                        "object": None,
                    },
                    "confidence": 0.95,
                }
            )

            result = maintain.merge_duplicates()
            winner = repository.get("knowledge", newer["knowledge_id"])
            loser = repository.get("knowledge", older["knowledge_id"])

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["merged"], 1)
            self.assertEqual(winner["status"], "candidate")
            self.assertEqual(loser["status"], "superseded")
            self.assertEqual(winner["reason"], f"maintain_merge_winner:{older['knowledge_id']}")
            self.assertEqual(loser["reason"], f"maintain_merge_loser:{newer['knowledge_id']}")
            self.assertEqual(
                {(ref["source_id"], ref["segment_id"]) for ref in winner["evidence_refs"]},
                {(source_one, "seg-1"), (source_two, "seg-1")},
            )

    def test_merge_duplicates_is_noop_after_losers_are_superseded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            source_one = self._seed_source(root, "src:one")
            source_two = self._seed_source(root, "src:two")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)

            for title, source_id, confidence in (("Duplicate one", source_one, 0.7), ("Duplicate two", source_two, 0.9)):
                remember.create_knowledge(
                    {
                        "kind": "fact",
                        "title": title,
                        "summary": "Duplicate fact.",
                        "subject_refs": [subject_id],
                        "evidence_refs": [{"source_id": source_id, "segment_id": "seg-1"}],
                        "payload": {
                            "subject": subject_id,
                            "predicate": "primary_language",
                            "value": "python",
                            "object": None,
                        },
                        "confidence": confidence,
                    }
                )

            first = maintain.merge_duplicates()
            second = maintain.merge_duplicates()

            self.assertEqual(first["merged"], 1)
            self.assertEqual(second["status"], "noop")
            self.assertEqual(second["merged"], 0)

    def test_merge_duplicates_does_not_merge_facts_with_different_object_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            source_one = self._seed_source(root, "src:one")
            source_two = self._seed_source(root, "src:two")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)
            repository = FsObjectRepository(root)

            first = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Ownership A",
                    "summary": "First ownership fact.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_one, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "owned_by",
                        "value": None,
                        "object": "team:a",
                    },
                    "confidence": 0.7,
                }
            )
            second = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Ownership B",
                    "summary": "Second ownership fact.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_two, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "owned_by",
                        "value": None,
                        "object": "team:b",
                    },
                    "confidence": 0.9,
                }
            )

            result = maintain.merge_duplicates()

            self.assertEqual(result["merged"], 0)
            self.assertEqual(repository.get("knowledge", first["knowledge_id"])["status"], "candidate")
            self.assertEqual(repository.get("knowledge", second["knowledge_id"])["status"], "candidate")

    def test_report_flags_active_agent_inferred_knowledge_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)

            flagged = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Agent inferred active claim",
                    "summary": "This active claim has no evidence.",
                    "status": "active",
                    "confidence": 0.8,
                    "payload": {
                        "subject": "memory_remember",
                        "predicate": "requires",
                        "value": "evidence",
                        "metadata": {"memory_source": "agent_inferred"},
                    },
                }
            )
            allowed = remember.create_knowledge(
                {
                    "kind": "preference",
                    "title": "User declared active preference",
                    "summary": "User-declared memory can be active without external evidence.",
                    "status": "active",
                    "confidence": 1.0,
                    "payload": {
                        "subject": "user",
                        "predicate": "prefers",
                        "value": "local-first memory",
                        "metadata": {"memory_source": "user_declared"},
                    },
                }
            )

            report = maintain.report()
            violations = report["data"]["governance_violations"]

            self.assertEqual(report["data"]["counts"]["governance_violations"], 1)
            self.assertEqual(violations[0]["object_id"], flagged["knowledge_id"])
            self.assertEqual(violations[0]["kind"], "active_knowledge_without_evidence")
            self.assertNotEqual(violations[0]["object_id"], allowed["knowledge_id"])

    def test_merge_duplicates_preserves_active_status_when_merging_candidate_into_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            source_one = self._seed_source(root, "src:one")
            source_two = self._seed_source(root, "src:two")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)
            repository = FsObjectRepository(root)

            active = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Active language fact",
                    "summary": "Already promoted fact.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_one, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "primary_language",
                        "value": "python",
                        "object": None,
                    },
                    "status": "active",
                    "confidence": 0.8,
                }
            )
            candidate = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Candidate language fact",
                    "summary": "Higher confidence candidate duplicate.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_two, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "primary_language",
                        "value": "python",
                        "object": None,
                    },
                    "status": "candidate",
                    "confidence": 0.95,
                }
            )

            result = maintain.merge_duplicates()
            active_item = repository.get("knowledge", active["knowledge_id"])
            candidate_item = repository.get("knowledge", candidate["knowledge_id"])

            self.assertEqual(result["merged"], 1)
            self.assertEqual(active_item["status"], "active")
            self.assertEqual(candidate_item["status"], "superseded")

    def test_decay_stale_marks_old_knowledge_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            source_id = self._seed_source(root, "src:test")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)
            repository = FsObjectRepository(root)

            knowledge = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Old fact",
                    "summary": "Should become stale.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_id, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "age",
                        "value": "old",
                        "object": None,
                    },
                    "status": "active",
                    "confidence": 0.8,
                    "last_verified_at": "2026-01-01T00:00:00+00:00",
                }
            )

            result = maintain.decay_stale(reference_time="2026-04-24T00:00:00+00:00", stale_after_days=30)
            stored = repository.get("knowledge", knowledge["knowledge_id"])

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["decayed"], 1)
            self.assertEqual(stored["status"], "stale")
            self.assertEqual(stored["reason"], "maintain_decay_stale")

    def test_report_summarizes_candidates_duplicates_stale_and_low_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            source_one = self._seed_source(root, "src:one")
            source_two = self._seed_source(root, "src:two")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)

            promotable = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Promotable report item",
                    "summary": "Enough confidence and evidence.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_one, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "report_promote",
                        "value": True,
                        "object": None,
                    },
                    "confidence": 0.9,
                }
            )
            low_evidence = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Low evidence report item",
                    "summary": "No evidence.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "report_low_evidence",
                        "value": True,
                        "object": None,
                    },
                    "confidence": 0.9,
                }
            )
            duplicate_one = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Duplicate one",
                    "summary": "Duplicate report fact.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_one, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "duplicate",
                        "value": "same",
                        "object": None,
                    },
                    "confidence": 0.7,
                }
            )
            duplicate_two = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Duplicate two",
                    "summary": "Duplicate report fact.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_two, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "duplicate",
                        "value": "same",
                        "object": None,
                    },
                    "confidence": 0.8,
                }
            )
            stale = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Stale report item",
                    "summary": "Old verification.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": source_one, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "report_stale",
                        "value": True,
                        "object": None,
                    },
                    "status": "active",
                    "confidence": 0.8,
                    "last_verified_at": "2026-01-01T00:00:00+00:00",
                }
            )

            report = maintain.report(reference_time="2026-04-24T00:00:00+00:00", min_confidence=0.75, min_evidence=1)

            self.assertEqual(report["result_type"], "maintain_report")
            self.assertIn(promotable["knowledge_id"], report["data"]["promote_candidate_ids"])
            self.assertIn(low_evidence["knowledge_id"], report["data"]["low_evidence_candidate_ids"])
            self.assertIn(stale["knowledge_id"], report["data"]["stale_candidate_ids"])
            self.assertEqual(
                {tuple(group) for group in report["data"]["duplicate_groups"]},
                {(duplicate_one["knowledge_id"], duplicate_two["knowledge_id"])},
            )

    def test_cycle_runs_all_maintain_steps_and_rebuilds_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subject_id = self._seed_node(root)
            promote_source = self._seed_source(root, "src:promote")
            stale_source = self._seed_source(root, "src:stale")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)
            paths = StoragePaths(root)
            validator = MaintainService(root)

            promotable = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Promotable",
                    "summary": "Will be promoted.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": promote_source, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "promotable",
                        "value": True,
                        "object": None,
                    },
                    "confidence": 0.9,
                }
            )
            stale = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Stale item",
                    "summary": "Will decay.",
                    "subject_refs": [subject_id],
                    "evidence_refs": [{"source_id": stale_source, "segment_id": "seg-1"}],
                    "payload": {
                        "subject": subject_id,
                        "predicate": "stale",
                        "value": True,
                        "object": None,
                    },
                    "status": "active",
                    "confidence": 0.8,
                    "last_verified_at": "2026-01-01T00:00:00+00:00",
                }
            )

            result = maintain.cycle(reference_time="2026-04-24T00:00:00+00:00")

            self.assertEqual(result["status"], "completed")
            self.assertGreaterEqual(result["promoted"], 1)
            self.assertGreaterEqual(result["decayed"], 1)
            self.assertGreater(result["projection_count"], 0)
            self.assertTrue((paths.projections_root / "debug" / "knowledge" / f"{promotable['knowledge_id']}.md").exists())
            self.assertTrue((paths.projections_root / "debug" / "knowledge" / f"{stale['knowledge_id']}.md").exists())
            self.assertEqual(validator.structure()["data"]["counts"]["warning"], 0)
            self.assertEqual(validator.structure()["data"]["counts"]["error"], 0)


if __name__ == "__main__":
    unittest.main()
