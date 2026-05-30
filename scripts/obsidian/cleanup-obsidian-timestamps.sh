#!/bin/bash
# ClaudeLog/daily/ 内の旧フォーマットタイムスタンプを圧縮形式に一括変換

DAILY_DIR="/home/yn4416/projects/openclaw-workspace/obsidian/ClaudeLog/daily"
MARKER="セッション: "

for f in "$DAILY_DIR"/*.md; do
    FNAME=$(basename "$f")
    OLD_COUNT=$(grep -c "^セッション終了: " "$f" 2>/dev/null || true)
    OLD_COUNT=${OLD_COUNT:-0}

    if [ "$OLD_COUNT" -gt 0 ]; then
        FIRST=$(grep "^セッション終了: " "$f" | grep -oP '\d{2}:\d{2}' | head -n 1)
        LAST=$(grep "^セッション終了: " "$f" | grep -oP '\d{2}:\d{2}' | tail -n 1)
        TEMP=$(mktemp)
        grep -v "^セッション終了: " "$f" | grep -v "^---$" > "$TEMP"
        echo "${MARKER}${FIRST}〜${LAST}（${OLD_COUNT}回）" >> "$TEMP"
        cat "$TEMP" > "$f"
        rm -f "$TEMP"
        echo "$FNAME: ${OLD_COUNT}件 → 1行に圧縮 (${FIRST}〜${LAST})"
    else
        echo "$FNAME: 変換不要"
    fi
done
