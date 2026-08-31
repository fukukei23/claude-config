#!/usr/bin/env bash
# check-mlr-ledger-coverage.sh — Stop Hook: 外部LLMレビュー実行日に判断収束台帳が更新されたか機械検証
#
# 狙い（2026-08-31 ふくけい指示）: multi-llm-review 等の成果物
# （00_SYSTEM/マルチLLMレビュー/<topic>/revised_proposal.md + frontmatter 3数値）の
# 保存忘れ・置き場所間違い（カレントディレクトリ出力等）を、LLMの自発性に依存せず機械検知する。
# これまで複数回すり抜け（2026-08-31 x-automation r1/r2・他セッションでも反復）。
#
# トリガ条件（誤検知回避）:
#   本日の ~/.claude/state/multi-llm-review.jsonl に llm=minimax または gemini の行がある
#   （= 本式レビューのシグナル。multi-llm-review-lite は OpenRouter free のみのため対象外。
#     minimax_ask をレビュー以外の要約等で使った日は免除フラグで通す）
# 合格条件（いずれか）:
#   a) 判断収束台帳_計測.md に本日付の行がある（集計スクリプトが反映済み）
#   b) 免除フラグ: ~/.claude/state/mlr-ledger-exempt-YYYY-MM-DD が存在する
#
# exit 0 = 合格/対象外・exit 2 = 差戻し（stderrをblocking表示）

set -uo pipefail

JSONL="$HOME/.claude/state/multi-llm-review.jsonl"
LEDGER="$HOME/projects/obsidian-ssot/00_SYSTEM/判断収束台帳_計測.md"
EXEMPT="$HOME/.claude/state/mlr-ledger-exempt-$(date +%F)"
TODAY=$(date +%F)

# 免除フラグ（lite的用途・minimax_askの別用途等・当日限り）
[ -f "$EXEMPT" ] && exit 0

# jsonl が無い/本日行が無い = 対象外
[ -f "$JSONL" ] || exit 0
TODAY_ROWS=$(grep -F "\"ts\": \"$TODAY" "$JSONL" 2>/dev/null || true)
[ -z "$TODAY_ROWS" ] && exit 0

# 本式レビューのシグナル（minimax/gemini）が無ければ対象外（lite等）
echo "$TODAY_ROWS" | grep -qF '"llm": "minimax"' || \
  echo "$TODAY_ROWS" | grep -qF '"llm": "gemini"' || exit 0

# 台帳に本日行があるか
if [ -f "$LEDGER" ] && grep -qF "| $TODAY |" "$LEDGER"; then
  exit 0
fi

cat >&2 <<EOF
⚠️ マルチLLMレビュー台帳カバレッジ: 本日（$TODAY）は minimax/gemini の外部LLM呼出があるのに判断収束台帳_計測.md に本日付の行が無い。
→ multi-llm-review を実行した場合: 成果物を正典 00_SYSTEM/マルチLLMレビュー/YYYY-MM-DD_<トピック>/revised_proposal.md（frontmatter: 手書き必須4項目 findings_total / overturned_by_measurement / decision_changed / negative_effect + v1互換 converted_to_cmd・0 < overturned ≤ 証跡数）に保存し、①mlr-log.sh annotate <round_id> <topic> --proposal <revised_proposal.mdのパス>（ingest・必須4項目欠損は警告）②python3 ~/projects/claude-config/scripts/obsidian/aggregate_judgment_ledger.py --ledger-db ~/.claude/state/judgment-ledger.jsonl を実行して台帳へ反映する。
  ※ カレントディレクトリ（プロジェクトrepo内）への出力は集計対象外。
→ 本式レビューでない（lite的用途・minimax_ask を要約等の別用途で使用 等）場合: touch ~/.claude/state/mlr-ledger-exempt-$TODAY で免除して終了。
EOF
exit 2
