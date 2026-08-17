#!/usr/bin/env python3
"""minimax-mcp-server.py のユニットテスト（urllibモック・実API不要）.

gemini版テストのパターンを写経・2026-08-18新設。

実行: cd ~/projects/claude-config && python3 -m pytest scripts/mcp/test_minimax_mcp_server.py -q
"""
import json
from pathlib import Path
from unittest import mock

import importlib.util

_SPEC = importlib.util.spec_from_file_location(
    "minimax_mcp_server", Path(__file__).parent / "minimax-mcp-server.py")
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


# ===== _load_key =====

def test_load_key_from_env(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "env-key-123")
    assert mod._load_key() == "env-key-123"


def test_load_key_fallback_to_secrets_env(monkeypatch, tmp_path):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    fake = tmp_path / ".secrets.env"
    fake.write_text('export MINIMAX_API_KEY="secret-456"\n')
    with mock.patch("os.path.expanduser", lambda p: str(fake)):
        assert mod._load_key() == "secret-456"


def test_load_key_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    fake = tmp_path / ".secrets.env"
    with mock.patch("os.path.expanduser", lambda p: str(fake)):
        assert mod._load_key() == ""


# ===== call_minimax =====

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


def test_call_minimax_success(monkeypatch):
    monkeypatch.setattr(mod, "MINIMAX_KEY", "test-key")
    fake = {"content": [{"type": "text", "text": "回答M"}]}
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return _fake_response(fake)

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        text = mod.call_minimax("指示", max_tokens=555)
    assert text == "回答M"
    assert captured["url"] == "https://api.minimax.io/anthropic/v1/messages"
    assert captured["data"]["model"] == "MiniMax-M3"
    assert captured["data"]["max_tokens"] == 555


def test_call_minimax_キー不在時エラー文(monkeypatch):
    monkeypatch.setattr(mod, "MINIMAX_KEY", "")
    assert "MINIMAX_API_KEY" in mod.call_minimax("x")


def test_call_minimax_ステータスファイル書込(monkeypatch, tmp_path):
    """/tmp/llm-last-used.txt に 🟠 MiniMax を記録."""
    monkeypatch.setattr(mod, "MINIMAX_KEY", "k")
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
        mod.call_minimax("x")
    assert "MiniMax" in fake_path.read_text()


# ===== handle_request（JSON-RPC） =====

def test_initialize():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r["result"]["serverInfo"]["name"] == "minimax-mcp"


def test_tools_list():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    assert "minimax_ask" in names
    assert "minimax_translate_file" in names


def test_initialized通知はnone():
    assert mod.handle_request({"method": "notifications/initialized"}) is None


def test_minimax_ask呼出(monkeypatch):
    monkeypatch.setattr(mod, "call_minimax", lambda p, m=2000: f"echo:{p[:10]}")
    r = mod.handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                            "params": {"name": "minimax_ask",
                                       "arguments": {"prompt": "指示文"}}})
    assert r["result"]["content"][0]["text"].startswith("echo:指示文")


def test_ファイル系ツール_不在ファイルはiserror():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                            "params": {"name": "minimax_summarize_file",
                                       "arguments": {"file_path": "/nonexistent/xx.txt"}}})
    assert r["result"]["isError"] is True


def test_不明ツールはiserror():
    r = mod.handle_request({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                            "params": {"name": "no_such_tool", "arguments": {}}})
    assert r["result"]["isError"] is True
    assert "不明なツール" in r["result"]["content"][0]["text"]
