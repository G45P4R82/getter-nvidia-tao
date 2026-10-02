"""Real FastMCP protocol and tool tests."""

from __future__ import annotations

import asyncio
import os
import unittest

from fastmcp import Client
from fastmcp.exceptions import ToolError

from tao_mcp.server import mcp


def real_tests_enabled() -> bool:
    return os.getenv("TAO_RUN_REAL_TESTS", "false").lower() == "true"


@unittest.skipUnless(real_tests_enabled(), "set TAO_RUN_REAL_TESTS=true")
class RealMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_protocol_exposes_tools(self):
        async with Client(mcp) as client:
            tools = await client.list_tools()
        names = {tool.name for tool in tools}
        self.assertIn("tao_health", names)
        self.assertIn("tao_list_jobs", names)
        self.assertIn("tao_create_workspace", names)
        self.assertIn("tao_submit_job", names)

    async def test_health_tool_calls_real_ftms(self):
        async with Client(mcp) as client:
            result = await client.call_tool("tao_health", {})
        self.assertIn("readiness", result.content[0].text)

    async def test_mutation_is_disabled_by_default(self):
        os.environ.pop("TAO_MCP_ALLOW_MUTATIONS", None)
        async with Client(mcp) as client:
            with self.assertRaises(ToolError):
                await client.call_tool(
                    "tao_create_workspace",
                    {"name": "blocked-unittest", "confirm": "I_CONFIRM"},
                )


if __name__ == "__main__":
    unittest.main()
