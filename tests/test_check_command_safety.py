"""check-command-safety.py（PreToolUseフック）の表駆動テスト.

本スクリプトは「毎ツール実行」で動く最頻出ガード。誤検知=全作業停止・
漏検知=rm -rf等の事故につながるため、ブロック/許可の境界を固定する。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_check_command_safety.py -q
"""

import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "security" / "check-command-safety.py"


def run_hook(payload: dict) -> tuple[int, str]:
    """フックをstdin JSON付きで実行し (exit_code, stdout) を返す."""
    r = subprocess.run(
        ["python3", str(SCRIPT)],
        input=json.dumps(payload), capture_output=True, text=True, timeout=15)
    return r.returncode, r.stdout


def bash(cmd: str) -> tuple[int, str]:
    return run_hook({"tool_name": "Bash", "tool_input": {"command": cmd}})


def read(path: str) -> tuple[int, str]:
    return run_hook({"tool_name": "Read", "tool_input": {"file_path": path}})


def is_blocked(out: str) -> bool:
    return '"decision"' in out and "block" in out


def block_reason(out: str) -> str:
    """stdout の JSON をパースして reason を返す（日本語は \\uXXXX エスケープされるため）."""
    try:
        return json.loads(out).get("reason", "")
    except json.JSONDecodeError:
        return ""


# ---- ブロックされるべきコマンド ----

BLOCK_CASES = [
    # 1. トレース系
    ("bash -x script.sh", "bash/sh -x"),
    ("sh -x ./run.sh", "bash/sh -x"),
    ("set -x", "set -x"),
    ("set -o xtrace", "xtrace"),
    ("strace python3 app.py", "strace"),
    ("ltrace ./binary", "ltrace"),
    # 2. 機密ファイル直接表示
    ("cat ~/.secrets.env", "機密ファイル"),
    ("head settings.json", "機密ファイル"),
    ("tail -5 ~/.claude/settings.json", "機密ファイル"),
    ("less .env", "機密ファイル"),
    ("vim ~/.claude/settings.local.json", "機密ファイル"),
    # 2b. jq全ダンプ
    ("jq . settings.json", "jq"),
    ("jq '.' ~/.claude/settings.json", "jq"),
    # 3. cat -A/-v/-E
    ("cat -A file.txt", "cat -A/-v/-E"),
    ("cat -v file.txt", "cat -A/-v/-E"),
    ("cat -E file.txt", "cat -A/-v/-E"),
    ("cat -nA file.txt", "cat -A/-v/-E"),
    # ※仕様メモ: .env.example / .env.bak も現行ではブロックされる
    #   （\.env(?![a-zA-Z]) の lookahead は直後が '.' の場合を通す＝過剰ブロック・安全側。
    #    コメントの意図「.env.example 等を除外」と乖離 → 改善候補として記録済み）
    ("cat .env.example", "機密ファイル"),
    ("cat prod.env.bak", "機密ファイル"),
    # 4. 機密ファイルgrep（マスクなし）
    ("grep KEY= ~/.secrets.env", "grep"),
    ("grep -i token settings.json", "grep"),
    # 5. 環境変数ダンプ
    ("env", "env"),
    ("printenv", "printenv"),
    ("declare -p", "declare"),
    ("set", "set"),
    # 6. /proc environ
    ("cat /proc/1234/environ", "/proc"),
    ("strings /proc/self/environ", "/proc"),
    # 7. ps 環境変数付き
    ("ps eww", "ps"),
    ("ps auxe", "ps"),
    # 複合コマンド（; 区切りで片方が危険）
    ("echo hi; cat ~/.secrets.env", "機密ファイル"),
    ("ls && strace ls", "strace"),
]


@pytest.mark.parametrize("cmd,expect_hint", BLOCK_CASES)
def test_ブロックされるコマンド(cmd, expect_hint):
    code, out = bash(cmd)
    assert code == 0, "フックは常にexit 0の設計"
    assert is_blocked(out), f"ブロックされるべき: {cmd}\nout: {out}"
    assert expect_hint in block_reason(out), f"理由に '{expect_hint}' を含むべき: {cmd}\nreason: {block_reason(out)}"


# ---- 許可されるべきコマンド（グレーゾーン境界の固定） ----

ALLOW_CASES = [
    # 通常操作
    "ls -la",
    "cat README.md",
    "git log --oneline",
    "python3 script.py",
    "echo $MY_VAR",
    # .envrc（.env の直後に[a-zA-Z]が続くケースは除外される）
    "cat .envrc",
    # grep -c / -l は値を表示しない
    "grep -c KEY ~/.secrets.env",
    "grep -l KEY settings.json",
    # grep + sed マスクあり
    "grep KEY ~/.secrets.env | sed 's/=.*/=<REDACTED>/'",
    'grep KEY ~/.secrets.env | sed "s/=.*/=<REDACTED>/"',
    # jq ホワイトリストフィールド
    "jq '.statusLine' settings.json",
    "jq '.model' ~/.claude/settings.json",
    # cat -n は -A/-v/-E 非該当
    "cat -n file.txt",
    # set -e / bash script.sh（-xなし）
    "set -e",
    "bash script.sh",
    # 機密ファイルでないgrep
    "grep KEY normal.txt",
    # ps 通常系
    "ps aux",
    "ps auxf",
]


@pytest.mark.parametrize("cmd", ALLOW_CASES)
def test_許可されるコマンド(cmd):
    code, out = bash(cmd)
    assert code == 0
    assert out.strip() == "", f"許可されるべき（何も出力しない）: {cmd}\nout: {out}"


# ---- Read ツール ----

@pytest.mark.parametrize("path", [
    "~/.claude/settings.json",
    "/home/user/.claude/settings.local.json",
    "~/.secrets.env",
    "~/.bash_history",
    "~/claude_desktop_config.json",
])
def test_read機密ファイルはブロック(path):
    code, out = read(path)
    assert code == 0
    assert is_blocked(out)
    assert "Read ツールによる機密ファイル読み取り禁止" in block_reason(out)


@pytest.mark.parametrize("path", [
    "~/projects/README.md",
    "~/.claude/CLAUDE.md",
    "~/projects/app/settings.example.json",  # settings.json 非一致を期待
    "~/.config/app/env.txt",
])
def test_read通常ファイルは許可(path):
    code, out = read(path)
    assert code == 0
    assert out.strip() == ""


# ---- 異常系（フック自体が堅牢か） ----

def test_不正json_stdinでもexit0で何も出力しない():
    r = subprocess.run(["python3", str(SCRIPT)],
                       input="this is not json", capture_output=True, text=True)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_不明tool_nameは素通り():
    code, out = run_hook({"tool_name": "WebSearch", "tool_input": {"query": "x"}})
    assert code == 0
    assert out.strip() == ""


def test_コマンド空文字は素通り():
    code, out = bash("")
    assert code == 0
    assert out.strip() == ""


def test_tool_input欠損でもクラッシュしない():
    code, out = run_hook({"tool_name": "Bash"})
    assert code == 0
    assert out.strip() == ""
