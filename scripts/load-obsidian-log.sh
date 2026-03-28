#!/bin/bash
# セッション開始時にObsidianログを表示

OBSIDIAN_PATH="/home/yn441611/openclaw-workspace/obsidian/ClaudeLog"
TODAY=$(date +%Y-%m-%d)
DAILY_LOG="$OBSIDIAN_PATH/daily/$TODAY.md"

if [ -f "$DAILY_LOG" ]; then
    echo "=== 今日のObsidianログ ==="
    cat "$DAILY_LOG"
    echo ""
    echo "↑ 前回の作業内容を確認してください"
fi

exit 0
