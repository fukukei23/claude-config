#!/usr/bin/env bash
# check-model-stay.sh — Stop Hook: glm-5.3（高消費モデル）の戻し忘れを検知して警告
# 設計: obsidian-ssot/docs/superpowers/specs/2026-09-01_glm5.3戻し忘れ検知-design.md §4.3-4.5
# exit 0 = 対象外/静観・exit 2 = 差戻し（stderrがCCへ渡りCCがふくけいへ伝える・既存規約と同一）
set -uo pipefail

DETECTOR="$HOME/.claude/scripts/llm/model_stay_detector.py"
NOTIFIER="$HOME/.claude/scripts/llm/notify_5dot3_windows.py"
STAY_WARN_MIN=30    # 暫定値（spec §4.2・警告ログ実績で2週間後に校正）
STAY_MIN_TURNS=5    # 離席放置（無消費）の誤検知防止（G1）
DEBOUNCE_SEC=1800   # 30分に1回まで
PROJECTS_DIR="${MODEL_STAY_PROJECTS_DIR:-$HOME/.claude/projects}"
WARN_LOG="$HOME/.claude/state/model5-3-warn-log.jsonl"

input=$(cat)
session_id=$(printf '%s' "$input" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("session_id", ""))
except Exception: print("")' 2>/dev/null)

# 合算判定: 直近2時間以内に更新された全transcript（M5・週間枠は合算で消えるため）
paths=$(find "$PROJECTS_DIR" -name '*.jsonl' -mmin -120 -type f 2>/dev/null)
[ -z "$paths" ] && exit 0

results=$(python3 "$DETECTOR" $paths 2>/dev/null) || exit 0
[ "$results" = "[]" ] && exit 0

hit=$(printf '%s' "$results" | python3 -c "
import json, sys
res = json.load(sys.stdin)
cands = [r for r in res if r.get('since_min') is not None]
best = max(cands, key=lambda r: r['since_min'], default=None)
if best and best['since_min'] >= $STAY_WARN_MIN and best['turns'] >= $STAY_MIN_TURNS:
    print(f\"{best['since_min']:.0f}分 {best['turns']}ターン\")
" 2>/dev/null)
[ -z "$hit" ] && exit 0

# E2E強制フラグ（実測検証用・通常運用では未設定）
if [ "${MODEL_STAY_FORCE:-0}" != "1" ]; then
  # デバウンス（書込失敗時は安全側=警告を出す）
  stamp="$HOME/.claude/state/model5-3-warn-${session_id:-global}"
  now=$(date +%s)
  if [ -f "$stamp" ]; then
    last=$(cat "$stamp" 2>/dev/null || echo 0)
    [ "$((now - last))" -lt "$DEBOUNCE_SEC" ] && exit 0
  fi
  echo "$now" > "$stamp" 2>/dev/null || true
fi

# 効果測定ログ（部品5）
printf '{"ts": "%s", "session_id": "%s", "detail": "%s"}\n' "$(date -Iseconds)" "${session_id:-global}" "$hit" >> "$WARN_LOG" 2>/dev/null || true

# Windowsトースト（部品4・失敗は静観）
python3 "$NOTIFIER" "glm-5.3 を使っています" "戻し忘れの可能性 ${hit} /model sonnet でflashへ戻せます" 2>/dev/null &

echo "⚠️ glm-5.3戻し忘れの可能性です（${hit}・全タブ合算）。/model sonnet で glm-5.3-flash へ戻してください。5.3が必要な作業ならこの警告は無視してください。" >&2
exit 2
