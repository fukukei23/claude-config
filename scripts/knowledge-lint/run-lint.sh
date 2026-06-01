#!/bin/bash
# Knowledge Lint エントリーポイント
# Cron: 3 3 * * 0,2,4

SSOT_DIR="/home/yn4416/projects/obsidian-ssot"
SCRIPT_DIR="/home/yn4416/.claude/scripts/knowledge-lint"
LOG_FILE="${SCRIPT_DIR}/logs/knowledge-lint-$(date +%Y-%m-%d).log"

mkdir -p "${SCRIPT_DIR}/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Knowledge Lint 開始" | tee -a "${LOG_FILE}"

python3 "${SCRIPT_DIR}/lint.py" --ssot-dir "${SSOT_DIR}" 2>&1 | tee -a "${LOG_FILE}"

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Knowledge Lint 終了 (exit=${EXIT_CODE})" | tee -a "${LOG_FILE}"
exit ${EXIT_CODE}
