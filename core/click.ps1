# PowerShell Click Script for Claude Code
# Usage: powershell.exe -File click.ps1 -X <x> -Y <y> [-Clicks <count>] [-Button <left|right|middle>]

param(
    [Parameter(Mandatory=$true)]
    [int]$X,

    [Parameter(Mandatory=$true)]
    [int]$Y,

    [int]$Clicks = 1,

    [ValidateSet("left", "right", "middle")]
    [string]$Button = "left"
)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Mouse {
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);

    public const uint MOUSEEVENTF_LEFTDOWN = 0x02;
    public const uint MOUSEEVENTF_LEFTUP = 0x04;
    public const uint MOUSEEVENTF_RIGHTDOWN = 0x08;
    public const uint MOUSEEVENTF_RIGHTUP = 0x10;
    public const uint MOUSEEVENTF_MIDDLEDOWN = 0x20;
    public const uint MOUSEEVENTF_MIDDLEUP = 0x40;
}
"@

# Move cursor to position
[Mouse]::SetCursorPos($X, $Y)
Start-Sleep -Milliseconds 100

# Determine button flags
$downFlag = switch ($Button) {
    "left" { [Mouse]::MOUSEEVENTF_LEFTDOWN }
    "right" { [Mouse]::MOUSEEVENTF_RIGHTDOWN }
    "middle" { [Mouse]::MOUSEEVENTF_MIDDLEDOWN }
}
$upFlag = switch ($Button) {
    "left" { [Mouse]::MOUSEEVENTF_LEFTUP }
    "right" { [Mouse]::MOUSEEVENTF_RIGHTUP }
    "middle" { [Mouse]::MOUSEEVENTF_MIDDLEUP }
}

# Perform clicks
for ($i = 0; $i -lt $Clicks; $i++) {
    [Mouse]::mouse_event($downFlag, 0, 0, 0, 0)
    Start-Sleep -Milliseconds 50
    [Mouse]::mouse_event($upFlag, 0, 0, 0, 0)
    if ($i -lt $Clicks - 1) {
        Start-Sleep -Milliseconds 100
    }
}

Write-Output "Clicked $Button mouse button at ($X, $Y) $Clicks time(s)"
