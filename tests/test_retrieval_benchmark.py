from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.experiments.retrieval_benchmark import run_planted_needle_benchmark
from memory_substrate.experiments.maintenance_benchmark import run_maintenance_dogfood_benchmark
from memory_substrate.experiments.end_to_end_dogfood import run_end_to_end_dogfood_acceptance


class RetrievalBenchmarkTest(unittest.TestCase):
    def test_planted_needle_benchmark_reports_stream_recall_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_planted_needle_benchmark(tmp)

            self.assertEqual(result["case_count"], 3)
            self.assertEqual(result["streams"]["lexical"]["recall_at_5"], 1.0)
            self.assertEqual(result["streams"]["semantic"]["status"], "not_configured")
            self.assertEqual(result["streams"]["hybrid"]["status"], "not_configured")
            self.assertEqual(result["cases"][0]["expected_id"], result["cases"][0]["top_ids"][0])

    def test_maintenance_dogfood_benchmark_reports_expected_lifecycle_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_maintenance_dogfood_benchmark(tmp)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["case_count"], 5)
            self.assertFalse(result["mutated"])
            self.assertEqual(result["expected_counts"], result["observed_counts"])
            self.assertTrue(all(check["passed"] for check in result["checks"]))
            self.assertEqual(
                {check["name"] for check in result["checks"]},
                {
                    "promote_candidate",
                    "low_evidence_candidate",
                    "stale_candidate",
                    "structured_duplicate_group",
                    "soft_duplicate_candidate",
                },
            )

    def test_end_to_end_dogfood_acceptance_exercises_mcp_memory_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_end_to_end_dogfood_acceptance(tmp)

            self.assertEqual(result["status"], "completed")
            self.assertTrue(result["mutated"])
            self.assertEqual(result["case_count"], 8)
            self.assertTrue(all(check["passed"] for check in result["checks"]))
            self.assertEqual(
                {check["name"] for check in result["checks"]},
                {
                    "repo_ingest_completed",
                    "ingest_candidate_is_compact",
                    "search_finds_ingested_repo",
                    "repo_full_page_is_unsupported",
                    "remember_candidate_created",
                    "maintain_report_sees_promotable_memory",
                    "reindex_completed",
                    "context_returns_remembered_memory",
                },
            )
            self.assertEqual(result["object_ids"]["candidate_title"], "Context Pack")
            self.assertIn(result["object_ids"]["knowledge_id"], result["observed"]["context_item_ids"])
            self.assertLess(result["payload_sizes"]["compact_candidate_chars"], 2200)


if __name__ == "__main__":
    unittest.main()
