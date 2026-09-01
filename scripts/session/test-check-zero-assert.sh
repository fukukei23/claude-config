#!/usr/bin/env bash
# test-check-zero-assert.sh — check-zero-assert.sh 自害テスト5ケース（spec v5 3-2・2026-09-01）
# 使い方: bash test-check-zero-assert.sh
# 終了: PASS=5 FAIL=0 で exit 0
set -u
HOOK="$(cd "$(dirname "$0")" && pwd)/check-zero-assert.sh"
FIX=/tmp/za-fixtures; mkdir -p "$FIX"; PASS=0; FAIL=0
export CLAUDE_DISABLE_ZA_CHECK=

run_case() {  # $1=名前 $2=期待exit $3=fixture名
  echo "{\"session_id\":\"$3\",\"transcript_path\":\"$FIX/$3.jsonl\"}" | bash "$HOOK" >/dev/null 2>&1
  local rc=$?
  if [ "$rc" = "$2" ]; then PASS=$((PASS+1)); echo "ok  $1 (exit=$rc)"; else FAIL=$((FAIL+1)); echo "NG  $1 (exit=$rc want=$2)"; fi
}

mk() {  # $1=fixture名 $2=assistant最終text $3=tool_result(-なら無し)
  python3 - "$FIX/$1.jsonl" "$2" "$3" <<'PY'
import json, sys
path, atext, tr = sys.argv[1:4]
with open(path, 'w') as f:
    # F層回避: 実ユーザー発言2個
    f.write(json.dumps({'type': 'user', 'message': {'content': '調査して'}}) + '\n')
    f.write(json.dumps({'type': 'user', 'message': {'content': '続けて'}}) + '\n')
    if tr != '-':
        f.write(json.dumps({'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 't1', 'content': tr}]}}) + '\n')
    f.write(json.dumps({'type': 'assistant', 'message': {'content': [
        {'type': 'text', 'text': atext}]}}) + '\n')
PY
}

# 1: ゼロ断定×再検索なし → 差戻し
mk za1 "参照元はゼロ件でした" "grep -rln foo/*.py: 0件"
# 2: ゼロ断定×再検索あり（ラベル+tool_result内grep 2回）→ 通過
mk za2 "参照元はゼロ件です。再検索: grep -rln --include={py,sh,md,ts,js,json,yaml} foo → 0件（N=0→M=0）" "grep -rln --include={py,sh,md,ts,js,json,yaml} foo: 0件
grep -rln foo/*.py: 0件"
# 3: ゼロ断定なし → 素通り
mk za3 "3件見つかりました" "-"
# 4: ゼロ断定×!override承認 → 通過
mk za4 "参照元はゼロ件でした" "grep: 0件"
python3 -c "
import json
p='$FIX/za4.jsonl'
lines=open(p).read().splitlines()
lines.append(json.dumps({'type':'user','message':{'content':'!override ゼロで正しい（仕様書確認済み）'}}))
open(p,'w').write('\n'.join(lines))"
# 5: F層（user発言1個）→ 素通り
python3 -c "
import json
recs = [
    {'type': 'user', 'message': {'content': '調査して'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'ゼロ件でした'}]}},
]
with open('$FIX/za5.jsonl', 'w') as f:
    for r in recs:
        f.write(json.dumps(r) + '\n')"

run_case "1:ゼロ断定×再検索なし→差戻し"       2 za1
run_case "2:ゼロ断定×再検索あり→通過"         0 za2
run_case "3:ゼロ断定なし→素通り"              0 za3
run_case "4:!override承認→通過"               0 za4
run_case "5:F層(user発言1個)→素通り"          0 za5
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = 0 ]
