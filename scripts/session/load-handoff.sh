#!/usr/bin/env bash
# load-handoff.sh — SessionStart Hook: ハンドオフ情報をClaudeコンテキストとユーザー画面の両方に表示
# stdout → Claude Codeコンテキスト, /dev/tty → ターミナル表示
#
# 仕様（2026-06-17改定）:
#   - 主: 00_SYSTEM/handoff/ の最新5件を全文 cat（セッション再開の文脈復元用）
#   - 副: 履歴が空の場合のみ ~/.claude/state/handoff.md（最新1件）にフォールバック
#   - バナー1行表示は最新1件のタイトルのみ（ノイズ回避）

HISTORY_DIR="$HOME/projects/obsidian-ssot/00_SYSTEM/handoff"
STATE_FILE="$HOME/.claude/state/handoff.md"

# 最新5件を新しい順に取得
mapfile -t FILES < <(ls -t "$HISTORY_DIR"/*.md 2>/dev/null | head -5)

if [[ ${#FILES[@]} -gt 0 ]]; then
  # Claude Codeコンテキストへ（stdout）— 履歴5件全文
  echo "--- Handoff (最新${#FILES[@]}件) ---"
  for f in "${FILES[@]}"; do
    echo ""
    echo "### $(basename "$f")"
    cat "$f"
  done
  echo ""
  echo "--- /Handoff ---"

  # ユーザー画面へ（/dev/tty）— バナー1行（最新1件のタイトルのみ）
  (
    summary=$(head -1 "${FILES[0]}" | sed 's/^# //')
    printf '📋 ハンドオフ(最新5件自動読込): %s\n' "$summary"
  ) >/dev/tty 2>/dev/null || true
elif [[ -f "$STATE_FILE" ]]; then
  # フォールバック: 履歴が空 → state（最新1件）
  echo "--- Handoff (state fallback) ---"
  cat "$STATE_FILE"
  echo "--- /Handoff ---"

  (
    summary=$(head -1 "$STATE_FILE" | sed 's/^# //')
    printf '📋 ハンドオフ: %s\n' "$summary"
  ) >/dev/tty 2>/dev/null || true
else
  echo "(handoff: なし)"
fi
