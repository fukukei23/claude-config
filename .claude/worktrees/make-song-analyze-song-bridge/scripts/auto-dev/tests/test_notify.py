"""daily_triage Discord通知ロジックのテスト（外部通信は mock 化）"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from daily_triage import send_discord, DISCORD_MAX_CHARS  # noqa: E402


class _FakeResp:
    """urlopen の戻り値コンテキストマネージャもどき。"""

    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_send_discord_success(monkeypatch):
    """webhook 送信成功（2xx）なら True・payload に content が入る。"""
    captured = {}

    def fake_urlopen(req, timeout=30):
        captured["data"] = req.data
        return _FakeResp(204)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert send_discord("hello", "https://discord.test/hook") is True
    assert json.loads(captured["data"])["content"] == "hello"


def test_send_discord_truncates_long_content(monkeypatch):
    """2000文字超はDiscord上限に切り詰められる。"""
    captured = {}

    def fake_urlopen(req, timeout=30):
        captured["data"] = req.data
        return _FakeResp(204)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    long_text = "あ" * (DISCORD_MAX_CHARS + 1000)
    assert send_discord(long_text, "https://discord.test/hook") is True
    assert len(json.loads(captured["data"])["content"]) == DISCORD_MAX_CHARS


def test_send_discord_exception_returns_false(monkeypatch):
    """通信例外時は False（クラッシュしない）。"""

    def fake_urlopen(req, timeout=30):
        raise ConnectionError("boom")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert send_discord("x", "https://discord.test/hook") is False


def test_main_notify_skip_when_no_webhook(monkeypatch, tmp_path, capsys):
    """webhook未設定時は通知せず skip メッセージ（exit 0）。"""
    monkeypatch.delenv("DISCORD_CLAUDE_WEBHOOK", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "daily_triage.py",
            "--no-llm",
            "--notify-discord",
            "--output",
            str(tmp_path / "out.md"),
        ],
    )
    from daily_triage import main

    assert main() == 0
    assert "スキップ" in capsys.readouterr().out
