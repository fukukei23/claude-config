#!/usr/bin/env bash
# =============================================================================
# cleanup-stale-ssot-record-flags.sh — ssot-record-active-* フラグの掃除
#
# 目的（2026-08-23 L26）:
#   ssot-recordスキル終了時にフラグをrmするが、異常終了・セッション破棄で
#   残ったままになると、手動Write禁止の二重防御（enforce-ssot-record.sh）が
#   形骸化する。本スクリプトは SessionStart で:
#     ① 自分のセッションID以外のフラグをmtime基準で掃除（案②）
#     ② 自分のセッションIDでも6時間超のフラグはTTL切れとして無効化（案①）
#
# 設計判断:
#   - mtime < 6h = 生存中（保護）
#   - mtime >= 6h = 異常終了（掃除対象）
#   - 自セッションID = 保護（自分が記録作業中の可能性）
#   - 他セッションID + mtime < 6h = 保護（並行セッション生存中）
#   - 他セッションID + mtime >= 6h = 掃除
# =============================================================================

set -euo pipefail

STATE_DIR="$HOME/.claude/state"
SID="${CLAUDE_CODE_SESSION_ID:-}"
TTL_SECONDS=$((6 * 3600))  # 6時間
NOW=$(date +%s)
REMOVED=0

# フラグディレクトリ確認
if [ ! -d "$STATE_DIR" ]; then
  exit 0
fi

for flag in "$STATE_DIR"/ssot-record-active-*; do
  [ -f "$flag" ] || continue
  flag_id=$(basename "$flag" | sed 's/^ssot-record-active-//')
  mtime=$(stat -c %Y "$flag" 2>/dev/null || echo 0)
  age=$((NOW - mtime))

  # 自分のセッションID → 保護（自分の作業中フラグ）
  if [ -n "$SID" ] && [ "$flag_id" = "$SID" ]; then
    continue
  fi

  # TTL判定（6時間超 = 異常終了とみなす）
  if [ "$age" -ge "$TTL_SECONDS" ]; then
    rm -f "$flag"
    REMOVED=$((REMOVED + 1))
    echo "[cleanup-stale-ssot-record-flags] 削除: $flag_id (age=${age}s / $((age/3600))h)" >&2
  fi
done

# 自分のセッションIDで、かつ6時間超のフラグがある場合は警告（記録漏れ）
if [ -n "$SID" ] && [ -f "$STATE_DIR/ssot-record-active-$SID" ]; then
  my_mtime=$(stat -c %Y "$STATE_DIR/ssot-record-active-$SID" 2>/dev/null || echo 0)
  my_age=$((NOW - my_mtime))
  if [ "$my_age" -ge "$TTL_SECONDS" ]; then
    echo "[cleanup-stale-ssot-record-flags] ⚠️ 自セッションフラグが ${my_age}s ($((my_age/3600))h) 経過。ssot-recordスキル異常終了の可能性 → 強制削除（次回はフックで再ブロックされます）" >&2
    rm -f "$STATE_DIR/ssot-record-active-$SID"
    REMOVED=$((REMOVED + 1))
  fi
fi

if [ "$REMOVED" -gt 0 ]; then
  echo "[cleanup-stale-ssot-record-flags] ${REMOVED}件削除完了" >&2
fi

exit 0
