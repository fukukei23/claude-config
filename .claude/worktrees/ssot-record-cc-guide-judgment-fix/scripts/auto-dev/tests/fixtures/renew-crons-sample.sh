#!/usr/bin/env bash
# 【Claude向け運用手順】
# 1. bash ~/bin/apply-crons.sh check   で整合・健康確認
# 2. 差分があれば bash ~/bin/apply-crons.sh diff  で内容確認
# 3. bash ~/bin/apply-crons.sh apply   を実行
# 4. stdout の CRON_APPLY_PROTOCOL から ACTION: create 行を抽出
# 5. 各 create 行について CronCreate ツールを durable=true, recurring=true で呼ぶ

# @cron id=1 name="Knowledge Lint" schedule="3 3 * * 0,2,4" health="commit:obsidian-ssot:3"
#   Knowledge Lint: bash ~/.claude/scripts/knowledge-lint/run-lint.sh

# @cron id=5 name="使用量日次集計" schedule="5 15 * * *" health="file:projects/obsidian-ssot/00_SYSTEM/stats/daily/*.json:2"
#   使用量集計: bash ~/.claude/scripts/stats/collect-daily-stats.py

# @cron id=9 name="Daily Triage" schedule="7 6 * * *" health="file:.claude/state/today-tasks.md:2"
#   Daily Triage: bash ~/.claude/scripts/auto-dev/daily-triage.sh --notify-discord

# @cron id=8 name="メロディ" schedule="0 0 1 * *" health="commit:obsidian-ssot:40" enabled=false
#   メロディ（無効）: echo melody
