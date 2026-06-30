#!/bin/bash
# brave-search MCP Server launcher
# .secrets.envからAPIキーを読み込んで起動
set -a
source /home/yn4416/.secrets.env
set +a
exec /home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/brave-search-mcp-server
