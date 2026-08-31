"""state_store.py の atomic + flock + stale + CLI 単体テスト"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import state_store  # noqa: E402


def test_save_is_atomic(tmp_path):
    """save 後 state.json が有効JSON。tmp は残存しない。"""
    state_path = tmp_path / "state.json"
    state_store.save(state_path, {"active": True, "pending": []})
    assert json.loads(state_path.read_text())["active"] is True
    assert not (tmp_path / "state.json.tmp").exists()


def test_load_returns_empty_on_missing(tmp_path):
    """ファイル無しは空dict。"""
    state_path = tmp_path / "state.json"
    assert state_store._load_locked(state_path) == {}


def test_load_recovers_from_corruption(tmp_path):
    """破損JSONはバックアップ退避して空dict。"""
    state_path = tmp_path / "state.json"
    state_path.write_text("{ broken json", encoding="utf-8")
    result = state_store._load_locked(state_path)
    assert result == {}
    backups = list(tmp_path.glob("state.json.corrupted-*"))
    assert len(backups) == 1


def test_update_mutates_atomically(tmp_path):
    """update で read-modify-write が安全に反映される。"""
    state_path = tmp_path / "state.json"
    state_store.save(state_path, {"count": 0})

    def bump(s):
        s["count"] += 1

    state_store.update(state_path, bump)
    assert state_store.read(state_path, lambda s: s["count"]) == 1


def test_update_concurrent_no_corruption(tmp_path):
    """2プロセス並行 update で state.json が破損せず増加する（flock 実証）。"""
    import multiprocessing as mp

    state_path = tmp_path / "state.json"
    state_store.save(state_path, {"count": 0})

    def increment():
        for _ in range(50):
            def bump(s):
                s["count"] = s.get("count", 0) + 1
            try:
                state_store.update(state_path, bump)
            except (BlockingIOError, OSError):
                pass

    procs = [mp.Process(target=increment) for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=10)
    final = state_store.read(state_path, lambda s: s.get("count", 0))
    assert final > 0  # 並行でも消失なく増加
    assert json.loads(state_path.read_text())["count"] == final  # 有効JSON・破損なし


# ===== stale検出（Task2）=====

def test_is_stale_detects_dead_pid():
    """存在しないPIDは stale。"""
    assert state_store.is_stale(running_pid=999999, running_create_time=0) is True


def test_is_stale_detects_none_pid():
    """PID None は stale。"""
    assert state_store.is_stale(running_pid=None, running_create_time=None) is True


def test_is_stale_detects_reused_pid():
    """PID生存でも create_time 不一致なら stale（PID再利用）。"""
    import psutil
    my_pid = os.getpid()
    real_ctime = int(psutil.Process(my_pid).create_time())
    wrong_ctime = real_ctime - 10000  # 別プロセスを装う
    assert state_store.is_stale(my_pid, wrong_ctime) is True


def test_is_stale_alive_same_ctime():
    """PID生存・create_time 一致は stale でない。"""
    import psutil
    my_pid = os.getpid()
    ctime = int(psutil.Process(my_pid).create_time())
    assert state_store.is_stale(my_pid, ctime) is False


def test_is_stale_max_age_safety():
    """running_since が24h超なら stale（最終安全弁）。"""
    old = time.time() - 100000  # 27時間前
    assert state_store.is_stale(running_pid=os.getpid(),
                                running_create_time=None, running_since=old) is True


def test_clear_running_cas_clears_when_matching(tmp_path):
    """PID+ctime 一致ならクリアされる。"""
    state_path = tmp_path / "state.json"
    state_store.save(state_path, {"running": True, "running_pid": 111,
                                  "running_create_time": 1000, "current": {"started": True}})
    cleared = state_store.clear_running_if_stale(state_path, 111, 1000)
    assert cleared is True
    assert state_store.read(state_path, lambda s: s["running"]) is False


def test_clear_running_cas_does_not_clobber_new_task(tmp_path):
    """stale判定→クリア間に新タスク起動した場合、新タスクを上書きしない。"""
    state_path = tmp_path / "state.json"
    state_store.save(state_path, {"running": True, "running_pid": 111,
                                  "running_create_time": 1000, "current": {"started": True}})

    def _new_task(s):
        s["running_pid"] = 222
        s["running_create_time"] = 2000

    state_store.update(state_path, _new_task)
    cleared = state_store.clear_running_if_stale(state_path, 111, 1000)
    assert cleared is False
    assert state_store.read(state_path, lambda s: s["running_pid"]) == 222


# ===== CLI（Task3）=====

def test_cli_set_running_records_pid_and_ctime(tmp_path, monkeypatch):
    """set-running が PID と create_time を記録。"""
    sp = tmp_path / "state.json"
    state_store.save(sp, {"current": {}})
    monkeypatch.setattr(state_store, "STATE", sp)
    rc = state_store._cli(["set-running", str(os.getpid())])
    assert rc == 0
    s = state_store._load_locked(sp)
    assert s["running"] is True
    assert s["running_pid"] == os.getpid()
    assert s["running_create_time"] > 0
    assert s["running_since"] > 0


def test_cli_clear_running(tmp_path, monkeypatch):
    """clear-running で running=False に。"""
    sp = tmp_path / "state.json"
    monkeypatch.setattr(state_store, "STATE", sp)
    state_store._cli(["set-running", str(os.getpid())])
    rc = state_store._cli(["clear-running"])
    assert rc == 0
    assert state_store._load_locked(sp)["running"] is False


def test_cli_set_task_id(tmp_path, monkeypatch):
    """set-task-id で current.task_id 設定。"""
    sp = tmp_path / "state.json"
    state_store.save(sp, {"current": {}})
    monkeypatch.setattr(state_store, "STATE", sp)
    rc = state_store._cli(["set-task-id", "run-task-123-456"])
    assert rc == 0
    assert state_store._load_locked(sp)["current"]["task_id"] == "run-task-123-456"


def test_cli_unknown_command_returns_1():
    """未知のコマンドは終了コード1。"""
    assert state_store._cli(["unknown-cmd"]) == 1


def test_is_stale_spared_when_run_task_cmdline_alive():
    """ctime不一致でも生存run-task.shは誤クリアしない（L819・2026-09-01実発）。

    再現: 実bashプロセスでrun-task.sh風cmdlineを持ち、意図的にずらしたctimeで
    is_staleを呼ぶ → False（クリアしない）。
    """
    import subprocess
    import time as _time
    # run-task.shをcmdlineに含むダミー生存プロセス（sleep）
    proc = subprocess.Popen(
        ["bash", "-c", "exec -a run-task.sh sleep 30"],
    )
    _time.sleep(0.2)
    try:
        import psutil
        wrong_ctime = int(psutil.Process(proc.pid).create_time()) - 10000
        # exec -a はargv0書換のため cmdline に run-task.sh が入る
        assert state_store.is_stale(proc.pid, wrong_ctime) is False
    finally:
        proc.kill()
        proc.wait()


def test_is_stale_clears_unrelated_ctime_mismatch():
    """run-task.sh無関係のプロセスのctime不一致は従来どおりstale（PID再利用検出維持）。"""
    import subprocess
    import time as _time
    import psutil
    proc = subprocess.Popen(["sleep", "30"])
    _time.sleep(0.2)
    try:
        wrong_ctime = int(psutil.Process(proc.pid).create_time()) - 10000
        assert state_store.is_stale(proc.pid, wrong_ctime) is True
    finally:
        proc.kill()
        proc.wait()
