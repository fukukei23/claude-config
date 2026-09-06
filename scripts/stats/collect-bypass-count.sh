#!/usr/bin/env bash
# collect-bypass-count.sh — 直近7日の「ラッパー非経由commit」集計（Phase 3再評価条件の監視）
# spec: docs/superpowers/specs/2026-09-05_並行セッション巻き込み再設計-design.md §3 Phase 3
#
# v1の限界（正直に明記）: commitメッセージから「ラッパー経由」を機械判定する材料が無いため
# 「Auto backup / chore / generated 等の機械commitを除いた総数」を出す。ラッパー経由のcommitに
# 識別接頭辞（例: scoped:）を付ける運用が定着したら、本スクリプトの識別ロジックを置き換える。
set -euo pipefail

REPO="${1:-$HOME/projects/obsidian-ssot}"

# 機械commitとみなす接頭辞（巻き込み評価の対象外）
MACHINE_PATTERNS='Auto backup|^chore(ssot-p2)|^chore: active-sessions|^generated'

total=$(git -C "$REPO" log --since="7 days ago" --pretty=format:'%s' | wc -l)
machine=$(git -C "$REPO" log --since="7 days ago" --pretty=format:'%s' | grep -cE "$MACHINE_PATTERNS" || true)
manual=$((total - machine))

echo "repo=$REPO"
echo "total_7d=$total"
echo "machine_commits=$machine"
echo "manual_commits_7d=$manual  # これが週次の「bypass再評価」対象母数（週2件超=Phase 3再評価の材料）"
exit 0
