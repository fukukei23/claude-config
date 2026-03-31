#!/bin/bash
# Type text using keyboard
# Usage: ./type.sh "<text>"
# Example: ./type.sh "Hello World"

TEXT="$1"
DELAY="${2:-50}"

SCRIPT_PATH="/home/yn441611/.claude/core/type.ps1"

/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -ExecutionPolicy Bypass \
    -File "$(wslpath -w "$SCRIPT_PATH")" \
    -Text "$TEXT" -Delay "$DELAY"
