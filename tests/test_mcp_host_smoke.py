from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memory_substrate.experiments.mcp_host_smoke import run_mcp_host_smoke


class McpHostSmokeTest(unittest.TestCase):
    def test_real_stdio_host_smoke_lists_resources_and_calls_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_mcp_host_smoke(tmpdir)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["failed_checks"], [])
            self.assertEqual(
                result["tool_names"],
                ["memory_ingest", "memory_maintain", "memory_query", "memory_remember"],
            )
            self.assertIn("memory://policy", result["resource_uris"])
            self.assertIn("memory://agent-playbook", result["resource_uris"])
            self.assertIn("memory://mcp-api-summary", result["resource_uris"])
            self.assertTrue(result["root_config_exists"])
            self.assertTrue((Path(tmpdir) / "memory" / "config.json").exists())


if __name__ == "__main__":
    unittest.main()
