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
# claude CLI解決: fnm旧パス→nvm現行→PATH（daily_triage.py _resolve_claude_binと同方針・2026-08-31 rot対策）
CLAUDE="/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/claude"
[ -x "$CLAUDE" ] || CLAUDE="/home/yn4416/.nvm/versions/node/v24.16.0/bin/claude"
[ -x "$CLAUDE" ] || CLAUDE="$(command -v claude)"
[ -n "$CLAUDE" ] || { echo "[run-task] claude CLIが見つかりません" >> "$LOG"; exit 1; }
SS="/home/yn4416/.claude/scripts/auto-dev/state_store.py"
SS_PYSPATH="/home/yn4416/.claude/scripts/auto-dev"

# state.json の current から PROMPT/REPO/ISSUE/TEST_POLICY 抽出（state_store.read 経由・共有ロック）
# JSON経由で取出す（複数行promptで行ベースsedが壊れる既存バグ修正・2026-08-12 13:38実測）
CURRENT_JSON=$(python3 -c "
import sys, json; sys.path.insert(0, '$SS_PYSPATH')
import state_store
from pathlib import Path
c = state_store.read(Path('$STATE'), lambda s: (s.get('current') or {})) or {}
print(json.dumps({
    'prompt': c.get('prompt', '$TITLE を実装せよ'),
    'repo': c.get('repo', '/home/yn4416'),
    'issue': c.get('issue') or '',
    'test_policy': c.get('test_policy') or {},
}, ensure_ascii=False))
")
PROMPT=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['prompt'])" "$CURRENT_JSON")
REPO=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['repo'])" "$CURRENT_JSON")
ISSUE=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['issue'])" "$CURRENT_JSON")
TEST_POLICY=$(python3 -c "import json,sys; print(json.dumps(json.loads(sys.argv[1])['test_policy'], ensure_ascii=False))" "$CURRENT_JSON")

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

# 終了時（exit パス問わず）: running=false にして next_issue.py を直接呼ぶ
# （Phase1.5/Phase2のabort exitでもfinalizeが走るよう前倒し・2026-08-20）
NEXT_ISSUE="/home/yn4416/.claude/scripts/auto-dev/next_issue.py"
finalize() {
  python3 "$SS" clear-running
  python3 "$NEXT_ISSUE" >> "$LOG" 2>&1
}
trap finalize EXIT

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

# Phase 1: 計画立案（claude --print で plan.md を生成・A層AC必須化をプロンプトで義務付け）
echo "[$(date '+%F %T')] Phase 1: 計画立案" >> "$LOG"
PLAN_PROMPT="【重要】あなたは計画立案専用フェーズのLLMである。ファイル変更・実装・git commit・テスト実行は一切禁止する（実装はPhase 3の別プロセスが行う。ここで実装するとPhase 3が空振りblockedになる）。テキストの計画のみを出力せよ。
タスク: $OBJECTIVE
KPI: ${KPI_JSON:-なし}
テスト方針(起票時宣言・F層): ${TEST_POLICY:-{}}

実装計画を立てよ。'# 計画' で始めて 3-5 セクション（概要・実装手順・テスト方針・想定リスク等）で簡潔に出力せよ。以下は必須（D″案A層・機械検証される）:
- 「受け入れ条件」セクション: 証跡は exit code / テスト緑件数 / coverage / 本番CLI実測ログ のみ有効。coverage目標は既存値±5pt以内・100%は禁止。指標間矛盾（テスト0件なのにcoverage目標100%等）も禁止。
- 「テスト区分: 新規追加」or「テスト区分: 既存修正」or「テスト区分: 対象外」の1行を必ず含めよ（対象外はコードファイル変更が無いタスクのみ可・テスト方針と矛盾する区分は禁止）。"
CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK=1 "$CLAUDE" --print "$PLAN_PROMPT" > "$TASK_DIR/plan.md" 2>"$TASK_DIR/logs/plan.stderr.log"
echo "[$(date '+%F %T')] plan saved ($(wc -l < "$TASK_DIR/plan.md" 2>/dev/null || echo 0)行)" >> "$LOG"

