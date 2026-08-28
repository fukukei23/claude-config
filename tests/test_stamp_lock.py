"""stamp-lock.sh の汎用実行ロックテスト（2026-08-28・durable cron残6件排他化③）.

LLM駆動スキル/cronタスク（/ssot-check auto・/update-guide・skill-catalog生成等）は
LLMが各bash呼び出しで別プロセスになるため flock（プロセス生存依存）で包めない。
よってスタンプ（mtime）+年齢チェック方式の汎用ロックを使う
（2026-08-28 07:27+07:33 並行発火実害=再是正ロールバック3回の再発防止）。

STAMP_LOCK_DIR 環境変数でロック置き場を一時パスに上書きし実stateを汚さない。
旧 test_ssot_check_auto_lock.py（name固定版・2026-08-28①）を汎用化置換。
"""

import os
import pathlib
import subprocess
import time

SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "scripts" / "obsidian" / "stamp-lock.sh"
)


def _run(name: str, action: str, lock_dir: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["STAMP_LOCK_DIR"] = lock_dir
    return subprocess.run(
        ["bash", str(SCRIPT), name, action],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _age_lock(lock_path: pathlib.Path, age_seconds: float) -> None:
    """ロックファイルのタイムスタンプを過去に戻す（停滞ロックの再現）."""
    lock_path.write_text(f'{{"ts": {time.time() - age_seconds}}}')
    past = time.time() - age_seconds
    os.utime(lock_path, (past, past))


def test_acquire_then_second_acquire_is_busy(tmp_path):
    """取得直後の再取得は BUSY（並行発火の封止）・exit 非0."""
    first = _run("unit-test", "acquire", str(tmp_path))
    assert first.returncode == 0, f"stderr: {first.stderr}"
    second = _run("unit-test", "acquire", str(tmp_path))
    assert second.returncode != 0
    assert "BUSY" in second.stdout


def test_release_allows_reacquire(tmp_path):
    """release後は再取得できる."""
    assert _run("unit-test", "acquire", str(tmp_path)).returncode == 0
    assert _run("unit-test", "release", str(tmp_path)).returncode == 0
    assert _run("unit-test", "acquire", str(tmp_path)).returncode == 0


def test_stale_lock_is_taken_over(tmp_path):
    """STALE_SEC超の古いロックは強制取得（クラッシュ残存からの自力復帰）."""
    lock = tmp_path / "unit-test.lock"
    _age_lock(lock, age_seconds=99999)
    proc = _run("unit-test", "acquire", str(tmp_path))
    assert proc.returncode == 0
    assert "stale" in proc.stdout.lower()


def test_release_without_lock_is_noop(tmp_path):
    """ロック不在のreleaseはエラーにしない（冪等）."""
    proc = _run("unit-test", "release", str(tmp_path))
    assert proc.returncode == 0


def test_different_names_are_independent(tmp_path):
    """nameが異なれば独立（update-guide実行中でもskill-catalogは取得できる）."""
    assert _run("update-guide", "acquire", str(tmp_path)).returncode == 0
    # 別nameは同一LOCK_DIRでも弾かれない
    assert _run("skill-catalog", "acquire", str(tmp_path)).returncode == 0
    # 同名は弾かれる
    assert _run("update-guide", "acquire", str(tmp_path)).returncode != 0


def test_invalid_name_is_rejected(tmp_path):
    """nameに英数字/ハイフン以外（パス区切り等）を含む場合は拒否・exit 2."""
    proc = _run("../evil", "acquire", str(tmp_path))
    assert proc.returncode == 2
    assert not (tmp_path / "../evil.lock").exists()
