#!/usr/bin/env bash
# check-review-policy-gate.sh — review_policy.yaml 参照化ゲート（G3・spec §3.6）
# YAML構文検証（先）→ 動的直書きgrep → pytest の順で自動実行（r5採用）。
# いずれか失敗で commit 拒否（exit 1）。grep失敗時のみpytest省略（工数節約・r5b）。
# SKIP_GREP=1 で直書きgrepのみスキップ（緊急用・G1/G2移行期の指定・r5b/r6）。
# 自己点検: bash 本スクリプト --self-test で fixture 陽性3件検出/陰性3件無検出を検証。
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
  echo "[review-policy-gate] git repo 外で実行されたためスキップ"
  exit 0
fi

YAML_PATH="$REPO_ROOT/config/multi-llm-review/review_policy.yaml"
SKILL_PATH="$REPO_ROOT/skills/multi-llm-review/SKILL.md"
LIB_PATH="$REPO_ROOT/scripts/auto-dev/review_lib.py"

# --- 自己点検モード（fixture 陽性/陰性各3件・spec §3.6「各3件以上」） ---
if [ "${1:-}" = "--self-test" ]; then
  FIXDIR="$REPO_ROOT/scripts/hooks/fixtures/review-policy-gate"
  fail=0
  for f in "$FIXDIR"/positive_*.txt; do
    if ! python3 "$REPO_ROOT/scripts/hooks/review-policy-grep.py" \
        --yaml "$YAML_PATH" --target "$f" >/dev/null 2>&1; then
      echo "SELF-TEST NG(陽性を検出できず): $(basename "$f")"
      fail=1
    fi
  done
  for f in "$FIXDIR"/negative_*.txt; do
    if python3 "$REPO_ROOT/scripts/hooks/review-policy-grep.py" \
        --yaml "$YAML_PATH" --target "$f" >/dev/null 2>&1; then
      echo "SELF-TEST NG(陰性を誤検出): $(basename "$f")"
      fail=1
    fi
  done
  if [ $fail -eq 0 ]; then
    echo "SELF-TEST OK: 陽性3件検出・陰性3件無検出"
  fi
  exit $fail
fi

# --- SKIP_GREP=1（r6・G1/G2移行期の緊急スキップ） ---
if [ "${SKIP_GREP:-0}" = "1" ]; then
  echo "SKIP_GREP=1: 直書きgrepスキップ（spec §3.6・r5b/r6）"
  exit 0
fi

# --- ゲート対象のstagedファイル判定（無関係なら高速終了） ---
if ! git -C "$REPO_ROOT" diff --cached --name-only | grep -qE \
  '(^config/multi-llm-review/review_policy\.yaml$|skills/multi-llm-review/SKILL\.md$|scripts/auto-dev/review_lib\.py$|tests/test_review_policy\.py$)'; then
  exit 0
fi

fail=0

# --- 1. YAML構文検証（先・r5採用: grepのスタックトレース露出防止） ---
if ! py_err=$(python3 -c "
import yaml
yaml.safe_load(open('$YAML_PATH', encoding='utf-8'))
" 2>&1); then
  echo "❌ review-policy-gate: YAML構文検証失敗"
  echo "$py_err"
  exit 1
fi
echo "✅ review-policy-gate: YAML構文検証 PASS"

# --- 2. 動的直書きgrep（YAMLから値リスト抽出→対象ファイル内出現検出・r4採用） ---
for target in "$SKILL_PATH" "$LIB_PATH"; do
  if python3 "$REPO_ROOT/scripts/hooks/review-policy-grep.py" \
      --yaml "$YAML_PATH" --target "$target" >/dev/null 2>&1; then
    echo "❌ review-policy-gate: 直書き検出（$(basename "$target")）— YAML正本参照へ修正すること"
    fail=1
  else
    echo "✅ review-policy-gate: 直書きgrep PASS（$(basename "$target")）"
  fi
done
if [ $fail -ne 0 ]; then
  exit 1
fi

# --- 3. pytest（ポリシー関連スコープ・先行存在2失敗を含まない） ---
# 注意: repo rootの tests/ と scripts/auto-dev/tests/ は同名列の衝突で
# 一括指定すると collection error になるため2回に分けて実行する（実測）。
pytest_out=""
if ! pytest_out=$(python3 -m pytest -q --no-header \
    "$REPO_ROOT/tests/test_review_policy.py" 2>&1) \
    || ! pytest_out2=$(cd "$REPO_ROOT/scripts/auto-dev" && python3 -m pytest -q --no-header \
    tests/test_review_policy_load.py tests/test_review_lib.py 2>&1); then
  echo "❌ review-policy-gate: pytest 失敗"
  echo "$pytest_out" | tail -3
  echo "${pytest_out2:-}" | tail -3
  exit 1
fi
echo "✅ review-policy-gate: pytest PASS（${pytest_out##*passed} $(echo "$pytest_out2" | tail -1)）"
exit 0
