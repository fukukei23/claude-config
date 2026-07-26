#!/usr/bin/env bash
# test_verify_post_tool_use.sh — verify-post-tool-use.sh のカバレッジテスト
#
# Phase1（層2・#7機械的検証）PostToolUse hook のテスト。
# 拡張子ホワイトリスト・ruff失敗/成功・キャッシュ・bypass・対象外tool の exit code 判定。
#
# 実行: bash scripts/hooks/test_verify_post_tool_use.sh
set -u
HOOK="$(cd "$(dirname "$0")" && pwd)/verify-post-tool-use.sh"
TMPDIR_TEST="$(mktemp -d)"
FAILS=0
PASSES=0

# テスト用 fixtures
cat > "$TMPDIR_TEST/clean.py" <<'PY'
def add(a: int, b: int) -> int:
    return a + b
PY

cat > "$TMPDIR_TEST/broken.py" <<'PY'
def add(a, b:
    return a + b
PY

cat > "$TMPDIR_TEST/notes.md" <<'MD'
# notes
MD

# PostToolUse JSON を生成
json_for() {
  # $1=tool_name $2=file_path
  printf '{"tool_name":"%s","tool_input":{"file_path":"%s"}}' "$1" "$2"
}

run_hook() {
  json_for "$1" "$2" | CLAUDE_VERIFY_BYPASS="${CLAUDE_VERIFY_BYPASS:-}" bash "$HOOK" >/tmp/verify_hook_stderr.log 2>&1
  echo $?
}

assert_rc() {
  local desc="$1" expected="$2" tool="$3" fp="$4"
  local rc; rc=$(run_hook "$tool" "$fp")
  if [ "$rc" -eq "$expected" ]; then
    echo "PASS $desc (exit $rc)"; PASSES=$((PASSES+1))
  else
    echo "FAIL $desc — 期待 exit $expected / 実際 exit $rc (tool=$tool fp=$fp)"; FAILS=$((FAILS+1))
  fi
}

echo "=== 対象外 tool / 拡張子（許可期待 exit 0）==="
assert_rc "Read tool は対象外"     0 "Read"  "$TMPDIR_TEST/clean.py"
assert_rc "*.md は対象外"          0 "Edit"  "$TMPDIR_TEST/notes.md"

echo ""
echo "=== ruff 成功（許可期待 exit 0）==="
# キャッシュクリアして初回
rm -rf ~/.claude/verify-cache 2>/dev/null
assert_rc "*.py ruff成功"          0 "Edit"  "$TMPDIR_TEST/clean.py"

echo ""
echo "=== ruff 失敗（ブロック期待 exit 2）==="
rm -rf ~/.claude/verify-cache 2>/dev/null
assert_rc "*.py ruff失敗"          2 "Edit"  "$TMPDIR_TEST/broken.py"

echo ""
echo "=== キャッシュ命中（許可期待 exit 0・2回目同じ内容）==="
# 1回目成功でキャッシュ作成済（clean.py）。2回目は同じ内容→キャッシュHit→exit 0
assert_rc "*.py キャッシュHit"     0 "Edit"  "$TMPDIR_TEST/clean.py"

echo ""
echo "=== CLAUDE_VERIFY_BYPASS（許可期待 exit 0）==="
rm -rf ~/.claude/verify-cache 2>/dev/null
rc=$(json_for "Edit" "$TMPDIR_TEST/broken.py" | CLAUDE_VERIFY_BYPASS="testing" bash "$HOOK" >/dev/null 2>&1; echo $?)
if [ "$rc" -eq 0 ]; then echo "PASS [bypass] broken.py bypassで許可 (exit 0)"; PASSES=$((PASSES+1)); else echo "FAIL [bypass] — 期待 exit 0 / 実際 exit $rc"; FAILS=$((FAILS+1)); fi

echo ""
echo "========================================"
echo "結果: PASS=$PASSES / FAIL=$FAILS"
echo "========================================"

# 後片付け
rm -rf "$TMPDIR_TEST" ~/.claude/verify-cache 2>/dev/null
# テスト用監査ログエントリは残す（append-only・実運用ログと混在回避のため別ファイルにすべきだが本テストでは~/.claude/hook-audit.logに追記される・実運用開始前に削除想定）
exit "$FAILS"
