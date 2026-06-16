#!/usr/bin/env bash
# =============================================================================
# check-ssot-sync-staleness.sh
# =============================================================================
# 目的: SessionStart で ssot-sync auto の実行要否を判定し、未実行なら
#       プロンプト注入で CC に自律実行させる（1日1回・REPL idle に依存しない）。
#
# 仕組み:
#   - state ファイル（~/.claude/state/ssot-sync-last-run）に前回実行日を保持
#   - state 日付 ≠ 今日 → stdout で実行指示をプロンプト注入（セッション開始直後に発動）
#   - state 日付 ＝ 今日 → 何も出力しない（本日既実行・再発火抑制）
#
# 実行契機: SessionStart hook
# =============================================================================

STATE="$HOME/.claude/state/ssot-sync-last-run"
TODAY=$(date +%Y-%m-%d)
LAST=$(cat "$STATE" 2>/dev/null)

# state未存在または今日以外の日付 → ssot-sync auto 実行を指示
if [ "$LAST" != "$TODAY" ]; then
  cat <<EOF
[ssot-sync 日次自動実行トリガー]
前回の ssot-sync auto 実行: ${LAST:-（未実行）}／本日（${TODAY}）は未実行です。
セッション開始直後に /ssot-sync auto を実行してください（無人モード・高重要度のみ自動修正）。

実行時の厳守事項:
- auto モード: フェーズ2承認スキップ・重要度「高」のみ自動修正・中低は10_DAILY記録
- 安全装置: 削除系（リポ消失等）はスキップ・5ファイル超/100行超でcommit中止
- 完了後 必ず: date +%Y-%m-%d > ~/.claude/state/ssot-sync-last-run （再発火抑制）
EOF
fi
