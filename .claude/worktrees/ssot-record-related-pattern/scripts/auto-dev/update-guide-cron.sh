#!/bin/bash
# claude-code-guide 自動更新 Cron（月・木 6:00）
# このスクリプトはCronプロンプトから呼ばれる前処理（git操作担当）
# GLMによるsource更新はCronプロンプト側で実施済みであることを前提とする

set -euo pipefail

GUIDE_DIR="/home/yn4416/projects/claude-code-guide"
QUEUE_FILE="$GUIDE_DIR/.update-queue.md"
LOG_FILE="/tmp/update-guide-cron-$(date +%Y%m%d-%H%M%S).log"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }

notify_discord() {
    local msg="$1"
    source /home/yn4416/.secrets.env 2>/dev/null || true
    if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
        curl -s -X POST "$DISCORD_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"content\": \"$msg\"}" >/dev/null 2>&1 || true
    fi
}

# キューが空なら終了
if [ ! -f "$QUEUE_FILE" ] || ! grep -q '^|' "$QUEUE_FILE" 2>/dev/null; then
    log "キューが空のため終了"
    exit 0
fi

CHAPTERS=$(grep '^|' "$QUEUE_FILE" | awk -F'|' '{print $4}' | tr -d ' ' | sort -u | tr '\n' ' ')
log "対象章: $CHAPTERS"

# ブランチ作成
BRANCH="guide-update-$(date +%Y-%m-%d)"
cd "$GUIDE_DIR"
git checkout main && git pull origin main
if git ls-remote --heads origin "$BRANCH" 2>/dev/null | grep -q "$BRANCH"; then
    BRANCH="guide-update-$(date +%Y-%m-%d-%H%M)"
fi
git branch -D "$BRANCH" 2>/dev/null || true
git checkout -b "$BRANCH"

# convert.py で全章を再生成（引数なし）
log "convert.py 実行中..."
python3 "$GUIDE_DIR/convert.py" 2>>"$LOG_FILE" || {
    log "convert.py 失敗"
    notify_discord "⚠️ ガイド自動更新: convert.py 失敗。ログ: $LOG_FILE"
    git checkout main
    git branch -D "$BRANCH" 2>/dev/null || true
    exit 1
}

# HTMLバリデーション（変更対象章のみ）
for chapter in $CHAPTERS; do
    html_file="$GUIDE_DIR/docs/chapters/$chapter"
    [ -f "$html_file" ] || { log "HTML未発見: $html_file"; continue; }
    python3 - << PYEOF 2>>"$LOG_FILE" || {
import sys
try:
    from html.parser import HTMLParser
    p = HTMLParser()
    p.feed(open("$html_file").read())
except Exception as e:
    print(f"INVALID: $html_file: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
        log "HTMLバリデーション失敗: $chapter"
        notify_discord "⚠️ ガイド自動更新: バリデーション失敗 ($chapter)"
        git checkout main
        git branch -D "$BRANCH" 2>/dev/null || true
        exit 1
    }
done

# 変更がなければ終了
if git diff --quiet docs/; then
    log "差分なし。ブランチ削除"
    git checkout main
    git branch -D "$BRANCH"
    exit 0
fi

# commit & push
CHAPTERS_CSV=$(echo "$CHAPTERS" | tr ' ' ',' | sed 's/,$//')
git add -u docs/ source/
git commit -m "auto: update guide chapters ($CHAPTERS_CSV)"
git push origin "$BRANCH"

# PR作成
PR_URL=$(gh pr create \
    --title "[auto] ガイド自動更新 $(date +%Y-%m-%d)" \
    --body "## 自動更新PR

更新された章: $CHAPTERS

このPRは自動更新システムにより生成されました。
24時間以内に問題がなければ自動マージされます。" \
    --base main 2>>"$LOG_FILE")

log "PR: $PR_URL"
notify_discord "🤖 ガイド自動更新\n章: $CHAPTERS\nPR: $PR_URL\n⏱ 24時間後に自動マージします。問題があればPRを閉じてください。"

# 自動マージスクリプト生成
MERGE_SCRIPT="/tmp/merge-guide-pr-$(date +%Y%m%d%H%M).sh"
cat > "$MERGE_SCRIPT" << MERGE_EOF
#!/bin/bash
source /home/yn4416/.secrets.env 2>/dev/null || true
PR_STATE=\$(gh pr view "$PR_URL" --json state -q .state 2>/dev/null || echo "UNKNOWN")
if [ "\$PR_STATE" = "OPEN" ]; then
    gh pr merge "$PR_URL" --squash --delete-branch
    curl -s -X POST "\$DISCORD_WEBHOOK_URL" -H 'Content-Type: application/json' \
        -d '{"content": "✅ ガイドPRをマージしました: $PR_URL"}' >/dev/null 2>&1 || true
else
    curl -s -X POST "\$DISCORD_WEBHOOK_URL" -H 'Content-Type: application/json' \
        -d '{"content": "⏭️ ガイドPRはクローズ済みのためスキップ: $PR_URL"}' >/dev/null 2>&1 || true
fi
rm -f "$MERGE_SCRIPT"
MERGE_EOF
chmod +x "$MERGE_SCRIPT"

if command -v at >/dev/null 2>&1; then
    echo "bash $MERGE_SCRIPT" | at now + 24 hours 2>>"$LOG_FILE"
    log "自動マージを24時間後にスケジュール"
else
    log "警告: atコマンド未発見。手動マージが必要: $PR_URL"
    notify_discord "⚠️ 自動マージ未設定。手動でマージしてください: $PR_URL"
fi

# 処理済み章をキューから削除（固定文字列マッチ）
python3 -c "
import sys
chapters = open(sys.argv[1]).readlines()
targets = sys.argv[2:]
filtered = [l for l in chapters if not any(t in l for t in targets)]
open(sys.argv[1], chr(119)).writelines(filtered)
" "$QUEUE_FILE" $CHAPTERS 2>/dev/null || true

git checkout main
log "完了"
exit 0
