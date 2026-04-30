from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.interfaces.mcp.tools import memory_ingest, memory_maintain, memory_query, resolve_root


class McpToolsTest(unittest.TestCase):
    def test_resolve_root_defaults_to_home_memory_substrate(self) -> None:
        with patch("memory_substrate.interfaces.mcp.tools.Path.home", return_value=Path("/tmp/fake-home")):
            self.assertEqual(resolve_root(None), Path("/tmp/fake-home/memory-substrate"))

    def test_memory_maintain_dispatches_to_lifecycle_modes(self) -> None:
        with patch("memory_substrate.interfaces.mcp.tools.MaintainService") as maintain_service:
            service = maintain_service.return_value
            service.promote_candidates.return_value = {"status": "completed", "promoted": 1}
            service.merge_duplicates.return_value = {"status": "completed", "merged": 1}
            service.resolve_duplicates.return_value = {"status": "completed", "outcome": "supersede", "resolved": 2}
            service.decay_stale.return_value = {"status": "completed", "decayed": 1}
            service.cycle.return_value = {"status": "completed", "promoted": 1, "merged": 1, "decayed": 1}

            self.assertEqual(
                memory_maintain(".", "promote_candidates", {"min_confidence": 0.8, "min_evidence": 2}, {"apply": True})["promoted"],
                1,
            )
            self.assertEqual(memory_maintain(".", "merge_duplicates", {}, {"apply": True})["merged"], 1)
            self.assertEqual(
                memory_maintain(
                    ".",
                    "resolve_duplicates",
                    {
                        "outcome": "supersede",
                        "knowledge_ids": ["know:a", "know:b"],
                        "canonical_knowledge_id": "know:a",
                        "reason": "Reviewed duplicate pair.",
                    },
                    {"apply": True},
                )["resolved"],
                2,
            )
            self.assertEqual(
                memory_maintain(
                    ".",
                    "decay_stale",
                    {"reference_time": "2026-04-24T00:00:00+00:00", "stale_after_days": 10},
                    {"apply": True},
                )["decayed"],
                1,
            )
            self.assertEqual(memory_maintain(".", "cycle", {"reference_time": "2026-04-24T00:00:00+00:00"}, {"apply": True})["merged"], 1)

            service.promote_candidates.assert_called_once_with(min_confidence=0.8, min_evidence=2)
            service.merge_duplicates.assert_called_once_with()
            service.resolve_duplicates.assert_called_once_with(
                outcome="supersede",
                knowledge_ids=["know:a", "know:b"],
                canonical_knowledge_id="know:a",
                reason="Reviewed duplicate pair.",
                updates=None,
            )
            service.decay_stale.assert_called_once_with(
                reference_time="2026-04-24T00:00:00+00:00",
                stale_after_days=10,
            )
            service.cycle.assert_called_once_with(
                min_confidence=0.75,
                min_evidence=1,
                reference_time="2026-04-24T00:00:00+00:00",
                stale_after_days=30,
            )

    def test_memory_maintain_rejects_unsupported_modes(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported maintain mode"):
            memory_maintain(".", "unknown", {})

    def test_memory_maintain_uses_default_root_when_omitted(self) -> None:
        with (
            patch("memory_substrate.interfaces.mcp.tools.Path.home", return_value=Path("/tmp/fake-home")),
            patch("memory_substrate.interfaces.mcp.tools.MaintainService") as maintain_service,
        ):
            service = maintain_service.return_value
            service.merge_duplicates.return_value = {"status": "completed", "merged": 1}

            result = memory_maintain(None, "merge_duplicates", {}, {"apply": True})

            self.assertEqual(result["merged"], 1)
            maintain_service.assert_called_once_with(Path("/tmp/fake-home/memory-substrate"))

    def test_memory_ingest_repo_passes_include_and_exclude_patterns(self) -> None:
        with patch("memory_substrate.interfaces.mcp.tools.IngestService") as ingest_service:
            service = ingest_service.return_value
            service.ingest_repo.return_value = {"source_id": "src:x"}

            result = memory_ingest(
                ".",
                "repo",
                {
                    "path": "/repo",
                    "include_patterns": ["src/**", "README.md"],
                    "exclude_patterns": [".codex", ".worktrees"],
                },
            )

            self.assertEqual(result["source_id"], "src:x")
            service.ingest_repo.assert_called_once_with(
                "/repo",
                include_patterns=["src/**", "README.md"],
                exclude_patterns=[".codex", ".worktrees"],
                force=False,
            )

    def test_memory_ingest_repo_passes_force_option(self) -> None:
        with patch("memory_substrate.interfaces.mcp.tools.IngestService") as ingest_service:
            service = ingest_service.return_value
            service.ingest_repo.return_value = {"source_id": "src:x"}

            result = memory_ingest(".", "repo", {"path": "/repo"}, {"force": True})

            self.assertEqual(result["source_id"], "src:x")
            service.ingest_repo.assert_called_once_with(
                "/repo",
                include_patterns=None,
                exclude_patterns=None,
                force=True,
            )

    def test_memory_query_direct_dispatch_rejects_mode_invalid_options(self) -> None:
        with self.assertRaisesRegex(Exception, "Extra inputs are not permitted"):
            memory_query(".", "search", {"query": "memory"}, {"detail": "full"})

    def test_memory_maintain_requires_apply_for_mutating_modes(self) -> None:
        with self.assertRaisesRegex(ValueError, "options.apply=true"):
            memory_maintain(".", "merge_duplicates", {})

        with self.assertRaisesRegex(ValueError, "options.apply=true"):
            memory_maintain(".", "repair", {}, {"apply": False})

        with self.assertRaisesRegex(ValueError, "options.apply=true"):
            memory_maintain(".", "resolve_duplicates", {})


if __name__ == "__main__":
    unittest.main()