# Phase 1.5: A層 plan機械検証（AC欄・テスト区分・coverage100%禁止・D″案第一段階）
python3 "$SS_PYSPATH/tdd_gate.py" validate-plan --plan "$TASK_DIR/plan.md" >> "$LOG" 2>&1
PLAN_VALID_RC=$?
echo "[$(date '+%F %T')] A層plan検証 rc=$PLAN_VALID_RC (0=ok)" >> "$LOG"
if [ "$PLAN_VALID_RC" -ne 0 ]; then
  echo "NG" > "$VERIFY"
  echo "A層plan検証NG: 受け入れ条件(AC)欄・テスト区分宣言が不正（tdd_gate validate-plan参照）" >> "$VERIFY"
  echo "[$(date '+%F %T')] A層plan検証NG・中止" >> "$LOG"
  exit 1
fi

# Phase 2: 計画レビュー（別ベンダーLLM・backend_kind必須・目的ホールド・2026-08-12有効化）
echo "[$(date '+%F %T')] Phase 2: 計画レビュー（別LLM・Gemini+MiniMax）" >> "$LOG"
python3 "$SS_PYSPATH/review_lib.py" --target-file "$TASK_DIR/plan.md" --objective-file "$TASK_DIR/objective.txt" --out "$TASK_DIR/plan_review.json" --round-id "al-${TASK_ID}-plan" --topic "$TASK_ID plan" >> "$LOG" 2>&1
PLAN_REVIEW_RC=$?
echo "[$(date '+%F %T')] plan_review rc=$PLAN_REVIEW_RC (0=ok/1=ng/2=abort)" >> "$LOG"
# ②で abort(2) は多様性保証不能・即停止（plan改訂ループはTask4品質ゲート拡張で別途）
if [ "$PLAN_REVIEW_RC" -eq 2 ]; then
  echo "NG" > "$VERIFY"
  echo "②計画レビュー abort: 多様性保証不能（ベンダー数<2）" >> "$VERIFY"
  echo "[$(date '+%F %T')] ②abort・停止" >> "$LOG"
  exit 1
fi

# run-task 実行中フラグ再設定（実装/検証 claude の Stop hook 発火を next_issue.py で無視させる）
python3 "$SS" set-running "$$"

# ① 実装フェーズ（作るAI）
HEAD_BEFORE=$(git rev-parse HEAD 2>/dev/null || echo "")
IMPL_PROMPT="以下のタスクを実装してください。完了したらテストを通し、git commit してください。タスク: $PROMPT"
CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK=1 "$CLAUDE" --print "$IMPL_PROMPT" >> "$LOG" 2>&1
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

# Phase 2.5: C層テストゲート（4条件block・allowlistはauto-loop-config.yaml・D″案第一段階）
# 4条件: ①テスト関数差分>=1 or 既存テストAST差分（空アサーション除外） ②pytest生ログ提出
#        ③repo種別allowlist ④失敗=block（機械的差戻し）
echo "[$(date '+%F %T')] Phase 2.5: C層テストゲート" >> "$LOG"
python3 "$SS_PYSPATH/tdd_gate.py" gate --repo "$REPO" --before "$HEAD_BEFORE" --task-dir "$TASK_DIR" >> "$LOG" 2>&1
GATE_RC=$?
echo "[$(date '+%F %T')] test-gate rc=$GATE_RC (0=pass/1=block)" >> "$LOG"
if [ "$GATE_RC" -ne 0 ]; then
  echo "NG" > "$VERIFY"
  echo "C層テストゲートblock（テスト無し完了・証跡不足・区分不整合等）:" >> "$VERIFY"
  python3 -c "
import json
try:
    d = json.load(open('$TASK_DIR/gate-result.json'))
    for r in d.get('reasons', []):
        print(f'- {r}')
except Exception as e:
    print(f'- gate-result.json読取失敗: {e}')
" >> "$VERIFY"
  echo "[$(date '+%F %T')] ゲートNG・差戻し" >> "$LOG"
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
CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK=1 "$CLAUDE" --print "$VERIFY_PROMPT" > "$VERIFY" 2>&1
VERIFY_RC=$?

