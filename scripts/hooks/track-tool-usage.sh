#!/usr/bin/env bash
# track-tool-usage.sh — PostToolUse Hook: ツール使用回数をCSVに記録
# claude-cost コマンドでサマリー確認可能

INPUT=$(cat)

# python3でJSONパース
tool_name=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
session_id=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id','unknown'))" 2>/dev/null)

[[ -z "$tool_name" ]] && exit 0

# ログディレクトリ
LOG_DIR="$HOME/.claude/logs"
mkdir -p "$LOG_DIR"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/tool-usage-${TODAY}.csv"

# 初回のみヘッダー
[[ ! -f "$LOG_FILE" ]] && echo "timestamp,session_id,tool_name" > "$LOG_FILE"

# レコード追記
echo "$(date +%H:%M:%S),$session_id,$tool_name" >> "$LOG_FILE"

exit 0
