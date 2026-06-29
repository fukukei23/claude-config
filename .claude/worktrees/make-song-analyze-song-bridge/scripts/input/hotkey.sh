#!/bin/bash
# Press hotkey combination
# Usage: ./hotkey.sh "<keys>"
# Examples:
#   ./hotkey.sh "^(c)"     # Ctrl+C (copy)
#   ./hotkey.sh "^(v)"     # Ctrl+V (paste)
#   ./hotkey.sh "^(a)"     # Ctrl+A (select all)
#   ./hotkey.sh "%{F4}"    # Alt+F4 (close window)
#   ./hotkey.sh "^+(s)"    # Ctrl+Shift+S (save as)
#   ./hotkey.sh "{ENTER}"  # Enter key
#   ./hotkey.sh "{TAB}"    # Tab key

KEYS="$1"

SCRIPT_PATH="/home/yn4416/.claude/scripts/hotkey.ps1"

/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -ExecutionPolicy Bypass \
    -File "$(wslpath -w "$SCRIPT_PATH")" \
    -Keys "$KEYS"
