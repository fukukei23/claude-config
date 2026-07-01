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
