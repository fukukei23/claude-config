#!/bin/bash
# セッション終了時にclaude-code-guideの更新キューを記録する（Stop hook）

GUIDE_DIR="/home/yn4416/projects/claude-code-guide"
QUEUE_FILE="$GUIDE_DIR/.update-queue.md"
CONFIG_DIR="/home/yn4416/projects/claude-config"
LAST_COMMIT_FILE="$GUIDE_DIR/.last-checked-commit"

cd "$CONFIG_DIR" || exit 0

CURRENT_HEAD=$(git rev-parse HEAD 2>/dev/null)
if [ -z "$CURRENT_HEAD" ]; then
    exit 0
fi

# 前回チェック時のcommit hashを読む（なければ最初のコミットとの差分）
if [ -f "$LAST_COMMIT_FILE" ]; then
    LAST_COMMIT=$(cat "$LAST_COMMIT_FILE")
    # 有効なcommit hashか確認
    git cat-file -e "${LAST_COMMIT}^{commit}" 2>/dev/null || LAST_COMMIT=""
else
    LAST_COMMIT=""
fi

# 差分を取る（前回チェック以降の全コミット）
if [ -n "$LAST_COMMIT" ] && [ "$LAST_COMMIT" != "$CURRENT_HEAD" ]; then
    CHANGED=$(git diff --name-only "$LAST_COMMIT" HEAD 2>/dev/null)
elif [ -z "$LAST_COMMIT" ]; then
    # 初回: HEAD~1 との差分（最低1コミット分は見る）
    CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null)
else
    # LAST_COMMIT == CURRENT_HEAD: 新しいコミットなし
    exit 0
fi

# 今回のHEADを記録（次回の基準点）
echo "$CURRENT_HEAD" > "$LAST_COMMIT_FILE"

if [ -z "$CHANGED" ]; then
    exit 0
fi

TODAY=$(date +%Y-%m-%d)

declare -A queued_chapters

if echo "$CHANGED" | grep -q 'settings.json'; then
    if git diff "$LAST_COMMIT" HEAD -- settings.json 2>/dev/null | grep -q '"hooks"'; then
        queued_chapters["05-hooks.html"]=1
    fi
    if git diff "$LAST_COMMIT" HEAD -- settings.json 2>/dev/null | grep -q '"mcpServers"'; then
        queued_chapters["04-mcp.html"]=1
    fi
fi

if echo "$CHANGED" | grep -q 'CLAUDE.md'; then
    queued_chapters["01-basics.html"]=1
    queued_chapters["08-config.html"]=1
fi

echo "$CHANGED" | grep -q 'scripts/hooks/'    && queued_chapters["05-hooks.html"]=1
echo "$CHANGED" | grep -q 'scripts/session/'  && { queued_chapters["05-hooks.html"]=1; queued_chapters["08-config.html"]=1; }
echo "$CHANGED" | grep -q 'scripts/config/'   && queued_chapters["08-config.html"]=1
echo "$CHANGED" | grep -q 'scripts/mcp/'      && queued_chapters["04-mcp.html"]=1
echo "$CHANGED" | grep -q 'scripts/llm/'      && queued_chapters["08-config.html"]=1
echo "$CHANGED" | grep -q 'scripts/security/' && queued_chapters["08-config.html"]=1
echo "$CHANGED" | grep -q 'scripts/auto-dev/' && queued_chapters["12-dev-cycle.html"]=1
echo "$CHANGED" | grep -q 'skills/'           && queued_chapters["03-skills.html"]=1

if [ "${#queued_chapters[@]}" -eq 0 ]; then
    exit 0
fi

if [ ! -f "$QUEUE_FILE" ]; then
    printf '# guide update queue\n<!-- 自動生成。手動編集不要 -->\n\n' > "$QUEUE_FILE"
fi

CHANGE_SUMMARY=$(echo "$CHANGED" | head -5 | tr '\n' ',' | sed 's/,$//')

for chapter in "${!queued_chapters[@]}"; do
    grep -qF "| $chapter |" "$QUEUE_FILE" 2>/dev/null && continue
    echo "| $TODAY | $CHANGE_SUMMARY | $chapter |" >> "$QUEUE_FILE"
done

exit 0
