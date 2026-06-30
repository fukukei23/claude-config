# PowerShell Keyboard Input Script for Claude Code
# Usage: powershell.exe -File type.ps1 -Text "<text>" [-Delay <ms>]

param(
    [Parameter(Mandatory=$true)]
    [string]$Text,

    [int]$Delay = 50
)

Add-Type -AssemblyName System.Windows.Forms

# Send keys with delay
[System.Windows.Forms.SendKeys]::SendWait($Text)

Write-Output "Typed: $Text"
