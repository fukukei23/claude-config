#!/bin/bash
# 意図せず公開ファイルにシークレットが混入していないか検出
# settings.json/settings.local.json のキーは想定内（.secrets.env由来）なので除外

set -uo pipefail

# 検査対象: キーが存在すべきでないファイルのみ
# ※ settings.json/settings.local.json は .secrets.env 由来で想定内のため除外
FILES=(
  "/home/yn4416/projects/claude-config/settings.example.json"
  "/mnt/c/Users/yn441/AppData/Roaming/Claude/claude_desktop_config.json"
)

WHITELIST_RE='^(https?://|/(home|mnt|c)/|[A-Z]:\\|file://|nexuscore-|claude-|agent-sdk-|mcp__|CLAUDE_)'

total_warnings=0

for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue

  candidates=$(grep -oE '"[A-Za-z0-9_.-]{32,}"' "$f" 2>/dev/null \
    | tr -d '"' \
    | grep -vE "$WHITELIST_RE" \
    | grep -vE '^[A-Za-z]+$' \
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
