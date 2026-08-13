#!/usr/bin/env bash
# =============================================================================
# check-ssot-check-staleness.sh
# =============================================================================
# 目的: SessionStart で ssot-check auto の実行要否を判定し、未実行なら
#       プロンプト注入で CC に自律実行させる（1日1回・REPL idle に依存しない）。
#
# 仕組み（2段階state・重複発火抑制）:
#   - ssot-check-triggered  : 今日の「発火指示済み」フラグ（本スクリプトが先行マーク）
#   - ssot-check-last-run   : 最終成功日（commit完了日・SKILL.md が更新）
#
#   1. triggered ≠ 今日 → 即座に triggered=今日 を書き込み（先行マーク）→ プロンプト注入
#   2. triggered = 今日 → 何も出力しない（本日既に発火指示済み・重複抑制）
#
# なぜ先行マークか:
#   複数セッションが同時に開始されると、state更新前に全セッションが発火してしまう
#   （2026-06-26 に04:39/41/42/43の4連鎖発火で発覚）。発火指示を出す瞬間に triggered を
#   更新することで、後続セッションを確実に抑制する。last-run は commit 成功時に
#   SKILL.md が更新する。実行失敗時は翌日 triggered≠今日 で再発火し自然リトライされる。
#
# 実行契機: SessionStart hook
# =============================================================================

STATE_DIR="$HOME/.claude/state"
TRIGGERED="$STATE_DIR/ssot-check-triggered"
LAST_RUN="$STATE_DIR/ssot-check-last-run"
TODAY=$(date +%Y-%m-%d)

mkdir -p "$STATE_DIR"

# triggered = 今日 → 本日既に発火指示済み・抑制
if [ "$(cat "$TRIGGERED" 2>/dev/null)" = "$TODAY" ]; then
  exit 0
fi

# triggered ≠ 今日 → 即座に先行マーク（重複発火抑制の肝・後続セッションを弾く）
echo "$TODAY" > "$TRIGGERED"

LAST=$(cat "$LAST_RUN" 2>/dev/null)

cat <<EOF
[ssot-check 日次自動実行トリガー]
本日（${TODAY}）の ssot-check auto を未実行なら実行してください（無人モード・高重要度のみ自動修正）。
前回の成功日: ${LAST:-（未実行）}

実行時の厳守事項:
- auto モード: フェーズ2承認スキップ・重要度「高」のみ自動修正・中低は10_DAILY記録
- 安全装置: 削除系（リポ消失等）はスキップ・5ファイル超/100行超でcommit中止
- 完了後 必ず: date +%Y-%m-%d > ~/.claude/state/ssot-check-last-run （実行成功日の記録・triggeredとは別管理）
EOF
