#!/bin/bash
# Z.AI Video Generation MCP Server launcher (custom / official REST API)
set -a
source ~/.secrets.env
set +a
exec python3 -u /home/yn4416/.claude/scripts/mcp/zai-video-mcp-server.py
