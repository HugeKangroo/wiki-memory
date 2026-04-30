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


if __name__ == "__main__":
    unittest.main()
