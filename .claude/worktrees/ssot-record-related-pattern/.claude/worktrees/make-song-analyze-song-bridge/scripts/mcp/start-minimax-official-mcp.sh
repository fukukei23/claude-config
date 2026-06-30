#!/bin/bash
set -e

exec 2>>/tmp/minimax-official-mcp.log

echo '[startup] Sun Jun  7 02:10:15     2026' >> /tmp/minimax-official-mcp.log

# シークレット読み込み
source ~/.secrets.env

echo '[secrets loaded]' >> /tmp/minimax-official-mcp.log

# 必須環境変数
export MINIMAX_API_HOST='https://api.minimax.io'
export MINIMAX_MCP_BASE_PATH='/home/yn4416/minimax-output'
mkdir -p /home/yn4416/minimax-output

echo '[starting minimax-mcp]' >> /tmp/minimax-official-mcp.log

exec /home/yn4416/.local/bin/minimax-mcp
