#!/bin/bash
# Send notification to Windows
# Usage: ./notify.sh "<title>" "<message>"

TITLE="${1:-Claude Code}"
MESSAGE="${2:-承認が必要です}"

SCRIPT_PATH="$HOME/.claude/scripts/notify.ps1"

/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -ExecutionPolicy Bypass \
    -File "$(wslpath -w "$SCRIPT_PATH")" \
    -Title "$TITLE" -Message "$MESSAGE"
