#!/bin/bash
# sync-check.sh: 実環境(~/.claude/scripts/)とclaude-configの差分を検出
# 使い方: bash ~/projects/claude-config/scripts/sync-check.sh

LIVE="$HOME/.claude/scripts"
REPO="$(dirname "$0")"

EXCLUDE=(
  "--exclude=__pycache__"
  "--exclude=*.pyc"
  "--exclude=loop.log"
  "--exclude=state.json"
  "--exclude=glm-rate-proxy"
)

echo "=== 実環境 → GitHub未反映のファイル ==="
diff_out=$(diff -rq "${EXCLUDE[@]/#/}" "$LIVE/" "$REPO/" 2>/dev/null \
  | grep "^Only in $LIVE" | sed "s|Only in $LIVE||;s|: |/|")

if [[ -z "$diff_out" ]]; then
  echo "  差分なし ✅"
else
  echo "$diff_out" | sed 's/^/  NEW: /'
fi

echo ""
echo "=== GitHub側にあって実環境にないファイル ==="
old_out=$(diff -rq "${EXCLUDE[@]/#/}" "$LIVE/" "$REPO/" 2>/dev/null \
  | grep "^Only in $REPO" | sed "s|Only in $REPO||;s|: |/|")

if [[ -z "$old_out" ]]; then
  echo "  差分なし ✅"
else
  echo "$old_out" | sed 's/^/  STALE: /'
fi

echo ""
echo "=== 内容が異なるファイル ==="
mod_out=$(diff -rq "${EXCLUDE[@]/#/}" "$LIVE/" "$REPO/" 2>/dev/null \
  | grep "^Files" | sed "s|Files ||;s| and .*||;s|$LIVE/||")

if [[ -z "$mod_out" ]]; then
  echo "  差分なし ✅"
else
  echo "$mod_out" | sed 's/^/  MODIFIED: /'
fi
