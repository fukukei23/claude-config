#!/usr/bin/env bash
# test_git_suction_guard.sh — git-suction-guard.sh の8ケーステスト
# 吸着検知(git init が上位.gitを持つディレクトリで実行されようとした時)のask出力を検証
set -uo pipefail

HOOK="$HOME/.claude/scripts/hooks/git-suction-guard.sh"
TMP_BASE=""
FAILS=0

setup() {
  TMP_BASE=$(mktemp -d)
}

teardown() {
  [ -n "$TMP_BASE" ] && rm -rf "$TMP_BASE"
  TMP_BASE=""
}

# hookにJSONを流す・stdout/stderrを返す（rcはグローバルRCへ）
send_hook() {
  local cmd="$1" cwd="$2"
  OUT=$(printf '{"tool_name":"Bash","tool_input":{"command":"%s"},"cwd":"%s"}' \
        "$(printf '%s' "$cmd" | sed 's/"/\\"/g')" "$cwd" | bash "$HOOK" 2>/dev/null)
  RC=$?
}

check_ask() {
  local case_no="$1"
  if [ "$RC" -ne 0 ]; then
    echo "FAIL Case$case_no: expected exit 0 got $RC"
    FAILS=$((FAILS+1)); return
  fi
  if ! printf '%s' "$OUT" | grep -q '"permissionDecision": *"ask"'; then
    echo "FAIL Case$case_no: expected ask decision, got: $OUT"
    FAILS=$((FAILS+1))
  fi
}

check_pass() {
  local case_no="$1"
  if [ "$RC" -ne 0 ]; then
    echo "FAIL Case$case_no: expected exit 0 got $RC"
    FAILS=$((FAILS+1)); return
  fi
  if [ -n "$OUT" ]; then
    echo "FAIL Case$case_no: expected empty output, got: $OUT"
    FAILS=$((FAILS+1))
  fi
}

# Case 1: 吸着状態でのgit init → ask
test_adsorbed_init_ask() {
  setup
  mkdir -p "$TMP_BASE/parent/child"
  git init -q "$TMP_BASE/parent"
  send_hook "git init" "$TMP_BASE/parent/child"
  check_ask 1
  teardown
}

# Case 2: 正当repo直下でのgit init（reinit）→ 通過
test_own_repo_init_pass() {
  setup
  git init -q "$TMP_BASE/parent"
  send_hook "git init" "$TMP_BASE/parent"
  check_pass 2
  teardown
}

# Case 3: 上位に.gitが無い場所でのgit init → 通過
test_isolated_init_pass() {
  setup
  mkdir -p "$TMP_BASE/isolated/sub"
  send_hook "git init" "$TMP_BASE/isolated/sub"
  check_pass 3
  teardown
}

# Case 4: git以外のコマンド → 通過
test_non_git_pass() {
  setup
  mkdir -p "$TMP_BASE/parent/child"
  git init -q "$TMP_BASE/parent"
  send_hook "echo hello && ls" "$TMP_BASE/parent/child"
  check_pass 4
  teardown
}

# Case 5: cd複合コマンド（fail条件b・MiniMax#10）→ ask
test_cd_compound_ask() {
  setup
  mkdir -p "$TMP_BASE/parent/child"
  git init -q "$TMP_BASE/parent"
  send_hook "cd $TMP_BASE/parent/child && git init" "$HOME"
  check_ask 5
  teardown
}

# Case 6: git -C 指定（fail条件b派生）→ ask
test_git_c_flag_ask() {
  setup
  mkdir -p "$TMP_BASE/parent/child"
  git init -q "$TMP_BASE/parent"
  send_hook "git -C $TMP_BASE/parent/child init" "$HOME"
  check_ask 6
  teardown
}

# Case 7: --bare init → 通過（bare repoは吸着被害なし）
test_bare_init_pass() {
  setup
  mkdir -p "$TMP_BASE/parent/child"
  git init -q "$TMP_BASE/parent"
  send_hook "git init --bare $TMP_BASE/parent/child/bare.git" "$TMP_BASE/parent/child"
  check_pass 7
  teardown
}

# Case 8: 吸着状態でgit status（init以外は対象外・誤爆防止）→ 通過
test_git_status_pass() {
  setup
  mkdir -p "$TMP_BASE/parent/child"
  git init -q "$TMP_BASE/parent"
  send_hook "git status" "$TMP_BASE/parent/child"
  check_pass 8
  teardown
}

# Case 9: 不正JSON → 通過（他hookに任せる）
test_bad_json_pass() {
  setup
  OUT=$(printf 'not json' | bash "$HOOK" 2>/dev/null)
  RC=$?
  check_pass 9
  teardown
}

test_adsorbed_init_ask
test_own_repo_init_pass
test_isolated_init_pass
test_non_git_pass
test_cd_compound_ask
test_git_c_flag_ask
test_bare_init_pass
test_git_status_pass
test_bad_json_pass

echo "FAILS=$FAILS"
[ "$FAILS" -eq 0 ]
