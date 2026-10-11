"""The MCP interface to the data tools: the same functions that the agent calls.

The server speaks stdio only, so it opens no network port. On stdio, stdout
carries the protocol: nothing here or in the tools can print to it.
"""

import sys

from mcp.server.mcpserver import MCPServer

from analyst import tools
from analyst.settings import SettingsError, get_settings

TOOLS = (
    tools.get_data_catalog,
    tools.get_schema,
    tools.resolve_player,
    tools.run_sql,
    tools.build_chart,
)

server = MCPServer("highbury")
for tool in TOOLS:
    server.add_tool(tool)


def main() -> None:
    try:
        get_settings()
    except SettingsError as error:
        # A client sees a start that failed, with the name of the variable on stderr.
        sys.exit(str(error))
    server.run()


if __name__ == "__main__":
    main()
