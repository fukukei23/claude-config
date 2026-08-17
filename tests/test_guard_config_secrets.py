"""guard-config-secrets.sh（PreToolUseフック・F）の契約テスト.

設定ファイルコピー（01_DECISIONS/claude-code/設定ファイル/）への
生値シークレット混入を機械ブロックする門番。秘密流出ガードの最後の層。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_guard_config_secrets.py -q
"""

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "hooks" / "guard-config-secrets.sh"

TARGET = "/home/yn4416/projects/obsidian-ssot/01_DECISIONS/claude-code/設定ファイル/settings.json"
OTHER = "/home/yn4416/projects/obsidian-ssot/01_DECISIONS/claude-code/other.md"


def run_guard(payload: dict) -> tuple[int, str]:
    env = {"HOME": os.environ.get("HOME", "/home/yn4416"), "PATH": os.environ["PATH"]}
    r = subprocess.run(["bash", str(SCRIPT)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=15, env=env)
    err = r.stderr.decode("utf-8", errors="replace")
    return r.returncode, err


def write(file_path: str, content: str) -> dict:
    return {"tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content}}


# ---- 許可系（exit 0） ----

def test_対象外パスは許可():
    code, _ = run_guard(write(OTHER, '"api_key": "sk-real-value"'))
    assert code == 0


def test_env参照は許可():
    code, _ = run_guard(write(TARGET, '"api_key": "${ZAI_API_KEY}"'))
    assert code == 0


def test_空値は許可():
    code, _ = run_guard(write(TARGET, '"api_key": ""'))
    assert code == 0


def test_シークレット系キー無しは許可():
    code, _ = run_guard(write(TARGET, '"model": "glm-5.3", "theme": "dark"'))
    assert code == 0


def test_不正json_stdinは許可():
    env = {"HOME": os.environ.get("HOME", "/home/yn4416"), "PATH": os.environ["PATH"]}
    r = subprocess.run(["bash", str(SCRIPT)], input=b"not json",
                       capture_output=True, timeout=15, env=env)
    assert r.returncode == 0


def test_old_stringのみは検査対象外():
    """sanitize作業で old_string に生値が残っていても新内容に ${} があれば通す."""
    code, _ = run_guard({"tool_name": "Edit", "tool_input": {
        "file_path": TARGET,
        "old_string": '"api_key": "sk-old-real"',
        "new_string": '"api_key": "${API_KEY}"'}})
    assert code == 0


# ---- ブロック系（exit 2） ----

BLOCK_CASES = [
    ("api_key", "sk-1234567890abcdef"),
    ("API_KEY", "sk-UPPER"),
    ("anthropic_token", "tok-real-value"),
    ("ANTHROPIC-AUTH-TOKEN", "tok-dash"),
    ("client_secret", "sec-real"),
    ("password", "p@ssw0rd"),
    ("minimax_api_key", "eyJ-real"),
]


def test_生値シークレットはブロック():
    for key, val in BLOCK_CASES:
        code, err = run_guard(write(TARGET, f'"{key}": "{val}"'))
        assert code == 2, f"ブロックされるべき: {key}"
        assert "生値シークレット" in err
        assert key in err


def test_部分混入_env参照以外の接頭辞付きもブロック():
    code, err = run_guard(write(TARGET, '"api_key": "${ENV}sk-abc"'))
    assert code == 2


def test_editのnew_string生値はブロック():
    code, err = run_guard({"tool_name": "Edit", "tool_input": {
        "file_path": TARGET,
        "old_string": '"api_key": "${OLD}"',
        "new_string": '"api_key": "sk-new-real"'}})
    assert code == 2


def test_multieditのedits配列生値はブロック():
    code, _ = run_guard({"tool_name": "MultiEdit", "tool_input": {
        "file_path": TARGET,
        "edits": [
            {"old_string": "a", "new_string": '"model": "x"'},
            {"old_string": "b", "new_string": '"secret_code": "real-secret"'},
        ]}})
    assert code == 2
