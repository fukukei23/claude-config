#!/bin/bash
# Knowledge Lint エントリーポイント
# Cron: 3 3 * * 0,2,4

SSOT_DIR="/c/Users/yn441/projects/obsidian-ssot"
SCRIPT_DIR=""/bin"
LOG_FILE="/logs/knowledge-lint-2026-06-02.log"

mkdir -p "/logs"

echo "[2026-06-02 00:43:57] Knowledge Lint 開始" | tee -a ""

python3 "/lint.py" --ssot-dir "" 2>&1 | tee -a ""

EXIT_CODE=
echo "[2026-06-02 00:43:57] Knowledge Lint 終了 (exit=)" | tee -a ""
exit 
