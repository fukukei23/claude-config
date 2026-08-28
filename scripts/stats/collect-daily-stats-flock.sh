#!/bin/bash
# collect-daily-stats-flock.sh — collect-daily-stats.py への flock 排他ラッパー
#
# 使い方:
#   bash ~/.claude/scripts/stats/collect-daily-stats-flock.sh [--date YYYY-MM-DD]
#
# 2026-08-28 追加（durable cron残6件の排他化・バックログP1）:
#   durable cron id=5（使用量集計）は各並行セッションが同一時刻に独立発火する仕様
#   （2026-08-28 実測: 4セッション中2実行）。先着1実行のみが集計を続行し、
#   他は即skip＋reason=flock_busy のjsonl記録（sync-from-ssot.sh F-1と同パターン）。
#   ロックはプロセス終了で自動解除（lockファイル残置は無害）。
#   STATS_LOCK_FILE / STATS_LOG_FILE は env で上書き可能（テスト用）。
#
# 引数・exit code は collect-daily-stats.py をそのままパススルーする。

set -euo pipefail

LOCK_FILE="${STATS_LOCK_FILE:-$HOME/.claude/state/collect-daily-stats.lock}"
LOG_FILE="${STATS_LOG_FILE:-$HOME/.claude/state/collect-daily-stats.jsonl}"

log_json() {
    python3 - "$@" "$LOG_FILE" <<'PYEOF'
import json, sys, time, os
rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
for kv in sys.argv[1:-1]:
    if "=" in kv:
        k, v = kv.split("=", 1)
        rec[k] = v
path = sys.argv[-1]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PYEOF
}

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "⏭️  他の使用量集計実行中（flock排他）— スキップ"
    log_json "action=skip" "reason=flock_busy"
    exit 0
fi

exec python3 "$HOME/.claude/scripts/stats/collect-daily-stats.py" "$@"
