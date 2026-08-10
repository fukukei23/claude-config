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

# hookにJSONを流す（tool_name=Bash・指定command）・stderr破棄
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

# Case 2: 50行追加 → exit 2
test_large_change_block() {
  setup
  seq 1 50 > big.txt
  git add big.txt
  send_hook "git commit -m test"
  local rc=$?
  if [ "$rc" -ne 2 ]; then
    echo "FAIL Case2: expected exit 2 got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 3: バイナリのみ → exit 0
test_binary_only() {
  setup
  printf '\x00\x01\x02\x03' > bin.dat
  git add bin.dat
  send_hook "git commit -m test"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case3: expected exit 0 got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 4: staged-empty → exit 0
test_staged_empty() {
  setup
  send_hook "git commit -m test"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case4: expected exit 0 got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 5: stderr構造（block時に5項目含有）
test_stderr_structure() {
  setup
  seq 1 50 > big.txt
  git add big.txt
  local stderr_out
  stderr_out=$(printf '{"tool_name":"Bash","command":"git commit -m test"}' | bash "$HOOK" 2>&1 1>/dev/null)
  local missing=0
  for key in EXIT_CODE REASON MAX_DELTA FILE REQUIRED_ACTION; do
    echo "$stderr_out" | grep -q "$key" || missing=$((missing+1))
  done
  if [ "$missing" -ne 0 ]; then
    echo "FAIL Case5: $missing keys missing in stderr"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 6: 実行時間 ≤2秒（date +%s%N の整数演算・bc非依存）
test_execution_time() {
  setup
  seq 1 100 > big.txt
  git add big.txt
  local start end elapsed_ns
  start=$(date +%s%N)
  send_hook "git commit -m test"
  end=$(date +%s%N)
  elapsed_ns=$(( end - start ))
  # 2秒 = 2,000,000,000 ns
  if [ "$elapsed_ns" -gt 2000000000 ]; then
    echo "FAIL Case6: elapsed ${elapsed_ns}ns > 2s"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# 全ケース実行
test_small_change
test_large_change_block
test_binary_only
test_staged_empty
test_stderr_structure
test_execution_time

echo "All cases done. FAILS=$FAILS"
[ "$FAILS" -eq 0 ] || exit 1
