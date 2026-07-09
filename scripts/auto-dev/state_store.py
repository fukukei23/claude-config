#!/usr/bin/env python3
"""state.json の atomic + flock 安全アクセス・ライブラリ+CLI兼用。

auto-loop の進行状況(state.json)の並行読み書きを安全化する。
- atomic書き込み: tmp + fsync + os.replace + dir fsync（クラッシュ破損防止）
- 排他制御: 専用 lockfile の fcntl.flock(LOCK_NB)（lost update防止）
- read-modify-write は update(fn)、読むだけは read(fn)（load は非公開）
- stale検出: PID + create_time 照合(psutil・int化) + CAS条件付きクリア
"""
import fcntl
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

import psutil


def _lock_path(state_path: Path) -> Path:
    """state.json に対応する専用ロックファイルのパス。"""
    return state_path.with_suffix(state_path.suffix + ".lock")


def _acquire_lock(lock_path: Path, exclusive: bool = True) -> int:
    """LOCK_NB でロック取得。失敗時は BlockingIOError。fd を返す（呼出元が閉じる）。

    Args:
        lock_path: ロックファイルのパス。
        exclusive: True=排他(LOCK_EX) / False=共有(LOCK_SH)。

    Returns:
        ロックを保持する fd（呼出元が os.close する）。
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    flag = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    fcntl.flock(fd, flag | fcntl.LOCK_NB)
    return fd


def _load_locked(state_path: Path) -> dict:
    """state.json を読む（ロック取得済み前提・非公開）。破損時はバックアップして空dict。

    Args:
        state_path: state.json のパス。

    Returns:
        state dict。ファイル無し or 破損時は {}。
    """
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        ts = int(time.time())
        corrupted = state_path.with_name(f"{state_path.name}.corrupted-{ts}")
        state_path.rename(corrupted)
        return {}


def save(state_path: Path, state: dict) -> None:
    """atomic書き込み。tmp→fsync→os.replace→dir fsync。

    Args:
        state_path: state.json のパス。
        state: 書き込む内容。
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, state_path)
    _fsync_dir(state_path.parent)


def _fsync_dir(path: Path) -> None:
    """ディレクトリの fsync（os.replace のメタデータを確定）。"""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def update(state_path: Path, mutator: Callable[[dict], None]) -> dict:
    """排他ロック内で load→mutator→save を一括実行（read-modify-write の唯一の安全経路）。

    Args:
        state_path: state.json のパス。
        mutator: state dict を受け取り破壊的に変更するコールバック。
                 軽量・ブロッキングI/O禁止・他ロック取得禁止・再入禁止。

    Returns:
        変更後の state。
    """
    lock_fd = _acquire_lock(_lock_path(state_path), exclusive=True)
    try:
        state = _load_locked(state_path)
        mutator(state)
        save(state_path, state)
        return state
    finally:
        os.close(lock_fd)


def read(state_path: Path, extractor: Callable[[dict], object]) -> object:
    """共有ロック内で安全に読む。

    Args:
        state_path: state.json のパス。
        extractor: state dict から値を抽出して返すコールバック。

    Returns:
        extractor の戻り値。
    """
    lock_fd = _acquire_lock(_lock_path(state_path), exclusive=False)
    try:
        state = _load_locked(state_path)
        return extractor(state)
    finally:
        os.close(lock_fd)


def is_stale(
    running_pid: int | None,
    running_create_time: int | None,
    running_since: float | None = None,
    max_age_sec: int = 86400,
) -> bool:
    """running プロセスが stale（死んだ/再利用された/期限超）か判定。

    Args:
        running_pid: 記録されたPID。
        running_create_time: 記録されたPIDの開始時刻(int化・psutil create_time)。
        running_since: 実行開始時刻(UNIX秒)。24h超で stale。
        max_age_sec: running_since の上限(デフォルト86400=24h)。

    Returns:
        stale なら True。
    """
    # 安全弁: 24h超で問答無用 stale
    if running_since is not None and (time.time() - running_since) > max_age_sec:
        return True
    if running_pid is None or running_create_time is None:
        return True
    try:
        current_ctime = int(psutil.Process(running_pid).create_time())
        return current_ctime != running_create_time  # 不一致=別プロセス再利用
    except psutil.NoSuchProcess:
        return True  # PID不存在=stale確定
    except psutil.AccessDenied:
        return False  # 権限エラー=判定不能・待機(単一ユーザー環境で稀)


def clear_running_if_stale(state_path: Path, stale_pid: int, stale_ctime: int) -> bool:
    """CAS: 現在の running_pid+create_time が一致する時だけクリア。

    Args:
        state_path: state.json のパス。
        stale_pid: stale と判定したPID。
        stale_ctime: stale と判定したcreate_time。

    Returns:
        クリアしたら True（既に新タスク起動済で何もしなければ False）。
    """
    cleared = {"done": False}

    def _clear(s: dict) -> None:
        if (s.get("running") and s.get("running_pid") == stale_pid
                and s.get("running_create_time") == stale_ctime):
            s["running"] = False
            s["running_pid"] = None
            s["running_create_time"] = None
            cleared["done"] = True

    update(state_path, _clear)
    return cleared["done"]


STATE = Path("/home/yn4416/.claude/scripts/auto-dev/state.json")


def _set_running(state_path: Path, pid: int) -> None:
    """running=True + PID + create_time を記録。"""
    def _mut(s: dict) -> None:
        s["running"] = True
        s["running_pid"] = pid
        s["running_create_time"] = int(psutil.Process(pid).create_time())
        s["running_since"] = time.time()

    update(state_path, _mut)


def _clear_running(state_path: Path) -> None:
    """running=False クリア（trap用・正規終了）。"""
    def _mut(s: dict) -> None:
        s["running"] = False
        s["running_pid"] = None
        s["running_create_time"] = None

    update(state_path, _mut)


def _set_task_id(state_path: Path, task_id: str) -> None:
    """current.task_id を設定（世代ガード）。"""
    def _mut(s: dict) -> None:
        cur = s.get("current") or {}
        cur["task_id"] = task_id
        s["current"] = cur

    update(state_path, _mut)


def _cli(argv: list[str]) -> int:
    """bash 用 CLI。全て update() 経由。

    Args:
        argv: sys.argv[1:] 相当。

    Returns:
        終了コード（0=成功 / 1=引数エラー）。
    """
    cmd = argv[0] if argv else ""
    if cmd == "set-running" and len(argv) >= 2:
        _set_running(STATE, int(argv[1]))
    elif cmd == "clear-running":
        _clear_running(STATE)
    elif cmd == "set-task-id" and len(argv) >= 2:
        _set_task_id(STATE, argv[1])
    else:
        sys.stderr.write(
            "usage: state_store.py [set-running <pid>|clear-running|set-task-id <id>]\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
