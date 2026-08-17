#!/bin/bash
# daily-triage.sh — Daily Triage Phase1 エントリ（薄ラッパー）
# 実体は daily_triage.py（next-issue.py と同じ Python実体 + .sh エントリ構成）
#
# Usage:
#   bash daily-triage.sh                 # 収集→Claude判定→today-tasks.md生成
#   bash daily-triage.sh --collect-only  # 収集データのみstdout（検証用）
#   bash daily-triage.sh --no-llm        # LLM不使用・収集データをそのまま出力
#
# 残留プロセス対策（2026-08-17・バックログL170・06:37発火が3h居座り連日再発）:
#   ① ロック保持プロセスの年齢チェック（STALE_SECONDS超→fd照合つきで強制解除し再実行）
#   ② シェル側タイムアウト二重がけ（py内LLM timeout 300sの不効経路を外面でカバー）
#   ③ 強制解除・タイムアウトを RESCUE_LOG に記録（子プロセスPID・経過時間込み）
set -euo pipefail
# 並行実行防止（D'案・2026-07-14 補助層）: 秒差の真の同時重複を防ぐ。
# 分差の再実行（17分差事故）は daily_triage.py 側の当日既生成チェックが主軸で防ぐ。
# 動的FD（bash 4+）で未使用FDを自動割当→python実行中も本シェルが保持しプロセス終了で自動解放。
#   注: openは「>>」（truncateなし）。「>」だと発火のたびロックファイルが空にされ、
#   保持者PID記録（下記）が次の発火で消えてしまい年齢チェック不能になる。
LOCK_FILE="${DAILY_TRIAGE_LOCK_FILE:-$HOME/.claude/state/daily-triage.lock}"
RESCUE_LOG="${DAILY_TRIAGE_RESCUE_LOG:-$HOME/.claude/state/daily-triage-rescue.log}"
STALE_SECONDS="${DAILY_TRIAGE_STALE_SECONDS:-3600}"  # 保持者を残留とみなす年齢（正常実行は~1分）
PY_TIMEOUT="${DAILY_TRIAGE_PY_TIMEOUT:-360}"         # 全体タイムアウト（py内LLM timeout 300s+収集の上限）

log_rescue() {
  # ③ 調査ログ強化: 残留検知・強制解除・タイムアウトを1行ずつ記録
  echo "[$(date '+%F %T')] $$ $*" >> "$RESCUE_LOG"
}

mkdir -p "$(dirname "$LOCK_FILE")"
exec {_LOCK_FD}>>"$LOCK_FILE"
if ! flock -n "$_LOCK_FD"; then
  # ① 保持者PIDをファイルから読み、/proc/<PID>/fd に当該ロックが開いていることを照合
  #    （PID再利用で無関係プロセスを誤殺しないための必須照合・2026-08-17設計）
  HOLDER_PID="$(cat "$LOCK_FILE" 2>/dev/null | tr -dc '0-9' || true)"
  HOLDER_OK=false
  if [ -n "$HOLDER_PID" ] && [ -d "/proc/$HOLDER_PID" ] \
     && ls -l "/proc/$HOLDER_PID/fd" 2>/dev/null | grep -qF "$LOCK_FILE"; then
    HOLDER_OK=true
  fi
  if [ "$HOLDER_OK" != true ]; then
    echo "[daily-triage] 別プロセスが実行中です。スキップします。（保持者PID特定不能: ${HOLDER_PID:-空}）" >&2
    log_rescue "SKIP 保持者特定不能 holder_pid=${HOLDER_PID:-空}"
    exit 0
  fi
  ETIME_S="$(ps -o etimes= -p "$HOLDER_PID" 2>/dev/null | tr -dc '0-9' || true)"
  ETIME_S="${ETIME_S:-0}"
  if [ "$ETIME_S" -lt "$STALE_SECONDS" ]; then
    echo "[daily-triage] 別プロセスが実行中です。スキップします。（holder=$HOLDER_PID etime=${ETIME_S}s < ${STALE_SECONDS}s）" >&2
    exit 0
  fi
  # ③ kill前に子プロセス（claude --print等）のPID・経過時間を記録してから強制解除
  log_rescue "STALE検知 holder=$HOLDER_PID etime=${ETIME_S}s children=[$(ps -o pid=,etimes=,args= --ppid "$HOLDER_PID" 2>/dev/null | tr '\n' '|')]"
  pkill -TERM -P "$HOLDER_PID" 2>/dev/null || true
  kill -TERM "$HOLDER_PID" 2>/dev/null || true
  for _ in $(seq 1 10); do
    kill -0 "$HOLDER_PID" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$HOLDER_PID" 2>/dev/null; then
    pkill -KILL -P "$HOLDER_PID" 2>/dev/null || true
    kill -KILL "$HOLDER_PID" 2>/dev/null || true
  fi
  log_rescue "強制解除完了 holder=$HOLDER_PID → 再取得へ"
  if ! flock -n "$_LOCK_FD"; then
    echo "[daily-triage] 強制解除後もロック取得失敗。スキップします。" >&2
    log_rescue "再取得失敗・スキップ"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"  # 保持者PID記録（次回発火の年齢チェック用・ロック保持中なので競合なし）

# テスト用フック: ロック取得経路のみを検証する（python実体を起動しない・ Hermeticテスト用）
if [ "${DAILY_TRIAGE_LOCK_TEST_ONLY:-0}" = "1" ]; then
  echo "[daily-triage] lock-test mode: ロック取得のみで終了"
  exit 0
fi

# gh は ~/.local/bin にあり、非ログインシェル（cron/wsl bash -c 経由の実行は全て非ログイン）では
# ~/.bashrc 等が読まれないため PATH に含まれない。command -v で未検出時のみ明示的に補う。
if ! command -v gh >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$PATH"
fi
# シークレット読み込み（DISCORD_CLAUDE_WEBHOOK 等・実行先pythonに環境変数として継承）
# 注: ~/.secrets.env の一部の値に $ を含む行があり set -e/-u 下で source すると
# 未定義変数展開で即exitするため、source 時のみ errexit/nounset を一時無効化
# （.bashrc 経由の通常読み込み=set -u なし と同じ挙動）
set +eu
set -a
source ~/.secrets.env 2>/dev/null || true
set +a
set -euo pipefail

# ② タイムアウト二重がけ: execせず本シェルの子としてpythonを実行し、
# py内のLLM timeout(300s)が不効経路で無効化されても全体を PY_TIMEOUT で打ち切る。
# SIGTERM後も残る場合に備え --kill-after=15 でSIGKILL追撃。rc=124=シェル側タイムアウト。
# 注: 本シェルがロックFDを保持したまま待機するため、残留時に子プロセスごと強制解除される。
set +e
timeout --kill-after=15 "$PY_TIMEOUT" python3 "$(dirname "$0")/daily_triage.py" "$@"
rc=$?
set -e
if [ "$rc" -eq 124 ]; then
  echo "[daily-triage] 全体タイムアウト(${PY_TIMEOUT}s)で停止しました。" >&2
  log_rescue "TIMEOUT 全体${PY_TIMEOUT}s超過で停止"
fi
exit "$rc"
