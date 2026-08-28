#!/bin/bash
# ssot-check-auto-lock.sh — /ssot-check auto 用の実行ロック（LLM駆動スキル向け）
#
# 使い方:
#   bash ~/.claude/scripts/obsidian/ssot-check-auto-lock.sh acquire   # 開始時（BUSYならexit 1）
#   bash ~/.claude/scripts/obsidian/ssot-check-auto-lock.sh release   # 終了時（last-run更新と同時に）
#
# 2026-08-28 追加（durable cron残6件の排他化①・バックログP1）:
#   /ssot-check auto（durable cron id=789e76ec）は各並行セッションが同一時刻に独立発火し、
#   LLMが複数ステップで実行するため flock（プロセス生存依存）では包めない。
#   よってスタンプ（mtime）+年齢チェック方式（aiwatch A″案の当日スタンプ・
#   daily-triageのrescueと同系）。08-28 07:27+07:33の並行発火で
#   MCPガイド4→3再是正（実質ロールバック3回）が起きた実害の再発防止。
#   クラッシュ等で release 忘れが起きても STALE_SEC 経過で次回実行が強制取得する。
#   SSOT_CHECK_LOCK 環境変数でロックファイルを上書き可能（テスト用）。

set -euo pipefail

LOCK_FILE="${SSOT_CHECK_LOCK:-$HOME/.claude/state/ssot-check-auto.lock}"
STALE_SEC=1800  # 30分（auto実行の想定最長・超過は停滞とみなす）

ACTION="${1:-}"

now=$(date +%s)

case "$ACTION" in
  acquire)
    mkdir -p "$(dirname "$LOCK_FILE")"
    if [ -f "$LOCK_FILE" ]; then
      mtime=$(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo "$now")
      age=$(( now - mtime ))
      if [ "$age" -lt "$STALE_SEC" ]; then
        echo "BUSY: 他セッションが ssot-check auto 実行中（経過${age}秒・${STALE_SEC}秒未満）— スキップ"
        exit 1
      fi
      echo "stale ロック検知（経過${age}秒）— 強制取得"
    fi
    printf '{"ts": %s, "sid": "%s"}\n' "$now" "${CLAUDE_CODE_SESSION_ID:-manual}" > "$LOCK_FILE"
    echo "ACQUIRED"
    ;;
  release)
    rm -f "$LOCK_FILE"
    echo "RELEASED"
    ;;
  *)
    echo "usage: $0 acquire|release" >&2
    exit 2
    ;;
esac
