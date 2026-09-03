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

# Case 2: 修正50行（M・L279①により新規Aは除外されたため M で検証）→ exit 2
test_large_change_block() {
  setup
  seq 1 50 > big.txt
  git add big.txt
  git commit -q -m init 2>/dev/null
  seq 51 100 >> big.txt
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

# Case 5: stderr構造（block時に5項目含有・M-statusで発火）
test_stderr_structure() {
  setup
  seq 1 50 > big.txt
  git add big.txt
  git commit -q -m init 2>/dev/null
  seq 51 100 >> big.txt
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
  git commit -q -m init 2>/dev/null
  seq 51 100 >> big.txt
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
  git commit -q -m init 2>/dev/null
  seq 51 100 >> big.txt
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

# Case 14: 空白+tool_inputネスト形(Windows Desktop版実入力形式・08-22実測) → exit 2（旧: 沈黙exit 0）
test_spaced_nested_input() {
  setup
  seq 1 50 > big.txt
  git add big.txt
  git commit -q -m init 2>/dev/null
  seq 51 100 >> big.txt
  git add big.txt
  local rc
  printf '{"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}}' | bash "$HOOK" 2>/dev/null
  rc=$?
  if [ "$rc" -ne 2 ]; then
    echo "FAIL Case14: expected exit 2 (spaced nested input) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

test_spaced_nested_input

# === 宣言ベース判定（v3・2026-08-29・Case15-21） ===
# env分離: PATHS_JSON_FILE/HEARTBEAT_DIR/PATHS_BOARD_FILE でテスト用隔离
PATHS_ENV() {
  printf '%s\n' "$1" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); json.dump(d, open('$2','w'), indent=2)"
}

# Case 15: 他タブ活性宣言一致+自タブ宣言外 → enforce時 exit 2
test_other_active_block() {
  setup
  echo hello > f.txt; git add f.txt
  local pj hb
  pj=$(mktemp -d); hb=$(mktemp -d)
  PATHS_ENV "{\"entries\":{\"othr\":[\"$TMP_REPO/f.txt\"]}}" "$pj/paths.json"
  : > "$hb/othr"  # 活性heartbeat
  local rc
  rc=$( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m t"}}' \
    | env WT_SESSION=zzzz PATHS_JSON_FILE="$pj/paths.json" HEARTBEAT_DIR="$hb" PATHS_BOARD_FILE=/nonexistent \
      PATHS_BLOCK_MODE=enforce DRY_RUN=1 bash "$HOOK" >/dev/null 2>&1; echo $? )
  rm -rf "$pj" "$hb"
  if [ "$rc" -ne 2 ]; then
    echo "FAIL Case15: expected exit 2 (other active declared) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 16: 自タブ宣言内+過大diff(50行) → blockされない(exit 0・理由付きwarn)
test_self_declared_free() {
  setup
  seq 1 50 > big.txt; git add big.txt
  local pj hb
  pj=$(mktemp -d); hb=$(mktemp -d)
  PATHS_ENV "{\"entries\":{\"zzzz\":[\"$TMP_REPO/big.txt\"]}}" "$pj/paths.json"
  local rc out
  out=$( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m t"}}' \
    | env WT_SESSION=zzzzzzzz PATHS_JSON_FILE="$pj/paths.json" HEARTBEAT_DIR="$hb" PATHS_BOARD_FILE=/nonexistent \
      PATHS_BLOCK_MODE=enforce DRY_RUN=1 bash "$HOOK" 2>&1; echo "rc=$?" )
  rc=${out##*rc=}
  rm -rf "$pj" "$hb"
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case16: expected exit 0 (self declared) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 17: 未宣言+delta±20超 → enforce時 exit 2
test_undeclared_block() {
  setup
  seq 1 25 > u.txt; git add u.txt
  local pj hb
  pj=$(mktemp -d); hb=$(mktemp -d)
  PATHS_ENV '{"entries":{}}' "$pj/paths.json"
  local rc
  rc=$( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m t"}}' \
    | env WT_SESSION=zzzz PATHS_JSON_FILE="$pj/paths.json" HEARTBEAT_DIR="$hb" PATHS_BOARD_FILE=/nonexistent \
      PATHS_BLOCK_MODE=enforce DRY_RUN=1 bash "$HOOK" >/dev/null 2>&1; echo $? )
  rm -rf "$pj" "$hb"
  if [ "$rc" -ne 2 ]; then
    echo "FAIL Case17: expected exit 2 (undeclared +25 lines) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 18: paths.json破損 → DEGRADEDでexit 0(通す)+警告
test_paths_json_broken() {
  setup
  echo x > f.txt; git add f.txt
  local pj hb rc out
  pj=$(mktemp -d); hb=$(mktemp -d)
  printf 'THIS IS NOT JSON{{{}}}' > "$pj/paths.json"
  out=$( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m t"}}' \
    | env WT_SESSION=zzzz PATHS_JSON_FILE="$pj/paths.json" HEARTBEAT_DIR="$hb" PATHS_BOARD_FILE=/nonexistent \
      PATHS_BLOCK_MODE=enforce bash "$HOOK" 2>&1; echo "rc=$?" )
  rc=${out##*rc=}
  rm -rf "$pj" "$hb"
  if [ "$rc" -ne 0 ] || ! echo "$out" | grep -q 'DEGRADED'; then
    echo "FAIL Case18: expected exit 0 + DEGRADED warn got rc=$rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 19: stale宣言(12h超) → warnのみ・enforceでもblockしない
test_stale_declared_warn() {
  setup
  echo hello > f.txt; git add f.txt
  local pj hb rc out
  pj=$(mktemp -d); hb=$(mktemp -d)
  PATHS_ENV "{\"entries\":{\"othr\":[\"$TMP_REPO/f.txt\"]}}" "$pj/paths.json"
  touch -d '2 days ago' "$hb/othr"  # stale
  out=$( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m t"}}' \
    | env WT_SESSION=zzzz PATHS_JSON_FILE="$pj/paths.json" HEARTBEAT_DIR="$hb" PATHS_BOARD_FILE=/nonexistent \
      PATHS_BLOCK_MODE=enforce DRY_RUN=1 bash "$HOOK" 2>&1; echo "rc=$?" )
  rc=${out##*rc=}
  rm -rf "$pj" "$hb"
  if [ "$rc" -ne 0 ] || ! echo "$out" | grep -q 'stale'; then
    echo "FAIL Case19: expected exit 0 + stale warn got rc=$rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 20: 1000ファイル大repoで実行時間2秒以内
test_perf_1000_files() {
  setup
  local i pj hb start end elapsed_ns
  pj=$(mktemp -d); hb=$(mktemp -d)
  PATHS_ENV "{\"entries\":{\"zzzz\":[\"$TMP_REPO/f0001.txt\"]}}" "$pj/paths.json"
  for i in $(seq -w 1 1000); do echo "line$i" > "f$i.txt"; done
  git add f*.txt
  start=$(date +%s%N)
  ( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m t"}}' \
    | env WT_SESSION=zzzzzzzz PATHS_JSON_FILE="$pj/paths.json" HEARTBEAT_DIR="$hb" PATHS_BOARD_FILE=/nonexistent \
      PATHS_BLOCK_MODE=shadow DRY_RUN=1 bash "$HOOK" >/dev/null 2>&1 )
  end=$(date +%s%N)
  elapsed_ns=$(( end - start ))
  rm -rf "$pj" "$hb"
  if [ "$elapsed_ns" -gt 2000000000 ]; then
    echo "FAIL Case20: elapsed ${elapsed_ns}ns > 2s (1000 files)"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 21: 書込ヘルパー並列5本でpaths.json破損ゼロ・全エントリ反映
test_helper_parallel() {
  local pj i ok
  pj=$(mktemp -d)
  export PATHS_JSON_FILE="$pj/paths.json"
  for i in 1 2 3 4 5; do
    python3 "$HOME/projects/claude-config/scripts/session/paths-json-update.py" "tab$i" "$pj/f$i.txt" >/dev/null 2>&1 &
  done
  wait
  ok=$(python3 -c "
import json, os
d = json.load(open('$pj/paths.json'))
e = d.get('entries', {})
print(1 if all(f'tab{i}' in e for i in range(1, 6)) else 0)
" 2>/dev/null || echo 0)
  unset PATHS_JSON_FILE
  rm -rf "$pj"
  if [ "$ok" -ne 1 ]; then
    echo "FAIL Case21: parallel writes lost entries or JSON broken"
    FAILS=$((FAILS+1))
  fi
}

test_other_active_block
test_self_declared_free
test_undeclared_block
test_paths_json_broken
test_stale_declared_warn
test_perf_1000_files
test_helper_parallel

# === L279 運用阻害3件修正（2026-09-04・Case 22-26） ===

# Case 22: 新規ファイル(status A)50行・パス指定なし → exit 0（L279①: A新規は意図的追加なのでblockしない）
test_new_file_not_blocked() {
  setup
  seq 1 50 > new.txt
  git add new.txt
  send_hook "git commit -m test"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case22: expected exit 0 (new A file exempt) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 23: 他セッション大量M(big.txt 50行)がstage + 自small(own.txt 11行M)、`git commit -- own.txt` → exit 0（L279②: pathspec限定）
test_pathspec_limited() {
  setup
  echo base > big.txt; echo own > own.txt
  git add big.txt own.txt
  git commit -q -m init 2>/dev/null
  seq 1 50 >> big.txt      # 他セッション分（stageに残す）
  git add big.txt
  seq 1 11 >> own.txt      # 自分の小変更
  git add own.txt
  send_hook "git commit -m test -- own.txt"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case23: expected exit 0 (pathspec limited) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 24: pathspec指定でも自分のパス自体が大量M(50行) → exit 2（限定は巻き込み除外であって大量変更の無罪化ではない）
test_pathspec_own_large_still_blocked() {
  setup
  echo own > own.txt
  git add own.txt
  git commit -q -m init 2>/dev/null
  seq 1 50 >> own.txt
  git add own.txt
  send_hook "git commit -m test -- own.txt"
  local rc=$?
  if [ "$rc" -ne 2 ]; then
    echo "FAIL Case24: expected exit 2 (own path large M) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 25: block時のREQUIRED_ACTIONが実行可能手順（paths-json-update.py宣言追加 と restore --staged の両方を案内）
test_required_action_executable() {
  setup
  echo base > med.txt
  git add med.txt
  git commit -q -m init 2>/dev/null
  seq 1 50 >> med.txt
  git add med.txt
  local stderr_out
  stderr_out=$(printf '{"tool_name":"Bash","command":"git commit -m test"}' | bash "$HOOK" 2>&1 1>/dev/null)
  local missing=0
  echo "$stderr_out" | grep -q "paths-json-update.py" || missing=$((missing+1))
  echo "$stderr_out" | grep -q "restore --staged" || missing=$((missing+1))
  if [ "$missing" -ne 0 ]; then
    echo "FAIL Case25: $missing executable steps missing in REQUIRED_ACTION"
    FAILS=$((FAILS+1))
  fi
  teardown
}

# Case 26: 自タブ宣言したM-file 50行・DRY_RUNなし → exit 0（宣言追加が実際の脱出経路として機能=L279①の解消）
test_self_declared_m_no_dryrun() {
  setup
  echo base > big.txt
  git add big.txt
  git commit -q -m init 2>/dev/null
  seq 1 50 >> big.txt
  git add big.txt
  local pj hb
  pj=$(mktemp -d); hb=$(mktemp -d)
  PATHS_ENV "{\"entries\":{\"zzzz\":[\"$TMP_REPO/big.txt\"]}}" "$pj/paths.json"
  local rc out
  out=$( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m t"}}' \
    | env WT_SESSION=zzzz PATHS_JSON_FILE="$pj/paths.json" HEARTBEAT_DIR="$hb" PATHS_BOARD_FILE=/nonexistent \
      PATHS_BLOCK_MODE=shadow bash "$HOOK" 2>&1; echo "rc=$?" )
  rc=${out##*rc=}
  rm -rf "$pj" "$hb"
  if [ "$rc" -ne 0 ] || ! echo "$out" | grep -q '過大diff'; then
    echo "FAIL Case26: expected exit 0 + self warn (self declared M, no DRY_RUN) got rc=$rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

test_new_file_not_blocked
test_pathspec_limited
test_pathspec_own_large_still_blocked
test_required_action_executable
test_self_declared_m_no_dryrun

# Case 27: コマンド文字列内のインライン DRY_RUN=1 が効く（hook別processでも案内どおり脱出可能・L279①）
test_inline_dry_run() {
  setup
  echo base > big.txt
  git add big.txt
  git commit -q -m init 2>/dev/null
  seq 1 50 >> big.txt
  git add big.txt
  send_hook "DRY_RUN=1 git commit -m test"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAIL Case27: expected exit 0 (inline DRY_RUN=1 honored) got $rc"
    FAILS=$((FAILS+1))
  fi
  teardown
}

test_inline_dry_run

echo "All cases done. FAILS=$FAILS"
[ "$FAILS" -eq 0 ] || exit 1
