#!/bin/bash
# check-guide-count.sh — 全体マップのガイド数と index.html 掲載数を照合
# カウント基準（SSOT）: https://fukukei23.github.io/guides/index.html に掲載された
#   自サイト内ガイドリンク数（外部URL・アンカー・.md除外・重複排除）。
# 理由: 公開台帳 = index.html を正とすることで「公開しているガイド数」と一致する。
#   ディレクトリ実数は未掲載/実体なしリンクの不整合を含むため不採用。
set -uo pipefail

GUIDES_INDEX="$HOME/projects/guides/index.html"
MOC="$HOME/projects/obsidian-ssot/00_SYSTEM/全体マップ_MOC.md"
STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

if [ ! -f "$GUIDES_INDEX" ] || [ ! -f "$MOC" ]; then
  echo " ✅ ガイド数: ファイル不在（スキップ）" > "$STATUS_DIR/guide-count.status"
  exit 0
fi

# index.html の自サイト内ガイドリンク数を計算
ACTUAL=$(grep -oP 'href="[^"]+/?"' "$GUIDES_INDEX" \
  | grep -vE 'https?:|mailto:|#|\.md"' \
  | sed 's|href="||; s|"$||; s|/||' \
  | sort -u | wc -l)

# 全体マップから「ガイドサイト（N冊」の N を抽出（最初の命中）
RECORDED=$(grep -oP 'ガイドサイト（\s*\K[0-9]+(?=\s*冊)' "$MOC" | head -1)

if [ -z "$RECORDED" ]; then
  echo " ⚠️ ガイド数: 全体マップに『N冊』記載なし（index.html実数 ${ACTUAL}）" > "$STATUS_DIR/guide-count.status"
  exit 0
fi

if [ "$ACTUAL" = "$RECORDED" ]; then
  echo " ✅ ガイド数: ${ACTUAL}冊（index.htmlと整合）" > "$STATUS_DIR/guide-count.status"
else
  echo " ⚠️ ガイド数: index.html=${ACTUAL}冊 vs 全体マップ=${RECORDED}冊（要更新）" > "$STATUS_DIR/guide-count.status"
fi

exit 0
