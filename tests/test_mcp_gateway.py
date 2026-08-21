from __future__ import annotations

import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
