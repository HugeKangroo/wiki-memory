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

    def test_report_surfaces_unstructured_soft_duplicate_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)
            first = remember.create_knowledge(
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
            second = remember.create_knowledge(
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

            report = maintain.report()

            self.assertEqual(report["data"]["counts"]["soft_duplicate_candidates"], 1)
            self.assertEqual(
                set(report["data"]["soft_duplicate_candidates"][0]["object_ids"]),
                {first["knowledge_id"], second["knowledge_id"]},
            )
            self.assertIn("title_overlap", report["data"]["soft_duplicate_candidates"][0]["reasons"])

    def test_report_surfaces_fact_checker_lifecycle_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            node_a = self._seed_node(root, "node:memory-substrate")
            self._seed_node(root, "node:memory_substrate")
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)

            stale = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Expired active fact",
                    "summary": "This fact is past its validity window.",
                    "subject_refs": [node_a],
                    "payload": {"subject": node_a, "predicate": "backend", "value": "file"},
                    "status": "active",
                    "valid_until": "2026-01-01T00:00:00+00:00",
                    "confidence": 0.8,
                }
            )
            first = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Backend is Kuzu",
                    "summary": "First backend claim.",
                    "subject_refs": [node_a],
                    "payload": {"subject": node_a, "predicate": "backend", "value": "kuzu"},
                    "status": "active",
                    "confidence": 0.8,
                }
            )
            second = remember.create_knowledge(
                {
                    "kind": "fact",
                    "title": "Backend is Neo4j",
                    "summary": "Conflicting backend claim.",
                    "subject_refs": [node_a],
                    "payload": {"subject": node_a, "predicate": "backend", "value": "neo4j"},
                    "status": "candidate",
                    "confidence": 0.7,
                }
            )

            report = maintain.report(reference_time="2026-04-30T00:00:00+00:00")
            issues = report["data"]["fact_check_issues"]
            issue_kinds = {issue["kind"] for issue in issues}

            self.assertIn("similar_entity_name", issue_kinds)
            self.assertIn("stale_fact", issue_kinds)
            self.assertIn("relationship_mismatch", issue_kinds)
            stale_issue = next(issue for issue in issues if issue["kind"] == "stale_fact")
            mismatch = next(issue for issue in issues if issue["kind"] == "relationship_mismatch")
            self.assertEqual(stale_issue["object_id"], stale["knowledge_id"])
            self.assertEqual(set(mismatch["object_ids"]), {first["knowledge_id"], second["knowledge_id"]})
            self.assertIn("contest", mismatch["next_actions"])
            self.assertEqual(report["data"]["counts"]["fact_check_issues"], len(issues))

    def test_report_surfaces_repeated_uncrystallized_concept_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repository = FsObjectRepository(root)
            repository.save(
                "source",
                {
                    "id": "src:concept-notes",
                    "kind": "markdown",
                    "origin": {"path": "/tmp/concept-notes.md"},
                    "title": "Concept Notes",
                    "identity_key": "source|test|concept-notes",
                    "fingerprint": "concept-notes",
                    "content_type": "markdown",
                    "payload": {"title": "Concept Notes"},
                    "segments": [
                        {
                            "segment_id": "seg-1",
                            "locator": {"kind": "source", "line_start": 1, "heading_path": ["Memory Substrate"]},
                            "excerpt": "Memory Substrate captures evidence before durable memory writes.",
                            "hash": "seg-1",
                        },
                        {
                            "segment_id": "seg-2",
                            "locator": {"kind": "source", "line_start": 5},
                            "excerpt": "The Memory Substrate should surface concept candidates before agents call memory_remember.",
                            "hash": "seg-2",
                        },
                    ],
                    "metadata": {},
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )
            maintain = MaintenanceLifecycle(root)

            report = maintain.report()

            candidates = report["data"]["concept_candidates"]
            candidate = next(item for item in candidates if item["title"] == "Memory Substrate")
            self.assertEqual(candidate["kind"], "concept_candidate")
            self.assertEqual(candidate["suggested_memory"]["kind"], "concept")
            self.assertIn("review_guidance", candidate)
            self.assertIn("remember_as_concept", {outcome["action"] for outcome in candidate["review_guidance"]["outcomes"]})
            self.assertIn("remember_as_procedure", {outcome["action"] for outcome in candidate["review_guidance"]["outcomes"]})
            self.assertEqual(candidate["source_count"], 1)
            self.assertGreaterEqual(candidate["occurrences"], 2)
            self.assertEqual(
                {evidence["segment_id"] for evidence in candidate["evidence_refs"]},
                {"seg-1", "seg-2"},
            )
            suggested_input = candidate["suggested_memory"]["input_data"]
            self.assertEqual(suggested_input["kind"], "concept")
            self.assertEqual(suggested_input["title"], "Memory Substrate")
            self.assertEqual(suggested_input["status"], "candidate")
            self.assertEqual(suggested_input["memory_source"], "agent_inferred")
            self.assertEqual(suggested_input["scope_refs"], ["src:concept-notes"])
            self.assertEqual(suggested_input["evidence_refs"], candidate["evidence_refs"])
            self.assertIn("review_and_remember", candidate["next_actions"])
            self.assertEqual(report["data"]["counts"]["concept_candidates"], len(candidates))

    def test_report_suppresses_concept_candidates_already_in_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repository = FsObjectRepository(root)
            repository.save(
                "source",
                {
                    "id": "src:retrieval-notes",
                    "kind": "markdown",
                    "origin": {"path": "/tmp/retrieval-notes.md"},
                    "title": "Retrieval Notes",
                    "identity_key": "source|test|retrieval-notes",
                    "fingerprint": "retrieval-notes",
                    "content_type": "markdown",
                    "payload": {"title": "Retrieval Notes"},
                    "segments": [
                        {
                            "segment_id": "seg-1",
                            "locator": {"kind": "source", "line_start": 1, "heading_path": ["Retrieval Fusion"]},
                            "excerpt": "Retrieval Fusion combines lexical and semantic ranking.",
                            "hash": "seg-1",
                        },
                        {
                            "segment_id": "seg-2",
                            "locator": {"kind": "source", "line_start": 4},
                            "excerpt": "Retrieval Fusion should stay a derived query strategy, not canonical memory.",
                            "hash": "seg-2",
                        },
                    ],
                    "metadata": {},
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )
            RememberService(root).create_knowledge(
                {
                    "kind": "concept",
                    "title": "Retrieval Fusion",
                    "summary": "Retrieval Fusion combines multiple ranking streams before query results are returned.",
                    "reason": "Existing crystallized concept should suppress duplicate concept candidates.",
                    "scope_refs": ["scope:test"],
                    "status": "active",
                    "memory_source": "user_declared",
                    "confidence": 1.0,
                }
            )
            maintain = MaintenanceLifecycle(root)

            report = maintain.report()

            self.assertNotIn(
                "Retrieval Fusion",
                {candidate["title"] for candidate in report["data"]["concept_candidates"]},
            )

    def test_report_filters_generic_document_noise_from_concept_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repository = FsObjectRepository(root)
            repository.save(
                "source",
                {
                    "id": "src:noisy-doc",
                    "kind": "markdown",
                    "origin": {"path": "/tmp/noisy.md"},
                    "title": "Noisy Doc",
                    "identity_key": "source|test|noisy-doc",
                    "fingerprint": "noisy-doc",
                    "content_type": "markdown",
                    "payload": {"title": "Noisy Doc"},
                    "segments": [
                        {
                            "segment_id": "seg-title",
                            "locator": {"kind": "source", "line_start": 1, "heading_path": ["Agent Memory MCP Usage"]},
                            "excerpt": "Agent Memory MCP Usage describes how agents call memory tools.",
                            "hash": "seg-title",
                        },
                        {
                            "segment_id": "seg-noise",
                            "locator": {"kind": "source", "line_start": 10, "heading_path": ["Bug Fixes"]},
                            "excerpt": "Bug Fixes include Content-Type cleanup and END FILE marker removal.",
                            "hash": "seg-noise",
                        },
                        {
                            "segment_id": "seg-usage-repeat",
                            "locator": {"kind": "source", "line_start": 14},
                            "excerpt": "Agent Memory MCP Usage is a documentation page title, not a durable concept.",
                            "hash": "seg-usage-repeat",
                        },
                        {
                            "segment_id": "seg-todo",
                            "locator": {"kind": "source", "line_start": 16, "heading_path": ["Current Todo"]},
                            "excerpt": "Current Todo lists temporary execution items.",
                            "hash": "seg-todo",
                        },
                        {
                            "segment_id": "seg-format",
                            "locator": {"kind": "source", "line_start": 18, "heading_path": ["MANDATORY OUTPUT LANGUAGE"]},
                            "excerpt": "MANDATORY OUTPUT LANGUAGE, Written BEFORE, and YYYY-MM-DD are prompt or format instructions.",
                            "hash": "seg-format",
                        },
                        {
                            "segment_id": "seg-before",
                            "locator": {"kind": "source", "line_start": 18, "heading_path": ["Written BEFORE"]},
                            "excerpt": "Written BEFORE is a prompt instruction marker.",
                            "hash": "seg-before",
                        },
                        {
                            "segment_id": "seg-features",
                            "locator": {"kind": "source", "line_start": 19, "heading_path": ["New Features"]},
                            "excerpt": "New Features is a changelog heading and pt-br is a locale marker.",
                            "hash": "seg-features",
                        },
                        {
                            "segment_id": "seg-action",
                            "locator": {"kind": "source", "line_start": 19, "heading_path": ["Evaluates MemPal"]},
                            "excerpt": "Evaluates MemPal is a feature-style action phrase, not a durable concept.",
                            "hash": "seg-action",
                        },
                        {
                            "segment_id": "seg-shortcut",
                            "locator": {"kind": "source", "line_start": 19, "heading_path": ["Graceful Ctrl"]},
                            "excerpt": "Graceful Ctrl+C handling is terminal behavior, not a durable concept.",
                            "hash": "seg-shortcut",
                        },
                        {
                            "segment_id": "seg-concept",
                            "locator": {"kind": "source", "line_start": 20, "heading_path": ["Memory Substrate"]},
                            "excerpt": "Memory Substrate captures source evidence before durable memory.",
                            "hash": "seg-concept",
                        },
                        {
                            "segment_id": "seg-concept-2",
                            "locator": {"kind": "source", "line_start": 24},
                            "excerpt": "Memory Substrate uses memory_remember only after review.",
                            "hash": "seg-concept-2",
                        },
                    ],
                    "metadata": {},
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )

            report = MaintenanceLifecycle(root).report()

            titles = {candidate["title"] for candidate in report["data"]["concept_candidates"]}
            self.assertIn("Memory Substrate", titles)
            self.assertNotIn("Agent Memory MCP Usage", titles)
            self.assertNotIn("Bug Fixes", titles)
            self.assertNotIn("Content-Type", titles)
            self.assertNotIn("END FILE", titles)
            self.assertNotIn("Current Todo", titles)
            self.assertNotIn("MANDATORY OUTPUT LANGUAGE", titles)
            self.assertNotIn("Written BEFORE", titles)
            self.assertNotIn("YYYY-MM-DD", titles)
            self.assertNotIn("New Features", titles)
            self.assertNotIn("Evaluates MemPal", titles)
            self.assertNotIn("Graceful Ctrl", titles)
            self.assertNotIn("pt-br", titles)
            skipped = report["data"]["candidate_diagnostics"]["skipped"]
            skipped_by_title = {item["title"]: item["reason"] for item in skipped}
            self.assertEqual(skipped_by_title["Bug Fixes"], "document_artifact")
            self.assertEqual(skipped_by_title["Current Todo"], "document_artifact")
            self.assertEqual(skipped_by_title["YYYY-MM-DD"], "document_artifact")
            self.assertEqual(skipped_by_title["Evaluates MemPal"], "action_phrase")
            self.assertEqual(skipped_by_title["Graceful Ctrl"], "shortcut_marker")
            self.assertEqual(skipped_by_title["pt-br"], "format_marker")

    def test_report_classifies_and_ranks_core_candidates_before_tool_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repository = FsObjectRepository(root)
            repository.save(
                "source",
                {
                    "id": "src:ranking",
                    "kind": "markdown",
                    "origin": {"path": "/tmp/ranking.md"},
                    "title": "Ranking Notes",
                    "identity_key": "source|test|ranking",
                    "fingerprint": "ranking",
                    "content_type": "markdown",
                    "payload": {"title": "Ranking Notes"},
                    "segments": [
                        {
                            "segment_id": "seg-design",
                            "locator": {"kind": "source", "line_start": 2, "heading_path": ["Design Principles"]},
                            "excerpt": "Design Principles guide future memory architecture choices.",
                            "hash": "seg-design",
                        },
                        {
                            "segment_id": "seg-design-2",
                            "locator": {"kind": "source", "line_start": 5},
                            "excerpt": "Design Principles should rank ahead of tool-specific implementation details.",
                            "hash": "seg-design-2",
                        },
                        {
                            "segment_id": "seg-tool",
                            "locator": {"kind": "source", "line_start": 10, "heading_path": ["BAAI/bge-m3"]},
                            "excerpt": "`BAAI/bge-m3` is an embedding model used by semantic retrieval.",
                            "hash": "seg-tool",
                        },
                        {
                            "segment_id": "seg-tool-2",
                            "locator": {"kind": "source", "line_start": 14},
                            "excerpt": "The `BAAI/bge-m3` model is a replaceable implementation dependency.",
                            "hash": "seg-tool-2",
                        },
                        {
                            "segment_id": "seg-procedure",
                            "locator": {"kind": "source", "line_start": 20, "heading_path": ["Candidate Review Workflow"]},
                            "excerpt": "Candidate Review Workflow requires evidence reading, query checks, then memory_remember.",
                            "hash": "seg-procedure",
                        },
                        {
                            "segment_id": "seg-procedure-2",
                            "locator": {"kind": "source", "line_start": 24},
                            "excerpt": "Candidate Review Workflow prevents automatic writes from advisory suggestions.",
                            "hash": "seg-procedure-2",
                        },
                        {
                            "segment_id": "seg-tool-mode",
                            "locator": {"kind": "source", "line_start": 28, "heading_path": ["memory_query search"]},
                            "excerpt": "memory_query search is an MCP operation mode rather than a durable concept.",
                            "hash": "seg-tool-mode",
                        },
                        {
                            "segment_id": "seg-tool-mode-2",
                            "locator": {"kind": "source", "line_start": 32},
                            "excerpt": "memory_query search should rank below Design Principles.",
                            "hash": "seg-tool-mode-2",
                        },
                        {
                            "segment_id": "seg-command",
                            "locator": {"kind": "source", "line_start": 36, "heading_path": ["mempalace init"]},
                            "excerpt": "mempalace init is a command phrase and should not outrank Design Principles.",
                            "hash": "seg-command",
                        },
                        {
                            "segment_id": "seg-command-2",
                            "locator": {"kind": "source", "line_start": 40},
                            "excerpt": "mempalace init configures local command state.",
                            "hash": "seg-command-2",
                        },
                        {
                            "segment_id": "seg-command-option",
                            "locator": {"kind": "source", "line_start": 42, "heading_path": ["mempalace init --llm"]},
                            "excerpt": "`mempalace init --llm` is a command invocation with a local model flag.",
                            "hash": "seg-command-option",
                        },
                        {
                            "segment_id": "seg-command-option-2",
                            "locator": {"kind": "source", "line_start": 43},
                            "excerpt": "mempalace init --llm should rank below durable memory concepts.",
                            "hash": "seg-command-option-2",
                        },
                        {
                            "segment_id": "seg-lm-studio",
                            "locator": {"kind": "source", "line_start": 44, "heading_path": ["LM Studio"]},
                            "excerpt": "LM Studio is a local model tool used in experiments.",
                            "hash": "seg-lm-studio",
                        },
                        {
                            "segment_id": "seg-lm-studio-2",
                            "locator": {"kind": "source", "line_start": 48},
                            "excerpt": "LM Studio remains a replaceable tool dependency.",
                            "hash": "seg-lm-studio-2",
                        },
                        {
                            "segment_id": "seg-mcp-package",
                            "locator": {"kind": "source", "line_start": 50, "heading_path": ["mempalace-mcp"]},
                            "excerpt": "`mempalace-mcp` is a tool package name rather than a reusable memory concept.",
                            "hash": "seg-mcp-package",
                        },
                        {
                            "segment_id": "seg-mcp-package-2",
                            "locator": {"kind": "source", "line_start": 51},
                            "excerpt": "mempalace-mcp should rank below durable memory concepts.",
                            "hash": "seg-mcp-package-2",
                        },
                        {
                            "segment_id": "seg-sql",
                            "locator": {"kind": "source", "line_start": 52, "heading_path": ["TEXT NOT NULL"]},
                            "excerpt": "TEXT NOT NULL is a schema fragment and implementation detail.",
                            "hash": "seg-sql",
                        },
                        {
                            "segment_id": "seg-sql-2",
                            "locator": {"kind": "source", "line_start": 56},
                            "excerpt": "TEXT NOT NULL should rank below Design Principles.",
                            "hash": "seg-sql-2",
                        },
                    ],
                    "metadata": {},
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )

            report = MaintenanceLifecycle(root).report()

            candidates = report["data"]["concept_candidates"]
            by_title = {candidate["title"]: candidate for candidate in candidates}
            titles = [candidate["title"] for candidate in candidates]

            self.assertLess(titles.index("Design Principles"), titles.index("BAAI/bge-m3"))
            self.assertEqual(by_title["Design Principles"]["candidate_type"], "concept")
            self.assertEqual(by_title["BAAI/bge-m3"]["candidate_type"], "tool_library")
            self.assertEqual(by_title["BAAI/bge-m3"]["suggested_memory"]["kind"], "concept")
            self.assertIn("tool_or_library_name", by_title["BAAI/bge-m3"]["ranking_signals"]["penalties"])
            self.assertEqual(by_title["Candidate Review Workflow"]["candidate_type"], "procedure")
            self.assertEqual(by_title["Candidate Review Workflow"]["suggested_memory"]["kind"], "procedure")
            self.assertEqual(by_title["memory_query search"]["candidate_type"], "implementation_detail")
            self.assertLess(titles.index("Design Principles"), titles.index("memory_query search"))
            self.assertEqual(by_title["mempalace init"]["candidate_type"], "implementation_detail")
            self.assertLess(titles.index("Design Principles"), titles.index("mempalace init"))
            self.assertEqual(by_title["mempalace init --llm"]["candidate_type"], "implementation_detail")
            self.assertLess(titles.index("Design Principles"), titles.index("mempalace init --llm"))
            self.assertEqual(by_title["LM Studio"]["candidate_type"], "tool_library")
            self.assertLess(titles.index("Design Principles"), titles.index("LM Studio"))
            self.assertEqual(by_title["mempalace-mcp"]["candidate_type"], "tool_library")
            self.assertLess(titles.index("Design Principles"), titles.index("mempalace-mcp"))
            self.assertEqual(by_title["TEXT NOT NULL"]["candidate_type"], "implementation_detail")
            self.assertLess(titles.index("Design Principles"), titles.index("TEXT NOT NULL"))

    def test_merge_duplicates_does_not_merge_unstructured_soft_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remember = RememberService(root)
            maintain = MaintenanceLifecycle(root)
            first = remember.create_knowledge(
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
            second = remember.create_knowledge(
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

            result = maintain.merge_duplicates()
            repository = FsObjectRepository(root)

            self.assertEqual(result["merged"], 0)
            self.assertEqual(repository.get("knowledge", first["knowledge_id"])["status"], "active")
            self.assertEqual(repository.get("knowledge", second["knowledge_id"])["status"], "candidate")

    def test_resolve_duplicates_supersedes_reviewed_soft_duplicate_loser(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remember = RememberService(root)
            repository = FsObjectRepository(root)
            first = remember.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Use Kuzu as the local graph backend",
                    "summary": "Kuzu is the selected local graph backend for lightweight prototypes.",
                    "reason": "This decision should guide backend work.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:memory-substrate"],
                    "payload": {},
                    "status": "active",
                    "confidence": 1.0,
                }
            )
            second = remember.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Choose Kuzu for local graph storage",
                    "summary": "The local prototype graph backend should stay on Kuzu.",
                    "reason": "This duplicate should be explicitly reviewed.",
                    "memory_source": "agent_inferred",
                    "scope_refs": ["scope:memory-substrate"],
                    "payload": {},
                    "status": "candidate",
                    "confidence": 0.8,
                }
            )

            result = MaintenanceLifecycle(root).resolve_duplicates(
                outcome="supersede",
                knowledge_ids=[first["knowledge_id"], second["knowledge_id"]],
                canonical_knowledge_id=first["knowledge_id"],
                reason="Reviewed soft duplicate; first item is the canonical decision.",
            )

            winner = repository.get("knowledge", first["knowledge_id"])
            loser = repository.get("knowledge", second["knowledge_id"])
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["outcome"], "supersede")
            self.assertEqual(result["resolved"], 2)
            self.assertEqual(winner["status"], "active")
            self.assertEqual(loser["status"], "superseded")
            self.assertEqual(loser["valid_until"], winner["last_verified_at"])
            self.assertIn("Reviewed soft duplicate", loser["reason"])
            soft_duplicate_sets = [
                set(group["object_ids"]) for group in MaintenanceLifecycle(root).report()["data"]["soft_duplicate_candidates"]
            ]
            self.assertNotIn({first["knowledge_id"], second["knowledge_id"]}, soft_duplicate_sets)

    def test_resolve_duplicates_keeps_both_after_scope_clarification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remember = RememberService(root)
            repository = FsObjectRepository(root)
            first = remember.create_knowledge(
                {
                    "kind": "procedure",
                    "title": "Memory review workflow",
                    "summary": "Review memory candidates before writing durable memory.",
                    "reason": "This workflow applies to project A.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:shared"],
                    "payload": {},
                    "status": "active",
                    "confidence": 0.9,
                }
            )
            second = remember.create_knowledge(
                {
                    "kind": "procedure",
                    "title": "Memory review process",
                    "summary": "Review memory candidates before writing durable memory.",
                    "reason": "This workflow applies to project B.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:shared"],
                    "payload": {},
                    "status": "active",
                    "confidence": 0.9,
                }
            )

            result = MaintenanceLifecycle(root).resolve_duplicates(
                outcome="keep_both",
                knowledge_ids=[first["knowledge_id"], second["knowledge_id"]],
                reason="Same words but different project scopes.",
                updates=[
                    {
                        "knowledge_id": first["knowledge_id"],
                        "summary": "Project A memory review workflow.",
                        "scope_refs": ["scope:project-a"],
                    },
                    {
                        "knowledge_id": second["knowledge_id"],
                        "summary": "Project B memory review workflow.",
                        "scope_refs": ["scope:project-b"],
                    },
                ],
            )

            updated_first = repository.get("knowledge", first["knowledge_id"])
            updated_second = repository.get("knowledge", second["knowledge_id"])
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["outcome"], "keep_both")
            self.assertEqual(updated_first["status"], "active")
            self.assertEqual(updated_second["status"], "active")
            self.assertEqual(updated_first["scope_refs"], ["scope:project-a"])
            self.assertEqual(updated_second["scope_refs"], ["scope:project-b"])
            self.assertEqual(updated_first["summary"], "Project A memory review workflow.")
            self.assertEqual(updated_second["summary"], "Project B memory review workflow.")
            self.assertIn("different project scopes", updated_first["reason"])
            self.assertEqual(MaintenanceLifecycle(root).report()["data"]["soft_duplicate_candidates"], [])

    def test_resolve_duplicates_rejects_non_soft_duplicate_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remember = RememberService(root)
            first = remember.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Use Kuzu",
                    "summary": "Kuzu backs local graph storage.",
                    "reason": "This decision should guide graph work.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:graph"],
                    "payload": {},
                    "status": "active",
                    "confidence": 0.9,
                }
            )
            second = remember.create_knowledge(
                {
                    "kind": "preference",
                    "title": "Prefer compact context",
                    "summary": "Context packs should avoid duplicated summaries.",
                    "reason": "This preference should guide MCP responses.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:query"],
                    "payload": {},
                    "status": "active",
                    "confidence": 0.9,
                }
            )

            with self.assertRaisesRegex(ValueError, "not a current soft duplicate candidate"):
                MaintenanceLifecycle(root).resolve_duplicates(
                    outcome="contest",
                    knowledge_ids=[first["knowledge_id"], second["knowledge_id"]],
                    reason="These are unrelated.",
                )

    def test_resolve_duplicates_contests_reviewed_soft_duplicate_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remember = RememberService(root)
            repository = FsObjectRepository(root)
            first = remember.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Kuzu graph backend decision",
                    "summary": "Kuzu is the selected local graph backend.",
                    "reason": "This decision may conflict with another memory.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:memory-substrate"],
                    "payload": {},
                    "status": "active",
                    "confidence": 0.8,
                }
            )
            second = remember.create_knowledge(
                {
                    "kind": "decision",
                    "title": "Kuzu graph backend choice",
                    "summary": "Kuzu is the selected local graph backend.",
                    "reason": "This may be a duplicate or a conflict.",
                    "memory_source": "human_curated",
                    "scope_refs": ["scope:memory-substrate"],
                    "payload": {},
                    "status": "active",
                    "confidence": 0.8,
                }
            )

            result = MaintenanceLifecycle(root).resolve_duplicates(
                outcome="contest",
                knowledge_ids=[first["knowledge_id"], second["knowledge_id"]],
                reason="The pair needs human review before reuse.",
            )

            self.assertEqual(result["outcome"], "contest")
            self.assertEqual(repository.get("knowledge", first["knowledge_id"])["status"], "contested")
            self.assertEqual(repository.get("knowledge", second["knowledge_id"])["status"], "contested")
            self.assertEqual(MaintenanceLifecycle(root).report()["data"]["soft_duplicate_candidates"], [])

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
