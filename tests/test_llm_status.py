"""llm-status.sh（statusLineフック・毎プロンプト表示）のテスト.

壊れると全セッションのUI異常になる最頻出スクリプト。
stdin JSONスキーマの正常/最小/不正の3パターンと主要分岐を固定する。

実行: cd ~/projects/claude-config && python3 -m pytest tests/test_llm_status.py -q
"""

import json
import os
import subprocess
import urllib.request
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "llm" / "llm-status.sh"


def run_statusline(payload: str | bytes, env_extra: dict | None = None) -> tuple[int, str]:
    """llm-status.sh をstdin付きで実行し (exit_code, stdout) を返す."""
    env = dict(os.environ)
    env.pop("WT_SESSION", None)
    env.pop("CLAUDE_CODE_AUTO_COMPACT_WINDOW", None)  # 窓サイズ環境依存を排除
    env.update(env_extra or {})
    data = payload.encode() if isinstance(payload, str) else payload
    r = subprocess.run(["bash", str(SCRIPT)], input=data,
                       capture_output=True, timeout=15, env=env)
    return r.returncode, r.stdout.decode("utf-8", errors="replace").strip()


def _proxy_alive() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8787/proxy/status", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def _make_transcript(tmp_path: Path, tokens: int) -> str:
    """assistant usage を1件含む擬似 transcript JSONL を作る."""
    p = tmp_path / "transcript.jsonl"
    entry = {"type": "assistant", "message": {"usage": {
        "input_tokens": tokens, "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0}}}
    p.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return str(p)


# ---- パターン1: 正常系（公式スキーマ充足） ----

def test_正常系_モデル名とctxとタブidを表示(tmp_path):
    payload = json.dumps({
        "model": {"display_name": "Opus", "id": "claude-opus-4-7"},
        "session_id": "abcd1234-xxxx",
        "transcript_path": _make_transcript(tmp_path, 250_000),
        "cost": {"total_lines_added": 100, "total_lines_removed": 50},
    })
    code, out = run_statusline(payload, {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
                                         "WT_SESSION": "84ad31dd"})
    assert code == 0
    assert out != "statusline-error"
    assert "Opus" in out
    assert "Ctx" in out          # 250k/1M = 25%
    assert "25%" in out
    assert "1M" in out
    assert "+100 -50" in out
    assert "🪟84ad" in out       # WT_SESSION先頭4桁


def test_正常系_ctxが85pct超なら赤色コード(tmp_path):
    payload = json.dumps({
        "model": {"display_name": "Opus"},
        "transcript_path": _make_transcript(tmp_path, 900_000),
    })
    code, out = run_statusline(payload, {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000"})
    assert code == 0
    assert "\033[31m" in out     # 赤（>=85%）


def test_正常系_窓200kデフォルト表記(tmp_path):
    payload = json.dumps({
        "model": "glm-5.3",
        "transcript_path": _make_transcript(tmp_path, 100_000),
    })
    code, out = run_statusline(payload)  # AUTO_COMPACT_WINDOW未設定→200k
    assert code == 0
    assert "200k" in out
    assert "50%" in out


# ---- パターン2: 最小入力 ----

def test_最小入力_空dictでもunknownとタブidは出す():
    code, out = run_statusline("{}", {"WT_SESSION": "1234abcd"})
    assert code == 0
    assert out != "statusline-error"
    assert "unknown" in out
    assert "🪟1234" in out


def test_最小入力_空stdinでもクラッシュしない():
    code, out = run_statusline("")
    assert code == 0
    assert out != "statusline-error"


def test_最小入力_session_idフォールバックでタブid():
    code, out = run_statusline(json.dumps({"session_id": "feedface-1111"}))
    assert code == 0
    assert "🪟feed" in out


# ---- パターン3: 不正入力 ----

def test_不正jsonでもクラッシュしない():
    code, out = run_statusline("this is not json at all")
    assert code == 0
    assert out != "statusline-error"


def test_壊れたtranscript_pathでも動作継続():
    payload = json.dumps({
        "model": {"display_name": "Opus"},
        "transcript_path": "/nonexistent/path/xx.jsonl",
    })
    code, out = run_statusline(payload)
    assert code == 0
    assert "Opus" in out


def test_exceeds_200kフラグ表示():
    code, out = run_statusline(json.dumps({"model": "x", "exceeds_200k_tokens": True}))
    assert code == 0
    assert "Ctx >200k (1M窓)" in out


# ---- プロキシ実応答との連動（稼働時のみ・環境依存を明示） ----

@pytest.mark.skipif(not _proxy_alive(), reason="glm-rate-proxy が稼働していない")
def test_プロキシ稼働時_glmバッジが付く():
    """プロキシが zai provider で応答する間は 🟡[GLM] バッジが出る."""
    code, out = run_statusline(json.dumps({"model": {"display_name": "Opus"}}))
    assert code == 0
    assert "🟡[GLM]" in out


def test_wt_session未設定でタブidダッシュ():
    code, out = run_statusline("{}")
    assert code == 0
    assert "🪟----" in out
