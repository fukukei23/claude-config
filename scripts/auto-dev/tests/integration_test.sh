#!/usr/bin/env bash
# scripts/auto-dev/tests/integration_test.sh
# auto-loop 拡張（⓪目的抽出 / ⑥ズレ検知 / ⑦記録）の E2E 生成テスト
# 注意: claude --print を呼ばない（Phase 1 は plan.md を固定文字列で代用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_DEV_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_REPO="$SCRIPT_DIR/fixtures/test-repo"
TASK_ID="integration-test-001"
TASK_DIR="$TEST_REPO/.auto-loop/$TASK_ID"

# 1. テスト用 fixture リポジトリ準備
if [[ ! -d "$TEST_REPO" ]]; then
  mkdir -p "$TEST_REPO"
  cd "$TEST_REPO"
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test"
  echo "# test repo" > README.md
  git add . && git commit -qm "init"
  cd "$SCRIPT_DIR"
fi

# 2. .auto-loop クリーンアップ
rm -rf "$TASK_DIR"
mkdir -p "$TASK_DIR/logs"

# 3. Phase 0: 目的抽出（Task 3 のモジュールを直接呼出）
PROMPT="[OBJECTIVE] validate_email を RFC 5321 準拠にする [KPI] 95 % 達成"
echo "$PROMPT" > "$TASK_DIR/prompt.txt"

OBJECTIVE=$(python3 -c "
import sys; sys.path.insert(0, '$AUTO_DEV_DIR')
from objective_extractor import extract_objective
print(extract_objective(open('$TASK_DIR/prompt.txt').read()))
")
KPI_JSON=$(python3 -c "
import sys, json; sys.path.insert(0, '$AUTO_DEV_DIR')
from objective_extractor import parse_kpi
k = parse_kpi(open('$TASK_DIR/prompt.txt').read())
print(json.dumps(k, ensure_ascii=False) if k else '')
")

echo "$OBJECTIVE" > "$TASK_DIR/objective.txt"

# 4. Phase 1 スキップ: plan.md を固定文字列で代用（claude --print 回避）
cat > "$TASK_DIR/plan.md" <<EOF
# 計画

## 概要
validate_email を RFC 5321 準拠に更新する。

## 実装手順
1. validate_email 関数の修正
2. テスト追加
3. pytest で確認
EOF

# 5. Phase 6: ズレ検知（Task 4 のモジュールを直接呼出）
REVIEW_SUMMARY="テストカバレッジ 96% 達成。validate_email が RFC 5321 準拠になった。"
DRIFT_RESULT=$(python3 -c "
import sys, json; sys.path.insert(0, '$AUTO_DEV_DIR')
from drift_detector import detect_drift
kpi = json.loads('''$KPI_JSON''') if '''$KPI_JSON''' else None
r = detect_drift('''$REVIEW_SUMMARY''', open('$TASK_DIR/objective.txt').read().strip(), kpi)
print(json.dumps({'drifted': r.drifted, 'reason': r.reason, 'kpi_value': r.kpi_value}, ensure_ascii=False))
")
echo "$DRIFT_RESULT" > "$TASK_DIR/drift-result.json"

# 6. Phase 7: task-log.md 生成（Task 5 のモジュールを直接呼出）
REVIEW_JSON='{"critical": [], "high": [], "med": [], "low": []}'
python3 -c "
import sys, json; sys.path.insert(0, '$AUTO_DEV_DIR')
from pathlib import Path
from task_logger import write_task_log
write_task_log(
    task_id='$TASK_ID',
    task_dir=Path('$TASK_DIR'),
    objective=open('$TASK_DIR/objective.txt').read().strip(),
    kpi=json.loads('''$KPI_JSON''') if '''$KPI_JSON''' else None,
    plan_summary=open('$TASK_DIR/plan.md').read(),
    review_result=json.loads('''$REVIEW_JSON'''),
    drift_result=json.load(open('$TASK_DIR/drift-result.json')),
    verdict='SUCCESS',
)
"

# 7. 検証: 4 ファイル存在 + 内容の妥当性
[[ -f "$TASK_DIR/objective.txt" ]] || { echo "FAIL: objective.txt not created"; exit 1; }
[[ -f "$TASK_DIR/plan.md" ]] || { echo "FAIL: plan.md not created"; exit 1; }
[[ -f "$TASK_DIR/drift-result.json" ]] || { echo "FAIL: drift-result.json not created"; exit 1; }
[[ -f "$TASK_DIR/task-log.md" ]] || { echo "FAIL: task-log.md not created"; exit 1; }

# objective.txt に期待文字列が含まれる
grep -q "validate_email" "$TASK_DIR/objective.txt" || { echo "FAIL: objective.txt missing validate_email"; exit 1; }

# task-log.md に SUCCESS verdict が含まれる
grep -q "SUCCESS" "$TASK_DIR/task-log.md" || { echo "FAIL: task-log.md missing SUCCESS"; exit 1; }

# drift-result.json に drifted:false が含まれる（KPI 96 >= 95）
grep -q '"drifted": false' "$TASK_DIR/drift-result.json" || { echo "FAIL: drift-result.json missing drifted:false"; exit 1; }

# 8. テスト2: KPI 未達 → drifted:true になる
TASK_ID_2="integration-test-002"
TASK_DIR_2="$TEST_REPO/.auto-loop/$TASK_ID_2"
rm -rf "$TASK_DIR_2"
mkdir -p "$TASK_DIR_2/logs"

REVIEW_SUMMARY_BAD="テストカバレッジ 80% 達成"
DRIFT_BAD=$(python3 -c "
import sys, json; sys.path.insert(0, '$AUTO_DEV_DIR')
from drift_detector import detect_drift
kpi = {'value': 95.0, 'unit': '%', 'direction': 'gte'}
r = detect_drift('''$REVIEW_SUMMARY_BAD''', 'validate_email のテストカバレッジを 95% 以上にする', kpi)
print(json.dumps({'drifted': r.drifted, 'reason': r.reason, 'kpi_value': r.kpi_value}, ensure_ascii=False))
")
echo "$DRIFT_BAD" | grep -q '"drifted": true' || { echo "FAIL: KPI未達ケースで drifted:true にならない"; echo "actual: $DRIFT_BAD"; exit 1; }

# 9. クリーンアップ
rm -rf "$TASK_DIR" "$TASK_DIR_2"

echo "PASS: integration_test"