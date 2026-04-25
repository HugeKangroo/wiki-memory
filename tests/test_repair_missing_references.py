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
from wiki_memory.application.lint.service import LintService
from wiki_memory.domain.protocols.wiki_patch import PatchOperation, WikiPatch
from wiki_memory.domain.services.patch_applier import PatchApplier, utc_now_iso
from wiki_memory.infrastructure.repositories.fs_audit_repository import FsAuditRepository
from wiki_memory.infrastructure.repositories.fs_object_repository import FsObjectRepository
from wiki_memory.infrastructure.repositories.fs_patch_repository import FsPatchRepository


class RepairMissingReferencesTest(unittest.TestCase):
    def test_repair_clears_missing_owner_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            crystallize = CrystallizeService(root)
            lint = LintService(root)

            result = crystallize.create_work_item(
                {
                    "kind": "issue",
                    "title": "Broken ref test",
                    "summary": "Create a repairable missing owner reference.",
                    "owner_refs": ["node:missing-owner"],
                }
            )
            work_item_id = result["work_item_id"]

            report_before = lint.structure()
            self.assertTrue(
                any(
                    issue["kind"] == "missing_reference"
                    and issue["target_id"] == work_item_id
                    and issue["details"]["field"] == "owner_refs"
                    for issue in report_before["data"]["issues"]
                )
            )

            repair_result = lint.repair()
            work_item = FsObjectRepository(root).get("work_item", work_item_id)

            self.assertEqual(repair_result["data"]["status"], "completed")
            self.assertEqual(work_item["owner_refs"], [])

            report_after = lint.structure()
            self.assertFalse(
                any(
                    issue["kind"] == "missing_reference"
                    and issue["target_id"] == work_item_id
                    and issue["details"]["field"] == "owner_refs"
                    for issue in report_after["data"]["issues"]
                )
            )


if __name__ == "__main__":
    unittest.main()
