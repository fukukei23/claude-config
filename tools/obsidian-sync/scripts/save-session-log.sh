#!/bin/bash
# Claude Code セッション終了時にObsidianログを更新
# settings.json の Stop フックで実行される

# Obsidian vaultのパス（環境に合わせて変更）
OBSIDIAN_PATH="$HOME/openclaw-workspace/obsidian/ClaudeLog"
TODAY=$(date +%Y-%m-%d)
DAILY_LOG="$OBSIDIAN_PATH/daily/$TODAY.md"

# ディレクトリが存在しない場合は作成
mkdir -p "$OBSIDIAN_PATH/daily"
mkdir -p "$OBSIDIAN_PATH/projects"
mkdir -p "$OBSIDIAN_PATH/sessions"

# 日次ログが存在しない場合はテンプレートから作成
if [ ! -f "$DAILY_LOG" ]; then
    sed "s/{{date}}/$TODAY/g" "$OBSIDIAN_PATH/../templates/daily.md" > "$DAILY_LOG"
fi

# セッション終了のタイムスタンプを追加
echo "" >> "$DAILY_LOG"
echo "---" >> "$DAILY_LOG"
echo "セッション終了: $(date +%H:%M)" >> "$DAILY_LOG"

exit 0
