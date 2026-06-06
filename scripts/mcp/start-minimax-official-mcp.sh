#!/bin/bash
# MiniMax 公式MCP起動スクリプト（動画・音声・画像生成対応）
set -e

# シークレット読み込み
source ~/.secrets.env

# 必須環境変数
export MINIMAX_API_HOST='https://api.minimax.io'

# 出力先ディレクトリ
export MINIMAX_MCP_BASE_PATH="/home/yn4416/minimax-output"
mkdir -p ""

# 公式MCPサーバー起動
exec /home/yn4416/.local/bin/minimax-mcp
