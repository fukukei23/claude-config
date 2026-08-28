#!/usr/bin/env bash
# test-check-fail-coverage.sh — check-fail-coverage.sh 自害テスト8ケース（spec §5・2026-08-28）
# 使い方: bash test-check-fail-coverage.sh
# 終了: PASS=8 FAIL=0 で exit 0
set -u
HOOK="$(cd "$(dirname "$0")" && pwd)/check-fail-coverage.sh"
FIX=/tmp/fc-fixtures; mkdir -p "$FIX"; PASS=0; FAIL=0
export CLAUDE_DISABLE_FC_CHECK=

mk_transcript() {  # $1=fixture名 $2=assistant最終text $3=tool_result text(-なら無し) $4=追加user入力(-なら無し)
  python3 - "$FIX/$1.jsonl" "$2" "$3" "$4" <<'PY'
import json, sys
path, atext, tr, utext = sys.argv[1:5]
with open(path, 'w') as f:
    # F層回避: 実ユーザー発言2個を必ず含める（機械呼び出し判定されないため）
    f.write(json.dumps({'type': 'user', 'message': {'content': 'タスクを開始してください'}}) + '\n')
    f.write(json.dumps({'type': 'user', 'message': {'content': '続けてください'}}) + '\n')
    if tr != '-':
        f.write(json.dumps({'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 't1', 'content': tr}]}}) + '\n')
    f.write(json.dumps({'type': 'assistant', 'message': {'content': [
        {'type': 'text', 'text': atext}]}}) + '\n')
    if utext != '-':
        f.write(json.dumps({'type': 'user', 'message': {'content': utext}}) + '\n')
PY
}

run_case() {  # $1=名前 $2=期待exit(0=通過/2=差戻し) $3=fixture名 $4=state初期化(1=する)
  if [ "$4" = "1" ]; then rm -f "$HOME/.claude/state/fc-check-guard/"*.cnt 2>/dev/null; fi
  echo "{\"session_id\":\"$3\",\"transcript_path\":\"$FIX/$3.jsonl\"}" | bash "$HOOK" >/dev/null 2>&1
  local rc=$?
  if [ "$rc" = "$2" ]; then PASS=$((PASS+1)); echo "ok  $1 (exit=$rc)"; else FAIL=$((FAIL+1)); echo "NG  $1 (exit=$rc want=$2)"; fi
}

# --- fixtures（spec §5の8ケース）---
GOOD='## 合格
検証済み:
- ケース1: grep -c hoge f.txt → EXIT=0
3
- 閾値: 0件なら不合格(fail条件) [fp:123/l1=64]
fail条件ケース(未実施): cwd不一致×≤10ファイル → 合格(限定条件: cwd一致)'
mk_transcript c2 "$GOOD" '---tool result: EXIT=0 --- 3' '-'
mk_transcript c1 '## 合格
検証した結果、問題なし。' '-' '-'
mk_transcript c3 '## 本日の作業は合格ラインに達しました（報告）' '-' '-'
mk_transcript c4 "$GOOD" '---EXIT=0--- 3' '承認: テストタスク'
mk_transcript c5 '## 合格
検証した結果、問題なし。' '---EXIT=0--- 3' '-'
mk_transcript c6 '## 合格
検証済み:
- 引用: EXIT=5 の結果（tool_resultに存在しない偽引用）' '-' '-'
mk_transcript c7 '## 合格
検証済み:
閾値: exit code 0-255ならOK [fp:1/l1=64]' '---EXIT=2---' '-'
mk_transcript c8 '## 合格
検証済み:
```EXIT=0
別セッション由来のログ
```
閾値: X≠0なら不合格' '---EXIT=9---' '-'

run_case "1:共起あり・要素なし→差戻し"          2 c1 1
run_case "2:共起あり・要素あり→通過"            0 c2 1
run_case "3:確定語のみ(検証語なし)→通過"        0 c3 1
run_case "4:承認なし→block(1回目)"              2 c5 1
run_case "4b:承認なし→block継続(2回目)"         2 c5 0
run_case "5:実ユーザー承認あり→通過"            0 c4 1
run_case "6:偽引用(tool_result不在)→差戻し"     2 c6 1
run_case "7:恒真閾値(0-255)→差戻し"             2 c7 1
run_case "8:引用不整合→差戻し"                  2 c8 1
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = 0 ]
