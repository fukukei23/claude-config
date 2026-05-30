#!/usr/bin/env bash
# load-handoff.sh — SessionStart Hook: ハンドオフ情報をClaudeコンテキストとユーザー画面の両方に表示
# stdout → Claude Codeコンテキスト, /dev/tty → ターミナル表示

HANDOFF_FILE="$HOME/.claude/state/handoff.md"

if [[ -f "$HANDOFF_FILE" ]]; then
  # Claude Codeコンテキストへ（stdout）
  echo "--- Handoff ---"
  cat "$HANDOFF_FILE"
  echo "--- /Handoff ---"

  # ユーザー画面へ（/dev/tty）— バナーに1行追加
  (
    summary=$(head -1 "$HANDOFF_FILE" | sed 's/^# //')
    printf '📋 ハンドオフ: %s\n' "$summary"
  ) >/dev/tty 2>/dev/null || true
else
  echo "(handoff: なし)"
fi
