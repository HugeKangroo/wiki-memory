from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_substrate.interfaces.mcp.tools import memory_maintain, memory_query


class McpSemanticBackendOptionsTest(unittest.TestCase):
    def test_query_passes_configured_semantic_index_to_service(self) -> None:
        semantic = object()
        with (
            patch("memory_substrate.interfaces.mcp.tools.create_graph_backend", return_value=None),
            patch("memory_substrate.interfaces.mcp.tools.create_semantic_index_service", return_value=semantic) as semantic_factory,
            patch("memory_substrate.interfaces.mcp.tools.QueryService") as query_service,
        ):
            service = query_service.return_value
            service.search.return_value = {"result_type": "search_results", "data": {"items": []}, "warnings": []}

            result = memory_query(".", "search", {"query": "Codex dogfood MCP"}, {"semantic_backend": "lancedb", "max_items": 3})

            self.assertEqual(result["result_type"], "search_results")
            semantic_factory.assert_called_once_with(Path("."), "lancedb")
            query_service.assert_called_once_with(Path("."), semantic_index=semantic)
            service.search.assert_called_once_with(query="Codex dogfood MCP", max_items=3, filters=None)

    def test_maintain_reindex_passes_configured_semantic_index_to_service(self) -> None:
        semantic = object()
        with (
            patch("memory_substrate.interfaces.mcp.tools.create_graph_backend", return_value=None),
            patch("memory_substrate.interfaces.mcp.tools.create_semantic_index_service", return_value=semantic) as semantic_factory,
            patch("memory_substrate.interfaces.mcp.tools.MaintainService") as maintain_service,
        ):
            service = maintain_service.return_value
            service.reindex.return_value = {"result_type": "reindex_result", "data": {"semantic_index": {}}, "warnings": []}

            result = memory_maintain(".", "reindex", {}, {"semantic_backend": "lancedb"})

            self.assertEqual(result["result_type"], "reindex_result")
            semantic_factory.assert_called_once_with(Path("."), "lancedb")
            maintain_service.assert_called_once_with(Path("."), semantic_index=semantic)

    def test_configure_can_set_semantic_backend_without_graph_backend(self) -> None:
        with tempfile_root() as root:
            result = memory_maintain(root, "configure", {"semantic_backend": "lancedb"}, {"apply": True})

            self.assertEqual(result["data"]["config"]["semantic"]["backend"], "lancedb")
            self.assertEqual(result["data"]["config"]["semantic"]["model"], "BAAI/bge-m3")


class tempfile_root:
    def __enter__(self) -> Path:
        import tempfile

        self._directory = tempfile.TemporaryDirectory()
        return Path(self._directory.name)

    def __exit__(self, exc_type, exc, tb) -> None:
        self._directory.cleanup()


if __name__ == "__main__":
    unittest.main()
