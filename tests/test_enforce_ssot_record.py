"""enforce-ssot-record.sh（PreToolUse・01_DECISIONS直書き防止ガード）のテスト.

ガード系で最後の無テストだった門番。並行セッション誤許可防止（セッションID分離）
を含む契約を固定する。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_enforce_ssot_record.py -q
"""

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "hooks" / "enforce-ssot-record.sh"

DECISIONS = "/home/yn4416/projects/obsidian-ssot/01_DECISIONS/claude-code/x.md"
OTHER = "/home/yn4416/projects/obsidian-ssot/00_SYSTEM/other.md"


def run_guard(payload: dict, home: Path, sid: str | None) -> tuple[int, str]:
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    if sid is not None:
        env["CLAUDE_CODE_SESSION_ID"] = sid
    r = subprocess.run(["bash", str(SCRIPT)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=15, env=env)
    return r.returncode, r.stderr.decode("utf-8", errors="replace")


def write(path: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"}}


def _flag(home: Path, sid: str) -> Path:
    f = home / ".claude" / "state" / f"ssot-record-active-{sid}"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.touch()
    return f


def test_01decisions直書きはブロック(tmp_path):
    code, err = run_guard(write(DECISIONS), tmp_path, "mysession1")
    assert code == 2
    assert "01_DECISIONS" in err
    assert "ssot-record" in err


def test_自セッションのフラグありは許可(tmp_path):
    _flag(tmp_path, "mysession1")
    code, _ = run_guard(write(DECISIONS), tmp_path, "mysession1")
    assert code == 0


def test_他セッションのフラグでは許可しない(tmp_path):
    """並行セッション隔離: 他人のフラグで通ってはいけない."""
    _flag(tmp_path, "other-session")
    code, _ = run_guard(write(DECISIONS), tmp_path, "mysession1")
    assert code == 2


def test_対象外パスは許可(tmp_path):
    code, _ = run_guard(write(OTHER), tmp_path, "mysession1")
    assert code == 0


def test_edit形式のtool_inputも検知(tmp_path):
    payload = {"tool_name": "Edit", "tool_input": {
        "file_path": DECISIONS, "old_string": "a", "new_string": "b"}}
    code, _ = run_guard(payload, tmp_path, "mysession1")
    assert code == 2


def test_不正jsonは許可(tmp_path):
    env = {"HOME": str(tmp_path), "PATH": os.environ["PATH"],
           "CLAUDE_CODE_SESSION_ID": "mysession1"}
    r = subprocess.run(["bash", str(SCRIPT)], input=b"not json",
                       capture_output=True, timeout=15, env=env)
    assert r.returncode == 0


def test_sid未設定時はいずれかのフラグで許可(tmp_path):
    """SESSION_ID未取得フォールバック（glob）: フラグが1つでもあれば許可."""
    _flag(tmp_path, "someone")
    code, _ = run_guard(write(DECISIONS), tmp_path, sid=None)
    assert code == 0


def test_sid未設定_フラグ完全なしはブロック(tmp_path):
    code, _ = run_guard(write(DECISIONS), tmp_path, sid=None)
    assert code == 2
