#!/bin/bash
# Claude Code セッション終了時にObsidianログを更新

OBSIDIAN_PATH="/home/yn441611/openclaw-workspace/obsidian/ClaudeLog"
TODAY=$(date +%Y-%m-%d)
DAILY_LOG="$OBSIDIAN_PATH/daily/$TODAY.md"

# 日次ログが存在しない場合は作成
if [ ! -f "$DAILY_LOG" ]; then
    mkdir -p "$(dirname "$DAILY_LOG")"
    cat > "$DAILY_LOG" << EOF
# $TODAY Claude作業ログ

## 今日やったこと
-

## 進行中のタスク
- [ ]

## 完了したタスク
- [x]

## メモ・気づき
-

## 次回やること
-

## 関連リンク
- [[projects/MOC|プロジェクト一覧]]
EOF
fi

# セッション終了のタイムスタンプを追加
echo "" >> "$DAILY_LOG"
echo "---" >> "$DAILY_LOG"
echo "セッション終了: $(date +%H:%M)" >> "$DAILY_LOG"

exit 0
