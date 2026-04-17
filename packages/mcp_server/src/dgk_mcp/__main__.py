"""Entry point for running the MCP server via stdio."""
import asyncio

from mcp.server.stdio import stdio_server

from dgk_mcp.server import server


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
