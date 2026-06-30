#!/usr/bin/env bash
# Claude Code version check with changelog — SessionStart hook
set -euo pipefail

STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

CURRENT=$(claude --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)
if [[ -z "$CURRENT" ]]; then
  echo "⚠️ Claude Codeバージョン取得失敗"
  echo "⚠️ Claude Codeバージョン取得失敗" > "$STATUS_DIR/version.status"
  exit 0
fi

LATEST=$(npm show @anthropic-ai/claude-code version 2>/dev/null || echo "")
if [[ -z "$LATEST" ]]; then
  echo "⚠️ 最新版取得失敗（npm応答なし）"
  echo "⚠️ 最新版取得失敗（npm応答なし）" > "$STATUS_DIR/version.status"
  exit 0
fi

# Color codes (defined early for use in all paths)
RED='\033[1;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'
BELL='\a'

# Version comparison
IFS='.' read -r c_major c_minor c_patch <<< "$CURRENT"
IFS='.' read -r l_major l_minor l_patch <<< "$LATEST"

if [[ "$CURRENT" == "$LATEST" ]]; then
  # Box style for latest version
  MSG="  ✅ Claude Code ${CURRENT} — 最新版！ ✅  "
  INNER=${#MSG}
  BORDER=$(printf '═%.0s' $(seq 1 $INNER))
  BOX="${GREEN}╔${BORDER}╗${RESET}\n${GREEN}║${BOLD}${MSG}${RESET}${GREEN}║${RESET}\n${GREEN}╚${BORDER}╝${RESET}"
  echo -e "\n${BOX}\n"
  # ステータスファイルにも書き出し（startup-banner.sh用）
  echo -e "${BOX}" > "$STATUS_DIR/version.status"
  exit 0
fi

# Count how many versions behind
VERSIONS_BEHIND=$(npm show @anthropic-ai/claude-code versions --json 2>/dev/null \
  | python3 -c "
import sys, json
vs = json.load(sys.stdin)
try:
    idx_c = vs.index('$CURRENT')
    idx_l = vs.index('$LATEST')
    print(idx_l - idx_c)
except ValueError:
    print('?')
" 2>/dev/null || echo "?")

# Determine severity
SEVERITY="patch"
if [[ "$c_major" != "$l_major" ]] || [[ "$c_minor" != "$l_minor" ]]; then
  SEVERITY="major"
fi

# Warning header with box
MSG1="  🚨 Claude Code ${CURRENT} ← ${LATEST}（${VERSIONS_BEHIND}遅れ）"
MSG2="  → claude update で更新してください"
INNER=${#MSG1}
if [[ ${#MSG2} -gt $INNER ]]; then INNER=${#MSG2}; fi
BORDER=$(printf '═%.0s' $(seq 1 $INNER))

if [[ "$SEVERITY" == "major" ]]; then
  BOX="${RED}╔${BORDER}╗${BELL}${RESET}\n${RED}║${BOLD}${MSG1}${RESET}${RED}║${RESET}\n${RED}║${BOLD}${MSG2}${RESET}${RED}║${RESET}\n${RED}╚${BORDER}╝${RESET}"
else
  BOX="${YELLOW}╔${BORDER}╗${RESET}\n${YELLOW}║${BOLD}${MSG1}${RESET}${YELLOW}║${RESET}\n${YELLOW}║${BOLD}${MSG2}${RESET}${YELLOW}║${RESET}\n${YELLOW}╚${BORDER}╝${RESET}"
fi
echo -e "\n${BOX}\n"
# ステータスファイルにも書き出し（startup-banner.sh用）
echo -e "${BOX}" > "$STATUS_DIR/version.status"

# Fetch changelog for versions between current and latest
CHANGELOG=$(curl -sf "https://api.github.com/repos/anthropics/claude-code/releases?per_page=20" 2>/dev/null || echo "[]")

echo -e "${CYAN}━━━ 📋 変更履歴（${CURRENT} → ${LATEST}）━━━${RESET}"

echo "$CHANGELOG" | python3 -c "
import sys, json, re

current = '$CURRENT'
latest = '$LATEST'
CYAN = '\033[0;36m'
DIM = '\033[2m'
BOLD = '\033[1m'
GREEN = '\033[0;32m'
RESET = '\033[0m'

try:
    releases = json.load(sys.stdin)
except:
    print('  changelog取得失敗')
    sys.exit(0)

def ver_tuple(v):
    parts = v.lstrip('v').split('.')
    return tuple(int(p) for p in parts)

cur_t = ver_tuple(current)
lat_t = ver_tuple(latest)
found_start = False
count = 0

for r in releases:
    tag = r.get('tag_name', '').lstrip('v')
    try:
        tag_t = ver_tuple(tag)
    except:
        continue

    # Skip versions newer than latest (shouldn't happen) or older/equal to current
    if tag_t <= cur_t:
        continue
    if tag_t > lat_t:
        continue

    body = (r.get('body', '') or '').strip()
    # Truncate long changelogs to first ~500 chars
    if len(body) > 500:
        body = body[:500] + '...'

    # Bold the version, dim the body
    print(f'{BOLD}  📦 {tag}{RESET}')
    for line in body.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('##'):
            continue
        # Highlight key features
        if line.startswith('-'):
            print(f'{GREEN}    {line}{RESET}')
        else:
            print(f'{DIM}    {line}{RESET}')
    print()
    count += 1

if count == 0:
    print(f'  ${DIM}（該当バージョンのリリースノートなし）{RESET}')
" 2>/dev/null

echo -e "${BOLD}  ┗ claude update で更新${RESET}"
