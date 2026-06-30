#!/bin/bash
# 01_DECISIONS配下の_INDEX.md鮮度チェック

DECISIONS_DIR="/home/yn4416/projects/obsidian-ssot/01_DECISIONS"
stale_dirs=()
missing_dirs=()

for dir in "$DECISIONS_DIR"/*/; do
    [ -d "$dir" ] || continue
    dir_name=$(basename "$dir")

    # 直下のmdのみ（サブディレクトリは除く）— index_count側も純粋名参照のみで比較
    md_count=$(find "$dir" -maxdepth 1 -name '*.md' ! -name '_INDEX.md' ! -name 'README.md' | wc -l)

    INDEX="$dir/_INDEX.md"
    if [ ! -f "$INDEX" ]; then
        if [ "$md_count" -gt 0 ]; then
            missing_dirs+=("$dir_name")
        fi
        continue
    fi

    # index_count: 純粋なファイル名参照のみ（パス区切り/Win/チルダの外部参照は除外）
    # バッククォート形式 `file.md` と リンク形式 [text](file.md) の両方を集計
    # md_count(直下のみ)と口径を一致させることで偽陽性を防止
    index_count=$(python3 -c "
import re
with open('$INDEX','rb') as f: c=f.read().decode('utf-8','replace')
refs=set()
for m in re.findall(r'\x60([^\x60]+\.md)\x60', c):
    if '/' in m or '\\\\' in m or m.startswith('~'):
        continue
    refs.add(m.strip('\x60'))
for m in re.findall(r'\]\(([^)]+\.md)\)', c):
    if '/' in m or '\\\\' in m or m.startswith('~'):
        continue
    refs.add(m)
refs.discard('README.md')
print(len(refs))
")

    if [ "$md_count" -ne "$index_count" ]; then
        diff=$((md_count - index_count))
        if [ "$diff" -gt 0 ]; then
            stale_dirs+=("$dir_name:${diff}件")
        fi
    fi
done

if [ ${#missing_dirs[@]} -gt 0 ] || [ ${#stale_dirs[@]} -gt 0 ]; then
  TOTAL=$((${#missing_dirs[@]} + ${#stale_dirs[@]}))
  MSG=" ⚠️ INDEX差分: ${TOTAL}プロジェクト（generate-decision-indexes推奨）"
else
  MSG=" ✅ INDEX: 全プロジェクト同期済み"
fi
mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/indexes.status
exit 0
