from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.domain.objects.entity import Entity
from memory_substrate.domain.objects.episode import Episode
from memory_substrate.domain.objects.memory_scope import MemoryScope
from memory_substrate.domain.objects.relation import Relation
from memory_substrate.domain.protocols.remember_request import RememberRequest
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class MemoryCoreContractTest(unittest.TestCase):
    def test_core_objects_have_graph_ready_defaults(self) -> None:
        scope = MemoryScope(
            id="scope:project",
            kind="project",
            name="memory-substrate",
            created_at="2026-04-28T00:00:00+00:00",
            updated_at="2026-04-28T00:00:00+00:00",
        )
        episode = Episode(
            id="ep:design",
            created_at="2026-04-28T01:01:00+00:00",
            updated_at="2026-04-28T01:01:00+00:00",
            source_ref="src:design",
            kind="conversation",
            observed_at="2026-04-28T01:00:00+00:00",
            ingested_at="2026-04-28T01:01:00+00:00",
            actor={"type": "user", "id": "local"},
            summary="Design discussion.",
            scope_refs=["scope:project"],
        )
        entity = Entity(
            id="ent:memory-substrate",
            kind="project",
            name="memory-substrate",
            created_at="2026-04-28T00:00:00+00:00",
            updated_at="2026-04-28T00:00:00+00:00",
            scope_refs=["scope:project"],
        )
        relation = Relation(
            id="rel:supports",
            created_at="2026-04-28T01:01:00+00:00",
            updated_at="2026-04-28T01:01:00+00:00",
            source_ref="know:decision",
            target_ref="ent:memory-substrate",
            relation_type="applies_to",
            scope_refs=["scope:project"],
        )

        self.assertEqual(scope.parent_refs, [])
        self.assertEqual(episode.metadata, {})
        self.assertEqual(entity.aliases, [])
        self.assertEqual(entity.status, "active")
        self.assertEqual(relation.status, "candidate")
        self.assertEqual(relation.evidence_refs, [])

    def test_file_repository_persists_new_core_object_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            objects = FsObjectRepository(tmp)
            scope = MemoryScope(
                id="scope:project",
                kind="project",
                name="memory-substrate",
                created_at="2026-04-28T00:00:00+00:00",
                updated_at="2026-04-28T00:00:00+00:00",
            )
            entity = Entity(
                id="ent:memory-substrate",
                kind="project",
                name="memory-substrate",
                created_at="2026-04-28T00:00:00+00:00",
                updated_at="2026-04-28T00:00:00+00:00",
                scope_refs=["scope:project"],
            )
            relation = Relation(
                id="rel:applies-to",
                created_at="2026-04-28T01:01:00+00:00",
                updated_at="2026-04-28T01:01:00+00:00",
                source_ref="know:decision",
                target_ref="ent:memory-substrate",
                relation_type="applies_to",
                scope_refs=["scope:project"],
            )

            objects.save("memory_scope", scope)
            objects.save("entity", entity)
            objects.save("relation", relation)

            self.assertEqual(objects.get("memory_scope", "scope:project")["name"], "memory-substrate")
            self.assertEqual(objects.get("entity", "ent:memory-substrate")["kind"], "project")
            self.assertEqual(objects.get("relation", "rel:applies-to")["relation_type"], "applies_to")

    def test_remember_request_requires_governance_for_active_knowledge(self) -> None:
        with self.assertRaisesRegex(ValueError, "active knowledge requires evidence_refs"):
            RememberRequest(
                mode="knowledge",
                reason="This decision affects future backend work.",
                memory_source="agent_inferred",
                scope_refs=["scope:project"],
                status="active",
                confidence=0.9,
                payload={"kind": "decision", "title": "Use GraphBackend"},
            ).validate_governance()

        request = RememberRequest(
            mode="knowledge",
            reason="The user explicitly chose this direction.",
            memory_source="user_declared",
            scope_refs=["scope:project"],
            status="active",
            confidence=1.0,
            payload={"kind": "decision", "title": "Use GraphBackend"},
        )

        self.assertEqual(request.validate_governance(), request)

    def test_remember_request_defaults_agent_inferred_memory_to_candidate(self) -> None:
        request = RememberRequest(
            mode="knowledge",
            reason="This was inferred from source material.",
            memory_source="agent_inferred",
            scope_refs=["scope:project"],
            status="active",
            confidence=0.65,
            evidence_refs=[{"source_id": "src:design", "segment_id": "seg:1"}],
            payload={"kind": "fact", "title": "GraphBackend is a boundary"},
        )

        normalized = request.normalize()

        self.assertEqual(normalized.status, "candidate")
        self.assertEqual(asdict(normalized)["memory_source"], "agent_inferred")


if __name__ == "__main__":
    unittest.main()
