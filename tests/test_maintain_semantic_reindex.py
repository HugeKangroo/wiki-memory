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
from memory_substrate.infrastructure.repositories.fs_object_repository import FsObjectRepository


class FakeSemanticService:
    def __init__(self) -> None:
        self.called = False

    def rebuild(self) -> dict:
        self.called = True
        return {"backend": "fake", "model": "fake-model", "chunk_count": 1}


class MaintainSemanticReindexTest(unittest.TestCase):
    def test_reindex_rebuilds_semantic_index_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            FsObjectRepository(tmp).save(
                "knowledge",
                {
                    "id": "know:x",
                    "kind": "fact",
                    "title": "Semantic fact",
                    "summary": "This should be projected into the semantic index.",
                    "status": "active",
                },
            )
            semantic = FakeSemanticService()

            result = MaintainService(tmp, semantic_index=semantic).reindex()

            self.assertTrue(semantic.called)
            self.assertEqual(result["data"]["semantic_index"]["backend"], "fake")
            self.assertEqual(result["data"]["semantic_index"]["chunk_count"], 1)


if __name__ == "__main__":
    unittest.main()
