from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.interfaces.mcp.tools import memory_maintain, memory_query, memory_remember


class McpConfiguredGraphBackendTest(unittest.TestCase):
    def test_configured_graph_backend_is_used_when_options_omit_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            configured = memory_maintain(root, "configure", {"graph_backend": "file"}, {"apply": True})
            remembered = memory_remember(
                root,
                "knowledge",
                {
                    "kind": "decision",
                    "title": "Configured graph backend",
                    "summary": "Remember uses the configured graph backend.",
                    "payload": {"subject": "node:memory", "predicate": "uses", "object": "node:file-graph"},
                    "subject_refs": ["node:memory"],
                    "status": "active",
                    "confidence": 0.9,
                },
            )
            search = memory_query(root, "search", {"query": "Configured graph"}, {"max_items": 5})
            context = memory_query(root, "context", {"task": "Configured graph"}, {"max_items": 5})
            graph = memory_query(root, "graph", {"id": "node:memory"}, {"max_items": 10})
            report = memory_maintain(root, "report", {})
            reindex = memory_maintain(root, "reindex", {})

            self.assertEqual(configured["data"]["config"]["graph"]["backend"], "file")
            self.assertEqual(remembered["graph_sync"]["backend"], "FileGraphBackend")
            self.assertEqual([item["id"] for item in search["data"]["items"]], [remembered["knowledge_id"]])
            self.assertEqual([item["id"] for item in context["data"]["items"]], [remembered["knowledge_id"]])
            self.assertTrue(any(edge["relation"] == "uses" for edge in graph["data"]["edges"]))
            self.assertEqual(report["data"]["graph"]["backend"], "FileGraphBackend")
            self.assertEqual(reindex["data"]["graph_sync"]["backend"], "FileGraphBackend")


if __name__ == "__main__":
    unittest.main()
