#!/bin/bash
# Start Windows application
# Usage: ./start-app.sh "<app_path>" ["<args>"] [--wait]
# Examples:
#   ./start-app.sh "notepad.exe"
#   ./start-app.sh "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" "https://google.com"
#   ./start-app.sh "notepad.exe" "" --wait

APP_PATH="$1"
ARGS="$2"
WAIT_FLAG=""

if [ "$3" == "--wait" ]; then
    WAIT_FLAG="-Wait"
fi

SCRIPT_PATH="/home/yn441611/.claude/core/start-app.ps1"

/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -ExecutionPolicy Bypass \
    -File "$(wslpath -w "$SCRIPT_PATH")" \
    -AppPath "$APP_PATH" -Args "$ARGS" $WAIT_FLAG
