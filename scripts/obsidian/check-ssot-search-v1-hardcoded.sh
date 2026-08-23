#!/usr/bin/env bash
# check-ssot-search-v1-hardcoded.sh — v1ハードコード手順書の機械検出
#
# 背景（2026-08-23 L21起票）:
#   v1（`scripts/ssot/search.py`）と v2（`~/projects/ssot-search-v2/`）が
#   共存する状況で、CCガイドや手順書に v1 のパスだけが書かれていると
#   「v1 を実行したつもりが v2 を実行していた」型の取り違えが起きる。
#   （実例: 2026-08-22 「RAG を実測した」と誤報告 → 実際は v1）
#
# 検出ロジック:
#   1. obsidian-ssot 配下の Markdown ファイルで `scripts/ssot/search.py` を grep
#   2. 以下のディレクトリは除外（経緯・設計記録・履歴で「手順書」ではない）:
#      - .backup-wikilinks-*, worktrees
#      - 01_DECISIONS/, 00_SYSTEM/handoff/, 00_SYSTEM/マルチLLMレビュー/
#      - docs/, .claude/worktrees/*
#   3. **ファイル全体**をコンテキストとして以下の「明示キーワード」のいずれかが
#      あるか確認（「v1」単独は除外キーワードとして弱いので使わない）:
#      - 「v1 字句完全一致用」/「v1 補助経路」/「v1 を残す理由」
#      - 「型番」「エラー文」「字句完全一致」「主経路」「意味検索」「字句検索」
#      - 「RAG ではない」「ripgrep 前置フィルタ」
#   4. 明示キーワードなし → v1 ハードコード警告
#
# 出力:
#   - exit 0 = 検出なし（または全て除外条件を満たす）
#   - exit 1 = 検出あり（warning 出力後）
#
# 呼び出し: bash ~/projects/claude-config/scripts/obsidian/check-ssot-search-v1-hardcoded.sh

set -u
SSOT_DIR="${SSOT_DIR:-$HOME/projects/obsidian-ssot}"
EXIT_CODE=0

# 1. v1 パスを grep（バックアップ/worktree/経緯記録 除外）
HITS=$(grep -rln "scripts/ssot/search\.py" "$SSOT_DIR" 2>/dev/null \
  --include="*.md" --include="*.sh" --include="*.py" \
  --exclude-dir=".backup-wikilinks-*" \
  --exclude-dir="worktrees" \
  --exclude-dir="01_DECISIONS" \
  --exclude-dir="handoff" \
  --exclude-dir="マルチLLMレビュー" \
  --exclude-dir="docs")

if [ -z "$HITS" ]; then
  echo "✅ v1 ハードコードなし"
  exit 0
fi

# 2. 各ヒットファイルを精査（**ファイル全体**をコンテキストとして判定）
WARNINGS=0
while IFS= read -r file; do
  [ -z "$file" ] && continue

  # ファイル全体を読んで「明示キーワード」があるか確認
  # （「v1」単独は除外キーワードとして弱い・本文に v1 と書かれていれば除外されてしまう）
  if grep -qiE "v1 字句完全一致用|v1 補助経路|v1 を残す理由|型番|エラー文|字句完全一致|主経路|意味検索|字句検索|RAG ではない|ripgrep 前置フィルタ" "$file" 2>/dev/null; then
    # 除外OK
    continue
  fi

  # 警告: 該当行のみ表示
  echo "⚠️  $file"
  grep -n "scripts/ssot/search\.py" "$file" 2>/dev/null | head -3
  echo ""
  WARNINGS=$((WARNINGS + 1))
done <<< "$HITS"

if [ "$WARNINGS" -gt 0 ]; then
  echo ""
  echo "⚠️  v1 ハードコード手順書を $WARNINGS ファイル検出"
  echo "   対応: 該当ファイルに『v1 字句完全一致用』等の明示を追加、または v2 パスに置換"
  echo "   詳細: 01_DECISIONS/claude-code/2026-08-23_autostash-pull-rebase再発の構造対策.md の層4"
  EXIT_CODE=1
else
  echo "✅ v1 ハードコード手順書なし（全て v1 用途明示済）"
fi

exit "$EXIT_CODE"
