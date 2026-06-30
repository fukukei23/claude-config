#!/bin/bash
# claude-config リポジトリの未コミット変更を検知
# scripts/ はシンボリックリンクで claude-config/scripts/ と同一のため
# スクリプト編集が git 管理外になっていないかチェックする

REPO="$HOME/projects/claude-config"
STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

[ -d "$REPO/.git" ] || exit 0

cd "$REPO" || exit 0

UNCOMMITTED=$(git status --porcelain 2>/dev/null | grep -v '^??' | wc -l)
UNPUSHED=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l)

MSG=""
if [ "$UNCOMMITTED" -gt 0 ]; then
  MSG=" ⚠️ claude-config: 未コミット変更 ${UNCOMMITTED}件 (git commit → push 忘れずに)"
elif [ "$UNPUSHED" -gt 0 ]; then
  MSG=" ⚠️ claude-config: 未push ${UNPUSHED}コミット"
else
  MSG=" ✅ claude-config: 同期済み"
fi

echo "$MSG" > "$STATUS_DIR/claude-config-sync.status"
exit 0
