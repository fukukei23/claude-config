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

    # dataview ブロック または no-dataviewマーカー(案W・CLI前提・全件は実ファイル直参照)があれば参照数チェック不要
    # - dataview: 人間用Obsidianで全件表示（spec §4.5 KPI-2）
    # - no-dataviewマーカー: 案W採用PJ（dataview廃止・CLI前提・2026-08-11 Zernio知見分断RCA）
    if grep -q "FROM \"01_DECISIONS/$dir_name\"" "$INDEX" || grep -q "<!-- no-dataview" "$INDEX"; then
        continue
    fi

    # index_count: 純粋なファイル名参照のみ（パス区切り/Win/チルダの外部参照は除外）
    # バッククォート形式 `file.md` と リンク形式 [text](file.md) の両方を集計
    # md_count(直下のみ)と口径を一致させることで偽陽性を防止
    # 修正(2026-07-17):
    #   - リンク形式は URL decode（%20 → 半角スペース等）して実体ファイル名と一致させる
    #   - `_INDEX.md` 自己参照を集計から除外（孤児カウント防止）
    index_count=$(python3 -c "
import re
from urllib.parse import unquote
with open('$INDEX','rb') as f: c=f.read().decode('utf-8','replace')
refs=set()
for m in re.findall(r'\x60([^\x60]+\.md)\x60', c):
    if '/' in m or '\\\\' in m or m.startswith('~'):
        continue
    refs.add(m.strip('\x60'))
for m in re.findall(r'\]\(([^)]+\.md)\)', c):
    if '/' in m or '\\\\' in m or m.startswith('~'):
        continue
    refs.add(unquote(m))
refs.discard('README.md')
refs.discard('_INDEX.md')
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
