#!/usr/bin/env bash
# notify-discord-on-error.sh — Notification Hook
# エラー/ブロック時のみDiscord webhookに通知

INPUT=$(cat)

# python3でJSONパース
title=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('title',''))" 2>/dev/null)
message=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',''))" 2>/dev/null)

# エラー/ブロック系のみ通知（通常の完了通知はskip）
if echo "$title $message" | grep -qiE "error|failed|blocked|timeout|crash|fatal|exception"; then
  # Discord webhook URL（環境変数から取得）
  WEBHOOK_URL="${DISCORD_CLAUDE_WEBHOOK:-}"
  if [[ -n "$WEBHOOK_URL" ]]; then
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "{\"content\":\"⚠️ Claude Code Error\n**Title:** $title\n**Message:** $(echo "$message" | cut -c1-500)\"}" \
      > /dev/null 2>&1
  fi
fi

exit 0
