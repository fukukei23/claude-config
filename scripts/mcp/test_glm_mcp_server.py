#!/usr/bin/env python3
"""glm-mcp-server.py のユニットテスト（urllibモック・実API不要）.

gemini版テスト（test_gemini_mcp_server.py）のパターンを写経・2026-08-18新設。
壊れると glm MCP 依存スキル全滅する常駐サーバーの契約を固定する。

実行: cd ~/projects/claude-config && python3 -m pytest scripts/mcp/test_glm_mcp_server.py -q
"""
import json
from pathlib import Path
from unittest import mock

import importlib.util

_SPEC = importlib.util.spec_from_file_location(
    "glm_mcp_server", Path(__file__).parent / "glm-mcp-server.py")
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


# ===== _load_key =====

def test_load_key_from_env(monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "env-key-123")
    assert mod._load_key() == "env-key-123"


def test_load_key_fallback_to_secrets_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    fake = tmp_path / ".secrets.env"
    fake.write_text('export GLM_API_KEY="secret-456"\nexport OTHER=x\n')
    with mock.patch("os.path.expanduser", lambda p: str(fake)):
        assert mod._load_key() == "secret-456"


def test_load_key_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    fake = tmp_path / ".secrets.env"  # 存在しない
    with mock.patch("os.path.expanduser", lambda p: str(fake)):
        assert mod._load_key() == ""


# ===== call_glm =====

def _fake_response(data):
    class FakeRes:
        def __init__(self, d):
            self._d = json.dumps(d).encode()
        def read(self):
            return self._d
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    return FakeRes(data)


def test_call_glm_success(monkeypatch):
    """正しいエンドポイント・ヘッダ・ペイロードで呼び、content[].text を抽出する."""
    monkeypatch.setattr(mod, "GLM_KEY", "test-key")
    fake = {"content": [{"type": "text", "text": "回答"}]}
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return _fake_response(fake)

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        text = mod.call_glm("テスト指示", max_tokens=777)
    assert text == "回答"
    assert captured["url"] == "https://api.z.ai/api/anthropic/v1/messages"
    assert captured["data"]["model"] == "GLM-5.3"
    assert captured["data"]["max_tokens"] == 777
    assert captured["data"]["messages"][0]["content"] == "テスト指示"


def test_call_glm_キー不在時エラー文(monkeypatch):
    monkeypatch.setattr(mod, "GLM_KEY", "")
    assert "GLM_API_KEY" in mod.call_glm("x")


def test_call_glm_ステータスファイル書込(monkeypatch, tmp_path):
    """/tmp/llm-last-used.txt に GLM 使用を記録（statusLineフォールバック用）."""
    monkeypatch.setattr(mod, "GLM_KEY", "k")
    fake_path = tmp_path / "llm-last-used.txt"
    fake = {"content": [{"type": "text", "text": "ok"}]}
    real_open = open

    def spy_open(path, *a, **kw):
        if str(path) == "/tmp/llm-last-used.txt":
            return real_open(fake_path, *a, **kw)
        return real_open(path, *a, **kw)

    with mock.patch("urllib.request.urlopen",
                    return_value=_fake_response(fake)), \
         mock.patch("builtins.open", side_effect=spy_open):
        mod.call_glm("x")
    assert "GLM" in fake_path.read_text()


# ===== handle_request（JSON-RPC） =====

def test_initialize():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r["result"]["serverInfo"]["name"] == "glm-mcp"
    assert r["id"] == 1


def test_tools_list():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    assert "glm_ask" in names
    assert "glm_review_code" in names


def test_initialized通知はnone():
    r = mod.handle_request({"method": "notifications/initialized"})
    assert r is None


def test_glm_ask呼出(monkeypatch):
    monkeypatch.setattr(mod, "call_glm", lambda p, m=4000: f"echo:{p[:10]}")
    r = mod.handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                            "params": {"name": "glm_ask",
                                       "arguments": {"prompt": "指示文"}}})
    assert r["result"]["content"][0]["text"].startswith("echo:指示文")


def test_ファイル系ツール_不在ファイルはiserror():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                            "params": {"name": "glm_review_code",
                                       "arguments": {"file_path": "/nonexistent/xx.py"}}})
    assert r["result"]["isError"] is True
    assert "見つかりません" in r["result"]["content"][0]["text"]


def test_不明ツールはiserror():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                            "params": {"name": "no_such_tool", "arguments": {}}})
    assert r["result"]["isError"] is True
    assert "不明なツール" in r["result"]["content"][0]["text"]


def test_通知系でid無しはnone():
    r = mod.handle_request({"method": "tools/list"})  # id無し
    assert r is None
