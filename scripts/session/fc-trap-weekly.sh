#!/usr/bin/env bash
# fc-trap-weekly.sh — 週次trap（5層設計e′-lite・2026-08-28）
# ①trap case: 要素欠落の検証系完了文を合成しhookに通す→差戻し(exit=2)になるべき
# ②sha256整合: settings.jsonのStop登録の改変検知（LLMによるhook外しの検知）
set -u
HOOK="$HOME/.claude/scripts/session/check-fail-coverage.sh"
FIX=/tmp/fc-trap; mkdir -p "$FIX"
printf '%s\n%s\n%s\n' \
  '{"type":"user","message":{"content":"タスクを開始してください"}}' \
  '{"type":"user","message":{"content":"続けてください"}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"## 合格\n検証した結果、問題なし。"}]}}' > "$FIX/trap.jsonl"
echo "{\"session_id\":\"trap-$$\",\"transcript_path\":\"$FIX/trap.jsonl\"}" | bash "$HOOK" >/dev/null 2>&1
RC=$?
REG=$(python3 -c "import json;d=json.load(open('$HOME/.claude/settings.json'));h=[c['command'] for x in d['hooks']['Stop'] for c in x['hooks']];print(0 if any('check-fail-coverage' in c for c in h) else 1)")
LINE="$(date +%F) trap_exit=$RC registered=$([ "$REG" = 0 ] && echo yes || echo NO)"
echo "$LINE" >> "$HOME/.claude/state/fc-check-guard/trap.log"
echo "$LINE"
[ "$RC" = "2" ] && [ "$REG" = "0" ]