# 検証範囲宣言の機械検査（spec v5 3-3・2026-09-01「テストは充分？」体系化）
# 自己修復なし・宣言セクション不在なら即NG（r3レビューで確定・逆用封じ）
if ! grep -qE '(検証範囲宣言|検証範囲:|宣言:)' "$VERIFY"; then
  echo "NG" > "$VERIFY"
  echo "検証出力に検証範囲宣言セクションなし（spec v5 3-3・テンプレ不遵守）" >> "$VERIFY"
  echo "[$(date '+%F %T')] 検証宣言セクション不在 → NG" >> "$LOG"
fi

# Phase 5: 実装後レビュー（別ベンダーLLM・git diff対象・⑤拒否権・2026-08-12有効化）
echo "[$(date '+%F %T')] Phase 5: 実装後レビュー（別LLM・git diff）" >> "$LOG"
git diff "$HEAD_BEFORE"..HEAD > "$TASK_DIR/impl_diff.txt" 2>/dev/null || git diff >> "$TASK_DIR/impl_diff.txt"
python3 "$SS_PYSPATH/review_lib.py" --target-file "$TASK_DIR/impl_diff.txt" --objective-file "$TASK_DIR/objective.txt" --out "$TASK_DIR/impl_review.json" --round-id "al-${TASK_ID}-impl" --topic "$TASK_ID impl" >> "$LOG" 2>&1
IMPL_REVIEW_RC=$?
echo "[$(date '+%F %T')] impl_review rc=$IMPL_REVIEW_RC (0=ok/1=ng/2=abort)" >> "$LOG"
# ⑤ verdict で VERIFY に追記（G3追記式・④結果を上書きしない・次ループ実装AIが修正可能）
# ng(1) は指摘追記のみ・abort(2) は先頭OKをNG化（多様性保証不能は強制停止）
if [ "$IMPL_REVIEW_RC" -ne 0 ]; then
  python3 -c "
import json
d = json.load(open('$TASK_DIR/impl_review.json'))
verdict = d.get('verdict','?')
crits = d.get('by_severity',{}).get('critical',[])
with open('$VERIFY','a') as f:
    f.write(f'\n--- ⑤別LLMレビュー verdict={verdict} ---\n')
    for c in crits[:5]:
        f.write(f'[critical] {c.get(\"issue\",\"\")[:300]}\n')
        sug = c.get('suggestion','')
        if sug:
            f.write(f'  -> {sug[:300]}\n')
"
  if [ "$IMPL_REVIEW_RC" -eq 2 ]; then
    # abort: 先頭OKをNG化
    python3 -c "
lines = open('$VERIFY').read().splitlines()
if lines and lines[0].strip().upper().startswith('OK'):
    lines[0] = 'NG'
try:
    reason = json.load(open('$TASK_DIR/impl_review.json')).get('abort_reason','')
except Exception:
    reason = ''
lines.insert(1, f'[5phase-abort] {reason}')
open('$VERIFY','w').write('\n'.join(lines) + '\n')
"
  fi
  echo "[$(date '+%F %T')] ⑤review ng/abort -> VERIFY追記済み" >> "$LOG"
fi

HEAD=$(head -1 "$VERIFY" | tr '[:lower:]' '[:upper:]')
echo "[$(date '+%F %T')] 検証結果 rc=$VERIFY_RC head=$HEAD (⑤反映後)" >> "$LOG"

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
# Phase5 impl_review.json の by_severity を読込（⑤未実行/失敗時は空dict）
try:
    _ir = json.load(open(sys.argv[8]))
    review_result = _ir.get('by_severity', {'critical':[], 'high':[], 'med':[], 'low':[]})
except Exception:
    review_result = {'critical':[], 'high':[], 'med':[], 'low':[]}
write_task_log(
    task_id=sys.argv[1],
    task_dir=Path(sys.argv[2]),
    objective=open(sys.argv[3]).read().strip(),
    kpi=json.loads(sys.argv[4]) if sys.argv[4] else None,
    plan_summary=json.loads(sys.argv[5]),
    review_result=review_result,
    drift_result=json.load(open(sys.argv[6])),
    verdict=sys.argv[7],
)
" "$TASK_ID" "$TASK_DIR" "$TASK_DIR/objective.txt" "$KPI_ESCAPED" "$PLAN_PY" "$TASK_DIR/drift-result.json" "$VERDICT" "$TASK_DIR/impl_review.json" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] task-log saved" >> "$LOG"

if [[ "$HEAD" == OK* ]]; then
  exit 0
else
  exit 1
fi
