#!/bin/bash
# MiniMax Video MCP Server launcher - 動画生成専用（従量 Cash$ アカウント）
# MINIMAX_API_KEY_VIDEO を MINIMAX_API_KEY にマップして minimax-mcp バイナリへ
set -e

exec 2>>/tmp/minimax-video-mcp.log

echo '[startup] minimax-video-mcp' >> /tmp/minimax-video-mcp.log

# シークレット読み込み（MINIMAX_API_KEY と MINIMAX_API_KEY_VIDEO 両方が入る）
source ~/.secrets.env

# 動画用キーへ切替: VIDEO キーをバイナリが期待する MINIMAX_API_KEY に上書き
export MINIMAX_API_KEY="${MINIMAX_API_KEY_VIDEO}"

echo '[secrets loaded: VIDEO key]' >> /tmp/minimax-video-mcp.log

# 必須環境変数（出力パスを official と分離）
export MINIMAX_API_HOST='https://api.minimax.io'
export MINIMAX_MCP_BASE_PATH='/home/yn4416/minimax-output-video'
mkdir -p /home/yn4416/minimax-output-video

echo '[starting minimax-video-mcp]' >> /tmp/minimax-video-mcp.log

exec /home/yn4416/.local/bin/minimax-mcp
