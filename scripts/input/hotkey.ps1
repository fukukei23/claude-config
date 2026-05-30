# PowerShell Hotkey Script for Claude Code
# Usage: powershell.exe -File hotkey.ps1 -Keys "<keys>"
# Example: hotkey.ps1 -Keys "^(c)"  (Ctrl+C), "%(f)" (Alt+F), "+(a)" (Shift+A)

param(
    [Parameter(Mandatory=$true)]
    [string]$Keys
)

Add-Type -AssemblyName System.Windows.Forms

# Special key mappings
# ^ = Ctrl, % = Alt, + = Shift, ~ = Enter
# Examples:
#   "^(c)" = Ctrl+C (copy)
#   "^(v)" = Ctrl+V (paste)
#   "^(a)" = Ctrl+A (select all)
#   "%{F4}" = Alt+F4 (close window)
#   "^+(s)" = Ctrl+Shift+S (save as)
#   "{ENTER}" = Enter key
#   "{TAB}" = Tab key
#   "{ESC}" = Escape key

[System.Windows.Forms.SendKeys]::SendWait($Keys)

Write-Output "Pressed hotkey: $Keys"
