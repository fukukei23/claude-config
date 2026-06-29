#!/bin/bash
# mirror-to-custom.sh
# PostToolUse (Edit/Write) でプラグインスキルが変更された時に skills-custom/ へ自動ミラー

TOOL_INPUT=$(cat)
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)

PLUGIN_BASE="/home/yn4416/.claude/plugins/marketplaces/claude-plugins-official/plugins"
CUSTOM_BASE="/home/yn4416/projects/claude-config/skills-custom"

[[ "$FILE_PATH" != "$PLUGIN_BASE"* ]] && exit 0
[[ "$FILE_PATH" != */skills/*/SKILL.md ]] && exit 0

REL="${FILE_PATH#$PLUGIN_BASE/}"
PLUGIN_NAME=$(echo "$REL" | cut -d/ -f1)
SKILL_NAME=$(echo "$REL" | cut -d/ -f3)

DEST="$CUSTOM_BASE/$SKILL_NAME/SKILL.md"
mkdir -p "$(dirname "$DEST")"
cp "$FILE_PATH" "$DEST"
echo "[skill-mirror] $PLUGIN_NAME/$SKILL_NAME を skills-custom/ にミラーしました" >&2
