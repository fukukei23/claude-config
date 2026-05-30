#!/usr/bin/env python3
"""
Stop hook: 次の GitHub Issue をキューから取り出して claude CLI で起動する。
~/.claude/settings.json の Stop フックから呼ばれる。

state.json スキーマ:
  active    bool      - false なら何もしない（誤爆防止）
  pending   list[int] - 未着手 issue 番号
  current   int|null  - 実行中 issue 番号
  completed list[int] - 完了済み issue 番号
  project   str       - プロジェクト名（ログ用）
  repo_path str       - リポジトリの絶対パス
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATE      = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")
LOG        = Path("/home/yn4416/.claude/scripts/auto-dev/loop.log")
RUN_SCRIPT = Path("/home/yn4416/.claude/scripts/auto-dev/run-issue.sh")
NOTIFY     = Path("/home/yn4416/.claude/scripts/hooks/notify-done.sh")


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


def notify_complete(project: str, completed: list) -> None:
    """全完了時のWindowsトースト通知（非同期）"""
    msg = f"dev-cycle 完了: {project} / Issues {completed}"
    log(f"[通知] {msg}")

    # ターミナルベル
    print("\a", flush=True)

    # Windows トースト通知（nohup で非同期実行）
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        f"$n.BalloonTipTitle = 'dev-cycle 完了'; "
        f"$n.BalloonTipText = '{project} Issues {completed} 全完了'; "
        "$n.BalloonTipIcon = 'Info'; "
        "$n.Visible = $true; "
        "$n.ShowBalloonTip(8000); "
        "Start-Sleep -Seconds 9; "
        "$n.Dispose()"
    )
    subprocess.Popen(
        ["powershell.exe", "-c", ps_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    if not STATE.exists():
        return

    state = json.loads(STATE.read_text())

    if not state.get("active"):
        return  # 誤爆防止

    project   = state.get("project", "unknown")
    repo_path = state.get("repo_path", "/home/yn4416/projects/atelier-kyo-manager")

    # 直前の current を completed に移動
    if state.get("current") is not None:
        state["completed"].append(state["current"])
        log(f"[{project}] Issue #{state['current']} 完了 → completed: {state['completed']}")
        state["current"] = None

    if not state["pending"]:
        # ── 全完了 ──
        state["active"] = False
        STATE.write_text(json.dumps(state, indent=2))
        log(f"[{project}] ✅ 全 Issue 完了: {state['completed']}")
        notify_complete(project, state["completed"])
        return

    # 次の issue を取り出す
    next_issue = state["pending"].pop(0)
    state["current"] = next_issue
    STATE.write_text(json.dumps(state, indent=2))
    log(f"[{project}] 🚀 Issue #{next_issue} 起動 (残り: {state['pending']})")

    subprocess.Popen(
        ["setsid", "bash", str(RUN_SCRIPT), str(next_issue)],
        cwd=repo_path,
        start_new_session=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[ERROR] next-issue.py 例外: {e}")
    sys.exit(0)  # Stop フックは必ず 0 で終了
