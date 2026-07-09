#!/bin/bash
# Usage: run-task.sh "<task_title>"
# next_issue.py から呼ばれる。state.json の current を実装→検証の2プロセスで処理。
# 終了コード: 0=検証OK / 1=検証NG(または実装失敗)
# ch8: 実装①と検証②は別 claude --print プロセス（別コンテキスト）。
# state.json アクセスは全て state_store.py（atomic+flock）経由。
set -uo pipefail

TITLE="${1:-}"
STATE="/home/yn4416/.claude/scripts/auto-dev/state.json"
LOG="/home/yn4416/.claude/scripts/auto-dev/loop.log"
VERIFY_FBACK="/home/yn4416/.claude/scripts/auto-dev/verify-result.txt"  # フォールバック(current.task_id無し時)
CLAUDE="/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/claude"
SS="/home/yn4416/.claude/scripts/auto-dev/state_store.py"
SS_PYSPATH="/home/yn4416/.claude/scripts/auto-dev"

# state.json の current から PROMPT/REPO/ISSUE 抽出（state_store.read 経由・共有ロック）
CURRENT_JSON=$(python3 -c "
import sys; sys.path.insert(0, '$SS_PYSPATH')
import state_store
from pathlib import Path
c = state_store.read(Path('$STATE'), lambda s: (s.get('current') or {})) or {}
print(c.get('prompt', '$TITLE を実装せよ'))
print(c.get('repo', '/home/yn4416'))
print(c.get('issue') or '')
")
PROMPT=$(echo "$CURRENT_JSON" | sed -n '1p')
REPO=$(echo "$CURRENT_JSON" | sed -n '2p')
ISSUE=$(echo "$CURRENT_JSON" | sed -n '3p')

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === run-task: '$TITLE' repo=$REPO issue=$ISSUE ===" >> "$LOG"

# current なし（next_issue.py 事前消化等）なら即中止（HOME repo 誤動作防止・2026-07-07）
CURRENT_EXISTS=$(python3 -c "
import sys; sys.path.insert(0, '$SS_PYSPATH')
import state_store
from pathlib import Path
print('yes' if state_store.read(Path('$STATE'), lambda s: s.get('current')) else 'no')
")
if [ "$CURRENT_EXISTS" = "no" ]; then
  echo "[$(date '+%F %T')] [ERROR] current なし・run-task.sh 中止（next_issue.py 事前消化の疑い）" >> "$LOG"
  echo "NG" > "$VERIFY_FBACK"
  echo "current 不在・起動中止（REPO フォールバックによる誤動作防止）" >> "$VERIFY_FBACK"
  exit 1
fi

cd "$REPO" || { echo "repo不在: $REPO" >> "$LOG"; echo "NG" > "$VERIFY_FBACK"; echo "repo不存在" >> "$VERIFY_FBACK"; exit 1; }

# current.started=True + running=True（state_store CLI・事前消化ガード・2026-07-07）
# set-running が current.started=True と running+PID+create_time を一括設定
python3 "$SS" set-running "$$"
echo "[$(date '+%F %T')] current.started=True・running=True（事前消化ガード）" >> "$LOG"

# ====== auto-loop 拡張（Phase 0/1 追加） ======
# task_id 決定: ISSUE があれば issue-<番号>、無ければ run-task-<UNIX秒>-<PID>（衝突回避）
TASK_ID="${ISSUE:+issue-$ISSUE}"
TASK_ID="${TASK_ID:-run-task-$(date +%s)-$$}"
TASK_DIR="$REPO/.auto-loop/$TASK_ID"
mkdir -p "$TASK_DIR/logs"
# 世代ガード: current.task_id を記録（verify-result を TASK_DIR に隔離）
python3 "$SS" set-task-id "$TASK_ID"
export PYTHONPATH="$SS_PYSPATH:${PYTHONPATH:-}"

# verify-result.txt は TASK_DIR 配下（世代ガード・グローバル混入防止）
VERIFY="$TASK_DIR/verify-result.txt"

# Phase 0: 目的抽出（PROMPT → objective.txt + KPI JSON）
echo "[$(date '+%F %T')] Phase 0: 目的抽出 task_id=$TASK_ID" >> "$LOG"
PROMPT_PY=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$PROMPT")
OBJECTIVE=$(python3 -c "
import sys, json
sys.path.insert(0, '$SS_PYSPATH')
from objective_extractor import extract_objective
print(extract_objective(json.loads(sys.argv[1])))
" "$PROMPT_PY")
KPI_JSON=$(python3 -c "
import sys, json
sys.path.insert(0, '$SS_PYSPATH')
from objective_extractor import parse_kpi
k = parse_kpi(json.loads(sys.argv[1]))
print(json.dumps(k, ensure_ascii=False) if k else '')
" "$PROMPT_PY")
echo "$OBJECTIVE" > "$TASK_DIR/objective.txt"
echo "[$(date '+%F %T')] objective=${OBJECTIVE:0:80} kpi=${KPI_JSON:-なし}" >> "$LOG"

# Phase 1: 計画立案（claude --print で plan.md を生成）
echo "[$(date '+%F %T')] Phase 1: 計画立案" >> "$LOG"
PLAN_PROMPT="タスク: $OBJECTIVE
KPI: ${KPI_JSON:-なし}

実装計画を立てよ。'# 計画' で始めて 3-5 セクション（概要・実装手順・テスト方針・想定リスク等）で簡潔に出力せよ。"
"$CLAUDE" --print "$PLAN_PROMPT" > "$TASK_DIR/plan.md" 2>"$TASK_DIR/logs/plan.stderr.log"
echo "[$(date '+%F %T')] plan saved ($(wc -l < "$TASK_DIR/plan.md" 2>/dev/null || echo 0)行)" >> "$LOG"

# Phase 2/5: スキップ（v1 は LLM 呼出なし・将来タスク）
echo "Phase 2/5 スキップ (v1)" > "$TASK_DIR/logs/review_skipped.txt"

# run-task 実行中フラグ再設定（実装/検証 claude の Stop hook 発火を next_issue.py で無視させる）
python3 "$SS" set-running "$$"

# 終了時（exit パス問わず）: running=false にして next_issue.py を直接呼ぶ
NEXT_ISSUE="/home/yn4416/.claude/scripts/auto-dev/next_issue.py"
finalize() {
  python3 "$SS" clear-running
  python3 "$NEXT_ISSUE" >> "$LOG" 2>&1
}
trap finalize EXIT

# ① 実装フェーズ（作るAI）
HEAD_BEFORE=$(git rev-parse HEAD 2>/dev/null || echo "")
IMPL_PROMPT="以下のタスクを実装してください。完了したらテストを通し、git commit してください。タスク: $PROMPT"
"$CLAUDE" --print "$IMPL_PROMPT" >> "$LOG" 2>&1
IMPL_RC=$?
if [ "$IMPL_RC" -ne 0 ]; then
  echo "NG" > "$VERIFY"
  echo "実装フェーズ失敗(rc=$IMPL_RC)" >> "$VERIFY"
  echo "[$(date '+%F %T')] 実装失敗 rc=$IMPL_RC" >> "$LOG"
  exit 1
fi

# 実装空振り検出: コミットが無ければ NG（タスク曖昧・既に完了・実装AIが判断迷い）
HEAD_AFTER=$(git rev-parse HEAD 2>/dev/null || echo "")
if [ "$HEAD_BEFORE" = "$HEAD_AFTER" ]; then
  echo "NG" > "$VERIFY"
  echo "実装でコミットなし（タスク曖昧・既に完了の可能性）" >> "$VERIFY"
  echo "[$(date '+%F %T')] 実装空振り（HEAD不変・検証スキップ）" >> "$LOG"
  exit 1
fi

# Issue番号があれば close
if [ -n "$ISSUE" ]; then
  gh issue close "$ISSUE" >> "$LOG" 2>&1 || true
fi

# ② 検証フェーズ（検証AI・別プロセス=ch8 別コンテキスト・doubt-driven 本式化）
# 敵対的プロンプト（find issues only・validate禁止）+ CONTRACT(objective+KPI)明示
VERIFY_PROMPT="あなたは敵対的レビューア。直前のコミット(git HEAD)を審査せよ。
**issues のみを出力せよ。validate するな・褒めるな。**
探せ: バグ・境界ケース・隠れた依存・契約違反・規約違反・スレッド安全性。
見つからなければ '見つからなかった' と明示せよ。

【満たすべき契約(CONTRACT)】
目的: $(cat "$TASK_DIR/objective.txt")
KPI: ${KPI_JSON:-なし}

結果の1行目は必ず OK または NG のみ（他の文字・日本語を一切含めない）。2行目以降に理由を書け。
基準: テスト通過・明らかなバグなし・契約(CONTRACT)違反なしなら OK。"
"$CLAUDE" --print "$VERIFY_PROMPT" > "$VERIFY" 2>&1
VERIFY_RC=$?

HEAD=$(head -1 "$VERIFY" | tr '[:lower:]' '[:upper:]')
echo "[$(date '+%F %T')] 検証結果 rc=$VERIFY_RC head=$HEAD" >> "$LOG"

# ====== auto-loop 拡張（Phase 6/7 追加） ======
# Phase 6: ズレ検知（verify-result.txt → drift-result.json）
echo "[$(date '+%F %T')] Phase 6: ズレ検知" >> "$LOG"
REVIEW_SUMMARY=$(head -c 2000 "$VERIFY" 2>/dev/null || echo "検証結果なし")
REVIEW_PY=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$REVIEW_SUMMARY")
OBJECTIVE_PY=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(open(sys.argv[1]).read().strip()))" "$TASK_DIR/objective.txt")
KPI_ESCAPED="$KPI_JSON"
DRIFT_RESULT=$(python3 -c "
import sys, json
sys.path.insert(0, '$SS_PYSPATH')
from drift_detector import detect_drift
review = json.loads(sys.argv[1])
objective = json.loads(sys.argv[2])
kpi = json.loads(sys.argv[3]) if sys.argv[3] else None
r = detect_drift(review, objective, kpi)
print(json.dumps({'drifted': r.drifted, 'reason': r.reason, 'kpi_value': r.kpi_value}, ensure_ascii=False))
" "$REVIEW_PY" "$OBJECTIVE_PY" "$KPI_ESCAPED")
echo "$DRIFT_RESULT" > "$TASK_DIR/drift-result.json"
echo "[$(date '+%F %T')] drift: $DRIFT_RESULT" >> "$LOG"

# Phase 7: task-log.md 生成（task_logger.write_task_log）
echo "[$(date '+%F %T')] Phase 7: 記録" >> "$LOG"
PLAN_SUMMARY=$(head -c 1000 "$TASK_DIR/plan.md" 2>/dev/null || echo "plan未生成")
PLAN_PY=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$PLAN_SUMMARY")
VERDICT="SUCCESS"
[[ "$HEAD" == OK* ]] || VERDICT="FAILURE"
python3 -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '$SS_PYSPATH')
from task_logger import write_task_log
write_task_log(
    task_id=sys.argv[1],
    task_dir=Path(sys.argv[2]),
    objective=open(sys.argv[3]).read().strip(),
    kpi=json.loads(sys.argv[4]) if sys.argv[4] else None,
    plan_summary=json.loads(sys.argv[5]),
    review_result={'critical':[], 'high':[], 'med':[], 'low':[]},
    drift_result=json.load(open(sys.argv[6])),
    verdict=sys.argv[7],
)
" "$TASK_ID" "$TASK_DIR" "$TASK_DIR/objective.txt" "$KPI_ESCAPED" "$PLAN_PY" "$TASK_DIR/drift-result.json" "$VERDICT" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] task-log saved" >> "$LOG"

if [[ "$HEAD" == OK* ]]; then
  exit 0
else
  exit 1
fi
