#!/usr/bin/env bash
# run-security-check.sh — check-command-safety.py のクロスプラットフォームラッパー
# python3 / python / wsl python3 を自動検出して実行する

SCRIPT="/home/yn4416/.claude/scripts/security/check-command-safety.py"
WIN_SCRIPT="C:\\Users\\yn441\\.claude\\scripts\\security\\check-command-safety.py"

INPUT=$(cat)

# 実行環境を検出して適切なPythonで起動
if command -v python3 &>/dev/null; then
  # WSL / Linux / Mac — python3 が直接使える
  echo "$INPUT" | python3 "$SCRIPT"
elif command -v python &>/dev/null; then
  # Windows (python コマンドのみ) — WSLパスをWindowsパスに変換
  echo "$INPUT" | python "$WIN_SCRIPT"
elif command -v wsl &>/dev/null; then
  # Windows で WSL経由で実行
  echo "$INPUT" | wsl bash -c "cat | python3 '$SCRIPT'"
else
  # Python が見つからない → フックをスキップ（セッションを止めない）
  exit 0
fi
