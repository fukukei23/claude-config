#!/bin/bash
# Usage: run-task.sh "<task_title>"
# next_issue.py から呼ばれる。state.json の current を実装→検証の2プロセスで処理。
# 終了コード: 0=検証OK / 1=検証NG(または実装失敗)
# ch8: 実装①と検証②は別 claude --print プロセス（別コンテキスト）。
set -uo pipefail

TITLE="${1:-}"
STATE="/home/yn4416/.claude/scripts/auto-dev/state.json"
LOG="/home/yn4416/.claude/scripts/auto-dev/loop.log"
VERIFY="/home/yn4416/.claude/scripts/auto-dev/verify-result.txt"
CLAUDE="/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/claude"

# state.json の current から PROMPT/REPO/ISSUE 抽出（python3 -c の複数行printをsedで分割）
CURRENT_JSON=$(python3 -c "
import json
s=json.load(open('$STATE'))
c=s.get('current') or {}
print(c.get('prompt','$TITLE を実装せよ'))
print(c.get('repo','/home/yn4416'))
print(c.get('issue') or '')
")
PROMPT=$(echo "$CURRENT_JSON" | sed -n '1p')
REPO=$(echo "$CURRENT_JSON" | sed -n '2p')
ISSUE=$(echo "$CURRENT_JSON" | sed -n '3p')

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === run-task: '$TITLE' repo=$REPO issue=$ISSUE ===" >> "$LOG"

cd "$REPO" || { echo "repo不在: $REPO" >> "$LOG"; echo "NG" > "$VERIFY"; echo "repo不存在" >> "$VERIFY"; exit 1; }

# run-task 実行中フラグ（実装/検証 claude の Stop hook 発火を next_issue.py で無視させる）
python3 -c "import json; s=json.load(open('$STATE')); s['running']=True; json.dump(s, open('$STATE','w'), indent=2, ensure_ascii=False)"

# 終了時（exit パス問わず）: running=false にして next_issue.py を直接呼ぶ
# Stop hook 二重発火回避・run-task 末尾で1回だけ状態遷移（ch6 証明可能な完了）
NEXT_ISSUE="/home/yn4416/.claude/scripts/auto-dev/next_issue.py"
finalize() {
  python3 -c "import json; s=json.load(open('$STATE')); s['running']=False; json.dump(s, open('$STATE','w'), indent=2, ensure_ascii=False)"
  python3 "$NEXT_ISSUE" >> "$LOG" 2>&1
}
trap finalize EXIT

# ① 実装フェーズ（作るAI）
IMPL_PROMPT="以下のタスクを実装してください。完了したらテストを通し、git commit してください。タスク: $PROMPT"
"$CLAUDE" --print "$IMPL_PROMPT" >> "$LOG" 2>&1
IMPL_RC=$?
if [ "$IMPL_RC" -ne 0 ]; then
  echo "NG" > "$VERIFY"
  echo "実装フェーズ失敗(rc=$IMPL_RC)" >> "$VERIFY"
  echo "[$(date '+%F %T')] 実装失敗 rc=$IMPL_RC" >> "$LOG"
  exit 1
fi

# Issue番号があれば close
if [ -n "$ISSUE" ]; then
  gh issue close "$ISSUE" >> "$LOG" 2>&1 || true
fi

# ② 検証フェーズ（検証AI・別プロセス=ch8 別コンテキスト）
VERIFY_PROMPT="あなたは検証AI。直前のコミット(git HEAD)を確認し、コードレビュー観点(バグ/簡潔性/規約違反)で厳しく評価せよ。結果の1行目に OK または NG を、2行目以降に理由を書いて出力せよ。基準: テスト通過・明らかなバグなし・規約違反なしなら OK。"
"$CLAUDE" --print "$VERIFY_PROMPT" > "$VERIFY" 2>&1
VERIFY_RC=$?

HEAD=$(head -1 "$VERIFY" | tr '[:lower:]' '[:upper:]')
echo "[$(date '+%F %T')] 検証結果 rc=$VERIFY_RC head=$HEAD" >> "$LOG"

if [[ "$HEAD" == OK* ]]; then
  exit 0
else
  exit 1
fi
