#!/usr/bin/env python3
"""gemini-mcp-server.py のユニットテスト（urllibモック・実API不要・TDD）"""
import os
import sys
import json
from pathlib import Path
from unittest import mock

# ハイフン入りファイル名(gemini-mcp-server.py)は直接import不可→importlibで読込
import importlib.util
_SPEC = importlib.util.spec_from_file_location(
    "gemini_mcp_server", Path(__file__).parent / "gemini-mcp-server.py")
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


# ===== Task 1: _load_key =====

def test_load_key_from_env(monkeypatch):
    """環境変数 GEMINI_API_KEY が優先される."""
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-123")
    assert mod._load_key() == "env-key-123"


def test_load_key_fallback_to_secrets_env(monkeypatch, tmp_path):
    """環境変数がない時は ~/.secrets.env の export 行を読む."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake = tmp_path / ".secrets.env"
    fake.write_text('export GEMINI_API_KEY="secret-456"\nexport OTHER=x\n')
    monkeypatch.setattr("os.path.expanduser", lambda p: str(fake))
    assert mod._load_key() == "secret-456"


def test_load_key_unset(monkeypatch, tmp_path):
    """どちらにも無い時は空文字列."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake = tmp_path / ".secrets.env"  # 存在しないパス
    monkeypatch.setattr("os.path.expanduser", lambda p: str(fake))
    assert mod._load_key() == ""


# ===== Task 2: call_gemini 基本 + atomic write =====

def _fake_response(data):
    class FakeRes:
        def __init__(self, d): self._d = json.dumps(d).encode()
        def read(self): return self._d
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return FakeRes(data)


def test_call_gemini_success(monkeypatch):
    """call_gemini が正しいエンドポイント・ペイロードで Gemini を呼び、テキストを抽出する."""
    monkeypatch.setattr(mod, "GEMINI_KEY", "test-key")
    fake = {"candidates": [{"content": {"parts": [{"text": "レビュー結果"}]}, "finishReason": "STOP"}]}
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return _fake_response(fake)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = mod.call_gemini("レビューして", model="gemini-2.5-pro")
    assert result == "レビュー結果"
    assert "models/gemini-2.5-pro:generateContent" in captured["url"]
    assert captured["data"]["contents"][0]["parts"][0]["text"] == "レビューして"


def test_call_gemini_atomic_status(monkeypatch, tmp_path):
    """ステータスファイルが atomic write で Gemini 使用を記録する."""
    monkeypatch.setattr(mod, "GEMINI_KEY", "test-key")
    status = tmp_path / "llm-last-used.txt"
    monkeypatch.setattr(mod, "_STATUS_FILE", str(status))
    fake = {"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}]}
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _fake_response(fake))
    mod.call_gemini("x")
    assert "Gemini" in status.read_text()


# ===== Task 3: call_gemini エラー処理 =====

def test_call_gemini_safety_block(monkeypatch):
    """finishReason=SAFETY を検出し safety block エラーを返す."""
    monkeypatch.setattr(mod, "GEMINI_KEY", "test-key")
    fake = {"candidates": [{"content": {"parts": [{"text": ""}]}, "finishReason": "SAFETY"}]}
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _fake_response(fake))
    result = mod.call_gemini("sensitive code")
    assert "safety" in result.lower()


def test_call_gemini_prompt_feedback_block(monkeypatch):
    """promptFeedback.blockReason でブロックされた場合も safety エラー."""
    monkeypatch.setattr(mod, "GEMINI_KEY", "test-key")
    fake = {"promptFeedback": {"blockReason": "SAFETY"}}
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _fake_response(fake))
    result = mod.call_gemini("x")
    assert "safety" in result.lower()


def test_call_gemini_429_exhaustion(monkeypatch):
    """429 でバックオフ再試行後も失敗したらエラーメッセージを返す."""
    monkeypatch.setattr(mod, "GEMINI_KEY", "test-key")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    import urllib.error
    err = urllib.error.HTTPError(url="u", code=429, msg="rate", hdrs={}, fp=None)
    def raise_err(req, timeout=None):
        raise err
    monkeypatch.setattr("urllib.request.urlopen", raise_err)
    result = mod.call_gemini("x")
    assert "429" in result or "rate" in result.lower()


def test_call_gemini_key_missing(monkeypatch):
    """API key 未設定時のエラー."""
    monkeypatch.setattr(mod, "GEMINI_KEY", "")
    result = mod.call_gemini("x")
    assert "GEMINI_API_KEY" in result


def test_call_gemini_input_truncation(monkeypatch):
    """入力長上限超過時は切り詰め＋警告."""
    monkeypatch.setattr(mod, "GEMINI_KEY", "test-key")
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return _fake_response({"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}]})
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    long_code = "x" * (mod.MAX_INPUT_CHARS + 100)
    result = mod.call_gemini(long_code)
    assert "切り詰め" in result
    assert len(captured["data"]["contents"][0]["parts"][0]["text"]) < len(long_code)
