# PowerShell Get Cursor Position Script
# Usage: powershell.exe -File get-cursor-position.ps1

Add-Type -AssemblyName System.Windows.Forms

$position = [System.Windows.Forms.Cursor]::Position
Write-Output "Cursor position: X=$($position.X), Y=$($position.Y)"
Write-Output "$($position.X),$($position.Y)"
