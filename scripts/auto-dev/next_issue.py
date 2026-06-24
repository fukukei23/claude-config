#!/usr/bin/env python3
"""
Stop hook: 次のタスクをキューから取り出して claude CLI で起動する。
~/.claude/settings.json の Stop フックから呼ばれる。

state.json スキーマ（タスク本文ベース・Loop Engineering Phase3）:
  active    bool        - false なら何もしない（誤爆防止）
  pending   list[dict]  - 未着手タスク {title, prompt, repo, issue}
  current   dict|null   - 実行中タスク
  completed list[dict]  - 完了済み（検証OK）{title}
  blocked   list[dict]  - 検証NG停止 {title, reason}
  project   str         - プロジェクト名（ログ用）
  repo_path str         - リポジトリの絶対パス
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


def advance_state(state: dict, verify_ok: bool) -> dict:
    """直前の current を completed(OK) または blocked(NG) に移動し、
    次の current に pending 先頭を取り出す。

    Args:
        state: state.json の内容（ミューテートせず複製を返す）。
        verify_ok: 検証フェーズの結果。True=completed / False=blocked。

    Returns:
        遷移後の state。pending 空で次が無ければ active=False。
    """
    import copy
    s = copy.deepcopy(state)

    if s.get("current") is not None:
        cur = s["current"]
        if verify_ok:
            s["completed"].append({"title": cur.get("title")})
            s["current"] = None
        else:
            s["blocked"].append({"title": cur.get("title"), "reason": "verify NG"})
            s["current"] = None
            s["active"] = False
            return s  # 検証NG は停止（次へ進まない）

    if not s.get("pending"):
        s["active"] = False
        return s

    s["current"] = s["pending"].pop(0)
    return s


def load_state(path: Path) -> dict:
    """state.json を読む。存在しなければ空 dict。"""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    """state.json を書く（インデント付き）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


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
