#!/usr/bin/env bash
# test_check_ssot_search_v1_hardcoded.sh — 検出スクリプトのテスト
#
# テストケース:
#   T1: v1のみのテストファイル → exit=1（検出されること）
#   T2: v1+明示キーワードのテストファイル → exit=0（除外されること）
#   T3: 本番 obsidian-ssot で全ファイル明示済 → exit=0

set -u
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0
SCRIPT="$HOME/projects/claude-config/scripts/obsidian/check-ssot-search-v1-hardcoded.sh"

assert_exit() {
  local desc="$1" expected="$2" actual="$3"
  TESTS_TOTAL=$((TESTS_TOTAL + 1))
  if [ "$expected" = "$actual" ]; then
    echo "  ✅ $desc (exit=$actual)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "  ❌ $desc: expected exit=$expected got exit=$actual"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

# --- T1: v1 のみ（明示なし）→ exit=1 ---
echo "T1: v1 のみ（明示なし）"
TMPDIR=$(mktemp -d /tmp/check-ssot-v1-T1-XXXXXX)
cat > "$TMPDIR/naive.md" <<EOF
# v1 のみのテスト手順書

このドキュメントは v1 のみの説明。

\`\`\`bash
python3 ~/projects/claude-config/scripts/ssot/search.py "クエリ"
\`\`\`
EOF
SSOT_DIR="$TMPDIR" bash "$SCRIPT" >/dev/null 2>&1
assert_exit "T1: v1のみは検出される" "1" "$?"
rm -rf "$TMPDIR"

# --- T2: v1 + 明示キーワード → exit=0 ---
echo ""
echo "T2: v1 + 明示キーワード"
TMPDIR=$(mktemp -d /tmp/check-ssot-v1-T2-XXXXXX)
cat > "$TMPDIR/explicit.md" <<EOF
# v1 字句完全一致用として明示

v1 は ripgrep 前置フィルタ。型番・エラー文の字句完全一致用。

\`\`\`bash
python3 ~/projects/claude-config/scripts/ssot/search.py "クエリ"
\`\`\`
EOF
SSOT_DIR="$TMPDIR" bash "$SCRIPT" >/dev/null 2>&1
assert_exit "T2: 明示キーワード付きは除外される" "0" "$?"
rm -rf "$TMPDIR"

# --- T3: 本番 obsidian-ssot → exit=0 ---
echo ""
echo "T3: 本番 obsidian-ssot"
bash "$SCRIPT" >/dev/null 2>&1
assert_exit "T3: 本番は全ファイル明示済" "0" "$?"

echo ""
echo "=== 結果: ${TESTS_PASSED}/${TESTS_TOTAL} PASS (FAIL: ${TESTS_FAILED}) ==="
[ "$TESTS_FAILED" -eq 0 ] && exit 0 || exit 1
