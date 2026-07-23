#!/bin/bash
# SSOT体系化 P2: 日次バッチ（system cron・純bash+Python orchestrator）
# spec: 2026-07-22-ssot-taikika-p2-design.md
set -uo pipefail

# === secrets.env 読込（WSL cron 非ログイン環境対策・両LLM高指摘）===
# secrets.env 内にシェル特殊文字（$#/等）を含む値があり `set -u` の source 評価で unbound になるため、
# source 前後で一時的に set -u/+u を切り替える。
set +u
set -a
. "$HOME/.secrets.env"
set +a
set -u

# === 環境変数（実行時に決定）===
SSOT_ROOT="$HOME/projects/obsidian-ssot"
CLAUDE_CONFIG="$HOME/projects/claude-config"
LOG_FILE="/tmp/claude-startup/ssot-daily-error.log"
STAMP="$HOME/.claude/state/ssot-batch.lock"
PROJECTS=("reserve-optimizer" "NexusCore" "claude-code")

mkdir -p /tmp/claude-startup
mkdir -p "$(dirname "$STAMP")"

# === デッドロック防止（stamp+24h・fallback⑥）===
if [ -f "$STAMP" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$STAMP" 2>/dev/null || echo 0) ))
  if [ "$AGE" -lt 86400 ]; then
    echo "[ssot-daily] 前回実行から24h未満（stamp残存 ${AGE}s）・スキップ" | tee -a "$LOG_FILE"
    exit 0
  fi
fi
date +%s > "$STAMP"
trap 'rm -f "$STAMP"' EXIT

# === 終了時の後始末（trap で EXIT 時にログ通知・失敗時のみ）===
cleanup_and_notify() {
  local rc=$1
  local summary=$2
  if [ "$rc" -ne 0 ] && [ -n "${DISCORD_CLAUDE_WEBHOOK:-}" ]; then
    curl -s -X POST "$DISCORD_CLAUDE_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{\"content\":\"⚠️ SSOT日次バッチ\\n$summary (rc=$rc)\"}" > /dev/null 2>&1 || \
      echo "[$(date)] Discord通知失敗 (rc=$rc): $summary" >> "$LOG_FILE"
  elif [ "$rc" -ne 0 ]; then
    echo "[$(date)] Discord未設定・通知skip (rc=$rc): $summary" >> "$LOG_FILE"
  fi
}

# === ステップ1: Python orchestrator 実行（INDEX + last_verified + pending）===
DRY_RUN="${1:-}"
DRY_FLAG=""
[ "$DRY_RUN" = "--dry-run" ] && DRY_FLAG="--dry-run"

cd "$SSOT_ROOT" || { echo "[ssot-daily] cd失敗: $SSOT_ROOT" >> "$LOG_FILE"; exit 1; }

# === ステップ0: daily-activity-stats（昨日の活動取得・|| 継続・dry-run時skip・spec v2）===
# 活動統計は INDEX/last_verified/pending と独立・1件失敗で全体停止しない（非致命）
# dry-run 時は skip（活動統計ファイル書き込みは副作用・純粋dry-run保持）
# ステップ0単独失敗は Discord通知しない（ステップ3通知は Python/commit/pending エラーのみ）
if [ "$DRY_RUN" != "--dry-run" ]; then
  echo "[ssot-daily] ステップ0: daily-activity-stats 開始" >> "$LOG_FILE"
  bash "$HOME/bin/daily-activity-stats" >> "$LOG_FILE" 2>&1 || \
    echo "[ssot-daily] daily-activity-stats 失敗（継続・ステップ0は非致命）" >> "$LOG_FILE"
fi

SUMMARY=$(PYTHONPATH="$CLAUDE_CONFIG" python3 -m scripts.obsidian.ssot_daily_batch \
  --ssot-root "$SSOT_ROOT" $DRY_FLAG 2>>"$LOG_FILE")
PYTHON_RC=$?
echo "$SUMMARY"
echo "$SUMMARY" >> "$LOG_FILE"

# === ステップ2: プロジェクト粒度 commit（fallback④・1プロジェクト失敗で全体ロールバックしない）===
COMMIT_RC=0
for proj in "${PROJECTS[@]}"; do
  M="01_DECISIONS/$proj/.dir-manifest.json"
  [ -f "$M" ] || continue
  if git diff --quiet -- "$M" 2>/dev/null; then continue; fi
  if git add -- "$M" 2>/dev/null && \
     git commit -m "chore(ssot-p2): $proj manifest 日次更新" -- "$M" >/dev/null 2>>"$LOG_FILE"; then
    echo "[ssot-daily] commit: $proj" >> "$LOG_FILE"
  else
    echo "[ssot-daily] commit失敗（継続）: $proj" >> "$LOG_FILE"
    COMMIT_RC=1
  fi
done

# INDEX 変更があれば commit
if ! git diff --cached --quiet -- "01_DECISIONS" 2>/dev/null; then
  if git commit -m "chore(ssot-p2): INDEX 自動更新（日次）" >/dev/null 2>>"$LOG_FILE"; then
    echo "[ssot-daily] commit: INDEX" >> "$LOG_FILE"
  else
    echo "[ssot-daily] INDEX commit失敗" >> "$LOG_FILE"
    COMMIT_RC=1
  fi
fi

# === ステップ3: 失敗判定とDiscord通知 ===
FINAL_RC=0
if [ "$PYTHON_RC" -ne 0 ]; then
  ERR=$(tail -3 "$LOG_FILE" 2>/dev/null | tr '\n' ' ' | cut -c1-300)
  cleanup_and_notify "$PYTHON_RC" "Python orchestrator失敗: $ERR"
  FINAL_RC=$PYTHON_RC
elif [ "$COMMIT_RC" -ne 0 ]; then
  cleanup_and_notify 1 "1件以上のcommit失敗（ログ確認）"
  FINAL_RC=1
# pending エラー（spec R2③・plan grep 検出）
elif grep -q '4xx\|429\|5xx\|MeaningGenError\|pending:追加[0-9]*件/err[1-9]' "$LOG_FILE" 2>/dev/null; then
  cleanup_and_notify 1 "pending再生成で一部エラー（ログ確認）"
  FINAL_RC=1
# P3-A: manifest ヘルス警告（rc=0でも drift/stale 検知時は通知・正常時は黙る）
elif echo "$SUMMARY" | grep -q 'health:' \
   && ! echo "$SUMMARY" | grep -q 'health:OK'; then
  if [ -n "${DISCORD_CLAUDE_WEBHOOK:-}" ]; then
    curl -s -X POST "$DISCORD_CLAUDE_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{\"content\":\"⚠️ SSOT manifest ヘルス警告\\n$SUMMARY\"}" > /dev/null 2>&1 || \
      echo "[$(date)] Discord通知失敗(health): $SUMMARY" >> "$LOG_FILE"
  else
    echo "[$(date)] Discord未設定・health通知skip: $SUMMARY" >> "$LOG_FILE"
  fi
  # FINAL_RC=0 のまま（ヘルス警告は失敗扱いしない・翌朝の調査トリガ）
fi

exit "$FINAL_RC"