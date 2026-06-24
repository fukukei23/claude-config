#!/bin/bash
# daily-triage.sh — Daily Triage Phase1 エントリ（薄ラッパー）
# 実体は daily_triage.py（next-issue.py と同じ Python実体 + .sh エントリ構成）
#
# Usage:
#   bash daily-triage.sh                 # 収集→Claude判定→today-tasks.md生成
#   bash daily-triage.sh --collect-only  # 収集データのみstdout（検証用）
#   bash daily-triage.sh --no-llm        # LLM不使用・収集データをそのまま出力
set -euo pipefail
exec python3 "$(dirname "$0")/daily_triage.py" "$@"
