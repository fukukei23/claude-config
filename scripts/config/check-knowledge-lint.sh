#!/bin/bash
# Knowledge Lint CronCreate check (SessionStart hook)
# Checks if the Knowledge Lint cron job is configured and outputs status

SCHEDULED_TASKS="/home/yn4416/.claude/scheduled_tasks.json"

if grep -q "Knowledge Lint" "$SCHEDULED_TASKS" 2>/dev/null; then
  echo "✅ Knowledge Lint cron: 設定済み"
else
  echo "⚠️ Knowledge Lint cron: 未設定 — CronCreate(durable:false, cron:'3 3 * * 0,2,4')で定期lintを設定してください"
fi
