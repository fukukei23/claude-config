#!/bin/bash
# guard-hooks-deletion.sh — af2be37型事故（commitでのSessionStart hook登録削除）の再発防止
# HOME repo (/home/yn4416) の .claude/settings.json commit 時に pre-commit から起動
# 保護対象10スクリプトの削除を staged diff で検知してブロック
# 正典: obsidian-ssot/00_SYSTEM/HOOKS_SSOT.md（保護対象リストは本スクリプトと同期）
set -uo pipefail

# 保護対象: SessionStart[0] (matcher=[]) に登録された11スクリプト
# 変更時は HOOKS_SSOT.md も同時更新（二重管理・運用ルール）
PROTECTED=(
  "load-handoff.sh"
  "load-obsidian-log.sh"
  "load-secrets.sh"
  "sync-secrets-to-settings.sh"
  "check-mcp-guide-sync.sh"
  "check-ssot-sync-staleness.sh"
  "check-decision-indexes.sh"
  "check-secrets-leak.sh"
  "check-submodule-sync.sh"
  "check-claude-config-sync.sh"
  "check-proxy-compat.sh"
)

SETTINGS_PATH=".claude/settings.json"

# staged な settings.json の diff を取得（未ステージ変更は対象外・pre-commit は staged のみ見る）
STAGED_DIFF=$(git diff --cached -- "$SETTINGS_PATH" 2>/dev/null)

# settings.json の変更なし → 通過
if [ -z "$STAGED_DIFF" ]; then
  exit 0
fi

# 削除行（先頭 "-"）かつ "scripts/" を含む行を抽出（diff ヘッダ "---" は除外）
# 追加行は問題ない（削除のみが事故）
DELETED_LINES=$(echo "$STAGED_DIFF" | grep '^-.*scripts/' | grep -v '^---' || true)

# scripts/ を含む削除なし → 通過
if [ -z "$DELETED_LINES" ]; then
  exit 0
fi

# 削除行に保護対象スクリプトが含まれるかチェック
HITS=""
for p in "${PROTECTED[@]}"; do
  if echo "$DELETED_LINES" | grep -q "$p"; then
    HITS="${HITS}  - ${p}"$'\n'
  fi
done

# 保護対象の削除検知 → ブロック
if [ -n "$HITS" ]; then
  cat >&2 <<EOF
❌ [guard-hooks-deletion] 保護対象 SessionStart スクリプトの削除を検知:

${HITS}
これは af2be37 型事故（commit での hook 登録削除・2026-06-24 発生・86行削除）の
再発防止のためブロックします。正典: obsidian-ssot/00_SYSTEM/HOOKS_SSOT.md

意図的な削除（スクリプト廃止・リネーム等）の場合は以下の手順で確認してください:
  1. HOOKS_SSOT.md の保護対象リストから該当スクリプトを削除
  2. 本スクリプト (guard-hooks-deletion.sh) の PROTECTED 配列も更新
  3. 上記更新を commit 後、対象スクリプト削除の commit を再実行
  4. 最終手段: git commit --no-verify（理由を commit message に明記）
EOF
  exit 1
fi

exit 0
