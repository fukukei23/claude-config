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

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
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

# --- 宣言pathの取得（repoルートは実行cwdで解決・相対pathspecはcwd基準）---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
  echo "git-commit-scoped: gitリポジトリ外" >&2
  exit 64
fi

DECLARED=$(python3 "$HOME/bin/active-declarations.py" --mode include \
  --paths-json "$PATHS_JSON" \
  --active-sessions "$REPO_ROOT/00_SYSTEM/active-sessions.md" \
  --repo-root "$REPO_ROOT" 2>/dev/null | sed 's/^://')

# active-sessions.md が無いrepo（obsidian-ssot以外）では上記は空になるため
# paths.jsonの自WT4宣言を直接使う（cwd起点で突合）
if [ -z "$DECLARED" ] || [ ! -f "$REPO_ROOT/00_SYSTEM/active-sessions.md" ]; then
  DECLARED=$(python3 -c "
import json, os
try:
    d = json.load(open(os.path.expanduser('$PATHS_JSON')))
    for p in d.get('entries',{}).get('$WT4',[]):
        print(os.path.relpath(os.path.normpath(p), '$REPO_ROOT') if os.path.isabs(p) else p)
except Exception:
    pass
" 2>/dev/null)
fi

if [ -z "$DECLARED" ]; then
  echo "git-commit-scoped: 自セッション($WT4)の宣言が空・commit拒否（先に paths-json-update.py で宣言せよ）" >&2
  exit 1
fi

# --- 宣言突合（各pathspecが宣言のいずれかに含まれるか） ---
for f in "${PATHS[@]}"; do
  norm=$(python3 -c "
import os, sys
p = os.path.normpath('$f')
root = '$REPO_ROOT'
if os.path.isabs(p):
    try:
        p = os.path.relpath(p, root)
    except ValueError:
        pass
print(p)
")
  ok=false
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    case "$norm" in
      "$d"|"$d"/*) ok=true; break ;;
    esac
  done <<< "$DECLARED"
  if ! $ok; then
    echo "git-commit-scoped: 宣言外path検出: $f （宣言: $DECLARED）" >&2
    echo "  → 先に paths-json-update.py で宣言するか、宣言内のファイルのみ指定せよ" >&2
    exit 1
  fi
done

# --- pathspec commit（一時index = HEAD+指定パスのみ・共有indexを参照しない）---
exec git commit "${COMMIT_ARGS[@]}" -- "${PATHS[@]}"
