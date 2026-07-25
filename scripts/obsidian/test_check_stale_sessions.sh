#!/usr/bin/env bash
# test_check_stale_sessions.sh — check-stale-sessions.sh 用ユニットテスト
# フィクスチャ: 一時ディレクトリに active-sessions.md / heartbeat / handoff を作り
# 期待出力(stale判定JSON)と一致するか確認。
#
# 使い方: bash test_check_stale_sessions.sh
# 終了コード: 0=全test pass / 1=fail

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/check-stale-sessions.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASS=0; FAIL=0
fail() { echo "  ❌ FAIL: $1"; FAIL=$((FAIL+1)); }
pass() { echo "  ✅ PASS: $1"; PASS=$((PASS+1)); }

# --- フィクスチャビルダー ---
make_board() {
  # $1=path, $2=table_md
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
---
updated: 2026-07-01
tags: [ssot, 並行セッション, 競合回避]
---

# アクティブセッション

## セッション状態

> 形式説明省略

| ID | セッション | 触る共通ファイル | 方針 | 開始 | 状態 |
|----|------------|------------------|------|------|------|
$2
EOF
}

touch_hb() {
  # $1=wt4, $2=hours_ago
  local mins_ago=$(( $2 * 60 ))
  touch -d "$mins_ago minutes ago" "$WORK/heartbeat/$1"
}

touch_handoff() {
  # $1=wt4, $2=YYYY-MM-DD_HHMM_wt4.md, $3=hours_ago
  mkdir -p "$WORK/handoff"
  local mins_ago=$(( $3 * 60 ))
  touch -d "$mins_ago minutes ago" "$WORK/handoff/$2"
}

# 状態クリア（各テスト間の相互干渉防止）
reset_state() {
  rm -f "$WORK/heartbeat/"*
  rm -rf "$WORK/handoff"
  mkdir -p "$WORK/heartbeat"
}

# === テスト1: heartbeat新鮮 → 非stale ===
echo "[T1] heartbeat 新鮮(2h) → 非stale"
mkdir -p "$WORK/heartbeat"
rm -f "$WORK/heartbeat/"*
make_board "$WORK/00_SYSTEM/active-sessions.md" "| df70 | テスト1 | — | 検証 | 07-25 10:00 | 🟢 |"
touch_hb df70 2
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
[ "$cnt" = "0" ] && pass "T1" || fail "T1: expected 0, got $cnt  output=$out"

# === テスト2: heartbeat古い(13h) → stale検知 ===
echo "[T2] heartbeat 古い(13h) → stale"
rm -f "$WORK/heartbeat/"*
make_board "$WORK/00_SYSTEM/active-sessions.md" "| df70 | テスト2 | — | 検証 | 07-25 00:00 | 🟢 |"
touch_hb df70 13
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
[ "$cnt" = "1" ] && pass "T2 count" || fail "T2 count: expected 1, got $cnt  output=$out"
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d[0]['id']=='df70' and 'heartbeat' in d[0]['reason']; print('  reason ok')" \
  && pass "T2 reason/heartbeat" || fail "T2 reason/heartbeat: $out"

# === テスト3: [長時間] + 13h → 非stale（72h閾値未満） ===
echo "[T3] [長時間] + 13h → 非stale"
rm -f "$WORK/heartbeat/"*
make_board "$WORK/00_SYSTEM/active-sessions.md" "| d857 | テスト3 [長時間] | — | 検証 | 07-25 00:00 | 🟢 |"
touch_hb d857 13
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
[ "$cnt" = "0" ] && pass "T3" || fail "T3: expected 0, got $cnt  output=$out"

# === テスト4: [長時間] + 73h → stale ===
echo "[T4] [長時間] + 73h → stale"
rm -f "$WORK/heartbeat/"*
touch_hb d857 73
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
[ "$cnt" = "1" ] && pass "T4 count" || fail "T4 count: expected 1, got $cnt  output=$out"

