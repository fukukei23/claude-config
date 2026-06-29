# PowerShell Application Launch Script for Claude Code
# Usage: powershell.exe -File start-app.ps1 -AppPath "<path>" [-Args "<arguments>"] [-Wait]

param(
    [Parameter(Mandatory=$true)]
    [string]$AppPath,

    [string]$Args = "",

    [switch]$Wait
)

if ($Args -ne "") {
    if ($Wait) {
        Start-Process -FilePath $AppPath -ArgumentList $Args -Wait
        Write-Output "Application closed: $AppPath"
    } else {
        Start-Process -FilePath $AppPath -ArgumentList $Args
        Write-Output "Application started: $AppPath"
    }
} else {
    if ($Wait) {
        Start-Process -FilePath $AppPath -Wait
        Write-Output "Application closed: $AppPath"
    } else {
        Start-Process -FilePath $AppPath
        Write-Output "Application started: $AppPath"
    }
}
