#!/bin/bash
# Claude Code 完了通知 — Windowsトースト通知 + ターミナルベル
# Stop hookから呼び出される

# ターミナルベル（ビープ音）
echo -e '\a'

# Windowsトースト通知（非同期・WSL2からPowerShell経由）
nohup powershell.exe -c "
Add-Type -AssemblyName System.Windows.Forms
\$notify = New-Object System.Windows.Forms.NotifyIcon
\$notify.Icon = [System.Drawing.SystemIcons]::Information
\$notify.BalloonTipTitle = 'Claude Code'
\$notify.BalloonTipText = '作業完了しました'
\$notify.BalloonTipIcon = 'Info'
\$notify.Visible = \$true
\$notify.ShowBalloonTip(5000)
Start-Sleep -Seconds 6
\$notify.Dispose()
" > /dev/null 2>&1 &

exit 0
