#!/bin/bash
# auto-update-indexes.sh — INDEX差分がある場合に自動更新
# SessionStart hook で実行。差分なしなら何もしない。
set -uo pipefail

STATUS_FILE="/tmp/claude-startup/indexes.status"

# check-decision-indexes.sh が先に実行されている前提
# 差分なし（✅）なら何もしない
if [ -f "$STATUS_FILE" ] && grep -q '^ ✅' "$STATUS_FILE"; then
  exit 0
fi

# 差分あり → 自動実行
if command -v generate-decision-indexes &>/dev/null; then
  OUTPUT=$(generate-decision-indexes 2>&1 || true)
  if [ -n "$OUTPUT" ]; then
    MSG=" ✅ INDEX: 自動更新完了 ($(echo "$OUTPUT" | tail -1))"
  else
    MSG=" ✅ INDEX: 更新不要"
  fi
else
  MSG=" ⚠️ INDEX: generate-decision-indexes 未インストール"
fi

mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/indexes.status
exit 0
