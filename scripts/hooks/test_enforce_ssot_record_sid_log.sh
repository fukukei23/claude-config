#!/bin/bash
# test_enforce_ssot_record_sid_log.sh — enforce-ssot-record.sh のSID観測ログのテスト
#
# 目的（2026-08-31）: 2026-07-08記録 L70-71 の残課題
#   「稼働後ログで SESSION_ID 取得実績を蓄積」「globフォールバックが頻発するなら別経路で担保」
#   を判定するための実測ログが、hook本体を壊さずに記録されることを検証する。
#
# 隔離方針: STATE_DIR は $HOME 由来のため HOME を差し替えるだけで本番 state を汚さない
#           （hook 側に新しい env 変数を足さない = フラグ判定の外部差し替え面を増やさない）

set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/enforce-ssot-record.sh"
PASS=0
FAIL=0

DEC_PATH='/home/yn4416/projects/obsidian-ssot/01_DECISIONS/test/dummy.md'
OUT_PATH='/home/yn4416/projects/obsidian-ssot/10_DAILY/2026-08-31.md'

setup_home() {
    TESTHOME=$(mktemp -d)
    mkdir -p "$TESTHOME/.claude/state"
}

teardown_home() {
    [ -n "${TESTHOME:-}" ] && chmod -R u+w "$TESTHOME" 2>/dev/null
    [ -n "${TESTHOME:-}" ] && rm -rf "$TESTHOME"
}

# run_hook <file_path> → 標準出力に "RC=<終了コード>"
run_hook() {
    printf '{"file_path": "%s"}' "$1" \
        | HOME="$TESTHOME" CLAUDE_CODE_SESSION_ID="${SID_ENV:-}" bash "$HOOK" >/dev/null 2>&1
    echo "RC=$?"
}

check() {
    local name="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo "  ✅ $name"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name — 期待:[$expected] 実際:[$actual]"
        FAIL=$((FAIL + 1))
    fi
}

LOG_REL=".claude/state/ssot-record-sid-observe.jsonl"

echo "T1: SIDあり・フラグなし → ブロック + sid_present=true/branch=exact を記録"
setup_home
SID_ENV="test-sid-0001"
check "T1 終了コード" "RC=2" "$(run_hook "$DEC_PATH")"
check "T1 ログ行数" "1" "$(grep -c '' "$TESTHOME/$LOG_REL" 2>/dev/null || echo 0)"
check "T1 sid_present" "1" "$(grep -c '"sid_present":true' "$TESTHOME/$LOG_REL" 2>/dev/null || echo 0)"
check "T1 branch" "1" "$(grep -c '"branch":"exact"' "$TESTHOME/$LOG_REL" 2>/dev/null || echo 0)"
check "T1 decision" "1" "$(grep -c '"decision":"block"' "$TESTHOME/$LOG_REL" 2>/dev/null || echo 0)"
teardown_home

echo "T2: SIDなし・生きたフラグあり → 許可 + branch=glob_fallback を記録（観測したい経路）"
setup_home
SID_ENV=""
touch "$TESTHOME/.claude/state/ssot-record-active-someone"
check "T2 終了コード" "RC=0" "$(run_hook "$DEC_PATH")"
check "T2 branch" "1" "$(grep -c '"branch":"glob_fallback"' "$TESTHOME/$LOG_REL" 2>/dev/null || echo 0)"
check "T2 sid_present" "1" "$(grep -c '"sid_present":false' "$TESTHOME/$LOG_REL" 2>/dev/null || echo 0)"
check "T2 decision" "1" "$(grep -c '"decision":"allow"' "$TESTHOME/$LOG_REL" 2>/dev/null || echo 0)"
teardown_home

echo "T3: 01_DECISIONS 配下以外 → 許可 + ログを書かない（ログ肥大の防止）"
setup_home
SID_ENV="test-sid-0003"
check "T3 終了コード" "RC=0" "$(run_hook "$OUT_PATH")"
check "T3 ログ未作成" "absent" "$([ -e "$TESTHOME/$LOG_REL" ] && echo present || echo absent)"
teardown_home

echo "T4: [fail条件] ログ書込不能でも hook 本体は正常に判定する（機能不全に落ちない）"
setup_home
SID_ENV="test-sid-0004"
chmod 500 "$TESTHOME/.claude/state"   # 追記不可にする
check "T4 終了コード（ブロック維持）" "RC=2" "$(run_hook "$DEC_PATH")"
check "T4 ログ未作成" "absent" "$([ -e "$TESTHOME/$LOG_REL" ] && echo present || echo absent)"
teardown_home

echo ""
echo "結果: PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
    exit 0
else
    exit 1
fi
