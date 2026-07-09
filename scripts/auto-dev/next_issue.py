#!/usr/bin/env python3
"""
Stop hook: 次のタスクをキューから取り出して claude CLI で起動する。
~/.claude/settings.json の Stop フックから呼ばれる。

state.json スキーマ（タスク本文ベース・Loop Engineering Phase3.1・per-task repo）:
  active    bool        - false なら何もしない（誤爆防止）
  pending   list[dict]  - 未着手タスク {title, prompt, repo, issue}
  current   dict|null   - 実行中タスク {title, prompt, repo, issue, task_id, started}
  completed list[dict]  - 完了済み（検証OK）
  blocked   list[dict]  - 検証NG停止
  running   bool        - run-task.sh 実行中フラグ
  running_pid/running_create_time/running_since - stale検出用
  project   str         - プロジェクト名（ログ用）

state.json へのアクセスは全て state_store（atomic+flock+update/read）経由。
状態遷移は update(fn) 内で原子に、副作用（launch/notify/log/fetch）は外。
"""
import copy
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import state_store

STATE = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")
LOG = Path("/home/yn4416/.claude/scripts/auto-dev/loop.log")
RUN_SCRIPT = Path("/home/yn4416/.claude/scripts/auto-dev/run-task.sh")
NOTIFY = Path("/home/yn4416/.claude/scripts/hooks/notify-done.sh")
# フォールバック: current.task_id が無い時（後方互換）
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
    print("\a", flush=True)
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
    """
    if not path.exists():
        return True
    first = path.read_text(encoding="utf-8").strip().splitlines()
    return bool(first) and first[0].upper().startswith("OK")


def advance_state(state: dict, verify_ok: bool) -> dict:
    """直前の current を completed(OK) または blocked(NG) に移動し、
    次の current に pending 先頭を取り出す（純粋関数・コピー返す）。

    update(fn) 内で呼ばれ、s.clear()+s.update() で state に反映。
    """
    s = copy.deepcopy(state)

    if s.get("current") is not None:
        cur = s["current"]
        if verify_ok:
            s["completed"].append(
                {"title": cur.get("title"), "repo": cur.get("repo")}
            )
            s["current"] = None
        else:
            s["blocked"].append(
                {
                    "title": cur.get("title"),
                    "reason": "verify NG",
                    "repo": cur.get("repo"),
                }
            )
            s["current"] = None
            s["active"] = False
            return s  # 検証NG は停止（次へ進まない）

    if not s.get("pending"):
        s["active"] = False
        return s

    s["current"] = s["pending"].pop(0)
    return s


def should_fetch(state: dict) -> bool:
    """auto モード・pending 枯渇・current 無し の時に fetch を呼ぶべきか。"""
    if state.get("mode") != "auto":
        return False
    if state.get("current") is not None:
        return False
    return not state.get("pending")


def reached_max(state: dict) -> bool:
    """auto モードの1セッション上限に到達したか。"""
    if state.get("mode") != "auto":
        return False
    count = state.get("session_task_count", 0)
    maximum = state.get("max_tasks_per_session", 3)
    return count >= maximum


def _verify_result_path(current: dict | None) -> Path:
    """current.task_id+repo から結果ファイル特定（世代ガード）。

    task_id 無し（旧形式）はグローバル VERIFY_RESULT にフォールバック。
    """
    cur = current or {}
    task_id = cur.get("task_id")
    repo = cur.get("repo") or "/home/yn4416"
    if task_id:
        return Path(repo) / ".auto-loop" / task_id / "verify-result.txt"
    return VERIFY_RESULT


def _launch_current(current: dict) -> None:
    """run-task.sh を current タスクでバックグラウンド起動。"""
    title = current.get("title", "")
    repo = current.get("repo") or "/home/yn4416"
    subprocess.Popen(
        ["setsid", "bash", str(RUN_SCRIPT), title],
        cwd=repo,
        start_new_session=True,
    )


def _read_snap() -> dict:
    """state を共有ロック内で読んで全体返す。"""
    return state_store.read(STATE, lambda s: s if isinstance(s, dict) else {}) or {}


def main() -> None:
    snap = _read_snap()
    if not snap or not snap.get("active"):
        return  # 誤爆防止・state 無し

    project = snap.get("project", "unknown")

    # stale検出: running=True なら実プロセス確認（PID+create_time照合）
    if snap.get("running"):
        pid = snap.get("running_pid")
        ctime = snap.get("running_create_time")
        since = snap.get("running_since")
        if pid is not None and state_store.is_stale(pid, ctime, since):
            cleared = state_store.clear_running_if_stale(STATE, pid, ctime or 0)
            if cleared:
                log(f"[{project}] [stale] クラッシュ残留PID={pid} を検出・クリア")
        return  # 実行中 or stale処理済・次回 Stop で再評価

    cur = snap.get("current")

    # current が run-task.sh によって開始済みか（事前消化防止・2026-07-07）
    if cur is not None and not cur.get("started"):
        log(f"[{project}] current 未開始(started=False)・消化スキップ")
        return

    # current 無し: auto モードで昇格・fetch・max 停止
    if cur is None:
        if snap.get("mode") != "auto":
            return  # manual モード・approve.py 未起動
        if reached_max(snap):
            state_store.update(STATE, lambda s: s.__setitem__("active", False))
            log(f"[{project}] auto上限到達({snap.get('session_task_count', 0)})・停止")
            return
        if should_fetch(snap):
            try:
                import fetch_issues
                new_tasks = fetch_issues.run()
                state_store.update(STATE, _make_appender(new_tasks))
                log(f"[{project}] auto fetch: 補充試行")
            except Exception:
                import traceback
                log(f"[{project}] auto fetch失敗: {traceback.format_exc()}")
        snap = _read_snap()
        if not snap.get("pending"):
            state_store.update(STATE, lambda s: s.__setitem__("active", False))
            log(f"[{project}] auto: 対象Issue空・停止")
            return
        state_store.update(STATE, _promote_next)
        new_cur = state_store.read(STATE, lambda s: s.get("current") or {})
        log(f"[{project}] 🚀 auto起動: {new_cur.get('title')}")
        _launch_current(new_cur)
        return

    # current あり: 検証結果で遷移（状態遷移は update 内・原子）
    verify_path = _verify_result_path(cur)
    verify_ok = read_verify_result(verify_path)

    new_state = state_store.update(STATE, _make_advancer(verify_ok))

    if verify_ok:
        log(f"[{project}] 完了→completed。blocked={len(new_state['blocked'])}")
    else:
        log(f"[{project}] ⚠️ 検証NG→blocked・停止")
        notify_blocked(project, new_state["blocked"])
        return

    # auto上限到達で停止（次タスク起動せず）
    if new_state.get("mode") == "auto" and reached_max(new_state):
        state_store.update(STATE, lambda s: s.__setitem__("active", False))
        log(f"[{project}] auto上限到達({new_state.get('session_task_count', 0)})・停止")
        return

    if not new_state.get("active"):
        log(f"[{project}] ✅ 全タスク完了: {new_state['completed']}")
        notify_complete(project, new_state["completed"])
        return

    next_cur = new_state.get("current") or {}
    log(f"[{project}] 🚀 次タスク起動: {next_cur.get('title')}")
    _launch_current(next_cur)


def _make_appender(new_tasks: list) -> callable:
    """fetch した新規タスクを pending に追記する mutator（重複除外）。"""
    import fetch_issues

    def _append(s: dict) -> None:
        s.setdefault("pending", [])
        added = fetch_issues.filter_duplicates(new_tasks, s)
        s["pending"].extend(added)
    return _append


def _promote_next(s: dict) -> None:
    """pending 先頭を current に昇格（started=False・run-task起動前）。"""
    cur = s["pending"].pop(0)
    cur["started"] = False
    s["current"] = cur


def _make_advancer(verify_ok: bool) -> callable:
    """advance_state を update 内で適用する mutator（session_count 含む）。"""
    def _advance(s: dict) -> None:
        if s.get("mode") == "auto" and verify_ok:
            s["session_task_count"] = s.get("session_task_count", 0) + 1
        new_s = advance_state(s, verify_ok=verify_ok)
        s.clear()
        s.update(new_s)
    return _advance


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[ERROR] next_issue.py 例外: {e}")
    sys.exit(0)  # Stop フックは必ず 0 で終了
