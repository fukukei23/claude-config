#!/bin/bash
# daily-triage.sh — Daily Triage Phase1 エントリ（薄ラッパー）
# 実体は daily_triage.py（next-issue.py と同じ Python実体 + .sh エントリ構成）
#
# Usage:
#   bash daily-triage.sh                 # 収集→Claude判定→today-tasks.md生成
#   bash daily-triage.sh --collect-only  # 収集データのみstdout（検証用）
#   bash daily-triage.sh --no-llm        # LLM不使用・収集データをそのまま出力
set -euo pipefail
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
