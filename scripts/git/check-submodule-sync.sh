#!/bin/bash
# サブモジュールの鮮度チェック

SSOT_PATH="/home/yn4416/projects/obsidian-ssot"
[ -d "$SSOT_PATH" ] || exit 0
cd "$SSOT_PATH" || exit 0
[ -f .gitmodules ] || exit 0

STALE=()
while IFS= read -r line; do
  STATUS="${line:0:1}"
  NAME=$(echo "$line" | awk '{print $2}')
  if [ "$STATUS" = "+" ] || [ "$STATUS" = "-" ]; then
    STALE+=("$NAME")
  fi
done < <(git submodule status 50_PROJECTS/ 2>/dev/null)

if [ ${#STALE[@]} -gt 0 ]; then
  MSG=" ⚠️ サブモジュール: 更新あり (${STALE[*]})"
else
  MSG=" ✅ サブモジュール: 最新"
fi
mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/submodules.status
exit 0
