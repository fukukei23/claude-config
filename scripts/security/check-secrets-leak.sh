#!/bin/bash
# settings 系ファイルに API キー値が平文で混入していないか検出

set -uo pipefail

FILES=(
  "/home/yn4416/.claude/settings.json"
  "/home/yn4416/.claude/settings.local.json"
  "/mnt/c/Users/yn441/.claude/settings.json"
  "/mnt/c/Users/yn441/.claude/settings.local.json"
  "/mnt/c/Users/yn441/AppData/Roaming/Claude/claude_desktop_config.json"
)

WHITELIST_RE='^(https?://|/(home|mnt|c)/|[A-Z]:\\|file://|nexuscore-|claude-|agent-sdk-)'

total_warnings=0

for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue

  candidates=$(grep -oE '"[A-Za-z0-9_.-]{32,}"' "$f" 2>/dev/null \
    | tr -d '"' \
    | grep -vE "$WHITELIST_RE" \
    || true)

  if [ -n "$candidates" ]; then
    count=$(echo "$candidates" | wc -l)
    total_warnings=$((total_warnings + count))
  fi
done

if [ "$total_warnings" -eq 0 ]; then
  MSG=" ✅ セキュリティ: 設定ファイルに問題なし"
else
  MSG=" ⚠️ セキュリティ: ${total_warnings}件警告 (→ シークレット管理ポリシー.md)"
fi
mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/security.status
exit 0
