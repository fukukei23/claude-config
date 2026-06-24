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

STATE        = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")
LOG          = Path("/home/yn4416/.claude/scripts/auto-dev/loop.log")
RUN_SCRIPT   = Path("/home/yn4416/.claude/scripts/auto-dev/run-issue.sh")
NOTIFY       = Path("/home/yn4416/.claude/scripts/hooks/notify-done.sh")
VERIFY_RESULT = Path("/home/yn4416/.claude/scripts/auto-dev/verify-result.txt")


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


def notify_complete(project: str, completed: list) -> None:
    """全完了時のWindowsトースト通知（非同期）"""
    titles = [c.get("title", "?") if isinstance(c, dict) else str(c) for c in completed]
    msg = f"dev-cycle 完了: {project} / {titles}"
    log(f"[通知] {msg}")

    # ターミナルベル
    print("\a", flush=True)

    # Windows トースト通知（nohup で非同期実行）
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        f"$n.BalloonTipTitle = 'dev-cycle 完了'; "
        f"$n.BalloonTipText = '{project} {titles} 全完了'; "
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


def notify_blocked(project: str, blocked: list) -> None:
    """検証NGで停止した時の通知（人間エスカレーション）。"""
    msg = f"⚠️ dev-loop 検証NG停止: {project} / blocked {len(blocked)}件"
    log(f"[通知] {msg}")
    print("\a", flush=True)


def read_verify_result(path: Path) -> bool:
    """verify-result.txt の先頭行が 'OK' で始まれば True、それ以外は False。

    ファイルが無い場合は True（実装のみで検証無しの後方互換）。

    Args:
        path: verify-result.txt のパス。

    Returns:
        検証OK なら True。
    """
    if not path.exists():
        return True
    first = path.read_text(encoding="utf-8").strip().splitlines()
    return bool(first) and first[0].upper().startswith("OK")


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


def _launch_current(current: dict, repo_path: str) -> None:
    """run-task.sh を current タスクでバックグラウンド起動。"""
    title = current.get("title", "")
    subprocess.Popen(
        ["setsid", "bash", str(RUN_SCRIPT), title],
        cwd=repo_path,
        start_new_session=True,
    )


def main() -> None:
    state = load_state(STATE)
    if not state or not state.get("active"):
        return  # 誤爆防止・state 無し

    project = state.get("project", "unknown")
    repo_path = state.get("repo_path", "/home/yn4416/projects/atelier-kyo-manager")

    # 初回起動（current=None・pending あり）は検証結果を見ずに最初を取り出し
    if state.get("current") is None and state.get("pending"):
        state["current"] = state["pending"].pop(0)
        save_state(STATE, state)
        log(f"[{project}] 🚀 最初のタスク起動: {state['current'].get('title')}")
        _launch_current(state["current"], repo_path)
        return

    # 2回目以降: 検証結果で遷移
    verify_ok = read_verify_result(VERIFY_RESULT)
    state = advance_state(state, verify_ok=verify_ok)
    save_state(STATE, state)

    if verify_ok:
        log(f"[{project}] 完了→completed。blocked={len(state['blocked'])}")
    else:
        log(f"[{project}] ⚠️ 検証NG→blocked・停止")
        notify_blocked(project, state["blocked"])
        return

    if not state["active"]:
        log(f"[{project}] ✅ 全タスク完了: {state['completed']}")
        notify_complete(project, state["completed"])
        return

    log(f"[{project}] 🚀 次タスク起動: {state['current'].get('title')}")
    _launch_current(state["current"], repo_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[ERROR] next_issue.py 例外: {e}")
    sys.exit(0)  # Stop フックは必ず 0 で終了
