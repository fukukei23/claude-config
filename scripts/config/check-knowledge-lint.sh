#!/bin/bash
# Knowledge Lint CronCreate check (SessionStart hook)

SCHEDULED_TASKS="/home/yn4416/.claude/scheduled_tasks.json"
STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

if grep -q "Knowledge Lint" "$SCHEDULED_TASKS" 2>/dev/null; then
  echo " ✅ Knowledge Lint: cron設定済み" > "$STATUS_DIR/knowledge-lint.status"
else
  echo " ⚠️ Knowledge Lint: cron未設定 (CronCreate推奨)" > "$STATUS_DIR/knowledge-lint.status"
fi
