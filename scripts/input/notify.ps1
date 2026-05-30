# PowerShell Toast Notification for Claude Code
# Usage: powershell.exe -File notify.ps1 -Title "<title>" -Message "<message>"

param(
    [Parameter(Mandatory=$true)]
    [string]$Title,

    [Parameter(Mandatory=$true)]
    [string]$Message
)

# Load Windows Runtime types for toast notifications
Add-Type -AssemblyName System.Windows.Forms

# Create and show balloon notification
$balloon = New-Object System.Windows.Forms.NotifyIcon
$balloon.Icon = [System.Drawing.SystemIcons]::Information
$balloon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$balloon.BalloonTipTitle = $Title
$balloon.BalloonTipText = $Message
$balloon.Visible = $true
$balloon.ShowBalloonTip(5000)

# Play notification sound
[System.Media.SystemSounds]::Exclamation.Play()

# Cleanup after delay
Start-Sleep -Seconds 6
$balloon.Dispose()
