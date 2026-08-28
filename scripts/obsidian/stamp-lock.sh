#!/bin/bash
# stamp-lock.sh — LLM駆動スキル/cronタスク用の汎用実行ロック（stamp+年齢方式）
#
# 使い方:
#   bash ~/.claude/scripts/obsidian/stamp-lock.sh <name> acquire   # 開始時（BUSYならexit 1）
#   bash ~/.claude/scripts/obsidian/stamp-lock.sh <name> release   # 終了時（異常終了時も必須）
#
# 2026-08-28 追加（durable cron残6件の排他化③・バックログP1）:
#   ssot-check-auto-lock.sh（①で新設）を name 引数対応に汎用化したもの。
#   LLM駆動スキルは各bash呼び出しが別プロセスになるため flock（プロセス生存依存）
#   で包めず、スタンプ（mtime）+年齢チェック方式を使う（daily-triageのrescue・
#   aiwatch A″案の当日スタンプと同系）。durable cronは各並行セッションが同一時刻に
#   独立発火するため、LLM複数ステップの実行窓をロックファイルの寿命で表現する。
#   クラッシュ等で release 忘れが起きても STALE_SEC 経過で次回実行が強制取得する。
#
# 環境変数（テスト用）:
#   STAMP_LOCK_DIR   ロックファイル置き場（デフォルト ~/.claude/state）
#   STAMP_LOCK_STALE 停滞とみなす秒数（デフォルト 1800）

set -euo pipefail

LOCK_DIR="${STAMP_LOCK_DIR:-$HOME/.claude/state}"
STALE_SEC="${STAMP_LOCK_STALE:-1800}"  # 30分（LLM駆動実行の想定最長・超過は停滞とみなす）

NAME="${1:-}"
ACTION="${2:-}"

if [ -z "$NAME" ] || [ -z "$ACTION" ]; then
  echo "usage: $0 <name> acquire|release" >&2
  exit 2
fi
# nameはロックファイル名に直結するため英数字とハイフンのみ許可
if ! [[ "$NAME" =~ ^[A-Za-z0-9-]+$ ]]; then
  echo "error: name は英数字とハイフンのみ（受け取った値は秘密保護のため表示しない）" >&2
  exit 2
fi

LOCK_FILE="$LOCK_DIR/$NAME.lock"

now=$(date +%s)

case "$ACTION" in
  acquire)
    mkdir -p "$LOCK_DIR"
    if [ -f "$LOCK_FILE" ]; then
      mtime=$(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo "$now")
      age=$(( now - mtime ))
      if [ "$age" -lt "$STALE_SEC" ]; then
        echo "BUSY: 他セッションが '$NAME' 実行中（経過${age}秒・${STALE_SEC}秒未満）— スキップ"
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
    echo "usage: $0 <name> acquire|release" >&2
    exit 2
    ;;
esac
