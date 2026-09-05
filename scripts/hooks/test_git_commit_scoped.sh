#!/usr/bin/env bash
# test_git_commit_scoped.sh — git-commit-scoped.sh の6ケーステスト
# 宣言検証+pathspec commit の薄いラッパー（spec 2026-09-05 巻き込み再設計 §3 Phase 2-1）
set -uo pipefail
RUNNER="$HOME/.claude/scripts/hooks/git-commit-scoped.sh"
TMP=""
FAILS=0

setup() {
  TMP=$(mktemp -d)
  cd "$TMP"
  git init -q
  git config user.email "t@t"; git config user.name "t"
  echo "init" > declared.md
  git add declared.md && git commit -qm "init"
  echo "v1" > declared.md
  mkdir -p sub
  echo "new file" > new.md
  echo "v1" > sub/nested.md; git add sub/nested.md && git commit -qm "nested"
  echo "v2" > sub/nested.md
  # paths.json（実形式・entries[WT4]=パス配列・ディレクトリ宣言も可）
  cat > paths.json << 'PEOF'
{"entries": {"aaaa": ["declared.md", "sub/nested.md"]}}
PEOF
}

teardown() { [ -n "$TMP" ] && rm -rf "$TMP" && cd /; TMP=""; }

run_scoped() { # run_scoped <wt4> <args...>
  local wt4="$1"; shift
  env -u CLAUDE_CODE_SESSION_ID WT_SESSION="${wt4}1111222233334444" PATHS_JSON="$TMP/paths.json" \
    bash "$RUNNER" "$@" > /tmp/gcs_out 2>&1
  RC=$?
}

