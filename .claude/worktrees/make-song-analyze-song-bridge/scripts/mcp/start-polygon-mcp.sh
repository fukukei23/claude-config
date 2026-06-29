#!/bin/bash
# Polygon MCP Server launcher - Claude Desktop用
export MASSIVE_API_KEY="${MASSIVE_API_KEY:?MASSIVE_API_KEY is not set. Add it to ~/.secrets.env}"
export PYTHONPATH="/mnt/c/Users/USER/AppData/Roaming/Claude/Claude Extensions/ant.dir.gh.polygon.polygon-mcp-server/src"
export MCP_TRANSPORT="stdio"
exec python3 -u "/mnt/c/Users/USER/AppData/Roaming/Claude/Claude Extensions/ant.dir.gh.polygon.polygon-mcp-server/entrypoint.py"
