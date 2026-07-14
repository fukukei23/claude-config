#!/bin/bash
# daily-triage.sh — Daily Triage Phase1 エントリ（薄ラッパー）
# 実体は daily_triage.py（next-issue.py と同じ Python実体 + .sh エントリ構成）
#
# Usage:
#   bash daily-triage.sh                 # 収集→Claude判定→today-tasks.md生成
#   bash daily-triage.sh --collect-only  # 収集データのみstdout（検証用）
#   bash daily-triage.sh --no-llm        # LLM不使用・収集データをそのまま出力
set -euo pipefail
# 並行実行防止（D'案・2026-07-14 補助層）: 秒差の真の同時重複を防ぐ。
# 分差の再実行（17分差事故）は daily_triage.py 側の当日既生成チェックが主軸で防ぐ。
# 動的FD（bash 4+）で未使用FDを自動割当→exec python にも引き継がれプロセス終了で自動解放。
LOCK_FILE="$HOME/.claude/state/daily-triage.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
exec {_LOCK_FD}>"$LOCK_FILE"
if ! flock -n "$_LOCK_FD"; then
  echo "[daily-triage] 別プロセスが実行中です。スキップします。" >&2
  exit 0
fi
# gh は ~/.local/bin にあり、非ログインシェル（cron/wsl bash -c 経由の実行は全て非ログイン）では
# ~/.bashrc 等が読まれないため PATH に含まれない。command -v で未検出時のみ明示的に補う。
if ! command -v gh >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$PATH"
fi
# シークレット読み込み（DISCORD_CLAUDE_WEBHOOK 等・exec先pythonに環境変数として継承）
# 注: ~/.secrets.env の一部の値に $ を含む行があり set -e/-u 下で source すると
# 未定義変数展開で即exitするため、source 時のみ errexit/nounset を一時無効化
# （.bashrc 経由の通常読み込み=set -u なし と同じ挙動）
set +eu
set -a
source ~/.secrets.env 2>/dev/null || true
set +a
set -euo pipefail
exec python3 "$(dirname "$0")/daily_triage.py" "$@"
