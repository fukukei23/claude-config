#!/bin/bash
mkdir -p /home/yn4416/.skillspector-reports
for d in /home/yn4416/.claude/skills/*/; do
  name=$(basename "$d")
  skillspector scan --no-llm --format json "$d" > "/home/yn4416/.skillspector-reports/${name}.json" 2>/dev/null
done
ls /home/yn4416/.skillspector-reports/ | wc -l
