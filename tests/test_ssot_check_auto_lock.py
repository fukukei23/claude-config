"""ssot-check-auto-lock.sh の実行ロックテスト（2026-08-28・durable cron残6件排他化①）.

/ssot-check auto（durable cron id=789e76ec）はLLM駆動スキルのためflockで包めない。
よってスタンプ（時刻）+年齢チェック方式の実行ロックを使う（daily-triageの
stamp+24h・aiwatch A″案の当日スタンプと同系・2026-08-28 07:27+07:33の並行発火
実害=再是正ロールバック3回の再発防止）。

SSOT_CHECK_LOCK 環境変数でロックファイルを一時パスに上書きし実stateを汚さない。
"""

import json
import os
import pathlib
import subprocess
import time

SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "scripts" / "obsidian" / "ssot-check-auto-lock.sh"
)


def _run(action: str, lock_path: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SSOT_CHECK_LOCK"] = lock_path
    return subprocess.run(
        ["bash", str(SCRIPT), action],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _age_lock(lock_path: pathlib.Path, age_seconds: float) -> None:
    """ロックファイルのタイムスタンプを過去に戻す（停滞ロックの再現）."""
    lock_path.write_text(json.dumps({"ts": time.time() - age_seconds}))
    past = time.time() - age_seconds
    os.utime(lock_path, (past, past))


def test_acquire_then_second_acquire_is_busy(tmp_path):
    """取得直後の再取得は BUSY（並行発火の封止）・exit 非0."""
    lock = tmp_path / "auto.lock"
    first = _run("acquire", str(lock))
    assert first.returncode == 0, f"stderr: {first.stderr}"
    second = _run("acquire", str(lock))
    assert second.returncode != 0
    assert "BUSY" in second.stdout


def test_release_allows_reacquire(tmp_path):
    """release後は再取得できる."""
    lock = tmp_path / "auto.lock"
    assert _run("acquire", str(lock)).returncode == 0
    assert _run("release", str(lock)).returncode == 0
    assert _run("acquire", str(lock)).returncode == 0


def test_stale_lock_is_taken_over(tmp_path):
    """STALE_SEC超の古いロックは強制取得（クラッシュ残存からの自力復帰）."""
    lock = tmp_path / "auto.lock"
    _age_lock(lock, age_seconds=99999)
    proc = _run("acquire", str(lock))
    assert proc.returncode == 0
    assert "stale" in proc.stdout.lower()


def test_release_without_lock_is_noop(tmp_path):
    """ロック不在のreleaseはエラーにしない（冪等）."""
    lock = tmp_path / "auto.lock"
    proc = _run("release", str(lock))
    assert proc.returncode == 0
