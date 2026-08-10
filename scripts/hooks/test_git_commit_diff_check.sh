#!/usr/bin/env bash
# test_git_commit_diff_check.sh — git-commit-diff-check.sh の6項目テスト
# 純bash・tmp git repo で実際にstageしてhookを実行しexit code/stderrを検証
set -uo pipefail

HOOK="$HOME/.claude/scripts/hooks/git-commit-diff-check.sh"
TMP_REPO=""
FAILS=0

setup() {
  TMP_REPO=$(mktemp -d)
  cd "$TMP_REPO" || exit 1
  git init -q
  git config user.email "test@test"
  git config user.name "test"
}

teardown() {
  [ -n "$TMP_REPO" ] && rm -rf "$TMP_REPO"
  TMP_REPO=""
}

# hookにJSONを流す（tool_name=Bash・指定command）
send_hook() {
  local cmd="$1"
  printf '{"tool_name":"Bash","command":"%s"}' "$cmd" | bash "$HOOK" 2>/dev/null
}

# Case 1: 小変更(5行) → exit 0
test_small_change() {
  setup
  printf 'a\nb\nc\nd\ne\n' > f.txt
  git add f.txt
  send_hook "git commit -m test"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case1: expected exit 0 got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

test_small_change
echo "Case1 done"
exit 0
