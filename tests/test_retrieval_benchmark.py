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


class RetrievalBenchmarkTest(unittest.TestCase):
    def test_planted_needle_benchmark_reports_stream_recall_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_planted_needle_benchmark(tmp)

            self.assertEqual(result["case_count"], 3)
            self.assertEqual(result["streams"]["lexical"]["recall_at_5"], 1.0)
            self.assertEqual(result["streams"]["semantic"]["status"], "not_configured")
            self.assertEqual(result["streams"]["hybrid"]["status"], "not_configured")
            self.assertEqual(result["cases"][0]["expected_id"], result["cases"][0]["top_ids"][0])


if __name__ == "__main__":
    unittest.main()
