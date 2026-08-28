"""collect-daily-stats-flock.sh の flock 排他テスト（2026-08-28・durable cron残6件排他化）.

durable cron id=5（使用量集計）は各並行セッションが同一時刻（15:05）に独立発火する
（2026-08-28 実測: 4セッション中2実行）。先着1実行のみ継続し、他は即skip
（reason=flock_busy）することを検証する。

テストはロック競合とパススルー（副作用なし引数）のみで検証し、
実際の集計書き込み（stats/daily/*.json）は踏まない。
STATS_LOCK_FILE / STATS_LOG_FILE は env で一時パスに上書きし実stateを汚さない。
"""

import json
import os
import pathlib
import fcntl
import subprocess

SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "scripts" / "stats" / "collect-daily-stats-flock.sh"
)


def _run_script(lock_path: str, log_path: str, args=None) -> subprocess.CompletedProcess:
    """wrapperをdryな引数で実行し、lock/logを一時パスに向ける."""
    env = dict(os.environ)
    env["STATS_LOCK_FILE"] = lock_path
    env["STATS_LOG_FILE"] = log_path
    return subprocess.run(
        ["bash", str(SCRIPT), *(args or ["--date", "invalid-date-for-test"])],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_flock_held_second_instance_skips(tmp_path):
    """他インスタンスがロック保持中は即 exit 0 + flock_busy ログ."""
    lock = tmp_path / "stats.lock"
    log = tmp_path / "stats.jsonl"

    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            proc = _run_script(str(lock), str(log))
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    assert "flock排他" in proc.stdout
    lines = log.read_text().strip().splitlines()
    assert lines, "flock_busy ログが記録されていること"
    rec = json.loads(lines[-1])
    assert rec["action"] == "skip"
    assert rec["reason"] == "flock_busy"


def test_lock_free_passes_through_to_python(tmp_path):
    """ロック解放時はpythonへパススルー（副作用なし引数でexit code 非0伝播・flock skipなし）."""
    lock = tmp_path / "stats.lock"
    log = tmp_path / "stats.jsonl"

    proc = _run_script(str(lock), str(log))

    assert "flock排他" not in proc.stdout
    # --date invalid → python argparse error (exit 2)。wrapperが握り潰さず伝播すること
    assert proc.returncode != 0


def test_lock_file_leftover_is_harmless(tmp_path):
    """lockファイル残置（ロック保持なし）でも通常実行される."""
    lock = tmp_path / "stats.lock"
    log = tmp_path / "stats.jsonl"
    lock.write_text("")

    proc = _run_script(str(lock), str(log))

    assert proc.returncode != 0  # パススルー（argparse error）
    assert "flock排他" not in proc.stdout
