#!/bin/bash
set -a
source ~/.claude/secrets.env
set +a
export PYTHONPATH="/mnt/c/Users/USER/AppData/Roaming/Claude/Claude Extensions/ant.dir.gh.polygon.polygon-mcp-server/src"
export MCP_TRANSPORT="stdio"
exec python3 -u "/mnt/c/Users/USER/AppData/Roaming/Claude/Claude Extensions/ant.dir.gh.polygon.polygon-mcp-server/entrypoint.py"
