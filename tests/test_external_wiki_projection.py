from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.application.maintain.service import MaintainService
from memory_substrate.application.remember.service import RememberService
from memory_substrate.infrastructure.config.repository import MemoryConfigRepository
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository
from memory_substrate.projections.markdown.external_wiki import ExternalWikiProjectionService


class ExternalWikiProjectionTest(unittest.TestCase):
    def _seed_knowledge(self, root: Path) -> str:
        return RememberService(root).create_knowledge(
            {
                "kind": "concept",
                "title": "Context Pack",
                "summary": "Context Pack is a bounded working set for agents.",
                "reason": "Projection tests need one durable memory item.",
                "memory_source": "user_declared",
                "scope_refs": ["scope:test"],
                "status": "active",
                "confidence": 1.0,
            }
        )["knowledge_id"]

    def test_render_projection_writes_manifest_bound_external_wiki_without_canonical_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "vault"
            target.mkdir()
            (target / "Personal.md").write_text("# Personal\n\nDo not touch.\n", encoding="utf-8")
            knowledge_id = self._seed_knowledge(root)
            repository = FsObjectRepository(root)
            before = repository.get("knowledge", knowledge_id)
            MemoryConfigRepository(root).set_wiki_projection(path=str(target), format="obsidian")

            result = MaintainService(root).render_projection()

            after = repository.get("knowledge", knowledge_id)
            manifest = target / ".memory-substrate-projection.json"
            rendered = target / "Knowledge" / "Context Pack.md"
            self.assertEqual(before, after)
            self.assertEqual(result["result_type"], "projection_render_result")
            self.assertEqual(result["data"]["status"], "completed")
            self.assertTrue(manifest.exists())
            self.assertTrue(rendered.exists())
            self.assertIn("memory_substrate_projection: true", rendered.read_text(encoding="utf-8"))
            self.assertEqual((target / "Personal.md").read_text(encoding="utf-8"), "# Personal\n\nDo not touch.\n")
            self.assertNotIn("Personal.md", {Path(path).as_posix() for path in result["data"]["written"]})

    def test_render_projection_reports_unmanaged_path_conflicts_without_overwriting_user_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "vault"
            target.mkdir()
            (target / "Home.md").write_text("# User Home\n", encoding="utf-8")
            self._seed_knowledge(root)
            MemoryConfigRepository(root).set_wiki_projection(path=str(target), format="obsidian")

            result = ExternalWikiProjectionService(root).render()

            self.assertEqual((target / "Home.md").read_text(encoding="utf-8"), "# User Home\n")
            self.assertEqual(result["status"], "completed_with_conflicts")
            self.assertIn("unmanaged_path_conflict", {conflict["kind"] for conflict in result["conflicts"]})

    def test_reconcile_projection_reports_candidates_and_conflicts_without_mutating_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "vault"
            knowledge_id = self._seed_knowledge(root)
            repository = FsObjectRepository(root)
            before = repository.get("knowledge", knowledge_id)
            MemoryConfigRepository(root).set_wiki_projection(path=str(target), format="obsidian")
            render = MaintainService(root).render_projection()
            generated = Path(render["data"]["target_path"]) / "Knowledge" / "Context Pack.md"
            generated.write_text(generated.read_text(encoding="utf-8") + "\nUser edit.\n", encoding="utf-8")
            inbox = target / "Inbox"
            inbox.mkdir()
            (inbox / "New Idea.md").write_text("# New Idea\n\nThis should become a reviewed memory candidate.\n", encoding="utf-8")

            report = MaintainService(root).reconcile_projection()

            after = repository.get("knowledge", knowledge_id)
            self.assertEqual(before, after)
            self.assertEqual(report["result_type"], "projection_reconcile_report")
            self.assertFalse(report["data"]["canonical_mutation"])
            self.assertIn("modified_generated_file", {conflict["kind"] for conflict in report["data"]["conflicts"]})
            candidate = next(item for item in report["data"]["remember_candidates"] if item["title"] == "New Idea")
            self.assertEqual(candidate["path"], "Inbox/New Idea.md")
            self.assertEqual(candidate["suggested_memory"]["mode"], "knowledge")
            self.assertEqual(candidate["suggested_memory"]["input_data"]["status"], "candidate")


if __name__ == "__main__":
    unittest.main()
