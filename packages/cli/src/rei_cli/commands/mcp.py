"""rei mcp — start the Model Context Protocol server."""
import subprocess
import sys

import click


@click.command("mcp")
@click.option(
    "--transport",
    type=click.Choice(["stdio"]),
    default="stdio",
    show_default=True,
    help="Transport protocol (currently only stdio is supported).",
)
def mcp_command(transport: str) -> None:
    """Start the rei-graph MCP server.

    The server exposes the code-graph tools and resources to any
    MCP-compatible AI assistant (e.g. Claude Desktop, VS Code Copilot).

    \b
    Example VS Code mcp.json entry:
        {
          "servers": {
            "rei-graph": {
              "type": "stdio",
              "command": "rei",
              "args": ["mcp"]
            }
          }
        }
    """
    result = subprocess.run(
        [sys.executable, "-m", "rei_mcp"],
        check=False,
    )
    raise SystemExit(result.returncode)
