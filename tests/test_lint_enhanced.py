from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wiki_memory.application.lint.service import LintService
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.projections.markdown.projector import MarkdownProjector


class EnhancedLintTest(unittest.TestCase):
    def test_structure_reports_duplicate_identity_active_without_evidence_orphans_and_projection_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            objects = FsObjectRepository(root)
            objects.save(
                "node",
                {
                    "id": "node:one",
                    "kind": "document",
                    "name": "One",
                    "slug": "one",
                    "identity_key": "duplicate",
                    "aliases": [],
                    "summary": "First.",
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )
            objects.save(
                "node",
                {
                    "id": "node:two",
                    "kind": "document",
                    "name": "Two",
                    "slug": "two",
                    "identity_key": "duplicate",
                    "aliases": [],
                    "summary": "Second.",
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )
            objects.save(
                "knowledge",
                {
                    "id": "know:no-evidence",
                    "kind": "fact",
                    "title": "No evidence",
                    "summary": "Active without evidence.",
                    "subject_refs": ["node:one"],
                    "evidence_refs": [],
                    "payload": {"subject": "node:one", "predicate": "x", "value": True, "object": None},
                    "status": "active",
                    "confidence": 0.9,
                    "valid_from": "2026-01-01T00:00:00+00:00",
                    "valid_until": None,
                    "last_verified_at": "2026-01-01T00:00:00+00:00",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )
            objects.save(
                "source",
                {
                    "id": "src:orphan",
                    "kind": "file",
                    "origin": {"path": "/tmp/orphan.txt"},
                    "title": "orphan.txt",
                    "identity_key": "source|orphan",
                    "fingerprint": "abc",
                    "content_type": "text",
                    "payload": {"text": "orphan"},
                    "segments": [],
                    "metadata": {},
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
            )
            MarkdownProjector(root).rebuild()
            (root / "memory" / "projections" / "debug" / "knowledge" / "know:no-evidence.md").unlink()

            report = LintService(root).structure()["data"]
            kinds = {issue["kind"] for issue in report["issues"]}

            self.assertIn("duplicate_identity", kinds)
            self.assertIn("active_knowledge_without_evidence", kinds)
            self.assertIn("orphan_source", kinds)
            self.assertIn("missing_projection", kinds)


if __name__ == "__main__":
    unittest.main()
