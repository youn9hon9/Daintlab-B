from __future__ import annotations

import asyncio

from src.config import Settings
from src.errors import DriverError
from src.mcp_gateway import MCPGateway


async def main() -> None:
    settings = Settings.from_env()
    settings.require_api_key()

    async with MCPGateway(settings) as gateway:
        tools = await gateway.list_openai_tools()
        names = sorted(tool["function"]["name"] for tool in tools)

    print(f"Connected to MCP. Tool count: {len(names)}")
    for name in names:
        print(f"- {name}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except DriverError as exc:
        raise SystemExit(f"MCP check failed: {exc}") from None
