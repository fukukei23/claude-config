#!/bin/bash
# MiniMax MCP Server launcher - Claude Desktop用
# Python unbuffered mode (-u) でnull byte問題を回避
set -a
source /home/yn4416/.secrets.env
set +a
exec python3 -u /home/yn4416/.claude/scripts/mcp/minimax-mcp-server.py
