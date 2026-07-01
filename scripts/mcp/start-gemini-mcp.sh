#!/bin/bash
# Gemini MCP Server launcher - Gemini(無料枠)をレビュー/デバッグ用第2オピニオンとして提供
# Python unbuffered mode (-u) でnull byte問題を回避
set -a
source /home/yn4416/.secrets.env
set +a
exec python3 -u /home/yn4416/.claude/scripts/mcp/gemini-mcp-server.py
