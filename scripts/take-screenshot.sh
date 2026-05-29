#!/bin/bash
# Take screenshot from WSL2 using PowerShell
# Usage: ./take-screenshot.sh [output_path]

OUTPUT_PATH="${1:-$HOME/screenshot.png}"
SCRIPT_PATH="$HOME/.claude/scripts/take-screenshot.ps1"

# Convert WSL path to Windows path for PowerShell
WIN_PATH=$(wslpath -w "$OUTPUT_PATH")

# Execute PowerShell script
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -ExecutionPolicy Bypass -File "$(wslpath -w "$SCRIPT_PATH")" -OutputPath "$WIN_PATH"

# Check if screenshot was created
sleep 1
if [ -f "$OUTPUT_PATH" ]; then
    echo "Screenshot ready: $OUTPUT_PATH"
else
    echo "Error: Screenshot not created"
    exit 1
fi
