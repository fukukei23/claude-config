#!/bin/bash
# test-active-tasks-display.sh — 🟢進行中タスク表示のfixtureテスト
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX="$HERE/fixtures/active-sessions-sample.md"

# 抽出ロジック（本物スクリプト load-obsidian-log.sh と同一の awk）
out=$(awk '/^## 🟢/{flag=1; next} /^## /{if(flag) exit} flag && /^\| / && !/^\| タスク/ && !/^\|-/' "$FIX")

echo "$out" | grep -q "オールブルー応募" || { echo "FAIL: オールブルー応募 未抽出"; exit 1; }
echo "$out" | grep -q "NexusCoreデモ動画" || { echo "FAIL: NexusCoreデモ動画 未抽出"; exit 1; }
echo "$out" | grep -q "settings.json" && { echo "FAIL: 共通ファイル節が混入"; exit 1; }
echo "$out" | grep -q "WSL-例" && { echo "FAIL: アクティブセッション欄が混入"; exit 1; }
echo "PASS: 🟢進行中タスク抽出"
