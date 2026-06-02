#!/bin/bash
# load-obsidian-log.sh — SessionStart Hook: 直近2日分のSSOT日記をClaudeコンテキストとユーザー画面に表示
# stdout → Claude Codeコンテキスト, /dev/tty → ターミナル表示

SSOT_PATH="/home/yn4416/projects/obsidian-ssot"
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null)
DAILY_DIR="$SSOT_PATH/10_DAILY"

tty_out() {
  printf '%s\n' "$1" >/dev/tty 2>/dev/null || true
}

# --- セッション数カウント用関数 ---
count_sessions() {
  local log="$1"
  local count=0
  if [[ -f "$log" ]]; then
    count=$(grep -c "^## セッションログ" "$log" 2>/dev/null)
    count=${count:-0}
  fi
  echo "$count"
}

last_session_task() {
  local log="$1"
  if [[ -f "$log" ]]; then
    grep -A1 "^## セッションログ" "$log" | grep "^-" | tail -1 | sed 's/^- //'
  fi
}

# --- 今日の日記 ---
if [[ -f "$DAILY_DIR/$TODAY.md" ]]; then
  echo "--- 今日のSSOT日記 ($TODAY) ---"
  cat "$DAILY_DIR/$TODAY.md"
  echo "--- /今日のSSOT日記 ---"
fi

# --- 昨日の日記（常に入れる） ---
if [[ -n "$YESTERDAY" ]] && [[ -f "$DAILY_DIR/$YESTERDAY.md" ]]; then
  echo "--- 昨日のSSOT日記 ($YESTERDAY) ---"
  cat "$DAILY_DIR/$YESTERDAY.md"
  echo "--- /昨日のSSOT日記 ---"
fi

# --- バックログ（未完了タスク） ---
BACKLOG="$SSOT_PATH/00_SYSTEM/バックログ.md"
if [[ -f "$BACKLOG" ]]; then
  # 未完了タスク（- [ ]）のみClaudeコンテキストに読み込み
  backlog_content=$(grep -A0 '^\- \[ \]' "$BACKLOG" 2>/dev/null)
  if [[ -n "$backlog_content" ]]; then
    echo "--- バックログ（未完了タスク） ---"
    # P0/P1/P2セクションヘッダー付きで抽出
    awk '/^## P[0-2]:/{section=$0; next} /^## 完了済み/{section=""} /^\- \[ \]/{if(section) print section " → " $0; else print $0}' "$BACKLOG"
    echo "--- /バックログ ---"
  fi

  # 自動確認プロンプト（7日以上経過タスク）
  prompt=$(python3 /home/yn4416/bin/backlog-auto-check.py prompt 2>/dev/null)
  if [[ -n "$prompt" ]]; then
    echo "$prompt"
  fi
fi

# --- ユーザー画面へ（/dev/tty）— サマリーのみ ---
(
  today_count=$(count_sessions "$DAILY_DIR/$TODAY.md")
  yesterday_count=$(count_sessions "$DAILY_DIR/$YESTERDAY.md")

  if [ "$today_count" -gt 0 ]; then
    last=$(last_session_task "$DAILY_DIR/$TODAY.md")
    printf '📖 今日: %dセッション | 最終: %s\n' "$today_count" "${last:-なし}"
  else
    printf '📖 今日: 記録なし\n'
  fi

  if [ "$yesterday_count" -gt 0 ]; then
    last_y=$(last_session_task "$DAILY_DIR/$YESTERDAY.md")
    printf '📖 昨日: %dセッション | 最終: %s\n' "$yesterday_count" "${last_y:-なし}"
  elif [[ -n "$YESTERDAY" ]] && [[ -f "$DAILY_DIR/$YESTERDAY.md" ]]; then
    printf '📖 昨日: 日記あり（セッション記録なし）\n'
  else
    printf '📖 昨日: 日記なし\n'
  fi

  # バックログ未完了件数
  if [[ -f "$BACKLOG" ]]; then
    p0=$(grep -c '^\- \[ \]' "$BACKLOG" 2>/dev/null || echo 0)
    printf '📋 バックログ: %d件の未完了タスク\n' "${p0:-0}"
  fi
) >/dev/tty 2>/dev/null || true
