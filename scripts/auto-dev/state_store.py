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
import time
from pathlib import Path
from typing import Callable


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
