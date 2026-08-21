from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any
from unittest.mock import patch

from src.mcp_gateway import MCPGateway
from tests.helpers import make_settings


class FakeHTTPClient:
    instances: list["FakeHTTPClient"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.enter_task: asyncio.Task[Any] | None = None
        self.exit_task: asyncio.Task[Any] | None = None
        self.exited = False
        self.__class__.instances.append(self)

    async def __aenter__(self) -> "FakeHTTPClient":
        self.enter_task = asyncio.current_task()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.exit_task = asyncio.current_task()
        self.exited = True


class FakeTransport:
    def __init__(self, terminate_on_close: bool) -> None:
        self.terminate_on_close = terminate_on_close
        self.enter_task: asyncio.Task[Any] | None = None
        self.exit_task: asyncio.Task[Any] | None = None
        self.exited = False

    async def __aenter__(self) -> object:
        self.enter_task = asyncio.current_task()
        return object()

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.exit_task = asyncio.current_task()
        self.exited = True


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(
        self,
        transport: FakeTransport,
        *,
        mode: str,
        read_timeout_seconds: float,
    ) -> None:
        self.transport = transport
        self.mode = mode
        self.read_timeout_seconds = read_timeout_seconds
        self.enter_task: asyncio.Task[Any] | None = None
        self.exit_task: asyncio.Task[Any] | None = None
        self.list_cursors: list[str | None] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.__class__.instances.append(self)

    async def __aenter__(self) -> "FakeClient":
        self.enter_task = asyncio.current_task()
        await self.transport.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.exit_task = asyncio.current_task()
        await self.transport.__aexit__(exc_type, exc, traceback)

    async def list_tools(self, *, cursor: str | None = None):
        self.list_cursors.append(cursor)
        tool = type(
            "FakeTool",
            (),
            {
                "name": "fake_search",
                "description": "Search fake evidence.",
                "title": None,
                "input_schema": {"type": "object", "properties": {}},
            },
        )()
        return type(
            "FakeToolPage",
            (),
            {"tools": [tool], "next_cursor": None},
        )()

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        read_timeout_seconds: float,
    ):
        self.tool_calls.append(
            {
                "name": name,
                "arguments": arguments,
                "read_timeout_seconds": read_timeout_seconds,
            }
        )

        class FakeResult:
            def model_dump(self, **kwargs: Any) -> dict[str, Any]:
                return {"isError": False, "content": []}

        return FakeResult()


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


class MCPGatewayLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeHTTPClient.instances.clear()
        FakeClient.instances.clear()
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


if __name__ == "__main__":
    unittest.main()
