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

# ② 追跡ブランチのリモート最新（remote-tracking ref）より古いかを検知
# （git submodule status に --remote は無いため自前比較。
#   auto-sync の `git submodule update --remote` が remote-tracking ref を更新する前提で、
#   「remoteに新commit」「submoduleは最新だが親が未commit」等を検知）
for sm in $(git config --file .gitmodules --get-regexp 'submodule\..*\.path' | awk '{print $2}'); do
  branch=$(git config "submodule.${sm}.branch" 2>/dev/null)
  [ -z "$branch" ] && continue
  head_sha=$(git -C "$sm" rev-parse HEAD 2>/dev/null)
  remote_sha=$(git -C "$sm" rev-parse "origin/${branch}" 2>/dev/null)
  if [ -n "$head_sha" ] && [ -n "$remote_sha" ] && [ "$head_sha" != "$remote_sha" ]; then
    case " ${STALE[*]} " in *" $sm "*) ;; *) STALE+=("$sm(remote更新あり)") ;; esac
  fi
done

if [ ${#STALE[@]} -gt 0 ]; then
  MSG=" ⚠️ サブモジュール: 更新あり (${STALE[*]})"
else
  MSG=" ✅ サブモジュール: 最新"
fi
mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/submodules.status
exit 0
