from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wiki_memory.application.crystallize.service import CrystallizeService
from wiki_memory.domain.protocols.wiki_patch import PatchOperation, WikiPatch
from wiki_memory.domain.services.patch_applier import PatchApplier, utc_now_iso
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.infrastructure.repositories.fs_patch_repository import FsPatchRepository
from wiki_memory.projections.markdown.projector import MarkdownProjector


class CrystallizeProjectionTest(unittest.TestCase):
    def test_create_work_item_rebuilds_projection_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            service = CrystallizeService(root)

            result = service.create_work_item(
                {
                    "kind": "task",
                    "title": "Projection sync smoke test",
                    "summary": "Ensure crystallize rebuilds markdown projection.",
                }
            )

            projection_path = root / "memory" / "projections" / "debug" / "work_items" / f"{result['work_item_id']}.md"

            self.assertTrue(projection_path.exists())
            contents = projection_path.read_text(encoding="utf-8")
            self.assertIn("# Projection sync smoke test", contents)
            self.assertGreater(result["projection_count"], 0)

    def test_rebuild_removes_stale_projection_files_after_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            service = CrystallizeService(root)

            result = service.create_work_item(
                {
                    "kind": "task",
                    "title": "Projection sync smoke test",
                    "summary": "Ensure stale projection files are removed.",
                }
            )
            work_item_id = result["work_item_id"]
            projection_path = root / "memory" / "projections" / "debug" / "work_items" / f"{work_item_id}.md"

            repository = FsObjectRepository(root)
            patch_repository = FsPatchRepository(root)
            audit_repository = FsAuditRepository(root)
            patch_applier = PatchApplier(repository, patch_repository, audit_repository)
            patch_applier.apply(
                WikiPatch(
                    id="patch:test-delete-work-item",
                    source={"type": "test", "id": "projection-sync"},
                    operations=[
                        PatchOperation(
                            op="delete_object",
                            object_type="work_item",
                            object_id=work_item_id,
                            changes={"reason": "delete for projection sync test"},
                        )
                    ],
                    created_at=utc_now_iso(),
                )
            )

            projector = MarkdownProjector(root)
            projector.rebuild()

            self.assertFalse(projection_path.exists())


if __name__ == "__main__":
    unittest.main()
