#!/bin/bash
# github MCP Server launcher
# .secrets.envからAPIキーを読み込んで起動
set -a
source /home/yn4416/.secrets.env
set +a
exec /home/yn4416/.local/bin/github-mcp-server
