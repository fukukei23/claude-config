#!/bin/bash
# Click at specific position
# Usage: ./click.sh <x> <y> [clicks] [button]
# Example: ./click.sh 100 200 1 left

X="${1:-0}"
Y="${2:-0}"
CLICKS="${3:-1}"
BUTTON="${4:-left}"

SCRIPT_PATH="/home/yn4416/.claude/scripts/click.ps1"

/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -ExecutionPolicy Bypass \
    -File "$(wslpath -w "$SCRIPT_PATH")" \
    -X "$X" -Y "$Y" -Clicks "$CLICKS" -Button "$BUTTON"