# === テスト5: heartbeat無 + handoff 古い(15h) → stale（フォールバック） ===
echo "[T5] heartbeat無 + handoff 15h → stale(フォールバック)"
reset_state
make_board "$WORK/00_SYSTEM/active-sessions.md" "| df70 | テスト5 | — | 検証 | 07-25 00:00 | 🟢 |"
touch_handoff df70 2026-07-25_0000_df70.md 15
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
[ "$cnt" = "1" ] && pass "T5 count" || fail "T5 count: expected 1, got $cnt  output=$out"
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'handoff' in d[0]['reason']; print('  reason ok')" \
  && pass "T5 reason/handoff" || fail "T5 reason/handoff: $out"

# === テスト6: heartbeat無 + handoff無 → stale(6d3f型) ===
echo "[T6] heartbeat無 + handoff無 → stale"
rm -f "$WORK/heartbeat/"*
rm -rf "$WORK/handoff"
make_board "$WORK/00_SYSTEM/active-sessions.md" "| 6d3f | テスト6 | — | 強制終了 | 07-23 14:00 | 🟢 |"
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
[ "$cnt" = "1" ] && pass "T6 count" || fail "T6 count: expected 1, got $cnt  output=$out"
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'no_trace' in d[0]['reason']; print('  reason ok')" \
  && pass "T6 reason/no_trace" || fail "T6 reason/no_trace: $out"

# === テスト7: unkn行 → 確認不能（ID=unknでもhandoff mtimeで判定） ===
echo "[T7] unkn行 + handoff 20h → stale"
rm -f "$WORK/heartbeat/unkn"
rm -rf "$WORK/handoff"
touch_handoff unkn 2026-07-25_0000_unkn.md 20
make_board "$WORK/00_SYSTEM/active-sessions.md" "| unkn | テスト7 | — | 検証 | 07-25 10:00 | 🟢 |"
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
[ "$cnt" = "1" ] && pass "T7 count" || fail "T7 count: expected 1, got $cnt  output=$out"

# === テスト8: 複数行混在 → 該当数だけ検出 ===
echo "[T8] 3行混在(新鮮/古い/非stale)"
rm -f "$WORK/heartbeat/"*
rm -rf "$WORK/handoff"
touch_hb aaaa 1
touch_hb bbbb 100
touch_hb cccc 5
make_board "$WORK/00_SYSTEM/active-sessions.md" "| aaaa | テスト8a | — | 新 | 07-25 10:00 | 🟢 |
| bbbb | テスト8b | — | 古い | 07-25 10:00 | 🟢 |
| cccc | テスト8c | — | 新 | 07-25 10:00 | 🟢 |"
out=$("$TARGET" --json --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
cnt=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
ids=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sorted([r['id'] for r in d]))")
[ "$cnt" = "1" ] && [ "$ids" = "['bbbb']" ] && pass "T8" || fail "T8: cnt=$cnt ids=$ids"

# === テスト9: --json なし → 人間可読形式（stale有りで exit 1） ===
echo "[T9] 人間可読出力 + exit 1"
rm -f "$WORK/heartbeat/"*
touch_hb df70 100
make_board "$WORK/00_SYSTEM/active-sessions.md" "| df70 | テスト9 | — | 検証 | 07-25 00:00 | 🟢 |"
set +e
out=$("$TARGET" --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
rc=$?
set -e
[ "$rc" = "1" ] && pass "T9 exit_code" || fail "T9 exit_code: expected 1, got $rc"
echo "$out" | grep -q "⚠" && pass "T9 warn symbol" || fail "T9: no warn symbol in output: $out"

# === テスト10: stale無し → exit 0 ===
echo "[T10] stale無し → exit 0"
rm -f "$WORK/heartbeat/"*
touch_hb df70 1
make_board "$WORK/00_SYSTEM/active-sessions.md" "| df70 | テスト10 | — | 検証 | 07-25 10:00 | 🟢 |"
set +e
out=$("$TARGET" --ssot-path "$WORK" --heartbeat-dir "$WORK/heartbeat" --handoff-dir "$WORK/handoff" 2>&1)
rc=$?
set -e
[ "$rc" = "0" ] && pass "T10 exit_code" || fail "T10 exit_code: expected 0, got $rc"

# === サマリ ===
echo ""
echo "============================="
echo "PASS: $PASS / FAIL: $FAIL"
echo "============================="
[ "$FAIL" = "0" ] && exit 0 || exit 1
