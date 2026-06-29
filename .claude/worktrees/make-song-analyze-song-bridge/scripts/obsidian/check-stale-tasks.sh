#!/bin/bash
# check-stale-tasks.sh — 占有ボードの🟢進行中タスクが残っていれば警告する
# active-sessions.md の「🟢現在進行中タスク」表に1件以上あれば確認を促す
# （タイムスタンプに日付がないため厳密な24h判定はできない簡易版）

SSOT_PATH="${1:-/home/yn4416/projects/obsidian-ssot}"
BOARD="$SSOT_PATH/00_SYSTEM/active-sessions.md"

[ -f "$BOARD" ] || exit 0

COUNT=$(awk '/^## 🟢/{f=1;next} /^## /{f=0} f && /🟢進行 *\|$/' "$BOARD" | wc -l)

if [ "$COUNT" -gt 0 ]; then
  echo "⚠️ 占有ボードに🟢進行中タスクが ${COUNT} 件あります。古いものは active-sessions.md で確認してください。"
  exit 1
fi

exit 0
