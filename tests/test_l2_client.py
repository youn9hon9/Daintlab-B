import unittest
from pathlib import Path

import httpx

from src.l2_client import L2Client, L2Settings, L2UpstreamError


class L2ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_authentication_failure_does_not_expose_key(self):
        secret = "never-print-this-secret"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "unauthorized"})

        client = L2Client(
            L2Settings("https://example.invalid", secret, "Lunit/L2-preview"),
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(L2UpstreamError) as caught:
            await client.create_chat_completion(
                [{"role": "user", "content": "hello"}]
            )

        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(str(caught.exception), "L2 returned HTTP 401")

    async def test_network_error_does_not_expose_key(self):
        secret = "another-never-print-secret"

        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        client = L2Client(
            L2Settings("https://example.invalid", secret, "Lunit/L2-preview"),
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(L2UpstreamError) as caught:
            await client.create_chat_completion(
                [{"role": "user", "content": "hello"}]
            )

        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(str(caught.exception), "L2 request failed")

    def test_source_does_not_reference_openai_api_key(self):
        project_root = Path(__file__).resolve().parents[1]
        for relative_path in ("app.py", "src/l2_client.py"):
            source = (project_root / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY", source)


if __name__ == "__main__":
    unittest.main()
