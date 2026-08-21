from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock

from src.mcp_gateway import MCPGateway
from tests.helpers import make_settings


class MCPGatewayTest(unittest.TestCase):
    def test_large_tool_message_is_bounded_and_keeps_citation_ids(self) -> None:
        settings = make_settings(max_mcp_result_chars=1024)
        gateway = MCPGateway(settings)
        payload = {
            "structuredContent": {
                "cite_uid": "cite-large-1",
                "content": "x" * 5000,
            },
            "isError": False,
        }
        raw = json.dumps(payload)

        content = gateway._bounded_tool_content(raw, payload)

        self.assertLessEqual(len(content), settings.max_mcp_result_chars)
        compact = json.loads(content)
        self.assertTrue(compact["truncated"])
        self.assertIn("cite-large-1", compact["cite_uids"])


class MCPGatewayCacheTest(unittest.IsolatedAsyncioTestCase):
    async def test_tool_schemas_are_cached_between_gateways(self) -> None:
        settings = make_settings(
            lunit_mcp_url="https://mcp-cache.example.test/mcp"
        )
        MCPGateway._tool_cache.pop(settings.lunit_mcp_url, None)
        schema = {
            "type": "function",
            "function": {
                "name": "cached_search",
                "description": "test",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        first = MCPGateway(settings)
        first._fetch_openai_tools = AsyncMock(return_value=[schema])
        second = MCPGateway(settings)
        second._fetch_openai_tools = AsyncMock(return_value=[])

        first_tools = await first.list_openai_tools()
        second_tools = await second.list_openai_tools()

        self.assertEqual(first_tools, [schema])
        self.assertEqual(second_tools, [schema])
        first._fetch_openai_tools.assert_awaited_once()
        second._fetch_openai_tools.assert_not_awaited()
        self.assertIn("cached_search", second._allowed_tools)


if __name__ == "__main__":
    unittest.main()
