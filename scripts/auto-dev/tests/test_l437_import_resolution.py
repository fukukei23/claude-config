"""L437: 対象repo（同名lib/パッケージ持ち）をcwdにしてもimportが解決すること。

本番経路の再現: run-task.sh は cwd=対象repo で review_lib.py を呼ぶ。
python3 -c / python3 script.py のいずれでも、_import_gemini_runner が
lib.api_base を解決できることを subprocess で検証する（sys.path 汚染を
親プロセスから持ち込まない・本番同等）。
"""

import subprocess
import sys
from pathlib import Path

import pytest

AUTO_DEV = Path("/home/yn4416/projects/claude-config/scripts/auto-dev")

_PROBE = """
import sys
sys.path.insert(0, {auto_dev!r})
import review_lib
run_api_with_fallback, _load_candidates = review_lib._import_gemini_runner()
assert callable(run_api_with_fallback) and callable(_load_candidates)
print("IMPORT_OK")
"""


def _run_probe(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _PROBE.format(auto_dev=str(AUTO_DEV))],
        cwd=str(cwd), capture_output=True, text=True, timeout=60,
    )


def test_import_gemini_runner_with_lib_package_cwd():
    """fail条件: 対象repoのcwdでlib.api_baseが解決されること（L437再現）。"""
    target_repo = Path("/home/yn4416/projects/x-automation")
    if not (target_repo / "lib" / "__init__.py").exists():
        pytest.skip("x-automation/lib が無い環境")
    r = _run_probe(target_repo)  # 同名lib正規パッケージを持つrepoをcwd化
    assert r.returncode == 0, f"L437再現（修正前はここで失敗）: {r.stderr[-300:]}"
    assert "IMPORT_OK" in r.stdout


def test_import_gemini_runner_with_neutral_cwd():
    """無関係なcwd（/tmp）でも解決すること（V4相当・回帰防止）。"""
    r = _run_probe(Path("/tmp"))
    assert r.returncode == 0, r.stderr[-300:]
    assert "IMPORT_OK" in r.stdout
