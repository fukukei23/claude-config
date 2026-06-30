#!/bin/bash
# post-tool-settings-sync.sh
# PostToolUse hook から呼ばれる。settings.json が変更された時だけ example を同期する。
# 環境変数 CLAUDE_TOOL_INPUT_FILE_PATH にツールで編集されたファイルパスが入る。

FILE_PATH="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"

# settings.json への変更でなければスキップ
case "$FILE_PATH" in
  */settings.json) ;;
  *) exit 0 ;;
esac

exec /home/yn4416/projects/claude-config/scripts/config/sync-settings-to-example.sh
