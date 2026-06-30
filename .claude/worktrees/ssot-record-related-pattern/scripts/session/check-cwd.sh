#!/bin/bash
# check-cwd.sh — カレントディレクトリが$HOMEでない場合に警告
set -uo pipefail

CWD="$(pwd)"
HOME_DIR="$(echo ~)"

if [ "$CWD" != "$HOME_DIR" ]; then
  MSG=" ⚠️ CWD=${CWD} — 推奨: cd ~ してから claude を起動"
else
  MSG=" ✅ CWD: ~ (正常)"
fi

mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/cwd.status
exit 0
