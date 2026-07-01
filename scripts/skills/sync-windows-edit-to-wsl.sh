#!/bin/bash
# sync-windows-edit-to-wsl.sh
# PostToolUse (Edit/Write/MultiEdit) で Windows Desktop 側の ~/.claude/skills/ 編集を検知し、
# WSL側の実git正典（claude-config/skills/ のsymlink先）へ即座にコピー＋軽量commitする。
# 目的: sync-skills-windows.sh（WSL→Windows一方向）による、
#       Windows側編集の上書き消失事故を防ぐ。

TOOL_INPUT=$(cat)
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)

WIN_SKILLS_PREFIX_1="C:\\Users\\yn441\\.claude\\skills\\"
WIN_SKILLS_PREFIX_2="C:/Users/yn441/.claude/skills/"
WSL_SKILLS_DIR="/home/yn4416/.claude/skills"

REL=""
case "$FILE_PATH" in
  "$WIN_SKILLS_PREFIX_1"*) REL="${FILE_PATH#$WIN_SKILLS_PREFIX_1}" ;;
  "$WIN_SKILLS_PREFIX_2"*) REL="${FILE_PATH#$WIN_SKILLS_PREFIX_2}" ;;
  *) exit 0 ;;
esac

[[ -z "$REL" ]] && exit 0

# バックスラッシュ区切りの相対パスをスラッシュに正規化
REL="${REL//\\//}"

WIN_SRC="/mnt/c/Users/yn441/.claude/skills/$REL"
WSL_DEST="$WSL_SKILLS_DIR/$REL"

[[ -f "$WIN_SRC" ]] || exit 0

mkdir -p "$(dirname "$WSL_DEST")"
if ! cp "$WIN_SRC" "$WSL_DEST" 2>/tmp/skill-sync-error.log; then
  echo "[skill-sync] Error: cp失敗 $(cat /tmp/skill-sync-error.log)" >&2
  exit 0
fi

cd /home/yn4416/projects/claude-config || exit 0
if ! git add "skills/$REL" 2>/tmp/skill-sync-error.log; then
  echo "[skill-sync] Error: git add失敗 $(cat /tmp/skill-sync-error.log)" >&2
  exit 0
fi
if ! git diff --cached --quiet; then
  SKILL_NAME=$(echo "$REL" | cut -d/ -f1)
  if git commit -m "chore: Windows Desktop編集を自動同期(${SKILL_NAME})" --quiet 2>/tmp/skill-sync-error.log; then
    echo "[skill-sync] ${SKILL_NAME} をWSL側実体へ同期・commitしました" >&2
  else
    echo "[skill-sync] Error: git commit失敗 $(cat /tmp/skill-sync-error.log)" >&2
  fi
fi

exit 0
