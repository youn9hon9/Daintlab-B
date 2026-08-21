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


<<<<<<< HEAD
class MCPGatewayLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeHTTPClient.instances.clear()
        FakeClient.instances.clear()
        MCPGateway.clear_tool_cache()
        self.transport_calls: list[dict[str, Any]] = []

    def fake_streamable_http_client(
        self,
        url: str,
        *,
        http_client: FakeHTTPClient,
        terminate_on_close: bool,
    ) -> FakeTransport:
        transport = FakeTransport(terminate_on_close)
        self.transport_calls.append(
            {
                "url": url,
                "http_client": http_client,
                "terminate_on_close": terminate_on_close,
                "transport": transport,
            }
        )
        return transport

    async def test_lifecycle_passes_termination_and_timeout_settings(self) -> None:
        settings = make_settings(
            mcp_tool_timeout_seconds=20.0,
            mcp_terminate_on_close=False,
        )

        with (
            patch("src.mcp_gateway.httpx2.AsyncClient", FakeHTTPClient),
            patch(
                "src.mcp_gateway.streamable_http_client",
                self.fake_streamable_http_client,
            ),
            patch("src.mcp_gateway.Client", FakeClient),
        ):
            async with MCPGateway(settings) as gateway:
                tools = await gateway.list_openai_tools()
                await gateway.call_tool("fake_search", {"query": "test"})

        self.assertEqual(len(self.transport_calls), 1)
        transport_call = self.transport_calls[0]
        self.assertFalse(transport_call["terminate_on_close"])
        self.assertEqual(transport_call["url"], settings.lunit_mcp_url)

        http_client = FakeHTTPClient.instances[0]
        timeout = http_client.kwargs["timeout"]
        self.assertEqual(timeout.connect, 20.0)
        self.assertEqual(timeout.read, 20.0)
        self.assertEqual(timeout.write, 20.0)
        self.assertEqual(timeout.pool, 20.0)

        client = FakeClient.instances[0]
        self.assertEqual(client.mode, "auto")
        self.assertEqual(client.read_timeout_seconds, 20.0)
        self.assertEqual(client.list_cursors, [None])
        self.assertEqual(tools[0]["function"]["name"], "fake_search")
        self.assertEqual(
            client.tool_calls,
            [
                {
                    "name": "fake_search",
                    "arguments": {"query": "test"},
                    "read_timeout_seconds": 20.0,
                }
            ],
        )
        self.assertTrue(http_client.exited)
        self.assertTrue(transport_call["transport"].exited)

    async def test_second_gateway_reuses_cached_tool_list(self) -> None:
        settings = make_settings()

        with (
            patch("src.mcp_gateway.httpx2.AsyncClient", FakeHTTPClient),
            patch(
                "src.mcp_gateway.streamable_http_client",
                self.fake_streamable_http_client,
            ),
            patch("src.mcp_gateway.Client", FakeClient),
        ):
            async with MCPGateway(settings) as first:
                await first.list_openai_tools()
            async with MCPGateway(settings) as second:
                tools = await second.list_openai_tools()
                await second.call_tool("fake_search", {"query": "cached"})

        self.assertEqual(FakeClient.instances[0].list_cursors, [None])
        self.assertEqual(FakeClient.instances[1].list_cursors, [])
        self.assertEqual(tools[0]["function"]["name"], "fake_search")

    async def test_concurrent_gateways_share_one_cold_tool_list_fetch(
        self,
    ) -> None:
        settings = make_settings()
        first_list_started = asyncio.Event()
        release_first_list = asyncio.Event()
        list_calls = 0

        original_list_tools = FakeClient.list_tools

        async def blocking_list_tools(
            client: FakeClient, *, cursor: str | None = None
        ):
            nonlocal list_calls
            list_calls += 1
            if list_calls == 1:
                first_list_started.set()
                await release_first_list.wait()
            return await original_list_tools(client, cursor=cursor)

        with (
            patch("src.mcp_gateway.httpx2.AsyncClient", FakeHTTPClient),
            patch(
                "src.mcp_gateway.streamable_http_client",
                self.fake_streamable_http_client,
            ),
            patch("src.mcp_gateway.Client", FakeClient),
            patch.object(FakeClient, "list_tools", blocking_list_tools),
        ):
            async with MCPGateway(settings) as first, MCPGateway(
                settings
            ) as second:
                first_task = asyncio.create_task(first.list_openai_tools())
                await first_list_started.wait()
                second_task = asyncio.create_task(second.list_openai_tools())
                await asyncio.sleep(0)
                release_first_list.set()
                first_tools, second_tools = await asyncio.gather(
                    first_task, second_task
                )

        self.assertEqual(list_calls, 1)
        self.assertEqual(first_tools, second_tools)
        self.assertIn("fake_search", second._allowed_tools)

    async def test_cancellation_exits_quickly_in_the_owner_task(self) -> None:
        settings = make_settings(
            mcp_tool_timeout_seconds=20.0,
            mcp_terminate_on_close=False,
        )
        entered = asyncio.Event()

        async def use_gateway() -> None:
            async with MCPGateway(settings):
                entered.set()
                await asyncio.Event().wait()

        with (
            patch("src.mcp_gateway.httpx2.AsyncClient", FakeHTTPClient),
            patch(
                "src.mcp_gateway.streamable_http_client",
                self.fake_streamable_http_client,
            ),
            patch("src.mcp_gateway.Client", FakeClient),
        ):
            task = asyncio.create_task(use_gateway())
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=0.1)

        http_client = FakeHTTPClient.instances[0]
        client = FakeClient.instances[0]
        transport = self.transport_calls[0]["transport"]
        self.assertTrue(http_client.exited)
        self.assertTrue(transport.exited)
        self.assertIs(client.enter_task, client.exit_task)
        self.assertIs(transport.enter_task, transport.exit_task)
        self.assertIs(http_client.enter_task, http_client.exit_task)


=======
>>>>>>> origin/lunit/hackathon-submission
if __name__ == "__main__":
    unittest.main()