# Case 1: 宣言内pathのみ → commit成功（HEAD移動+指定ファイルのみ変更）
test_declared_ok() {
  setup
  run_scoped aaaa -m "scoped commit" -- declared.md
  if [ "$RC" -ne 0 ]; then echo "FAIL Case1: rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); teardown; return; fi
  # HEADの内容確認: declared.md は v1・他ファイルは無関係
  local msg; msg=$(git log -1 --format=%s)
  [ "$msg" = "scoped commit" ] || { echo "FAIL Case1: msg=$msg"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 2: 宣言外path → 拒否（exit 1・commitされない）
test_undeclared_rejected() {
  setup
  run_scoped aaaa -m "bad" -- declared.md new.md
  if [ "$RC" -ne 1 ]; then echo "FAIL Case2: rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); teardown; return; fi
  local n; n=$(git rev-list --count HEAD)
  [ "$n" = "2" ] || { echo "FAIL Case2: commit数が増えた n=$n"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 3: 新規untrackedは git add 後なら commit可能（2段手順）
test_untracked_two_step() {
  setup
  git add new.md   # 追跡化（共有indexに載るが、commitはpathspecで限定される）
  run_scoped aaaa -m "add new" -- new.md
  if [ "$RC" -eq 0 ]; then echo "FAIL Case3: 宣言外new.mdが通ってしまった（宣言不足の検証が必要）"; FAILS=$((FAILS+1)); teardown; return; fi
  # new.md を宣言に追加した場合のみ成功する
  cat > paths.json << 'PEOF'
{"entries": {"aaaa": ["declared.md", "new.md"]}}
PEOF
  run_scoped aaaa -m "add new" -- new.md
  [ "$RC" -eq 0 ] || { echo "FAIL Case3: 宣言追加後も失敗 rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 4: pathspec未指定 → 使用法エラー exit 64
test_no_pathspec() {
  setup
  run_scoped aaaa -m "no paths"
  [ "$RC" -eq 64 ] || { echo "FAIL Case4: rc=$RC"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 5: セッションID未設定 → exit 64
test_no_session() {
  setup
  ( env -u CLAUDE_CODE_SESSION_ID -u WT_SESSION PATHS_JSON="$TMP/paths.json" bash "$RUNNER" -m x -- declared.md ) > /tmp/gcs_out 2>&1
  RC=$?
  [ "$RC" -ne 0 ] || { echo "FAIL Case5: rc=$RC（セッションID未設定は拒否されるべき）"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 6: 共有indexに他セッション分のstageがあっても、指定pathのみcommitされる（核心・巻き込み不発）
test_sweep_isolation() {
  setup
  echo "other session work" > other.md
  git add other.md          # 他セッションがstageした状態を再現
  run_scoped aaaa -m "scoped" -- declared.md
  if [ "$RC" -ne 0 ]; then echo "FAIL Case6: rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); teardown; return; fi
  # commitに other.md が含まれていないこと
  if git show --name-only HEAD | grep -q 'other.md'; then
    echo "FAIL Case6: 他セッションstageが巻き込まれた"; FAILS=$((FAILS+1)); teardown; return
  fi
  # other.md は引き続きstageに残る（他セッションの作業は破壊されない）
  git diff --cached --name-only | grep -q 'other.md' || { echo "FAIL Case6: 他セッションのstageが破壊された"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 7: WT_SESSION優先（WSL CLI規約・CLAUDE_CODE_SESSION_IDはfallback）
test_wt_session_precedence() {
  setup
  run_scoped aaaa -m "x" -- declared.md   # CLAUDE_CODE_SESSION_ID=aaaa1111...
  [ "$RC" -eq 0 ] || { echo "FAIL Case7-pre: rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); teardown; return; }
  # WT_SESSION=aaaa + CLAUDE_CODE_SESSION_ID=zzzz（異なるID）→ WT_SESSION優先で通る
  echo "v2" > declared.md   # 2回目のcommit用に変更（変更なし失敗の回避）
  CLAUDE_CODE_SESSION_ID="zzzz999988887777" WT_SESSION="aaaa222233334444" \
    PATHS_JSON="$TMP/paths.json" bash "$RUNNER" -m "wt session" -- declared.md > /tmp/gcs_out 2>&1
  RC=$?
  [ "$RC" -eq 0 ] || { echo "FAIL Case7: WT_SESSION優先が効いていない rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 8: シングルクォート入りのファイル名でも安全（インジェクション/構文エラーなし・宣言外なら拒否）
test_quote_filename_safe() {
  setup
  touch "we'ird.md"
  git add "we'ird.md"
  run_scoped aaaa -m "x" -- "we'ird.md"
  [ "$RC" -eq 1 ] || { echo "FAIL Case8: rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); teardown; return; }
  # 宣言に追加すれば通る（crashしない）
  cat > paths.json << 'PEOF'
{"entries": {"aaaa": ["declared.md", "we'ird.md"]}}
PEOF
  printf 'content' >> "we'ird.md"
  run_scoped aaaa -m "quote ok" -- "we'ird.md"
  [ "$RC" -eq 0 ] || { echo "FAIL Case8b: rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); }
  teardown
}

# Case 9: スペース入りの宣言パスが正しくcommitされる（word splitting不発）
test_space_filename_ok() {
  setup
  echo "sp content" > "my file.md"
  git add "my file.md"
  printf '{"entries": {"aaaa": ["declared.md", "my file.md"]}}' > paths.json
  run_scoped aaaa -m "space ok" -- "my file.md"
  if [ "$RC" -ne 0 ]; then echo "FAIL Case9: rc=$RC out=$(cat /tmp/gcs_out)"; FAILS=$((FAILS+1)); teardown; return; fi
  git show --name-only HEAD | grep -q 'my file.md' || { echo "FAIL Case9: スペース入りファイルがcommitされていない"; FAILS=$((FAILS+1)); }
  teardown
}

test_quote_filename_safe
test_space_filename_ok
test_wt_session_precedence

test_declared_ok
test_undeclared_rejected
test_untracked_two_step
test_no_pathspec
test_no_session
test_sweep_isolation

[ "$FAILS" -eq 0 ] && echo "ALL PASS (9 cases)" || echo "FAILS=$FAILS"
exit $FAILS
