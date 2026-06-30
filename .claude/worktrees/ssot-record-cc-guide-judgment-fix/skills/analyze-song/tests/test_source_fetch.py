"""source_fetch のテスト。"""
from pathlib import Path

import pytest

from scripts.source_fetch import fetch_source


def test_fetch_local_mp3_copies_into_workdir(yoen_mp3, workdir):
    """ローカル MP3 は workdir/audio.mp3 にコピーされること。"""
    out = fetch_source(str(yoen_mp3), workdir)
    assert out == workdir / "audio.mp3"
    assert out.exists()
    assert out.stat().st_size > 0


def test_fetch_invalid_path_raises(workdir):
    """存在しないローカルパスは FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        fetch_source("/nonexistent/hoge.mp3", workdir)


def test_fetch_youtube_url_calls_ytdlp(monkeypatch, workdir):
    """YouTube URL は yt-dlp を呼び出す（呼出だけモック検証）。"""
    called = {}

    def fake_download(url, outtmpl):
        called["url"] = url
        # 出力ファイルを模造
        Path(outtmpl).with_suffix(".mp3").write_bytes(b"fake")
        return 0

    monkeypatch.setattr(
        "scripts.source_fetch._ytdlp_download", fake_download
    )
    out = fetch_source("https://www.youtube.com/watch?v=abc123", workdir)
    assert called["url"] == "https://www.youtube.com/watch?v=abc123"
    assert out.exists()
