#!/usr/bin/env bash
# track-tool-usage.sh — PostToolUse Hook: ツール使用回数をCSVに記録
# claude-cost コマンドでサマリー確認可能
# 2026-07-24 拡張: Skill ツール発動時にスキル名(tool_input.skill)を4列目に記録

INPUT=$(cat)

# python3でJSONパース（tool_name, session_id, skill_name を一括取得・プロセス起動1回化）
# skill_name は tool_name=Skill の時だけ tool_input.skill から取得（他ツールは空）
read -r tool_name session_id skill_name < <(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tn = d.get('tool_name', '')
sid = d.get('session_id', 'unknown')
sk = ''
if tn == 'Skill':
    ti = d.get('tool_input', {})
    if isinstance(ti, dict):
        sk = ti.get('skill', '')
print(tn, sid, sk)
" 2>/dev/null)

[[ -z "$tool_name" ]] && exit 0

# ログディレクトリ
LOG_DIR="$HOME/.claude/logs"
mkdir -p "$LOG_DIR"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/tool-usage-${TODAY}.csv"

# 初回のみヘッダー（4列・skill_name 含む）
[[ ! -f "$LOG_FILE" ]] && echo "timestamp,session_id,tool_name,skill_name" > "$LOG_FILE"

# レコード追記（skill_name は Skill ツール時のみ値・他は空）
echo "$(date +%H:%M:%S),$session_id,$tool_name,$skill_name" >> "$LOG_FILE"

# heartbeat: WT4(タブID)別に最終活動時刻を touch（stale🟢検知用・L98）
# WT_SESSION は Windows Terminal がタブ生成時に設定、WSL hook 環境にも伝播
# unkn 環境（WT_SESSION 取得不可）は何もしない（fallback: handoff mtime）
WT4="${WT_SESSION:0:4}"
if [ -n "${WT_SESSION:-}" ] && [ -n "$WT4" ]; then
  mkdir -p "$HOME/.claude/state/heartbeat"
  : > "$HOME/.claude/state/heartbeat/$WT4" 2>/dev/null
fi

exit 0
