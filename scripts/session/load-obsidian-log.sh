#!/bin/bash
# load-obsidian-log.sh — SessionStart Hook: SSOT日記・バックログをClaudeコンテキストに表示（軽量版）
# stdout → Claude Codeコンテキスト, /dev/tty → ターミナル表示
# 軽量化: 今日=直近3セッション / 昨日=サマリー1行 / バックログ=P0+P1のみ

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

# --- 今日の日記: 直近3セッションのみ ---
if [[ -f "$DAILY_DIR/$TODAY.md" ]]; then
  TOTAL_SESSIONS=$(grep -c "^## セッションログ" "$DAILY_DIR/$TODAY.md" 2>/dev/null || echo 0)

  if [[ "$TOTAL_SESSIONS" -le 3 ]]; then
    # 3以下なら全量（そのまま）
    echo "--- 今日のSSOT日記 ($TODAY) ---"
    cat "$DAILY_DIR/$TODAY.md"
    echo "--- /今日のSSOT日記 ---"
  else
    # 4以上なら直近3セッション分のみ
    echo "--- 今日のSSOT日記 ($TODAY) — 直近3/${TOTAL_SESSIONS}セッション ---"
    # ヘッダー部分（## セッションログの前まで）を取得
    sed '/^## セッションログ/,$ d' "$DAILY_DIR/$TODAY.md"
    echo ""
    # 直近3セッションを取得: セッション区切り(## または --- or セッション終了)でブロック化
    # 最後の3つの ## セッションログ から次の ## セッションログの前までを抽出
    tac "$DAILY_DIR/$TODAY.md" | awk '
      /^## セッションログ/ { count++ }
      count <= 3 { lines[NR] = $0 }
      count > 3 { next }
      END {
        for (i = NR; i >= 1; i--) {
          if (i in lines) print lines[i]
        }
      }
    ' | sed '/^セッション終了:/d'
    echo ""
    echo "（※ ${TOTAL_SESSIONS}セッション中、直近3件のみ表示。全履歴は $DAILY_DIR/$TODAY.md を参照）"
    echo "--- /今日のSSOT日記 ---"
  fi
fi

# --- 昨日の日記: サマリー1行のみ（全量は不要時にRead） ---
if [[ -n "$YESTERDAY" ]] && [[ -f "$DAILY_DIR/$YESTERDAY.md" ]]; then
  yesterday_count=$(count_sessions "$DAILY_DIR/$YESTERDAY.md")
  last_y=$(last_session_task "$DAILY_DIR/$YESTERDAY.md")
  echo "--- 昨日のSSOT日記 ($YESTERDAY): ${yesterday_count}セッション | 最終: ${last_y:-なし} ---"
  echo "（※ 詳細必要時: Read $DAILY_DIR/$YESTERDAY.md）"
fi

# --- 🟢進行中タスク（他セッションの占有・着手前確認用）---
ACTIVE_SESSIONS="$SSOT_PATH/00_SYSTEM/active-sessions.md"
if [[ -f "$ACTIVE_SESSIONS" ]]; then
  active_tasks=$(awk '/^## 🟢/{flag=1; next} /^## /{if(flag) exit} flag && /^\| / && !/^\| タスク/ && !/^\|-/' "$ACTIVE_SESSIONS" 2>/dev/null)
  if [[ -n "$active_tasks" ]]; then
    echo "--- 🟢進行中タスク（他セッションが占有中・着手前に確認） ---"
    echo "$active_tasks"
    echo "--- /🟢進行中タスク ---"
  fi
fi

# --- バックログ: P0+P1のみ（P2は必要時にRead） ---
BACKLOG="$SSOT_PATH/00_SYSTEM/バックログ.md"
if [[ -f "$BACKLOG" ]]; then
  # P0+P1の未完了タスクのみ
  backlog_p01=$(awk '/^## P[0-1]:/{section=$0; next} /^## P[2]:/{section=""} /^## 完了済み/{section=""} /^\- \[ \]/{if(section) print "  " $0}' "$BACKLOG" 2>/dev/null)
  if [[ -n "$backlog_p01" ]]; then
    echo "--- バックログ（P0+P1 未完了） ---"
    echo "$backlog_p01"
    p2_count=$(awk '/^## P[2]:/{p2=1} /^## 完了済み/{p2=0} p2 && /^\- \[ \]/{c++} END{print c+0}' "$BACKLOG")
    if [[ "$p2_count" -gt 0 ]]; then
      echo "（※ P2: ${p2_count}件の未完了タスクあり → 必要時: Read $BACKLOG）"
    fi
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
