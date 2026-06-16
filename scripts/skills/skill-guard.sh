#!/bin/bash
# skill-guard.sh
# SessionStart フックで skills-custom/ とインストール済みスキルを比較・復元

PLUGIN_BASE="/home/yn4416/.claude/plugins/marketplaces/claude-plugins-official/plugins"
CUSTOM_BASE="/home/yn4416/projects/claude-config/skills-custom"
LOG="/tmp/skill-guard.log"
RESTORED=0

for CUSTOM_FILE in "$CUSTOM_BASE"/*/SKILL.md; do
  [[ -f "$CUSTOM_FILE" ]] || continue
  SKILL_NAME=$(basename "$(dirname "$CUSTOM_FILE")")

  INSTALLED=$(find "$PLUGIN_BASE" -path "*/skills/$SKILL_NAME/SKILL.md" 2>/dev/null | head -1)
  [[ -z "$INSTALLED" ]] && continue

  CUSTOM_HASH=$(sha256sum "$CUSTOM_FILE" | cut -d' ' -f1)
  INSTALLED_HASH=$(sha256sum "$INSTALLED" | cut -d' ' -f1)

  if [[ "$CUSTOM_HASH" != "$INSTALLED_HASH" ]]; then
    cp "$CUSTOM_FILE" "$INSTALLED"
    echo "$(date '+%Y-%m-%d %H:%M') [skill-guard] 復元: $SKILL_NAME" >> "$LOG"
    RESTORED=$((RESTORED + 1))
  fi
done

if [[ $RESTORED -gt 0 ]]; then
  echo "[skill-guard] $RESTORED 件のスキルを skills-custom/ から復元しました"
fi
