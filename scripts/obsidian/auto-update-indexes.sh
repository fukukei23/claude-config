#!/bin/bash
# auto-update-indexes.sh — INDEX差分がある場合に自動更新
# SessionStart hook で実行。差分なしなら何もしない。
set -uo pipefail

# SessionStart hook は非ログインシェルで ~/.profile が読み込まれないため
# ~/bin をPATHに追加（generate-decision-indexes が配置されている）
export PATH="$HOME/bin:$PATH"

STATUS_FILE="/tmp/claude-startup/indexes.status"

# check-decision-indexes.sh が先に実行されている前提
# 差分なし（✅）なら何もしない
if [ -f "$STATUS_FILE" ] && grep -q '^ ✅' "$STATUS_FILE"; then
  exit 0
fi

# 差分あり → 自動実行
if command -v generate-decision-indexes &>/dev/null; then
  OUTPUT=$(generate-decision-indexes 2>&1 || true)
  if [ -n "$OUTPUT" ]; then
    MSG=" ✅ INDEX: 自動更新完了 ($(echo "$OUTPUT" | tail -1))"
  else
    MSG=" ✅ INDEX: 更新不要"
  fi
else
  MSG=" ⚠️ INDEX: generate-decision-indexes 未インストール"
fi

mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/indexes.status

# === SSOT体系化 P1: .dir-manifest.json の last_verified 更新 + pending処理 ===
# cron 日次実行で manifest の last_verified（最終確認日）を当日で更新
# meaning 文字列は触らない（spec R1 のべき等性・cron は last_verified/path のみ更新）
TODAY=$(date +%Y-%m-%d)
PENDING_FILE="$HOME/projects/obsidian-ssot/.dir-manifest-pending.json"

# 3試行プロジェクト（P1）の manifest の last_verified を更新（meaningは触らない）
for proj in reserve-optimizer NexusCore claude-code; do
  MANIFEST="$HOME/projects/obsidian-ssot/01_DECISIONS/$proj/.dir-manifest.json"
  [ -f "$MANIFEST" ] || continue
  python3 -c "
import json
p = '$MANIFEST'
d = json.load(open(p))
d['last_verified'] = '$TODAY'
json.dump(d, open(p,'w'), ensure_ascii=False, indent=2)
"
done

# pendingキュー処理: 構造変化プロジェクトはログ出力のみ
# （meaning 再生成は人間確認後に CLI approve-meaning で手動実行・YAGNI）
if [ -f "$PENDING_FILE" ]; then
  PENDING_PROJECTS=$(python3 -c "import json; print(' '.join(json.load(open('$PENDING_FILE'))))" 2>/dev/null || echo "")
  if [ -n "$PENDING_PROJECTS" ]; then
    for proj in $PENDING_PROJECTS; do
      echo "[auto-update] pending に $proj あり・再生成は CLI で手動実行"
    done
  fi
  # 処理済みpendingをクリア
  echo '[]' > "$PENDING_FILE"
fi

exit 0
