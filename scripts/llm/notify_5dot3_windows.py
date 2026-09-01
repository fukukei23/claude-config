#!/usr/bin/env python3
"""notify_5dot3_windows.py — Windowsトースト通知（WSL→powershell.exe BalloonTip）

経路は auto-dev/next_issue.py:40-65 の notify_complete と同一（実績あり）。
powershell.exe 不在環境では静かにFalseを返す（設計§4.4・運用を止めない）。
"""
import subprocess
import sys


def notify(title: str, message: str) -> bool:
    """Windowsトースト通知を非同期発火する。発火できたらTrue。"""
    title = str(title).replace("'", " ")
    message = str(message).replace("'", " ")
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Warning; "
        f"$n.BalloonTipTitle = '{title}'; "
        f"$n.BalloonTipText = '{message}'; "
        "$n.BalloonTipIcon = 'Warning'; "
        "$n.Visible = $true; "
        "$n.ShowBalloonTip(8000); "
        "Start-Sleep -Seconds 9; "
        "$n.Dispose()"
    )
    try:
        subprocess.Popen(["powershell.exe", "-c", ps_cmd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, OSError):
        return False


if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else "glm-5.3 を使っています"
    message = sys.argv[2] if len(sys.argv) > 2 else "戻し忘れの可能性 /model sonnet でflashへ戻せます"
    notify(title, message)
    sys.exit(0)  # 通知失敗は運用を止めない
