#!/bin/bash
# Get current cursor position
# Usage: ./get-cursor.sh

SCRIPT_PATH="/home/yn4416/.claude/scripts/get-cursor-position.ps1"

/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -ExecutionPolicy Bypass \
    -File "$(wslpath -w "$SCRIPT_PATH")"
