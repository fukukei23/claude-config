#!/bin/bash
# startup-banner.sh — 各フックのステータスを集約して1つのバナーを出力
# SessionStart hooks の最後に配置すること
# /dev/tty のみに出力（stdoutはClaude Codeコンテキスト用として別途送信されるため重複防止）

STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

# --- ステータスファイルを収集 ---
secrets=""
glm_proxy=""
security=""
secrets_sync=""
mcp_guide=""
submodules=""
indexes=""
broken_links=""

cwd=""
for name in version secrets glm-proxy security secrets-sync mcp-guide submodules indexes broken-links cwd; do
  f="$STATUS_DIR/${name}.status"
  if [ -f "$f" ]; then
    content=$(cat "$f")
    eval "${name//-/_}=\$content"
  fi
done

# --- ハンドオフ情報 ---
HANDOFF_FILE="$HOME/.claude/state/handoff.md"
handoff_line="（初回セッション）"
if [ -f "$HANDOFF_FILE" ]; then
  handoff_line=$(head -1 "$HANDOFF_FILE" | sed 's/^# //')
fi

# --- 本日セッション数 ---
SSOT_PATH="/home/yn4416/projects/obsidian-ssot"
TODAY=$(date +%Y-%m-%d)
DAILY_LOG="$SSOT_PATH/10_DAILY/$TODAY.md"
session_info="本日初回"
if [ -f "$DAILY_LOG" ]; then
  SESSION_COUNT=$(grep -c "^## セッションログ" "$DAILY_LOG" 2>/dev/null)
  SESSION_COUNT=${SESSION_COUNT:-0}
  if [ "$SESSION_COUNT" -gt 0 ]; then
    LAST_TASK=$(grep -A1 "^## セッションログ" "$DAILY_LOG" | grep "^-" | tail -1 | sed 's/^- //')
    END_TIME=$(grep "^セッション終了:" "$DAILY_LOG" | tail -1 | sed 's/セッション終了: //')
    session_info="本日${SESSION_COUNT}セッション | 最終: ${LAST_TASK} (${END_TIME}終了)"
  fi
fi

# --- バナー生成 ---
SEP="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
banner=""
banner+="$(printf '%s\n' "$SEP")"$'\n'
banner+="$(printf ' 🚀 Claude Code セッション開始\n')"$'\n'
banner+="$(printf '%s\n' "$SEP")"$'\n'
[ -n "$version" ] && banner+="$(printf '%s\n' "$version")"$'\n'
[ -n "$cwd" ] && banner+="$(printf '%s\n' "$cwd")"$'\n'
[ -n "$secrets" ] && banner+="$(printf '%s\n' "$secrets")"$'\n'
[ -n "$glm_proxy" ] && banner+="$(printf '%s\n' "$glm_proxy")"$'\n'
[ -n "$security" ] && banner+="$(printf '%s\n' "$security")"$'\n'
[ -n "$secrets_sync" ] && banner+="$(printf '%s\n' "$secrets_sync")"$'\n'
[ -n "$mcp_guide" ] && banner+="$(printf '%s\n' "$mcp_guide")"$'\n'
[ -n "$submodules" ] && banner+="$(printf '%s\n' "$submodules")"$'\n'
[ -n "$indexes" ] && banner+="$(printf '%s\n' "$indexes")"$'\n'
[ -n "$broken_links" ] && banner+="$(printf '%s\n' "$broken_links")"$'\n'
banner+="$(printf '%s\n' "$SEP")"$'\n'
banner+="$(printf ' 📋 前回: %s\n' "$handoff_line")"$'\n'
banner+="$(printf ' 📝 %s\n' "$session_info")"$'\n'
banner+="$(printf '%s\n' "$SEP")"

# --- 出力: /dev/tty のみ（stdoutに出すとClaude Codeがターミナルにエコーして重複する）---
(bash -c 'printf "%s\n" "$0" >/dev/tty' "$banner" 2>/dev/null) || printf '%s\n' "$banner" >&2
