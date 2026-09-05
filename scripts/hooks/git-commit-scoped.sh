#!/bin/bash
# git-commit-scoped.sh — 宣言検証 + pathspec commit の薄いラッパー
#
# 目的（spec 2026-09-05 並行セッション巻き込み再設計 §3 Phase 2-1）:
#   共有index（stage）を参照しない形でcommitし、他セッションのstaged変更の
#   巻き込みを構造的に防ぐ。git commit -- <paths> は内部で一時index
#   (HEAD+指定パスのみ)を作るため、他セッションのstageを巻き込まない
#   （且つ他セッションのstageを破壊しない）。
#
# 使い方:
#   git-commit-scoped -m "message" -- <path1> [path2 ...]
#   # 新規untrackedファイルは先に git add <file> してから（2段手順）
#
# 検証: 全pathspecが自セッション（WT4）のpaths.json宣言に含まれることを強制。
#   宣言外は commit拒否（exit 1）。pathspec罠（working treeの該当パス変更を
#   全部取り込む）への防御はこの宣言突合が本体・検品hookは背後の最終防線。

set -uo pipefail

SESSION_ID="${WT_SESSION:-${CLAUDE_CODE_SESSION_ID:-unknown}}"
WT4="${SESSION_ID:0:4}"
PATHS_JSON="${PATHS_JSON:-$HOME/.claude/state/active-sessions-paths.json}"

usage() {
  echo "git-commit-scoped: 使い方: git-commit-scoped -m <msg> -- <path1> [path2 ...]" >&2
  echo "  （新規untrackedファイルは先に git add <file> を実行・2段手順）" >&2
}

# --- 引数解析: -- の前後を分離 ---
PATHS=()
COMMIT_ARGS=()
SEEN_DD=false
for arg in "$@"; do
  if [ "$arg" = "--" ]; then SEEN_DD=true; continue; fi
  if $SEEN_DD; then PATHS+=("$arg"); else COMMIT_ARGS+=("$arg"); fi
done

# --- 前提チェック ---
if [ ${#PATHS[@]} -eq 0 ]; then
  usage
  exit 64
fi
if [ -z "$WT4" ]; then
  echo "git-commit-scoped: CLAUDE_CODE_SESSION_ID 未設定" >&2
  exit 64
fi
if [ ! -f "$PATHS_JSON" ]; then
  echo "git-commit-scoped: paths.json 不在 ($PATHS_JSON)" >&2
  exit 64
fi

# --- 宣言検証（python 1本化・値はすべて環境変数渡し=インジェクション面なし）---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
  echo "git-commit-scoped: gitリポジトリ外" >&2
  exit 64
fi
# active-declarations.py --mode check が: ①path正規化 ②宣言突合 ③正規化済pathspec出力 を一括実行
VALIDATION=$(CLAUDE_GCS_WT4="$WT4" \
  CLAUDE_GCS_PATHS_JSON="$PATHS_JSON" \
  CLAUDE_GCS_REPO_ROOT="$REPO_ROOT" \
  CLAUDE_GCS_ACTIVE="$REPO_ROOT/00_SYSTEM/active-sessions.md" \
  CLAUDE_GCS_PATHS_INPUT="$(printf '%s\n' "${PATHS[@]}")" \
  python3 "$HOME/bin/active-declarations.py" --mode check 2>&1)
RC=$?
if [ $RC -ne 0 ]; then
  echo "git-commit-scoped: 検証失敗" >&2
  echo "$VALIDATION" >&2
  echo "  → 先に paths-json-update.py で宣言するか、宣言内のファイルのみ指定せよ" >&2
  exit 1
fi

# 正規化済みpathspec（1行目OK・2行目以降が正規化済みrepo相対パス）
NORM_PATHS=()
while IFS= read -r line; do
  [ -z "$line" ] && continue
  [ "$line" = "OK" ] && continue
  NORM_PATHS+=("$line")
done <<< "$VALIDATION"

# --- pathspec commit（一時index = HEAD+指定パスのみ・共有indexを参照しない）---
exec git commit "${COMMIT_ARGS[@]}" -- "${NORM_PATHS[@]}"
