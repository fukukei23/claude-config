#!/usr/bin/env bash
# scripts/auto-dev/tests/test_daily_triage_stale_lock.sh
# daily-triage.sh 残留プロセス対策（2026-08-17・バックログL170）のユニットテスト。
# ①若年ホルダー→スキップ ②staleホルダー→強制解除+再取得 ③保持者特定不能→スキップ
# ④全体タイムアウト二重がけ（rc=124） を検証。python実体・外部APIには依存しない。
# 注意: Case2はホルダー起動後 sleep 1.5 を入れること（STALE_SECONDS=1 に対し
#       etimes=0 の若年ホルダーだと若年skip経路に入りrescue経路を検証できない）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$BASH_SOURCE[0]}")" && pwd)"
TRIAGE="$SCRIPT_DIR/../daily-triage.sh"

TMP="$(mktemp -d)"
cleanup() {
  [ -n "${HOLDER_PID:-}" ] && kill "${HOLDER_PID}" 2>/dev/null || true
  rm -rf "$TMP" 2>/dev/null || true
}
trap cleanup EXIT
LOCK="$TMP/daily-triage.lock"
LOG="$TMP/daily-triage-rescue.log"

# ホルダー起動: ロックを保持し自分のPIDをロックファイルに書いて sleep（本番の残留を模擬）
start_holder() {
  DAILY_TRIAGE_LOCK_FILE="$LOCK" bash -c '
    exec 9>>"$DAILY_TRIAGE_LOCK_FILE"
    flock -n 9 || exit 9
    echo $$ > "$DAILY_TRIAGE_LOCK_FILE"
    # 9>&- でsleepにFD 9を継承させない（継承するとホルダーkill後もorphan sleepが
    # ロックを掴み続け、次Caseのホルダー起動をflock失敗させる・2026-08-17実測）
    sleep 300 9>&-
  ' &
  HOLDER_PID=$!
  sleep 0.3
  kill -0 "$HOLDER_PID" || { echo "  ✗ ホルダー起動失敗（flock競合残存?) holder=$HOLDER_PID"; return 1; }
}
kill_holder() {
  kill "${HOLDER_PID:-}" 2>/dev/null || true
  wait "${HOLDER_PID:-}" 2>/dev/null || true
  sleep 0.2
}

pass=0; fail=0
check() {  # check <名前> <条件コマンド>
  local name="$1"; shift
  if "$@"; then echo "  ✓ $name"; pass=$((pass+1))
  else echo "  ✗ $name"; fail=$((fail+1)); fi
}

echo "== Case 1: 若年ホルダー（etime < STALE_SECONDS）→ スキップ・ホルダー生存 =="
start_holder
OUT1="$(DAILY_TRIAGE_LOCK_FILE="$LOCK" DAILY_TRIAGE_RESCUE_LOG="$LOG" \
  DAILY_TRIAGE_STALE_SECONDS=3600 DAILY_TRIAGE_LOCK_TEST_ONLY=1 bash "$TRIAGE" 2>&1 || true)"
check "スキップメッセージ" grep -q "スキップします" <<<"$OUT1"
check "ホルダーは殺されない" bash -c "kill -0 $HOLDER_PID 2>/dev/null"
check "rescueログは空（誤発動なし）" test ! -s "$LOG"
kill_holder

echo "== Case 2: staleホルダー（etime >= STALE_SECONDS）→ 強制解除+再取得 =="
start_holder
sleep 1.5  # ホルダーをSTALE_SECONDS(=1s)超えまで老化させる
OUT2="$(DAILY_TRIAGE_LOCK_FILE="$LOCK" DAILY_TRIAGE_RESCUE_LOG="$LOG" \
  DAILY_TRIAGE_STALE_SECONDS=1 DAILY_TRIAGE_LOCK_TEST_ONLY=1 bash "$TRIAGE" 2>&1 || true)"
sleep 0.5
check "強制解除ログ(stale検知)" grep -q "STALE検知" "$LOG"
check "強制解除ログ(完了)" grep -q "強制解除完了" "$LOG"
check "再取得してlock-test modeで終了" grep -q "lock-test mode" <<<"$OUT2"
check "ホルダーは停止済み" bash -c "! kill -0 $HOLDER_PID 2>/dev/null"
kill_holder

echo "== Case 3: 保持者PID特定不能（ロックファイル空）→ スキップ・ログ記録 =="
rm -f "$LOG"
start_holder
kill -STOP "$HOLDER_PID" 2>/dev/null || true  # ロックは保持したまま応答不能に
: > "$LOCK"                                    # PID記録を欠損状態にする
OUT3="$(DAILY_TRIAGE_LOCK_FILE="$LOCK" DAILY_TRIAGE_RESCUE_LOG="$LOG" \
  DAILY_TRIAGE_STALE_SECONDS=1 DAILY_TRIAGE_LOCK_TEST_ONLY=1 bash "$TRIAGE" 2>&1 || true)"
kill -CONT "$HOLDER_PID" 2>/dev/null || true
check "スキップ(特定不能)" grep -q "保持者PID特定不能" <<<"$OUT3"
check "SKIPログ記録" grep -q "SKIP 保持者特定不能" "$LOG"
kill_holder

echo "== Case 4: 全体タイムアウト二重がけ（rc=124・SIGKILL追撃） =="
rm -f "$LOCK" "$LOG"
RC4=0
DAILY_TRIAGE_LOCK_FILE="$LOCK" DAILY_TRIAGE_RESCUE_LOG="$LOG" \
  DAILY_TRIAGE_PY_TIMEOUT=0.1 bash "$TRIAGE" --collect-only >/dev/null 2>&1 || RC4=$?
check "rc=124 (シェル側timeout)" test "$RC4" -eq 124
check "TIMEOUTログ記録" grep -q "TIMEOUT" "$LOG"

echo
echo "結果: pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
