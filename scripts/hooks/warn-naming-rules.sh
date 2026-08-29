#!/bin/bash
# warn-naming-rules.sh — 呼称ルール違反の警告表示（ブロックなし・spec 2026-08-29承認）
# 対象: obsidian-ssot配下のmd編集で (私|ユーザー)(が|の|に|を|から|へ) を含む行
# 除外: 外向きディレクトリ(20_PUBLISHING/40_CAREER)・エンドユーザー等の複合語はテストで保証
# 出力: exit 0 常時 + 違反時に additionalContext JSON（exit 2 にしない=ブロックしない）
set -euo pipefail
INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    ti=d.get('tool_input',{})
    print(ti.get('file_path','') or '')
except Exception: print('')" 2>/dev/null || echo "")

TEXT=$(echo "$INPUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    ti=d.get('tool_input',{})
    print((ti.get('new_string','') or '') + '\n' + (ti.get('content','') or ''))
except Exception: print('')" 2>/dev/null || echo "")

# 対象: obsidian-ssot配下のみ
case "$FILE_PATH" in
  *obsidian-ssot*) ;;
  *) exit 0 ;;
esac
# exclude: 外向き
case "$FILE_PATH" in
  *20_PUBLISHING*|*40_CAREER*) exit 0 ;;
esac

# 「エンドユーザー」「一般ユーザー」等の複合語を除外してから検出
HITS=$(echo "$TEXT" | grep -nE '(私|ユーザー)(が|の|に|を|から|へ)' | grep -nEv '(エンド|一般|対象|他の|第三者の)ユーザー' | head -5 || true)

if [ -n "$HITS" ]; then
  HITS="$HITS" python3 -c "
import json, os
hits = os.environ['HITS']
msg = '⚠️ 呼称ルール違反の疑い（spec 2026-08-29）: 人間=「ふくけい」/LLM=「CC」の固定名詞を使用（「私」「ユーザー（人間意味）」は書かない。機械的置換でなく主体判定で書き分け）。該当行:\n' + hits
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': msg}}, ensure_ascii=False))"
fi
exit 0
