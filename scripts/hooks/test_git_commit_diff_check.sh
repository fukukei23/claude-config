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

# === 観測ロガー(F案・spec §1.6) ===
# Case 7: WARN時ログ追記
test_warn_log() {
  setup
  export GIT_COMMIT_DIFF_CHECK_LOG="$TMP_REPO/test.log"
  seq 1 15 > med.txt
  git add med.txt
  send_hook "git commit -m test" >/dev/null 2>&1
  if [ ! -s "$GIT_COMMIT_DIFF_CHECK_LOG" ]; then
    echo "FAIL Case7: log not written on WARN"
    FAILS=$((FAILS+1))
  fi
  unset GIT_COMMIT_DIFF_CHECK_LOG
  teardown
}

# Case 8: ログ書込失敗時fallback（hookはexit 0維持・doubt-driven #4）
test_log_fallback() {
  setup
  export GIT_COMMIT_DIFF_CHECK_LOG="/nonexistent_dir_xyz/cannot/write.log"
  seq 1 15 > med.txt
  git add med.txt
  send_hook "git commit -m test" 2>/dev/null
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case8: expected exit 0 on log write failure got $rc"
    FAILS=$((FAILS+1))
  fi
  unset GIT_COMMIT_DIFF_CHECK_LOG
  teardown
}

# Case 9: rotation（1MB超で切捨め・doubt-driven #10 容量枯渇対策）
test_log_rotation() {
  setup
  export GIT_COMMIT_DIFF_CHECK_LOG="$TMP_REPO/test.log"
  mkdir -p "$(dirname "$GIT_COMMIT_DIFF_CHECK_LOG")"
  head -c 1572864 /dev/zero | tr '\0' 'x' > "$GIT_COMMIT_DIFF_CHECK_LOG"
  seq 1 15 > med.txt
  git add med.txt
  send_hook "git commit -m test" >/dev/null 2>&1
  local sz
  sz=$(stat -c%s "$GIT_COMMIT_DIFF_CHECK_LOG" 2>/dev/null || echo 0)
  if [ "$sz" -gt 1048576 ]; then
    echo "FAIL Case9: log not rotated, size=$sz"
    FAILS=$((FAILS+1))
  fi
  unset GIT_COMMIT_DIFF_CHECK_LOG
  teardown
}

# Case 10: status(A/M)記録（doubt-driven #7 正規/非正規タグ基盤）
test_log_status() {
  setup
  export GIT_COMMIT_DIFF_CHECK_LOG="$TMP_REPO/test.log"
  echo "original" > exist.txt
  git add exist.txt
  git commit -q -m init 2>/dev/null
  seq 1 15 >> exist.txt
  git add exist.txt
  send_hook "git commit -m test" >/dev/null 2>&1
  if ! grep -q "status=M" "$GIT_COMMIT_DIFF_CHECK_LOG" 2>/dev/null; then
    echo "FAIL Case10: status=M not logged"
    FAILS=$((FAILS+1))
  fi
  unset GIT_COMMIT_DIFF_CHECK_LOG
  teardown
}

test_warn_log
test_log_fallback
test_log_rotation
test_log_status

# === cwd対応改善（バックログL260①・2026-08-29） ===
# Case 11: git -C <repo> commit 形式・hookのcwdは対象repo外 → exit 2（旧: 見逃し exit 0）
test_git_dash_c() {
  setup
  seq 1 50 > big.txt
  git add big.txt
  local outer
  outer=$(mktemp -d)
  ( cd "$outer" && send_hook "git -C $TMP_REPO commit -m test" )
  local rc=$?
  rm -rf "$outer"
  if [ "$rc" -ne 2 ]; then
    echo "FAIL Case11: expected exit 2 (git -C detection) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 12: cd <repo> && git commit 形式・hookのcwdは対象repo外 → exit 2
test_cd_form() {
  setup
  seq 1 50 > big.txt
  git add big.txt
  local outer
  outer=$(mktemp -d)
  ( cd "$outer" && send_hook "cd $TMP_REPO && git commit -m test" )
  local rc=$?
  rm -rf "$outer"
  if [ "$rc" -ne 2 ]; then
    echo "FAIL Case12: expected exit 2 (cd detection) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 13: cd後に相対git -C無し・対象repoのstagedが空 → exit 0（誤検知なし回帰）
test_cd_staged_empty() {
  setup
  local outer
  outer=$(mktemp -d)
  ( cd "$outer" && send_hook "cd $TMP_REPO && git commit -m test" )
  local rc=$?
  rm -rf "$outer"
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case13: expected exit 0 (cd + staged empty) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

test_git_dash_c
test_cd_form
test_cd_staged_empty

echo "All cases done. FAILS=$FAILS"
[ "$FAILS" -eq 0 ] || exit 1
