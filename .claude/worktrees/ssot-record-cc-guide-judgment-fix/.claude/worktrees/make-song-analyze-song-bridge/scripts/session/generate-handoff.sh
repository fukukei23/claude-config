#!/usr/bin/env bash
# generate-handoff.sh — Stop Hook: セッション終了時にhandoff.mdを自動生成
# 翌日のコールドスタート問題を解消

HANDOFF_DIR="$HOME/.claude/state"
mkdir -p "$HANDOFF_DIR"
HANDOFF_FILE="$HANDOFF_DIR/handoff.md"

NOW=$(date '+%Y-%m-%d %H:%M')
TODAY=$(date +%Y-%m-%d)
DAILY_LOG="/home/yn4416/projects/obsidian-ssot/10_DAILY/$TODAY.md"

# 今日のセッションログから最後のセッション情報を抽出
last_session=""
if [[ -f "$DAILY_LOG" ]]; then
  last_session=$(grep -A5 "^## セッションログ" "$DAILY_LOG" | tail -6 | head -5)
fi

# 未解決問題を抽出
unresolved=""
if [[ -f "$DAILY_LOG" ]]; then
  unresolved=$(grep "未解決:" "$DAILY_LOG" | tail -1 | sed 's/.*未解発: //;s/.*未解決: //')
fi

# 現在のgit branch情報（作業ディレクトリがリポジトリの場合）
git_info=""
if git rev-parse --is-inside-work-tree &>/dev/null; then
  git_info="- ブランチ: $(git branch --show-current 2>/dev/null || echo 'unknown')"
  git_info="$git_info
- 未コミット: $(git status --porcelain 2>/dev/null | wc -l) files"
fi

# handoff.md生成
cat > "$HANDOFF_FILE" << EOF
# セッションハンドオフ

> 最終更新: $NOW

---

## 前回のセッション

$last_session

## 未解決問題

${unresolved:-なし}

## Git状態

${git_info:-リポジトリ外}

## 次にやること

- このファイルを確認して、前回の続きから始める
- 未解決問題があれば優先的に対応
EOF

exit 0
