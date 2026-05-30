#!/bin/bash
# Usage: run-issue.sh <issue_number>
# next-issue.py および start.sh から呼ばれる wrapper
ISSUE="$1"
CLAUDE="/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/claude"
LOG="/home/yn4416/.claude/scripts/auto-dev/loop.log"
REPO="/home/yn4416/projects/atelier-kyo-manager"

PROMPT="atelier-kyo-manager の GitHub Issue #${ISSUE} を実装してください。完了したら Issue を close して、作業を終了してください。次のタスクへの移行は Stop hook が自動で行います。"

exec "$CLAUDE" --print "$PROMPT" \
  --allowedTools "Bash,Read,Edit,Write,Glob,Grep,mcp__minimax__minimax_ask,mcp__minimax__minimax_batch_process" \
  >> "$LOG" 2>&1
