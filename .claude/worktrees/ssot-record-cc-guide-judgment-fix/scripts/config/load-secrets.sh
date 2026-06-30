#!/bin/bash
# load-secrets.sh — .secrets.env を環境に読み込み
set -a
source ~/.secrets.env 2>/dev/null
set +a
C=$(grep -cvE '^\s*#|^\s*$' ~/.secrets.env 2>/dev/null) || C=0
mkdir -p /tmp/claude-startup
echo " ✅ シークレット: ${C}件読み込み済み" > /tmp/claude-startup/secrets.status
exit 0
