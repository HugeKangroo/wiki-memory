from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.interfaces.mcp.tools import memory_maintain, memory_query, memory_remember


class McpGraphBackendOptionsTest(unittest.TestCase):
    def test_query_graph_passes_configured_backend_to_service(self) -> None:
        backend = object()
        with (
            patch("memory_substrate.interfaces.mcp.tools.create_graph_backend", return_value=backend) as factory,
            patch("memory_substrate.interfaces.mcp.tools.QueryService") as query_service,
        ):
            service = query_service.return_value
            service.graph.return_value = {"result_type": "graph", "data": {"nodes": []}, "warnings": []}

            result = memory_query(".", "graph", {"id": "know:x"}, {"graph_backend": "file", "max_items": 3})

            self.assertEqual(result["result_type"], "graph")
            factory.assert_called_once_with(Path("."), "file")
            query_service.assert_called_once_with(Path("."), graph_backend=backend)
            service.graph.assert_called_once_with(object_id="know:x", max_items=3)

    def test_remember_passes_configured_backend_to_service(self) -> None:
        backend = object()
        with (
            patch("memory_substrate.interfaces.mcp.tools.create_graph_backend", return_value=backend) as factory,
            patch("memory_substrate.interfaces.mcp.tools.RememberService") as remember_service,
        ):
            service = remember_service.return_value
            service.create_knowledge.return_value = {"knowledge_id": "know:x"}

            result = memory_remember(
                ".",
                "knowledge",
                {
                    "kind": "decision",
                    "title": "Use graph backend",
                    "summary": "Index this memory.",
                    "reason": "This verifies graph backend option dispatch.",
                    "memory_source": "system_generated",
                    "scope_refs": ["scope:test"],
                    "payload": {"predicate": "uses", "value": "graph"},
                },
                {"graph_backend": "file"},
            )

            self.assertEqual(result["knowledge_id"], "know:x")
            factory.assert_called_once_with(Path("."), "file")
            remember_service.assert_called_once_with(Path("."), graph_backend=backend)

    def test_maintain_reindex_passes_configured_backend_to_service(self) -> None:
        backend = object()
        with (
            patch("memory_substrate.interfaces.mcp.tools.create_graph_backend", return_value=backend) as factory,
            patch("memory_substrate.interfaces.mcp.tools.MaintainService") as maintain_service,
        ):
            service = maintain_service.return_value
            service.reindex.return_value = {"result_type": "reindex_result", "data": {"count": 1}, "warnings": []}

            result = memory_maintain(".", "reindex", {}, {"graph_backend": "file"})

            self.assertEqual(result["result_type"], "reindex_result")
            factory.assert_called_once_with(Path("."), "file")
            maintain_service.assert_called_once_with(Path("."), graph_backend=backend)


if __name__ == "__main__":
    unittest.main()
